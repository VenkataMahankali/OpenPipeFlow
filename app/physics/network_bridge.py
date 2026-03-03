"""
OpenPipeFlow — Network bridge: translates the NetworkModel into a
pandapipes network, runs pipeflow(), and writes results back.

If pandapipes is not available a simple series/parallel pressure-drop
fallback solver is used so the GUI remains functional.
"""

from __future__ import annotations
import math
from typing import Optional

from app.project.model import NetworkModel, PipeData, ValveData, PumpData
from app.physics.fluid_library import get_pandapipes_fluid_name

try:
    import pandapipes as pp
    import pandas as pd
    _PP = True
except ImportError:
    _PP = False

# ---------------------------------------------------------------------------
# Regime classification
# ---------------------------------------------------------------------------
from app.utils.constants import RE_LAMINAR_MAX, RE_TRANSITIONAL_MAX


def _regime(re: float) -> str:
    if re < RE_LAMINAR_MAX:
        return "Laminar"
    if re < RE_TRANSITIONAL_MAX:
        return "Transitional"
    return "Turbulent"


# ---------------------------------------------------------------------------
# Main solver entry-point
# ---------------------------------------------------------------------------

class SolverError(Exception):
    pass


def solve_network(model: NetworkModel) -> list[str]:
    """
    Solve the network and write results back into *model* in-place.
    Returns a list of warning/info strings.
    Raises SolverError on fatal errors.
    """
    warnings: list[str] = []

    # ── Pre-flight checks ──────────────────────────────────────────────────
    if model.node_count() == 0:
        raise SolverError("No nodes in network.")
    if model.branch_count() == 0:
        raise SolverError("No pipes or components in network.")
    if not model.has_sources():
        raise SolverError(
            "Network has no source nodes (fixed-pressure boundary).\n"
            "Add at least one Source node to define the inlet pressure."
        )
    if not model.has_sinks_or_multiple_sources():
        raise SolverError(
            "Network needs at least one Sink node (or a second Source at "
            "lower pressure) to drive flow."
        )

    # ── Connectivity check ─────────────────────────────────────────────────
    orphan_nodes = _find_orphan_nodes(model)
    if orphan_nodes:
        warnings.append(
            f"Nodes with no connections (ignored by solver): "
            + ", ".join(orphan_nodes)
        )

    disconnected = _find_disconnected_subgraphs(model)
    if len(disconnected) > 1:
        warnings.append(
            f"Network has {len(disconnected)} disconnected subgraphs. "
            "Only the subgraph containing a source will be solved."
        )

    if _PP:
        _solve_pandapipes(model, warnings)
    else:
        warnings.append(
            "pandapipes not installed — using built-in fallback solver. "
            "Install pandapipes for accurate looped-network solutions."
        )
        _solve_fallback(model, warnings)

    return warnings


# ---------------------------------------------------------------------------
# pandapipes solver
# ---------------------------------------------------------------------------

