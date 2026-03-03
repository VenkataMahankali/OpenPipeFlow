"""
OpenPipeFlow — Orifice pressure-loss model.

Implements ISO 5167-2 / Reader-Harris-Gallagher (1998) discharge coefficient
via the fluids library (Caleb Bell et al., MIT License).

Source: https://github.com/CalebBell/fluids
Citation: Caleb Bell and Contributors (2016-2025). fluids: Fluid dynamics
          component of Chemical Engineering Design Library (ChEDL).
          https://github.com/CalebBell/fluids
"""

from __future__ import annotations
import math

try:
    import fluids
    _FLUIDS = True
except ImportError:
    _FLUIDS = False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_orifice_K(
    d_orifice_m: float,
    d_pipe_m: float,
    rho: float,
    mu: float,
    velocity_pipe: float,
    tap_type: str = "flange",
    override_Cd: float | None = None,
    override_K: float | None = None,
) -> dict:
    """
    Compute the loss coefficient K and discharge coefficient Cd for an orifice.

    K is referenced to upstream pipe velocity head:
        dP = K * 0.5 * rho * v_pipe²

    Parameters
    ----------
    d_orifice_m   : orifice bore diameter [m]
    d_pipe_m      : upstream pipe internal diameter [m]
    rho           : fluid density [kg/m³]
    mu            : dynamic viscosity [Pa·s]
    velocity_pipe : bulk velocity in upstream pipe [m/s]  (used for Re)
    tap_type      : 'corner', 'flange', or 'D'
    override_Cd   : if set, use this Cd instead of ISO 5167 value
    override_K    : if set, bypass all geometry calculations and use this K

    Returns
    -------
    dict with keys:
        K              – loss coefficient (float)
        Cd             – discharge coefficient (float or None)
        beta           – diameter ratio d/D (float)
        Re_pipe        – Reynolds number in pipe (float or None)
        auto_calculated– True if ISO 5167 was used (bool)
        source         – description string
    """
    if d_pipe_m <= 0 or d_orifice_m <= 0:
        return {"K": 0.0, "Cd": None, "beta": 0.0,
                "Re_pipe": None, "auto_calculated": False,
                "source": "invalid geometry"}

    beta = d_orifice_m / d_pipe_m

    # ── Hard override: user has manually entered K ────────────────────────
    if override_K is not None:
        return {
            "K": float(override_K),
            "Cd": None,
            "beta": beta,
            "Re_pipe": None,
            "auto_calculated": False,
            "source": "manual K override",
        }

    # ── Compute mass flow from velocity ───────────────────────────────────
    A_pipe = math.pi * d_pipe_m**2 / 4.0
    v_safe = max(abs(velocity_pipe), 1e-4)   # avoid division by zero
    m      = rho * v_safe * A_pipe
    Re_pipe = rho * v_safe * d_pipe_m / max(mu, 1e-12)

    # ── Cd calculation ────────────────────────────────────────────────────
    if override_Cd is not None:
        Cd     = float(override_Cd)
        source = "manual Cd override"
    elif _FLUIDS:
        tap_map = {"corner": "corner", "flange": "flange", "D": "D"}
        tap = tap_map.get(tap_type, "flange")
        try:
            Cd = fluids.C_Reader_Harris_Gallagher(
                D=d_pipe_m, Do=d_orifice_m,
                rho=rho, mu=mu, m=m,
                taps=tap,
            )
            source = f"ISO 5167 / fluids (tap={tap})"
        except Exception as exc:
            # Out-of-range beta (must be 0.1–0.75) or Re out of range
            Cd = _fallback_cd(beta)
            source = f"fallback Cd≈{Cd:.3f} (fluids error: {exc})"
    else:
        # fluids not installed — use simple sharp-edged approximation
        Cd = _fallback_cd(beta)
        source = "fallback Cd (fluids not installed)"

    # ── K from Cd + geometry ──────────────────────────────────────────────
    if _FLUIDS and override_K is None:
        try:
            K = fluids.discharge_coefficient_to_K(
                D=d_pipe_m, Do=d_orifice_m, C=Cd)
        except Exception:
            K = _k_from_cd_beta(Cd, beta)
    else:
        K = _k_from_cd_beta(Cd, beta)

    K = max(K, 0.0)

    return {
        "K":               K,
        "Cd":              Cd,
        "beta":            beta,
        "Re_pipe":         Re_pipe,
        "auto_calculated": override_Cd is None and override_K is None,
        "source":          source,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fallback_cd(beta: float) -> float:
    """Simple sharp-edged orifice approximation for β in [0.1, 0.75]."""
    # Stolz equation (simplified ISO 5167 analytic approximation)
    # Cd ≈ 0.5959 + 0.0312 β^2.1 − 0.184 β^8
    b = max(0.1, min(beta, 0.75))
    return 0.5959 + 0.0312 * b**2.1 - 0.184 * b**8


def _k_from_cd_beta(Cd: float, beta: float) -> float:
    """
    Derive K from Cd and beta ratio.
    Uses the ASME MFC-3M formula (same as fluids.discharge_coefficient_to_K):
        K = [sqrt(1 - beta^4*(1 - Cd^2)) / (Cd * beta^2) - 1]^2
    K is referenced to upstream pipe velocity head.
    """
    if beta <= 0 or Cd <= 0:
        return 0.0
    beta2 = beta * beta
    beta4 = beta2 * beta2
    root_K = math.sqrt(1.0 - beta4 * (1.0 - Cd * Cd)) / (Cd * beta2) - 1.0
    return max(root_K * root_K, 0.0)
