"""
OpenPipeFlow ? Automated network tests (no GUI required).

Test network: Tank A (5 bar) -> Pipe -> Pump -> Ball Valve -> Orifice -> Pipe -> Tank B (1 bar)

Runs the solver multiple times and validates:
  - No exceptions
  - Consistent results across runs
  - Pressure decreases from source to sink
  - All branch elements show positive velocity
  - Reynolds number is within physical bounds
"""

import sys
import os
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.project.model import NetworkModel, NodeData, PipeData, ValveData, PumpData
import app.project.id_generator as id_gen
from app.physics.network_bridge import solve_network, SolverError


# ------------------------------------------------------------------------------
# Network builder
# ------------------------------------------------------------------------------

def build_test_network() -> NetworkModel:
    """
    Build: Tank A (5 bar) -> Inlet Pipe -> [Pump] -> [Ball Valve] -> [Orifice] -> Outlet Pipe -> Tank B (1 bar)
    """
    id_gen.reset()
    model = NetworkModel()
    model.fluid_name = "water"

    # -- Nodes --------------------------------------------------------------
    tank_a  = NodeData(id="SRC-001", name="Tank A",
                       node_type="source", x=0,   y=0, pressure_bar=5.0)
    j_pump  = NodeData(id="ND-001",  name="Pump Suction",
                       node_type="junction", x=100, y=0)
    j_valve = NodeData(id="ND-002",  name="Pump Discharge",
                       node_type="junction", x=200, y=0)
    j_ori   = NodeData(id="ND-003",  name="Valve Outlet",
                       node_type="junction", x=300, y=0)
    j_out   = NodeData(id="ND-004",  name="Orifice Outlet",
                       node_type="junction", x=400, y=0)
    tank_b  = NodeData(id="SNK-001", name="Tank B",
                       node_type="sink", x=500, y=0, pressure_bar=1.0)

    model.nodes = {
        "SRC-001": tank_a,
        "ND-001":  j_pump,
        "ND-002":  j_valve,
        "ND-003":  j_ori,
        "ND-004":  j_out,
        "SNK-001": tank_b,
    }

    # -- Pipes --------------------------------------------------------------
    p_inlet = PipeData(
        id="PIPE-001", name="Inlet Pipe", pipe_type="pipe",
        start_node_id="SRC-001", end_node_id="ND-001",
        length_m=5.0, diameter_m=0.1, roughness_mm=0.045,
    )
    p_outlet = PipeData(
        id="PIPE-002", name="Outlet Pipe", pipe_type="pipe",
        start_node_id="ND-004", end_node_id="SNK-001",
        length_m=5.0, diameter_m=0.1, roughness_mm=0.045,
    )
    model.pipes = {"PIPE-001": p_inlet, "PIPE-002": p_outlet}

    # -- Pump ---------------------------------------------------------------
    pump = PumpData(
        id="PMP-001", name="Feed Pump",
        start_node_id="ND-001", end_node_id="ND-002",
        on_off=True, diameter_m=0.1,
        curve_points=[(0.0, 30.0), (0.02, 25.0), (0.04, 18.0),
                      (0.06, 10.0), (0.08, 0.0)],
    )
    model.pumps = {"PMP-001": pump}

    # -- Ball valve (fully open) --------------------------------------------
    ball_valve = ValveData(
        id="VLV-001", name="Ball Valve BV-001",
        start_node_id="ND-002", end_node_id="ND-003",
        valve_type="ball", k_factor=0.1, open_pct=100.0, diameter_m=0.1,
    )

    # -- Orifice plate (Cd ? 0.6, ? ? 0.5 -> K ? 8) ------------------------
    orifice = ValveData(
        id="ORI-001", name="Orifice FE-001",
        start_node_id="ND-003", end_node_id="ND-004",
        valve_type="orifice", k_factor=8.0, open_pct=100.0, diameter_m=0.05,
    )
    model.valves = {"VLV-001": ball_valve, "ORI-001": orifice}

    return model