def _solve_pandapipes(model: NetworkModel, warnings: list[str]) -> None:
    """
    Solve using pandapipes (Fraunhofer IEE / University of Kassel, BSD-3-Clause).

    Element mapping:
      Pipe  → create_pipe_from_parameters (Darcy-Weisbach + Colebrook-White)
      Valve → create_pipe_from_parameters with loss_coefficient = K_effective
      Pump  → create_pump_from_parameters with H-Q polynomial (ON)
              or high-loss pipe (OFF)
    Boundary:
      source → ext_grid at fixed pressure
      sink   → ext_grid at fixed pressure (pressure-driven network)
    """
    fluid_pp = get_pandapipes_fluid_name(model.fluid_name)
    net = pp.create_empty_network(fluid=fluid_pp)

    # ── Estimate pressure gradient for junction initialisation ────────────
    src_pressures = [n.pressure_bar for n in model.nodes.values()
                     if n.node_type == "source"]
    snk_pressures = [n.pressure_bar for n in model.nodes.values()
                     if n.node_type == "sink"]
    p_hi  = max(src_pressures) if src_pressures else 5.0
    p_lo  = min(snk_pressures) if snk_pressures else 1.0
    p_mid = (p_hi + p_lo) / 2.0

    # ── Create junctions ──────────────────────────────────────────────────
    j_map: dict[str, int] = {}
    for nid, node in model.nodes.items():
        # Use node's own pressure if it's a BC, else mid-range estimate
        if node.node_type == "source":
            pn = node.pressure_bar
        elif node.node_type == "sink":
            pn = node.pressure_bar
        else:
            pn = p_mid
        idx = pp.create_junction(
            net,
            pn_bar=pn,
            tfluid_k=293.15,
            name=node.name,
            geodata=(node.x, -node.y),
        )
        j_map[nid] = idx

        if node.node_type == "source":
            pp.create_ext_grid(net, junction=idx, p_bar=node.pressure_bar, t_k=293.15)
        elif node.node_type == "sink":
            pp.create_ext_grid(net, junction=idx, p_bar=node.pressure_bar, t_k=293.15)

    # ── Pipe elements ──────────────────────────────────────────────────────
    pipe_idx_map: dict[str, int] = {}
    for pid, pipe in model.pipes.items():
        if pipe.start_node_id not in j_map or pipe.end_node_id not in j_map:
            warnings.append(f"{pid}: endpoint not found, skipping.")
            continue
        try:
            idx = pp.create_pipe_from_parameters(
                net,
                from_junction=j_map[pipe.start_node_id],
                to_junction=j_map[pipe.end_node_id],
                length_km=max(pipe.length_m / 1000.0, 1e-6),
                diameter_m=pipe.hydraulic_diameter_m,
                k_mm=pipe.roughness_mm,
                loss_coefficient=pipe.k_factor,
                name=pipe.name,
            )
            pipe_idx_map[pid] = idx
        except Exception as exc:
            warnings.append(f"{pid}: could not create pipe — {exc}")

    # ── Valve elements ─────────────────────────────────────────────────────
    # CLOSED valves are NOT added to the pandapipes network.
    # This creates a topological break: pandapipes sees dead-end pipe segments
    # on each side, which it correctly solves with exactly zero flow and the
    # appropriate static pressure (source pressure on inlet side, sink on outlet).
    # OPEN valves are modelled as short pipes with a K-factor loss.
    valve_idx_map:    dict[str, int] = {}
    closed_valve_ids: set[str]       = set()

    for vid, valve in model.valves.items():
        if valve.start_node_id not in j_map or valve.end_node_id not in j_map:
            warnings.append(f"{vid}: endpoint not found, skipping.")
            continue
        if not valve.is_open:
            # Fully closed: omit from network; results written after solve
            closed_valve_ids.add(vid)
            continue
        try:
            idx = pp.create_pipe_from_parameters(
                net,
                from_junction=j_map[valve.start_node_id],
                to_junction=j_map[valve.end_node_id],
                length_km=max(valve.length_m / 1000.0, 1e-6),
                diameter_m=valve.diameter_m,
                k_mm=0.045,
                loss_coefficient=valve.effective_k,
                name=valve.name,
            )
            valve_idx_map[vid] = idx
        except Exception as exc:
            warnings.append(f"{vid}: could not create valve — {exc}")

    # ── Pump elements ──────────────────────────────────────────────────────
    # Use pandapipes create_pump_from_parameters for running pumps.
    # H-Q curve points: pandapipes expects pressure_list in bar and
    # flowrate_list in m³/h.  H (m) → dp (bar) via rho*g*H/1e5.
    try:
        fluid_obj = pp.get_fluid(net)
        rho_fluid  = float(fluid_obj.get_density(293.15))
    except Exception:
        rho_fluid = 998.2
    g = 9.81

    pump_idx_map:       dict[str, int]        = {}  # centrifugal ON pumps → pump table index
    pump_pipe_map:      dict[str, int]        = {}  # OFF pumps → pipe table index
    fixed_disp_pump_map: dict[str, tuple[int, int]] = {}  # fixed-disp ON pumps → (j_in, j_out)

    for pump_id, pump in model.pumps.items():
        if pump.start_node_id not in j_map or pump.end_node_id not in j_map:
            warnings.append(f"{pump_id}: endpoint not found, skipping.")
            continue

        if not pump.on_off:
            # OFF pump: very high resistance pipe
            try:
                idx = pp.create_pipe_from_parameters(
                    net,
                    from_junction=j_map[pump.start_node_id],
                    to_junction=j_map[pump.end_node_id],
                    length_km=max(pump.length_m / 1000.0, 1e-6),
                    diameter_m=pump.diameter_m,
                    k_mm=0.045,
                    loss_coefficient=1e6,
                    name=pump.name,
                )
                pump_pipe_map[pump_id] = idx
            except Exception as exc:
                warnings.append(f"{pump_id}: could not create off-pump — {exc}")

        elif pump.pump_type == "fixed_displacement":
            # Fixed displacement: force exact mass flow by injecting a source at
            # the outlet junction and withdrawing a sink at the inlet junction.
            # This is the correct pandapipes API for forced-flow elements —
            # avoids the polynomial-fit instability of create_pump_from_parameters.
            try:
                Q_set = max(pump.fixed_flow_m3s, 1e-9)
                mdot  = rho_fluid * Q_set
                j_in  = j_map[pump.start_node_id]
                j_out = j_map[pump.end_node_id]
                pp.create_sink(net, j_in,  mdot_kg_per_s=mdot,
                               name=f"fdp_sink_{pump_id}")
                pp.create_source(net, j_out, mdot_kg_per_s=mdot,
                                 name=f"fdp_src_{pump_id}")
                fixed_disp_pump_map[pump_id] = (j_in, j_out)
            except Exception as exc:
                warnings.append(f"{pump_id}: could not create fixed-displacement pump — {exc}")

        else:
            # Centrifugal ON pump: H-Q polynomial via pandapipes pump model
            try:
                pts = sorted(pump.curve_points, key=lambda p: p[0])
                if len(pts) < 2:
                    pts = [(0.0, pump.max_head_m), (pump.max_flow_m3s, 0.0)]
                # Convert: H (m) → delta_p (bar); Q (m³/s) → Q (m³/h)
                p_list = [float(h) * rho_fluid * g / 1e5 for _, h in pts]
                q_list = [float(q) * 3600.0              for q, _ in pts]
                deg = min(2, len(pts) - 1)
                idx = pp.create_pump_from_parameters(
                    net,
                    from_junction=j_map[pump.start_node_id],
                    to_junction=j_map[pump.end_node_id],
                    new_std_type_name=f"pump_{pump_id}",
                    pressure_list=p_list,
                    flowrate_list=q_list,
                    reg_polynomial_degree=deg,
                    name=pump.name,
                )
                pump_idx_map[pump_id] = idx
            except Exception as exc:
                warnings.append(f"{pump_id}: could not create pump — {exc}")

    # ── Run solver ─────────────────────────────────────────────────────────
    try:
        pp.pipeflow(net, iter=1000, tol_p=1e-3, tol_v=1e-3, verbose=False)
    except Exception as exc:
        raise SolverError(f"Solver did not converge: {exc}")

    # ── Extract junction pressure results ──────────────────────────────────
    for nid, node in model.nodes.items():
        jidx = j_map.get(nid)
        if jidx is None:
            continue
        try:
            node.result_pressure_bar = float(net.res_junction.loc[jidx, "p_bar"])
        except Exception:
            node.result_pressure_bar = None

    # ── Extract pipe/valve results ─────────────────────────────────────────
    _extract_pipe_results(net, model.pipes, pipe_idx_map, rho_fluid)
    _extract_pipe_results(net, model.valves, valve_idx_map, rho_fluid)
    _extract_pipe_results(net, model.pumps, pump_pipe_map, rho_fluid)  # OFF pumps

    # ── Write CLOSED valve results (zero flow; pressures from junctions) ───
    for vid in closed_valve_ids:
        valve = model.valves[vid]
        jf_idx = j_map.get(valve.start_node_id)
        jt_idx = j_map.get(valve.end_node_id)
        try:
            pf = _finite(net.res_junction.loc[jf_idx, "p_bar"], 0.0) if jf_idx is not None else 0.0
            pt = _finite(net.res_junction.loc[jt_idx, "p_bar"], 0.0) if jt_idx is not None else 0.0
        except Exception:
            pf, pt = 0.0, 0.0
        valve.result_velocity_ms  = 0.0
        valve.result_flow_m3s     = 0.0
        valve.result_mdot_kgs     = 0.0
        valve.result_p_from_bar   = pf
        valve.result_p_to_bar     = pt
        valve.result_delta_p_bar  = pf - pt
        valve.result_reynolds     = 0.0
        valve.result_regime       = "Closed"

    # ── Extract running centrifugal pump results ────────────────────────────
    for pump_id, pidx in pump_idx_map.items():
        pump = model.pumps[pump_id]
        try:
            row   = net.res_pump.loc[pidx]
            vdot  = _finite(row.get("vdot_m3_per_s",        0.0), 0.0)
            mdot  = _finite(row.get("mdot_from_kg_per_s",   0.0), 0.0)
            pf    = _finite(row.get("p_from_bar",            0.0), 0.0)
            pt    = _finite(row.get("p_to_bar",              0.0), 0.0)
            dp    = _finite(row.get("deltap_bar",            0.0), 0.0)

            d  = pump.diameter_m
            A  = math.pi * d**2 / 4.0 if d > 0 else 1e-6
            v  = vdot / A if A > 0 else 0.0
            Re = rho_fluid * v * d / 1e-3 if d > 0 else 0.0
            H  = dp * 1e5 / (rho_fluid * g) if rho_fluid > 0 else 0.0

            pump.result_velocity_ms  = _finite(v,    0.0)
            pump.result_flow_m3s     = _finite(vdot, 0.0)
            pump.result_mdot_kgs     = _finite(mdot, 0.0)
            pump.result_p_from_bar   = _finite(pf,   0.0)
            pump.result_p_to_bar     = _finite(pt,   0.0)
            pump.result_delta_p_bar  = _finite(-dp,  0.0)   # negative = pressure gain
            pump.result_head_m       = _finite(H,    0.0)
            pump.result_reynolds     = abs(_finite(Re, 0.0))
            pump.result_regime       = _regime(abs(_finite(Re, 0.0)))
        except Exception:
            pass

    # ── Extract fixed-displacement pump results (from junction pressures) ───
    for pump_id, (j_in, j_out) in fixed_disp_pump_map.items():
        pump = model.pumps[pump_id]
        try:
            p_in  = _finite(float(net.res_junction.loc[j_in,  "p_bar"]), 0.0)
            p_out = _finite(float(net.res_junction.loc[j_out, "p_bar"]), 0.0)
            dp    = p_out - p_in               # positive = pressure gain
            H     = dp * 1e5 / (rho_fluid * g) if rho_fluid > 0 else 0.0
            Q_set = pump.fixed_flow_m3s
            d     = pump.diameter_m
            A     = math.pi * d**2 / 4.0 if d > 0 else 1e-6
            v     = Q_set / A if A > 0 else 0.0
            mdot  = rho_fluid * Q_set
            Re    = rho_fluid * v * d / 1e-3 if d > 0 else 0.0

            pump.result_velocity_ms  = _finite(v,     0.0)
            pump.result_flow_m3s     = _finite(Q_set, 0.0)
            pump.result_mdot_kgs     = _finite(mdot,  0.0)
            pump.result_p_from_bar   = _finite(p_in,  0.0)
            pump.result_p_to_bar     = _finite(p_out, 0.0)
            pump.result_delta_p_bar  = _finite(-dp,   0.0)  # negative = pressure gain
            pump.result_head_m       = _finite(H,     0.0)
            pump.result_reynolds     = abs(_finite(Re, 0.0))
            pump.result_regime       = _regime(abs(_finite(Re, 0.0)))
        except Exception:
            pass


