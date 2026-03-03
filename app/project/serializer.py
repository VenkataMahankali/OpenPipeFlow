"""
OpenPipeFlow — Save/load .opf JSON project files.
"""

import json
from pathlib import Path
from typing import Any

from app.project.model import (
    NetworkModel, NodeData, PipeData, ValveData, PumpData
)
import app.project.id_generator as id_gen

OPF_VERSION = "1.0"


def save_project(model: NetworkModel, filepath: str,
                 canvas_state: dict | None = None) -> None:
    """Serialise *model* (and optional canvas view state) to a .opf file."""
    data: dict[str, Any] = {
        "version":      OPF_VERSION,
        "fluid":        model.fluid_name,
        "unit_system":  model.unit_system,
        "notes":        model.notes,
        "id_counters":  id_gen.save_state(),
        "nodes":        [_node_to_dict(n) for n in model.nodes.values()],
        "pipes":        [_pipe_to_dict(p) for p in model.pipes.values()],
        "valves":       [_valve_to_dict(v) for v in model.valves.values()],
        "pumps":        [_pump_to_dict(p) for p in model.pumps.values()],
        "canvas":       canvas_state or {},
    }
    Path(filepath).write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def load_project(filepath: str) -> tuple[NetworkModel, dict]:
    """
    Load a .opf file.
    Returns (NetworkModel, canvas_state_dict).
    """
    raw = json.loads(Path(filepath).read_text(encoding="utf-8"))
    model = NetworkModel()
    model.fluid_name  = raw.get("fluid", "water")
    model.unit_system = raw.get("unit_system", "SI")
    model.notes       = raw.get("notes", "")

    for n in raw.get("nodes", []):
        model.nodes[n["id"]] = _dict_to_node(n)
    for p in raw.get("pipes", []):
        model.pipes[p["id"]] = _dict_to_pipe(p)
    for v in raw.get("valves", []):
        model.valves[v["id"]] = _dict_to_valve(v)
    for p in raw.get("pumps", []):
        model.pumps[p["id"]] = _dict_to_pump(p)

    if "id_counters" in raw:
        id_gen.load_state(raw["id_counters"])

    return model, raw.get("canvas", {})


# ---------------------------------------------------------------------------
# Node helpers
# ---------------------------------------------------------------------------

def _node_to_dict(n: NodeData) -> dict:
    return {
        "id": n.id, "name": n.name, "node_type": n.node_type,
        "x": n.x, "y": n.y, "elevation_m": n.elevation_m,
        "pressure_bar": n.pressure_bar,
        "host_pipe_id": n.host_pipe_id,
        "alarm_min_pressure_bar": n.alarm_min_pressure_bar,
        "alarm_max_pressure_bar": n.alarm_max_pressure_bar,
        "notes": n.notes,
    }


def _dict_to_node(d: dict) -> NodeData:
    return NodeData(
        id=d["id"], name=d["name"], node_type=d["node_type"],
        x=d.get("x", 0.0), y=d.get("y", 0.0),
        elevation_m=d.get("elevation_m", 0.0),
        pressure_bar=d.get("pressure_bar", 1.0),
        host_pipe_id=d.get("host_pipe_id"),
        alarm_min_pressure_bar=d.get("alarm_min_pressure_bar"),
        alarm_max_pressure_bar=d.get("alarm_max_pressure_bar"),
        notes=d.get("notes", ""),
    )


# ---------------------------------------------------------------------------
# Pipe helpers
# ---------------------------------------------------------------------------

def _pipe_to_dict(p: PipeData) -> dict:
    return {
        "id": p.id, "name": p.name, "pipe_type": p.pipe_type,
        "start_node_id": p.start_node_id, "end_node_id": p.end_node_id,
        "length_m": p.length_m, "diameter_m": p.diameter_m,
        "roughness_mm": p.roughness_mm,
        "cross_section": p.cross_section,
        "width_m": p.width_m, "height_m": p.height_m,
        "material": p.material, "notes": p.notes,
        "inlet_diameter_m": p.inlet_diameter_m,
        "outlet_diameter_m": p.outlet_diameter_m,
        "angle_deg": p.angle_deg, "k_factor": p.k_factor,
        "alarm_max_velocity_ms": p.alarm_max_velocity_ms,
        "alarm_max_delta_p_bar": p.alarm_max_delta_p_bar,
    }


def _dict_to_pipe(d: dict) -> PipeData:
    return PipeData(
        id=d["id"], name=d["name"],
        pipe_type=d.get("pipe_type", "pipe"),
        start_node_id=d["start_node_id"], end_node_id=d["end_node_id"],
        length_m=d.get("length_m", 10.0),
        diameter_m=d.get("diameter_m", 0.1),
        roughness_mm=d.get("roughness_mm", 0.045),
        cross_section=d.get("cross_section", "circular"),
        width_m=d.get("width_m", 0.1), height_m=d.get("height_m", 0.1),
        material=d.get("material", "Steel"), notes=d.get("notes", ""),
        inlet_diameter_m=d.get("inlet_diameter_m", 0.1),
        outlet_diameter_m=d.get("outlet_diameter_m", 0.05),
        angle_deg=d.get("angle_deg", 10.0),
        k_factor=d.get("k_factor", 0.0),
        alarm_max_velocity_ms=d.get("alarm_max_velocity_ms"),
        alarm_max_delta_p_bar=d.get("alarm_max_delta_p_bar"),
    )


# ---------------------------------------------------------------------------
# Valve helpers
# ---------------------------------------------------------------------------

def _valve_to_dict(v: ValveData) -> dict:
    return {
        "id": v.id, "name": v.name,
        "start_node_id": v.start_node_id, "end_node_id": v.end_node_id,
        "valve_type": v.valve_type, "k_factor": v.k_factor,
        "open_pct": v.open_pct, "diameter_m": v.diameter_m,
        "length_m": v.length_m, "notes": v.notes,
        "alarm_max_delta_p_bar": v.alarm_max_delta_p_bar,
    }


def _dict_to_valve(d: dict) -> ValveData:
    return ValveData(
        id=d["id"], name=d["name"],
        start_node_id=d["start_node_id"], end_node_id=d["end_node_id"],
        valve_type=d.get("valve_type", "gate"),
        k_factor=d.get("k_factor", 0.5),
        open_pct=d.get("open_pct", 100.0),
        diameter_m=d.get("diameter_m", 0.1),
        length_m=d.get("length_m", 0.5),
        notes=d.get("notes", ""),
        alarm_max_delta_p_bar=d.get("alarm_max_delta_p_bar"),
    )


# ---------------------------------------------------------------------------
# Pump helpers
# ---------------------------------------------------------------------------

def _pump_to_dict(p: PumpData) -> dict:
    return {
        "id": p.id, "name": p.name,
        "start_node_id": p.start_node_id, "end_node_id": p.end_node_id,
        "curve_points": p.curve_points,
        "speed_rpm": p.speed_rpm,
        "diameter_m": p.diameter_m, "length_m": p.length_m,
        "on_off": p.on_off, "notes": p.notes,
    }


def _dict_to_pump(d: dict) -> PumpData:
    return PumpData(
        id=d["id"], name=d["name"],
        start_node_id=d["start_node_id"], end_node_id=d["end_node_id"],
        curve_points=[tuple(pt) for pt in d.get("curve_points", [])],
        speed_rpm=d.get("speed_rpm", 1450.0),
        diameter_m=d.get("diameter_m", 0.1),
        length_m=d.get("length_m", 0.5),
        on_off=d.get("on_off", True),
        notes=d.get("notes", ""),
    )