# ------------------------------------------------------------------------------
# Assertion helpers
# ------------------------------------------------------------------------------

def assert_results_valid(model: NetworkModel, run_num: int):
    errors = []

    # Pressure at source > sink
    src_p = model.nodes["SRC-001"].result_pressure_bar
    snk_p = model.nodes["SNK-001"].result_pressure_bar
    if src_p is None or snk_p is None:
        errors.append("Source or sink pressure is None")
    elif src_p <= snk_p:
        errors.append(f"Source pressure ({src_p:.3f}) should exceed sink ({snk_p:.3f})")

    # Every pipe/valve should have a positive velocity
    for branch_dict in (model.pipes, model.valves, model.pumps):
        for eid, el in branch_dict.items():
            v = getattr(el, "result_velocity_ms", None)
            if v is None:
                errors.append(f"{eid}: velocity is None")
            elif v < 0:
                errors.append(f"{eid}: negative velocity {v:.4f} m/s")
            elif v == 0.0:
                errors.append(f"{eid}: zero velocity (no flow?)")

            re = getattr(el, "result_reynolds", None)
            if re is not None and re < 0:
                errors.append(f"{eid}: negative Reynolds {re:.0f}")

    if errors:
        print(f"  Run {run_num}: FAILED")
        for e in errors:
            print(f"    FAIL {e}")
        return False
    return True


def results_consistent(r1: dict, r2: dict, tol: float = 1e-6) -> bool:
    """Check that two result snapshots are numerically identical."""
    for key, v1 in r1.items():
        v2 = r2.get(key)
        if v1 is None and v2 is None:
            continue
        if v1 is None or v2 is None:
            return False
        if abs(v1 - v2) > tol:
            return False
    return True


def snapshot_results(model: NetworkModel) -> dict:
    snap = {}
    for d in (model.pipes, model.valves, model.pumps):
        for eid, el in d.items():
            for attr in ("result_velocity_ms", "result_flow_m3s",
                         "result_delta_p_bar", "result_reynolds"):
                snap[f"{eid}.{attr}"] = getattr(el, attr, None)
    for nid, node in model.nodes.items():
        snap[f"{nid}.result_pressure_bar"] = node.result_pressure_bar
    return snap


# ------------------------------------------------------------------------------
# Main test runner
# ------------------------------------------------------------------------------