def _finite(val, default=None):
    """Return float(val) if finite, else default.  Handles NaN/inf from solver."""
    try:
        f = float(val)
        return f if math.isfinite(f) else default
    except (TypeError, ValueError):
        return default


def _extract_pipe_results(net, elements: dict, idx_map: dict,
                          rho: float = 998.2) -> None:
    """Write pipe/valve results from net.res_pipe back onto model objects."""
    for eid, element in elements.items():
        pidx = idx_map.get(eid)
        if pidx is None:
            continue
        try:
            row  = net.res_pipe.loc[pidx]
            v    = _finite(row.get("v_mean_m_per_s",    0.0), 0.0)
            mdot = _finite(row.get("mdot_from_kg_per_s", 0.0), 0.0)
            pf   = _finite(row.get("p_from_bar",         0.0), 0.0)
            pt   = _finite(row.get("p_to_bar",           0.0), 0.0)
            re   = _finite(row.get("reynolds",           0.0), 0.0)
            vdot = _finite(row.get("vdot_m3_per_s",  mdot / max(rho, 1e-9)), 0.0)

            element.result_velocity_ms  = v
            element.result_flow_m3s     = vdot
            element.result_mdot_kgs     = mdot
            element.result_p_from_bar   = pf
            element.result_p_to_bar     = pt
            element.result_delta_p_bar  = pf - pt
            element.result_reynolds     = abs(re)
            element.result_regime       = _regime(abs(re))
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Fallback solver (series / tree networks only)
# Implements Darcy-Weisbach + Colebrook-White + H-Q pump curve.
# ---------------------------------------------------------------------------

