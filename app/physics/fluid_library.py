"""
OpenPipeFlow — Fluid library.

Priority order for property data:
  1. pandapipes built-in fluids (most accurate for the solver's own data)
  2. fluids package (Caleb Bell et al.) for density / viscosity at temperature
  3. Hard-coded fallback values at 20 °C

The solver always uses pandapipes fluid data internally; this module is used
for display values in the UI and for the fallback Darcy-Weisbach solver.
"""

from __future__ import annotations

try:
    import pandapipes as pp
    _PP_AVAILABLE = True
except ImportError:
    _PP_AVAILABLE = False

try:
    import fluids
    _FLUIDS_AVAILABLE = True
except ImportError:
    _FLUIDS_AVAILABLE = False

# ---------------------------------------------------------------------------
# Hard-coded fallback values for display (density kg/m³, viscosity Pa·s at 20°C)
# ---------------------------------------------------------------------------
_FALLBACK: dict[str, dict] = {
    "water": {
        "label": "Water (20°C)",
        "density_kg_m3": 998.2,
        "viscosity_pa_s": 1.002e-3,
    },
    "water_5c": {
        "label": "Water (5°C)",
        "density_kg_m3": 999.9,
        "viscosity_pa_s": 1.519e-3,
    },
    "water_80c": {
        "label": "Water (80°C)",
        "density_kg_m3": 971.8,
        "viscosity_pa_s": 3.54e-4,
    },
    "air": {
        "label": "Air (20°C, 1 atm)",
        "density_kg_m3": 1.204,
        "viscosity_pa_s": 1.81e-5,
    },
    "crude_oil": {
        "label": "Light Crude Oil",
        "density_kg_m3": 850.0,
        "viscosity_pa_s": 0.005,
    },
    "hydraulic_oil_vg46": {
        "label": "Hydraulic Oil ISO VG 46",
        "density_kg_m3": 870.0,
        "viscosity_pa_s": 0.046,
    },
}

# Mapping from our internal names to pandapipes library names
_PP_NAME_MAP: dict[str, str] = {
    "water":              "water",
    "water_5c":           "water",
    "water_80c":          "water",
    "air":                "air",
    "crude_oil":          "water",
    "hydraulic_oil_vg46": "water",
}

# Ordered list for the GUI dropdown
AVAILABLE_FLUIDS: list[str] = list(_FALLBACK.keys())


def get_fluid_display(fluid_name: str) -> dict:
    """
    Return a dict with label, density_kg_m3, viscosity_pa_s for UI display.

    Data source priority:
      1. pandapipes (uses its own fluid tables at 20°C)
      2. fluids package (uses its own IAPWS-97 / correlations)
      3. hard-coded fallback
    """
    info = _FALLBACK.get(fluid_name, _FALLBACK["water"]).copy()

    if _PP_AVAILABLE:
        try:
            net = pp.create_empty_network(fluid=_PP_NAME_MAP.get(fluid_name, "water"))
            fluid = pp.get_fluid(net)
            T = 293.15  # 20°C
            info["density_kg_m3"]  = float(fluid.get_density(T))
            info["viscosity_pa_s"] = float(fluid.get_dyn_viscosity(T))
            return info
        except Exception:
            pass   # fall through to fluids or hard-coded

    if _FLUIDS_AVAILABLE and fluid_name in ("water", "water_5c", "water_80c"):
        # fluids.IAPWS97 provides accurate water properties
        T_map = {"water": 293.15, "water_5c": 278.15, "water_80c": 353.15}
        T = T_map.get(fluid_name, 293.15)
        try:
            water = fluids.IAPWS97(T=T, P=1e5)
            info["density_kg_m3"]  = float(water.rho)
            info["viscosity_pa_s"] = float(water.mu)
            return info
        except Exception:
            pass

    return info


def get_pandapipes_fluid_name(fluid_name: str) -> str:
    """Translate our fluid key to the pandapipes library name."""
    return _PP_NAME_MAP.get(fluid_name, "water")


def pandapipes_available() -> bool:
    return _PP_AVAILABLE


def fluids_available() -> bool:
    return _FLUIDS_AVAILABLE