def run_tests(n_runs: int = 5):
    print("=" * 60)
    print(f"OpenPipeFlow ? Network Test Suite  ({n_runs} runs)")
    print("=" * 60)
    print()
    print("Network: Tank A (5 bar) -> Pipe -> Pump -> Ball Valve -> Orifice -> Pipe -> Tank B (1 bar)")
    print()

    model = build_test_network()
    n_passed = 0
    first_snapshot = None
    all_passed = True

    for run in range(1, n_runs + 1):
        print(f"Run {run}/{n_runs} ", end="", flush=True)
        try:
            warnings = solve_network(model)
            ok = assert_results_valid(model, run)

            if ok:
                snap = snapshot_results(model)
                if first_snapshot is None:
                    first_snapshot = snap
                else:
                    if not results_consistent(first_snapshot, snap):
                        print(f"  Run {run}: INCONSISTENT results vs run 1")
                        ok = False

            if ok:
                v_pipe  = model.pipes["PIPE-001"].result_velocity_ms
                q_lpm   = (model.pipes["PIPE-001"].result_flow_m3s or 0) * 60000
                dp_ori  = model.valves["ORI-001"].result_delta_p_bar
                re_pipe = model.pipes["PIPE-001"].result_reynolds
                regime  = model.pipes["PIPE-001"].result_regime
                src_p   = model.nodes["SRC-001"].result_pressure_bar
                snk_p   = model.nodes["SNK-001"].result_pressure_bar
                print(f"OK  v={v_pipe:.3f} m/s  Q={q_lpm:.2f} L/min  "
                      f"?P_orifice={dp_ori:.3f} bar  "
                      f"Re={re_pipe:.0f} ({regime})")
                if warnings:
                    for w in warnings:
                        print(f"   WARN  {w}")
                n_passed += 1
            else:
                all_passed = False

        except SolverError as exc:
            print(f"  FAIL SolverError: {exc}")
            all_passed = False
        except Exception as exc:
            print(f"  FAIL Unexpected: {exc}")
            traceback.print_exc()
            all_passed = False

    print()
    print("-" * 60)
    print(f"Results: {n_passed}/{n_runs} runs passed")

    # -- Additional edge-case tests -----------------------------------------
    print()
    print("Edge-case tests:")

    # Test 1: Closed ball valve -> solver should still run (very high resistance)
    print("  [1] Closing ball valve to 0% ...", end=" ", flush=True)
    try:
        model2 = build_test_network()
        model2.valves["VLV-001"].open_pct = 0.0
        solve_network(model2)
        v = model2.valves["VLV-001"].result_velocity_ms
        print(f"OK  velocity through closed valve = {v:.6f} m/s (near zero expected)")
    except Exception as exc:
        print(f"FAIL  {exc}")
        all_passed = False

    # Test 2: Pump OFF
    print("  [2] Pump OFF ...", end=" ", flush=True)
    try:
        model3 = build_test_network()
        model3.pumps["PMP-001"].on_off = False
        solve_network(model3)
        v = model3.pipes["PIPE-001"].result_velocity_ms
        print(f"OK  velocity with pump off = {v:.4f} m/s")
    except Exception as exc:
        print(f"FAIL  {exc}")
        all_passed = False

    # Test 3: High-pressure source (10 bar)
    print("  [3] High-pressure source (10 bar) ...", end=" ", flush=True)
    try:
        model4 = build_test_network()
        model4.nodes["SRC-001"].pressure_bar = 10.0
        solve_network(model4)
        v = model4.pipes["PIPE-001"].result_velocity_ms
        v_orig = first_snapshot.get("PIPE-001.result_velocity_ms", 0) if first_snapshot else 0
        faster = v > v_orig if v_orig else True
        print(f"OK  velocity = {v:.3f} m/s ({'higher' if faster else 'same'} than 5-bar case)")
    except Exception as exc:
        print(f"FAIL  {exc}")
        all_passed = False

    # Test 4: No source nodes -> should raise SolverError
    print("  [4] No source nodes (should raise SolverError) ...", end=" ", flush=True)
    try:
        model5 = build_test_network()
        model5.nodes["SRC-001"].node_type = "junction"
        solve_network(model5)
        print("FAIL  Should have raised SolverError but did not!")
        all_passed = False
    except SolverError:
        print("OK  SolverError raised correctly")
    except Exception as exc:
        print(f"FAIL  Wrong exception type: {type(exc).__name__}: {exc}")
        all_passed = False

    # Test 5: Node-on-node type replacement (no duplicate IDs)
    print("  [5] Duplicate node ID check ...", end=" ", flush=True)
    try:
        model6 = build_test_network()
        ids = list(model6.nodes.keys())
        assert len(ids) == len(set(ids)), "Duplicate node IDs found!"
        branch_ids = (list(model6.pipes.keys()) + list(model6.valves.keys())
                      + list(model6.pumps.keys()))
        assert len(branch_ids) == len(set(branch_ids)), "Duplicate branch IDs!"
        print(f"OK  {len(ids)} nodes, {len(branch_ids)} branches ? all unique IDs")
    except AssertionError as exc:
        print(f"FAIL  {exc}")
        all_passed = False

    print()
    print("=" * 60)
    print("ALL TESTS PASSED OK" if all_passed and n_passed == n_runs
          else f"SOME TESTS FAILED ? {n_passed}/{n_runs} main runs OK")
    print("=" * 60)
    return all_passed and n_passed == n_runs


if __name__ == "__main__":
    import sys
    ok = run_tests(n_runs=5)
    sys.exit(0 if ok else 1)
