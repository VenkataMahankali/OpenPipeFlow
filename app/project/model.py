"""
OpenPipeFlow — Network data model.

Provides lightweight dataclass-style objects for each network element.
The canvas items (QGraphicsItem subclasses) hold a reference to these
model objects; all physics/serialisation code works with the model layer.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Node types
# ---------------------------------------------------------------------------

@dataclass
class NodeData:
    """Base data for a node (junction, source, sink, measurement)."""
    id: str
    name: str
    node_type: str          # "junction" | "source" | "sink" | "measurement"
    x: float = 0.0          # canvas X position (scene coords)
    y: float = 0.0          # canvas Y position (scene coords)
    elevation_m: float = 0.0

    # Source / sink only
    pressure_bar: float = 1.0   # fixed pressure boundary condition

    # Measurement node only
    host_pipe_id: Optional[str] = None  # pipe this node sits on

    # Alarm thresholds (None = disabled)
    alarm_min_pressure_bar: Optional[float] = None
    alarm_max_pressure_bar: Optional[float] = None

    # Last solver result (updated in place after each solve)
    result_pressure_bar: Optional[float] = None

    notes: str = ""


# ---------------------------------------------------------------------------
# Edge / branch types
# ---------------------------------------------------------------------------

@dataclass
class PipeData:
    """Data for a pipe segment (or reducer/expander subtype)."""
    id: str
    name: str
    pipe_type: str          # "pipe" | "reducer" | "expander"
    start_node_id: str
    end_node_id: str

    # Geometry
    length_m: float = 10.0
    diameter_m: float = 0.1       # for circular cross-section
    roughness_mm: float = 0.045   # wall roughness in mm

    # Rectangular duct (pipe_type == "pipe" with cross_section == "rectangular")
    cross_section: str = "circular"   # "circular" | "rectangular"
    width_m: float = 0.1
    height_m: float = 0.1

    material: str = "Steel"
    notes: str = ""

    # Reducer / expander extras
    inlet_diameter_m: float = 0.1
    outlet_diameter_m: float = 0.05
    angle_deg: float = 10.0
    k_factor: float = 0.0         # additional minor loss

    # Alarm
    alarm_max_velocity_ms: Optional[float] = None
    alarm_max_delta_p_bar: Optional[float] = None

    # Solver results
    result_velocity_ms: Optional[float] = None
    result_flow_m3s: Optional[float] = None
    result_mdot_kgs: Optional[float] = None
    result_p_from_bar: Optional[float] = None
    result_p_to_bar: Optional[float] = None
    result_delta_p_bar: Optional[float] = None
    result_reynolds: Optional[float] = None
    result_regime: Optional[str] = None

    @property
    def hydraulic_diameter_m(self) -> float:
        """Hydraulic diameter for rectangular ducts: D_h = 4A / P."""
        if self.cross_section == "rectangular":
            A = self.width_m * self.height_m
            P = 2 * (self.width_m + self.height_m)
            return 4 * A / P if P > 0 else self.diameter_m
        return self.diameter_m


@dataclass
class ValveData:
    """Data for a valve element."""
    id: str
    name: str
    start_node_id: str
    end_node_id: str

    valve_type: str = "gate"   # "gate" | "ball" | "check" | "butterfly"
    k_factor: float = 0.5
    open_pct: float = 100.0    # 0 = closed, 100 = fully open
    diameter_m: float = 0.1
    length_m: float = 0.5      # physical length on canvas

    notes: str = ""
    alarm_max_delta_p_bar: Optional[float] = None

    # Flow coefficient (Cv in US gpm/psi^0.5; Kv in m³/h/bar^0.5)
    cv_usgpm: Optional[float] = None
    # Orifice-specific
    bore_diameter_m: Optional[float] = None   # bore / throat diameter
    cd: float = 0.61                           # discharge coefficient

    result_velocity_ms: Optional[float] = None
    result_flow_m3s: Optional[float] = None
    result_mdot_kgs: Optional[float] = None
    result_p_from_bar: Optional[float] = None
    result_p_to_bar: Optional[float] = None
    result_delta_p_bar: Optional[float] = None
    result_reynolds: Optional[float] = None
    result_regime: Optional[str] = None

    @property
    def is_open(self) -> bool:
        return self.open_pct > 0.0

    @property
    def effective_k(self) -> float:
        """K-factor adjusted for partial opening."""
        if self.open_pct <= 0.0:
            return 1e9   # effectively closed
        # Gate valve: K scales inversely with opening
        base_k = self.k_factor
        factor = 1.0 / max(self.open_pct / 100.0, 0.01) ** 2
        return base_k * factor


@dataclass
class PumpData:
    """Data for a pump (centrifugal or fixed-displacement)."""
    id: str
    name: str
    start_node_id: str
    end_node_id: str

    # Pump type
    pump_type: str = "centrifugal"   # "centrifugal" | "fixed_displacement"

    # Head-flow curve: list of (Q_m3s, H_m) tuples — used for centrifugal
    curve_points: list = field(default_factory=lambda: [
        (0.0, 30.0), (0.01, 28.0), (0.02, 24.0),
        (0.03, 18.0), (0.04, 10.0), (0.05, 0.0)
    ])

    # Fixed-displacement parameters (used when pump_type == "fixed_displacement")
    fixed_flow_m3s: float = 0.005   # setpoint volumetric flow (m³/s)
    fixed_head_m:   float = 50.0    # max head for synthetic H-Q curve (m)

    speed_rpm: float = 1450.0
    diameter_m: float = 0.1
    length_m: float = 0.5

    on_off: bool = True   # True = running
    notes: str = ""

    result_velocity_ms: Optional[float] = None
    result_flow_m3s: Optional[float] = None
    result_mdot_kgs: Optional[float] = None
    result_head_m: Optional[float] = None
    result_p_from_bar: Optional[float] = None
    result_p_to_bar: Optional[float] = None
    result_delta_p_bar: Optional[float] = None
    result_reynolds: Optional[float] = None
    result_regime: Optional[str] = None

    @property
    def max_head_m(self) -> float:
        if not self.curve_points:
            return 0.0
        return max(h for _, h in self.curve_points)

    @property
    def max_flow_m3s(self) -> float:
        if not self.curve_points:
            return 0.0
        return max(q for q, _ in self.curve_points)


# ---------------------------------------------------------------------------
# Network model container
# ---------------------------------------------------------------------------

class NetworkModel:
    """
    Top-level container for the entire pipe network.
    Provides dictionaries keyed by element ID for O(1) lookup.
    """

    def __init__(self):
        self.nodes:  dict[str, NodeData]  = {}
        self.pipes:  dict[str, PipeData]  = {}
        self.valves: dict[str, ValveData] = {}
        self.pumps:  dict[str, PumpData]  = {}

        self.fluid_name: str = "water"
        self.unit_system: str = "SI"     # "SI" | "Imperial"

        self.notes: str = ""

    # ---- Accessors -------------------------------------------------------

    def all_elements(self):
        """Yield every element across all types."""
        yield from self.nodes.values()
        yield from self.pipes.values()
        yield from self.valves.values()
        yield from self.pumps.values()

    def all_branch_elements(self):
        """Pipes, valves, and pumps (things that connect two nodes)."""
        yield from self.pipes.values()
        yield from self.valves.values()
        yield from self.pumps.values()

    def remove_node(self, node_id: str):
        """Remove a node and all branches that reference it."""
        self.nodes.pop(node_id, None)
        for d in [self.pipes, self.valves, self.pumps]:
            to_del = [eid for eid, el in d.items()
                      if el.start_node_id == node_id or el.end_node_id == node_id]
            for eid in to_del:
                d.pop(eid)

    def remove_branch(self, element_id: str):
        for d in [self.pipes, self.valves, self.pumps]:
            if element_id in d:
                d.pop(element_id)
                return

    def clear(self):
        self.nodes.clear()
        self.pipes.clear()
        self.valves.clear()
        self.pumps.clear()

    def has_sources(self) -> bool:
        return any(n.node_type == "source" for n in self.nodes.values())

    def has_sinks_or_multiple_sources(self) -> bool:
        sources = sum(1 for n in self.nodes.values() if n.node_type in ("source", "sink"))
        return sources >= 2

    def node_count(self) -> int:
        return len(self.nodes)

    def branch_count(self) -> int:
        return len(self.pipes) + len(self.valves) + len(self.pumps)
