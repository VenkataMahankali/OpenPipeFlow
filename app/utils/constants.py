"""
OpenPipeFlow — Physical constants, defaults, and unit conversions.
All internal calculations use SI units.
"""

# ---------------------------------------------------------------------------
# Physical constants
# ---------------------------------------------------------------------------
GRAVITY = 9.81          # m/s²
WATER_DENSITY = 1000.0  # kg/m³ at 20°C
WATER_VISCOSITY = 0.001 # Pa·s (dynamic) at 20°C

# ---------------------------------------------------------------------------
# Default pipe parameters
# ---------------------------------------------------------------------------
DEFAULT_PIPE_DIAMETER_M    = 0.1       # 100 mm
DEFAULT_PIPE_LENGTH_M      = 10.0      # m
DEFAULT_PIPE_ROUGHNESS_MM  = 0.045     # mm — commercial steel
DEFAULT_PIPE_MATERIAL      = "Steel"

# ---------------------------------------------------------------------------
# Default node pressures
# ---------------------------------------------------------------------------
DEFAULT_SOURCE_PRESSURE_BAR = 3.0
DEFAULT_SINK_PRESSURE_BAR   = 1.0
DEFAULT_JUNCTION_PN_BAR     = 1.0     # nominal pressure for pandapipes junction
DEFAULT_T_K                 = 293.15  # 20°C in Kelvin

# ---------------------------------------------------------------------------
# Solver settings
# ---------------------------------------------------------------------------
MAX_SOLVER_ITERATIONS   = 500
CONVERGENCE_CRITERION   = 1e-6   # m³/s
SOLVER_DEBOUNCE_MS      = 400    # ms delay before auto-solve on change
SOLVER_TIMEOUT_MS       = 30_000 # kill solver thread after 30 s

# ---------------------------------------------------------------------------
# Unit conversion helpers
# ---------------------------------------------------------------------------
PA_TO_BAR    = 1e-5
BAR_TO_PA    = 1e5
PA_TO_PSI    = 1.0 / 6894.757
PSI_TO_PA    = 6894.757
M3S_TO_LPM   = 60_000.0   # m³/s  → L/min
LPM_TO_M3S   = 1.0 / 60_000.0
M3S_TO_M3H   = 3600.0
KG_TO_LB     = 2.20462

# ---------------------------------------------------------------------------
# Canvas rendering
# ---------------------------------------------------------------------------
GRID_SIZE_PX          = 20
MIN_ZOOM              = 0.05
MAX_ZOOM              = 20.0
NODE_RADIUS_PX        = 10
PIPE_WIDTH_PX         = 3
MEAS_NODE_RADIUS_PX   = 7
ANIMATION_FPS         = 30
ANIMATION_INTERVAL_MS = 1000 // ANIMATION_FPS

# Velocity thresholds for colour coding (m/s)
VEL_COLOUR_LOW    = 0.1   # below → blue
VEL_COLOUR_HIGH   = 3.0   # above → red

# ---------------------------------------------------------------------------
# Flow regime thresholds
# ---------------------------------------------------------------------------
RE_LAMINAR_MAX       = 2300
RE_TRANSITIONAL_MAX  = 4000

# ---------------------------------------------------------------------------
# ID prefixes
# ---------------------------------------------------------------------------
ID_PREFIX = {
    "junction":    "ND",
    "source":      "SRC",
    "sink":        "SNK",
    "measurement": "MSR",
    "pipe":        "PIPE",
    "valve":       "VLV",
    "pump":        "PMP",
    "reducer":     "RED",
    "expander":    "EXP",
    "orifice":     "ORI",
}