def _pump_head_at_q(pump: PumpData, Q: float) -> float:
    """
    Interpolate pump head (m) from the H-Q curve at volumetric flow Q (m³/s).
    Returns 0 if pump is off.
    Fixed-displacement pumps: head is not used for Q calculation (Q is forced
    directly in _solve_fallback), but we return max_head for compatibility.
    """
    if not pump.on_off:
        return 0.0
    if pump.pump_type == "fixed_displacement":
        # Q is forced externally; return max_head so pressure walk is plausible
        return max(pump.fixed_head_m, 0.1)
    elif not pump.curve_points:
        return 0.0
    else:
        pts = sorted(pump.curve_points, key=lambda p: p[0])
    # Clamp to curve endpoints
    if Q <= pts[0][0]:
        return float(pts[0][1])
    if Q >= pts[-1][0]:
        return max(0.0, float(pts[-1][1]))
    # Linear interpolation between bracketing points
    for i in range(len(pts) - 1):
        q0, h0 = pts[i]
        q1, h1 = pts[i + 1]
        if q0 <= Q <= q1:
            t = (Q - q0) / (q1 - q0) if q1 > q0 else 0.0
            return h0 + t * (h1 - h0)
    return 0.0


def _solve_fallback(model: NetworkModel, warnings: list[str]) -> None:
    """
    Pressure-drop solver for simple (series/tree) networks.

    Physics:
      sum(R_i * Q^2) = dP_boundary + sum(rho * g * H_pump_i(Q))

    Where:
      dP_boundary = (P_source - P_sink) in Pa
      H_pump_i(Q) = pump head from H-Q curve, interpolated at Q
      R_i         = Darcy-Weisbach resistance coefficient for each element

    The operating point Q* is found by Newton-Raphson iteration.
    """
    sources = [n for n in model.nodes.values() if n.node_type == "source"]
    sinks   = [n for n in model.nodes.values() if n.node_type == "sink"]
    if not sources or not sinks:
        return

    source = sources[0]
    sink   = sinks[0]

    # Build adjacency list
    adj: dict[str, list[tuple[str, object]]] = {}
    for branch in model.all_branch_elements():
        s, e = branch.start_node_id, branch.end_node_id
        adj.setdefault(s, []).append((e, branch))
        adj.setdefault(e, []).append((s, branch))

    # BFS path from source to sink
    path = _bfs_path(adj, source.id, sink.id)
    if path is None:
        warnings.append("No path found from source to sink in fallback solver.")
        return

    if not path:
        return

    # Fluid properties
    from app.physics.fluid_library import get_fluid_display
    fdata = get_fluid_display(model.fluid_name)
    rho = fdata.get("density_kg_m3", 998.2)
    mu  = fdata.get("viscosity_pa_s", 1e-3)
    g   = 9.81  # m/s²

    # Boundary pressure difference (Pa)
    dp_boundary = (source.pressure_bar - sink.pressure_bar) * 1e5

    def _colebrook_friction(re: float, eps_d: float) -> float:
        """Swamee-Jain approximation to Colebrook-White equation."""
        if re < 2300.0:
            return 64.0 / max(re, 1.0)
        denom = math.log10(eps_d / 3.7 + 5.74 / re ** 0.9) ** 2
        return 0.25 / denom if denom != 0 else 0.02

    def _resistance(branch, Q_guess: float):
        """Return (d, L, eps_d, A, R) for a branch at flow Q_guess."""
        if isinstance(branch, PipeData):
            d     = branch.hydraulic_diameter_m
            L     = branch.length_m
            eps   = branch.roughness_mm / 1000.0
            eps_d = eps / d if d > 0 else 0.0
            A     = math.pi * d**2 / 4.0
            v     = Q_guess / A if A > 0 else 0.0
            Re    = rho * v * d / mu if mu > 0 and d > 0 else 1e5
            f     = _colebrook_friction(abs(Re), eps_d)
            R     = f * (L / d) * rho / (2.0 * A**2) if d > 0 and A > 0 else 0.0
            return d, L, eps_d, A, R

        elif isinstance(branch, ValveData):
            d = branch.diameter_m
            A = math.pi * d**2 / 4.0 if d > 0 else 1e-6
            K = branch.effective_k
            R = K * rho / (2.0 * A**2) if A > 0 else 1e12
            return d, 0.0, 0.0, A, R

        elif isinstance(branch, PumpData):
            # Pump has a small internal hydraulic resistance (seal losses)
            d = branch.diameter_m
            A = math.pi * d**2 / 4.0 if d > 0 else 1e-6
            # Minimal resistance — pressure is handled via H-Q head gain
            R = 0.5 * rho / (2.0 * A**2) if A > 0 else 0.0
            return d, 0.0, 0.0, A, R

        else:
            return 0.1, 0.0, 0.0, math.pi * 0.01 / 4.0, 0.0

    def _total_pump_head(Q_guess: float) -> float:
        """Sum of all pump heads on the path at flow Q."""
        return sum(
            _pump_head_at_q(b, Q_guess)
            for b in path
            if isinstance(b, PumpData)
        )

    def _system_equation(Q_guess: float) -> float:
        """
        f(Q) = R_total(Q)*Q^2 - dp_boundary - rho*g*H_pumps(Q) = 0
        """
        R_total = sum(_resistance(b, Q_guess)[4] for b in path)
        H_pump  = _total_pump_head(Q_guess)
        return R_total * Q_guess**2 - dp_boundary - rho * g * H_pump

    # Initial Q estimate — use max pump head or boundary pressure
    max_pump_head = _total_pump_head(0.0)
    dp_eff_initial = dp_boundary + rho * g * max_pump_head
    R_initial = sum(_resistance(b, 0.01)[4] for b in path) or 1.0
    Q = math.sqrt(max(dp_eff_initial / R_initial, 0.0))

    # Newton-Raphson iteration (with bisection fallback)
    for iteration in range(100):
        # Recompute resistances at current Q (friction factor update)
        R_total = sum(_resistance(b, Q)[4] for b in path)
        H_pump  = _total_pump_head(Q)
        dp_eff  = dp_boundary + rho * g * H_pump

        if R_total <= 0.0:
            break
        Q_new = math.sqrt(max(dp_eff / R_total, 0.0))
        if abs(Q_new - Q) < 1e-10:
            break
        Q = Q_new

    # Fixed-displacement pump in path: override Q to the set-point
    for b in path:
        if isinstance(b, PumpData) and b.on_off and b.pump_type == "fixed_displacement":
            Q = b.fixed_flow_m3s
            break

    # Clamp to physical range (non-negative)
    Q = max(Q, 0.0)

    # ── Write results back ──────────────────────────────────────────────────
    p_current = source.pressure_bar * 1e5   # Pa, walk from source to sink
    source.result_pressure_bar = source.pressure_bar

    visited_nodes = {source.id}
    for branch in path:
        d, L, eps_d, A, R = _resistance(branch, Q)

        v    = Q / A if A > 0 else 0.0
        mdot = rho * Q
        Re   = rho * v * d / mu if mu > 0 and d > 0 else 0.0

        p_from = p_current

        if isinstance(branch, PumpData) and branch.on_off:
            # Pump ADDS pressure (pressure increases downstream)
            head = _pump_head_at_q(branch, Q)
            dp_pump = rho * g * head        # Pa gained
            dp_loss  = R * Q**2             # Pa lost to internal friction
            p_to = p_from + dp_pump - dp_loss
            branch.result_head_m      = head
            branch.result_delta_p_bar = -(dp_pump - dp_loss) * 1e-5  # negative = gain
        else:
            # Resistive element: pressure drops
            dp_loss = R * Q**2
            p_to = p_from - dp_loss
            branch.result_delta_p_bar = dp_loss * 1e-5

        branch.result_velocity_ms = _finite(v,          0.0)
        branch.result_flow_m3s    = _finite(Q,          0.0)
        branch.result_mdot_kgs    = _finite(mdot,       0.0)
        branch.result_p_from_bar  = _finite(p_from * 1e-5, 0.0)
        branch.result_p_to_bar    = _finite(p_to   * 1e-5, 0.0)
        branch.result_reynolds    = abs(_finite(Re,    0.0))
        branch.result_regime      = _regime(abs(_finite(Re, 0.0)))

        p_current = p_to

        # Set downstream node pressure
        end_id = (branch.end_node_id
                  if branch.start_node_id in visited_nodes
                  else branch.start_node_id)
        if end_id in model.nodes:
            model.nodes[end_id].result_pressure_bar = p_to * 1e-5
        visited_nodes.add(end_id)

    sink.result_pressure_bar = sink.pressure_bar


