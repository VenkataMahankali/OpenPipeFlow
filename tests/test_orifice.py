"""
OpenPipeFlow — Orifice model tests.

Validates ISO 5167 implementation (Reader-Harris/Gallagher) against
known values and verifies override behaviour.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.physics.orifice_model import compute_orifice_K, _fallback_cd, _k_from_cd_beta


def test_orifice_known_values():
    """
    Validate against ISO 5167 reference case:
    D=0.1 m pipe, d=0.05 m orifice (beta=0.5),
    water at 20°C (rho=998.2, mu=0.001), v_pipe=2 m/s, flange taps.
    Expected Cd ≈ 0.605 ± 0.008 (typical ISO 5167 flange tap value)
    """
    result = compute_orifice_K(
        d_orifice_m=0.05, d_pipe_m=0.1,
        rho=998.2, mu=0.001, velocity_pipe=2.0,
        tap_type="flange",
    )
    assert result["auto_calculated"] is True,  "Should be auto-calculated"
    assert abs(result["beta"] - 0.5) < 1e-9,   f"beta wrong: {result['beta']}"
    assert 0.595 < result["Cd"] < 0.620,        f"Cd out of range: {result['Cd']:.6f}"
    assert result["K"] > 0,                     f"K must be positive, got {result['K']}"
    assert result["Re_pipe"] is not None
    print(f"  Cd={result['Cd']:.6f}  K={result['K']:.4f}  beta={result['beta']:.4f}  "
          f"Re={result['Re_pipe']:.0f}  source={result['source']}")


def test_orifice_corner_taps():
    """Corner taps give slightly different Cd from flange taps."""
    r_flange = compute_orifice_K(0.05, 0.1, 998.2, 0.001, 2.0, "flange")
    r_corner = compute_orifice_K(0.05, 0.1, 998.2, 0.001, 2.0, "corner")
    assert 0.595 < r_corner["Cd"] < 0.620
    # Flange and corner Cds differ by < 1%
    assert abs(r_flange["Cd"] - r_corner["Cd"]) < 0.01
    print(f"  Flange Cd={r_flange['Cd']:.6f}  Corner Cd={r_corner['Cd']:.6f}")


def test_override_K_bypasses_geometry():
    """When override_K is set, K is returned directly and auto_calculated=False."""
    result = compute_orifice_K(
        d_orifice_m=0.05, d_pipe_m=0.1,
        rho=998.2, mu=0.001, velocity_pipe=2.0,
        override_K=12.5,
    )
    assert result["K"] == 12.5,              f"Expected K=12.5, got {result['K']}"
    assert result["auto_calculated"] is False
    assert result["Cd"] is None,             "Cd should be None when K is overridden"
    assert abs(result["beta"] - 0.5) < 1e-9
    print(f"  K override=12.5 -> K={result['K']}, Cd={result['Cd']}, auto={result['auto_calculated']}")


def test_override_Cd_uses_geometry_for_K():
    """When override_Cd is set, K is still computed from geometry but uses given Cd."""
    r_auto = compute_orifice_K(0.05, 0.1, 998.2, 0.001, 2.0)
    r_override = compute_orifice_K(0.05, 0.1, 998.2, 0.001, 2.0, override_Cd=0.61)

    # With higher Cd, K should be lower (larger Cd → less restriction)
    assert r_override["Cd"] == 0.61
    assert r_override["auto_calculated"] is False
    assert r_override["K"] > 0
    print(f"  Auto Cd={r_auto['Cd']:.6f} K={r_auto['K']:.4f}  "
          f"Override Cd=0.61 K={r_override['K']:.4f}")


def test_beta_ratio_range():
    """Cd should be physically sensible for beta 0.2–0.7."""
    D = 0.2
    for beta in [0.2, 0.3, 0.4, 0.5, 0.6, 0.7]:
        d = D * beta
        result = compute_orifice_K(d, D, 998.2, 0.001, 2.0, "flange")
        assert 0.55 < result["Cd"] < 0.70, \
            f"Cd={result['Cd']:.4f} out of physical range for beta={beta}"
        assert result["K"] > 0
        print(f"  beta={beta:.1f}  Cd={result['Cd']:.4f}  K={result['K']:.2f}")


def test_low_velocity_doesnt_crash():
    """Very low velocity (near-zero Re) should return a sensible result, not crash."""
    result = compute_orifice_K(0.05, 0.1, 998.2, 0.001, 1e-6)
    assert result["K"] >= 0
    assert result["Cd"] is not None
    print(f"  Low v: Cd={result['Cd']:.4f}  K={result['K']:.4f}  source={result['source']}")


def test_invalid_geometry_returns_zero():
    """Zero diameter should return K=0 without crashing."""
    result = compute_orifice_K(0.0, 0.1, 998.2, 0.001, 2.0)
    assert result["K"] == 0.0
    result2 = compute_orifice_K(0.05, 0.0, 998.2, 0.001, 2.0)
    assert result2["K"] == 0.0
    print("  Invalid geometry returns K=0 OK")


def test_fallback_cd_stolz():
    """_fallback_cd should match published sharp-edged approximations."""
    # For beta=0.5, Stolz gives ~0.605 which matches well
    Cd = _fallback_cd(0.5)
    assert 0.595 < Cd < 0.620, f"Fallback Cd={Cd:.4f}"
    print(f"  Fallback Cd (beta=0.5) = {Cd:.6f}")


def test_k_from_cd_beta_roundtrip():
    """K → Cd → K should round-trip consistently."""
    import fluids
    D, Do = 0.1, 0.05
    beta  = Do / D
    Cd0   = 0.605
    K     = _k_from_cd_beta(Cd0, beta)
    # Recover Cd from K via fluids
    Cd_back = fluids.K_to_discharge_coefficient(D=D, Do=Do, K=K)
    assert abs(Cd_back - Cd0) < 1e-6, f"Round-trip error: Cd0={Cd0} Cd_back={Cd_back}"
    print(f"  K_from_Cd_beta: Cd0={Cd0}  K={K:.4f}  Cd_back={Cd_back:.6f}")


def test_network_orifice_integration():
    """
    Integration test: orifice in a simple network produces non-zero flow
    and a computed Cd stored on the model object.
    """
    from app.project.model import NetworkModel, NodeData, PipeData, ValveData
    from app.physics.network_bridge import solve_network

    m = NetworkModel()
    m.nodes['src']  = NodeData(id='src', name='Source', x=0,   y=0, node_type='source', pressure_bar=5.0)
    m.nodes['jn1']  = NodeData(id='jn1', name='J1',    x=100,  y=0, node_type='junction')
    m.nodes['jn2']  = NodeData(id='jn2', name='J2',    x=200,  y=0, node_type='junction')
    m.nodes['snk']  = NodeData(id='snk', name='Sink',  x=300, y=0, node_type='sink', pressure_bar=1.0)

    m.pipes['p1']  = PipeData(id='p1', name='Pipe1', pipe_type='pipe',
                              start_node_id='src', end_node_id='jn1',
                              length_m=10.0, diameter_m=0.1, roughness_mm=0.05)

    # Orifice: D=0.1 m pipe, d=0.05 m bore (beta=0.5), flange taps
    ori = ValveData(id='ori1', name='Orifice1',
                    start_node_id='jn1', end_node_id='jn2',
                    valve_type='orifice', diameter_m=0.1,
                    bore_diameter_m=0.05, tap_type='flange',
                    open_pct=100.0)
    m.valves['ori1'] = ori

    m.pipes['p2'] = PipeData(id='p2', name='Pipe2', pipe_type='pipe',
                             start_node_id='jn2', end_node_id='snk',
                             length_m=10.0, diameter_m=0.1, roughness_mm=0.05)

    warns = solve_network(m)
    if warns:
        print(f"  Warnings: {warns}")

    assert ori.result_flow_m3s  is not None, "No flow result"
    assert ori.result_flow_m3s  > 0,         f"Zero/negative flow: {ori.result_flow_m3s}"
    assert ori.result_cd        is not None,  "No Cd result"
    assert 0.595 < ori.result_cd < 0.620,     f"Cd out of range: {ori.result_cd:.4f}"
    assert ori.result_beta      is not None
    assert abs(ori.result_beta - 0.5) < 1e-6
    assert ori.result_k_iso     is not None
    assert ori.result_k_iso     > 0

    print(f"  Q={ori.result_flow_m3s*1000:.3f} L/s  "
          f"dP={ori.result_delta_p_bar:.4f} bar  "
          f"Cd={ori.result_cd:.4f}  K={ori.result_k_iso:.3f}")


if __name__ == "__main__":
    tests = [
        test_orifice_known_values,
        test_orifice_corner_taps,
        test_override_K_bypasses_geometry,
        test_override_Cd_uses_geometry_for_K,
        test_beta_ratio_range,
        test_low_velocity_doesnt_crash,
        test_invalid_geometry_returns_zero,
        test_fallback_cd_stolz,
        test_k_from_cd_beta_roundtrip,
        test_network_orifice_integration,
    ]
    failed = 0
    for t in tests:
        name = t.__name__
        try:
            print(f"\n[RUN] {name}")
            t()
            print(f"[OK]  {name}")
        except AssertionError as e:
            print(f"[FAIL] {name}: {e}")
            failed += 1
        except Exception as e:
            print(f"[ERROR] {name}: {type(e).__name__}: {e}")
            failed += 1
    print(f"\n{'='*50}")
    if failed:
        print(f"FAILED: {failed}/{len(tests)} tests")
        sys.exit(1)
    else:
        print(f"ALL {len(tests)} TESTS PASSED")
