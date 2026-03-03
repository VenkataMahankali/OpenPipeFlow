"""
OpenPipeFlow — unit conversion utilities.

UNITS is a module-level singleton.  All UI code reads/writes through it.
Internal model always stores SI (bar, m³/s, m, m/s).
"""

from __future__ import annotations

# ── Conversion factors: from each display unit TO SI base unit ─────────────

PRESSURE_UNITS: dict[str, float] = {
    "bar":  1.0,
    "psi":  0.0689476,
    "kPa":  0.01,
    "MPa":  10.0,
}

FLOW_UNITS: dict[str, float] = {
    "L/min":  1.0 / 60000.0,
    "m³/h":   1.0 / 3600.0,
    "m³/s":   1.0,
    "US gpm": 6.30902e-5,
}

LENGTH_UNITS: dict[str, float] = {
    "m":   1.0,
    "mm":  0.001,
    "ft":  0.3048,
    "in":  0.0254,
}

VELOCITY_UNITS: dict[str, float] = {
    "m/s":  1.0,
    "ft/s": 0.3048,
}

# ── Decimal places for spinboxes and labels ────────────────────────────────

PRESSURE_DECIMALS: dict[str, int] = {
    "bar": 3, "psi": 2, "kPa": 1, "MPa": 4,
}
FLOW_DECIMALS: dict[str, int] = {
    "L/min": 1, "m³/h": 3, "m³/s": 5, "US gpm": 1,
}
LENGTH_DECIMALS: dict[str, int] = {
    "m": 4, "mm": 1, "ft": 3, "in": 3,
}
VELOCITY_DECIMALS: dict[str, int] = {
    "m/s": 3, "ft/s": 2,
}

# Result label decimal places (slightly less than spinbox)
PRESSURE_RESULT_DEC: dict[str, int] = {
    "bar": 4, "psi": 2, "kPa": 1, "MPa": 5,
}
FLOW_RESULT_DEC: dict[str, int] = {
    "L/min": 1, "m³/h": 2, "m³/s": 5, "US gpm": 1,
}

# ── Single-step increments for spinboxes ──────────────────────────────────

PRESSURE_STEP: dict[str, float] = {
    "bar": 0.1, "psi": 1.0, "kPa": 10.0, "MPa": 0.01,
}
FLOW_STEP: dict[str, float] = {
    "L/min": 1.0, "m³/h": 0.1, "m³/s": 0.001, "US gpm": 1.0,
}
LENGTH_STEP: dict[str, float] = {
    "m": 0.001, "mm": 0.5, "ft": 0.01, "in": 0.1,
}
VELOCITY_STEP: dict[str, float] = {
    "m/s": 0.1, "ft/s": 0.5,
}


class UnitPrefs:
    """Mutable singleton for the user's chosen display units."""

    def __init__(self):
        self.pressure: str = "bar"
        self.flow:     str = "L/min"
        self.length:   str = "m"
        self.velocity: str = "m/s"

    # ── Convert FROM SI to display unit ───────────────────────────────────

    def p(self, bar: float | None) -> float:
        """bar → display pressure unit."""
        if bar is None:
            return 0.0
        return bar / PRESSURE_UNITS[self.pressure]

    def q(self, m3s: float | None) -> float:
        """m³/s → display flow unit."""
        if m3s is None:
            return 0.0
        return m3s / FLOW_UNITS[self.flow]

    def l(self, m: float | None) -> float:
        """m → display length unit."""
        if m is None:
            return 0.0
        return m / LENGTH_UNITS[self.length]

    def v(self, ms: float | None) -> float:
        """m/s → display velocity unit."""
        if ms is None:
            return 0.0
        return ms / VELOCITY_UNITS[self.velocity]

    # ── Convert FROM display unit TO SI ───────────────────────────────────

    def p_to_si(self, val: float) -> float:
        return val * PRESSURE_UNITS[self.pressure]

    def q_to_si(self, val: float) -> float:
        return val * FLOW_UNITS[self.flow]

    def l_to_si(self, val: float) -> float:
        return val * LENGTH_UNITS[self.length]

    def v_to_si(self, val: float) -> float:
        return val * VELOCITY_UNITS[self.velocity]

    # ── Convenience: scale factor SI→display ─────────────────────────────

    def l_factor(self) -> float:
        """How many display length units per SI metre."""
        return 1.0 / LENGTH_UNITS[self.length]


# Module-level singleton — import and use UNITS directly
UNITS = UnitPrefs()