# ---------------------------------------------------------------------------
# Topology helpers
# ---------------------------------------------------------------------------

def _find_orphan_nodes(model: NetworkModel) -> list[str]:
    connected = set()
    for b in model.all_branch_elements():
        connected.add(b.start_node_id)
        connected.add(b.end_node_id)
    return [nid for nid in model.nodes if nid not in connected]


def _find_disconnected_subgraphs(model: NetworkModel) -> list[set]:
    adj: dict[str, set[str]] = {nid: set() for nid in model.nodes}
    for b in model.all_branch_elements():
        adj.setdefault(b.start_node_id, set()).add(b.end_node_id)
        adj.setdefault(b.end_node_id, set()).add(b.start_node_id)

    visited: set[str] = set()
    components: list[set] = []
    for nid in model.nodes:
        if nid in visited:
            continue
        comp: set[str] = set()
        stack = [nid]
        while stack:
            cur = stack.pop()
            if cur in visited:
                continue
            visited.add(cur)
            comp.add(cur)
            stack.extend(adj.get(cur, set()) - visited)
        components.append(comp)
    return components


def _bfs_path(adj, start: str, end: str):
    """Return list of branch objects from start to end, or None."""
    from collections import deque
    queue = deque([(start, [])])
    visited = {start}
    while queue:
        node, path = queue.popleft()
        if node == end:
            return path
        for (neighbor, branch) in adj.get(node, []):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, path + [branch]))
    return None
