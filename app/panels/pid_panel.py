"""
OpenPipeFlow — PIDPanel: dockable P&ID control tree panel.
Shows all network elements hierarchically with live values and
master controls (fluid selector, units toggle).
"""

from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget,
    QTreeWidgetItem, QComboBox, QPushButton, QGroupBox,
    QFormLayout, QCheckBox, QSizePolicy, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QBrush, QFont, QIcon

from app.project.model import NetworkModel
from app.physics.fluid_library import AVAILABLE_FLUIDS, get_fluid_display
from app.utils.styles import COLOR


class PIDPanel(QWidget):
    """
    Hierarchical P&ID panel with master controls and live element tree.
    """

    # Emitted when fluid or other global settings change
    global_settings_changed = pyqtSignal()
    # Emitted when element is clicked in the tree
    element_selected = pyqtSignal(str)
    # Emitted when user clicks "System Off" (close all valves)
    system_off_requested = pyqtSignal()

    _MONO = QFont("Consolas", 10)

    def __init__(self, model: NetworkModel, parent=None):
        super().__init__(parent)
        self._model = model
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # ── Master controls ────────────────────────────────────────────────
        master_grp = QGroupBox("Master Controls")
        mfl = QFormLayout(master_grp)

        self._fluid_combo = QComboBox()
        self._fluid_combo.addItems([
            get_fluid_display(f)["label"] for f in AVAILABLE_FLUIDS
        ])
        self._fluid_keys = AVAILABLE_FLUIDS
        current_idx = (AVAILABLE_FLUIDS.index(self._model.fluid_name)
                       if self._model.fluid_name in AVAILABLE_FLUIDS else 0)
        self._fluid_combo.setCurrentIndex(current_idx)
        self._fluid_combo.currentIndexChanged.connect(self._on_fluid_changed)
        mfl.addRow("Fluid:", self._fluid_combo)

        self._units_combo = QComboBox()
        self._units_combo.addItems(["SI", "Imperial"])
        self._units_combo.setCurrentText(self._model.unit_system)
        self._units_combo.currentTextChanged.connect(self._on_units_changed)
        mfl.addRow("Units:", self._units_combo)

        system_off_btn = QPushButton("System OFF (close valves)")
        system_off_btn.setStyleSheet(
            "background-color: #3a1a1a; border-color: #e74c3c; color: #e74c3c;"
        )
        system_off_btn.clicked.connect(self.system_off_requested)
        mfl.addRow("", system_off_btn)

        layout.addWidget(master_grp)

        # ── Fluid properties display ───────────────────────────────────────
        self._fluid_info_lbl = QLabel()
        self._fluid_info_lbl.setStyleSheet(
            "color: #aab3be; font-size: 11px; padding: 2px 4px;"
        )
        layout.addWidget(self._fluid_info_lbl)
        self._refresh_fluid_info()

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #1e2d3d;")
        layout.addWidget(sep)

        # ── Element tree ───────────────────────────────────────────────────
        tree_lbl = QLabel("NETWORK ELEMENTS")
        tree_lbl.setStyleSheet(
            "color: #00d4aa; font-weight: bold; font-size: 10px;"
            " letter-spacing: 1px;"
        )
        layout.addWidget(tree_lbl)

        self._tree = QTreeWidget()
        self._tree.setColumnCount(4)
        self._tree.setHeaderLabels(["Tag", "Type", "Key Value", "Status"])
        self._tree.setAlternatingRowColors(True)
        self._tree.header().setDefaultSectionSize(80)
        self._tree.itemClicked.connect(self._on_tree_item_clicked)
        layout.addWidget(self._tree)

    # ── Public API ────────────────────────────────────────────────────────

    def refresh(self):
        """Rebuild tree from model (call after solver or model change)."""
        self._tree.clear()
        model = self._model

        # ── Sources ────────────────────────────────────────────────────────
        sources_root = QTreeWidgetItem(self._tree, ["Sources", "", "", ""])
        self._style_root(sources_root, COLOR["node_source"])
        for nid, node in model.nodes.items():
            if node.node_type != "source":
                continue
            p = node.result_pressure_bar
            val = f"{p:.3f} bar" if p is not None else "—"
            st  = self._status_for_node(node)
            item = QTreeWidgetItem(sources_root,
                                   [node.name, "Source", val, st])
            item.setData(0, Qt.ItemDataRole.UserRole, nid)
            item.setFont(2, self._MONO)
            self._apply_status_color(item, st)

        # ── Sinks ──────────────────────────────────────────────────────────
        sinks_root = QTreeWidgetItem(self._tree, ["Sinks", "", "", ""])
        self._style_root(sinks_root, COLOR["node_sink"])
        for nid, node in model.nodes.items():
            if node.node_type != "sink":
                continue
            p = node.result_pressure_bar
            val = f"{p:.3f} bar" if p is not None else "—"
            st  = self._status_for_node(node)
            item = QTreeWidgetItem(sinks_root,
                                   [node.name, "Sink", val, st])
            item.setData(0, Qt.ItemDataRole.UserRole, nid)
            item.setFont(2, self._MONO)
            self._apply_status_color(item, st)

        # ── Junctions ──────────────────────────────────────────────────────
        junc_root = QTreeWidgetItem(self._tree, ["Junctions", "", "", ""])
        self._style_root(junc_root, COLOR["node_junction"])
        for nid, node in model.nodes.items():
            if node.node_type not in ("junction", "measurement"):
                continue
            p = node.result_pressure_bar
            val = f"{p:.3f} bar" if p is not None else "—"
            st  = self._status_for_node(node)
            item = QTreeWidgetItem(junc_root,
                                   [node.name, node.node_type.title(), val, st])
            item.setData(0, Qt.ItemDataRole.UserRole, nid)
            item.setFont(2, self._MONO)
            self._apply_status_color(item, st)

        # ── Pipes ──────────────────────────────────────────────────────────
        pipes_root = QTreeWidgetItem(self._tree, ["Pipes", "", "", ""])
        self._style_root(pipes_root, "#e8edf2")
        for pid, pipe in model.pipes.items():
            v   = pipe.result_velocity_ms
            val = f"{v:.2f} m/s" if v is not None else "—"
            st  = self._status_for_branch(pipe)
            item = QTreeWidgetItem(pipes_root,
                                   [pipe.name, pipe.pipe_type.title(), val, st])
            item.setData(0, Qt.ItemDataRole.UserRole, pid)
            item.setFont(2, self._MONO)
            self._apply_status_color(item, st)

        # ── Valves ─────────────────────────────────────────────────────────
        valve_root = QTreeWidgetItem(self._tree, ["Valves", "", "", ""])
        self._style_root(valve_root, COLOR["warning"])
        for vid, valve in model.valves.items():
            v   = valve.result_velocity_ms
            val = f"{v:.2f} m/s" if v is not None else "—"
            st  = "CLOSED" if valve.open_pct <= 0 else self._status_for_branch(valve)
            item = QTreeWidgetItem(valve_root,
                                   [valve.name, valve.valve_type.title(), val, st])
            item.setData(0, Qt.ItemDataRole.UserRole, vid)
            item.setFont(2, self._MONO)
            self._apply_status_color(item, st)

        # ── Pumps ──────────────────────────────────────────────────────────
        pump_root = QTreeWidgetItem(self._tree, ["Pumps", "", "", ""])
        self._style_root(pump_root, COLOR["accent"])
        for pump_id, pump in model.pumps.items():
            v   = pump.result_flow_m3s
            val = f"{v*60000:.2f} L/min" if v is not None else "—"
            st  = "OFF" if not pump.on_off else self._status_for_branch(pump)
            item = QTreeWidgetItem(pump_root,
                                   [pump.name, "Pump", val, st])
            item.setData(0, Qt.ItemDataRole.UserRole, pump_id)
            item.setFont(2, self._MONO)
            self._apply_status_color(item, st)

        self._tree.expandAll()
        for i in range(4):
            self._tree.resizeColumnToContents(i)

    # ── Master control handlers ───────────────────────────────────────────

    def _on_fluid_changed(self, idx: int):
        key = self._fluid_keys[idx]
        self._model.fluid_name = key
        self._refresh_fluid_info()
        self.global_settings_changed.emit()

    def _on_units_changed(self, text: str):
        self._model.unit_system = text
        self.global_settings_changed.emit()

    def _refresh_fluid_info(self):
        info = get_fluid_display(self._model.fluid_name)
        self._fluid_info_lbl.setText(
            f"ρ = {info['density_kg_m3']:.1f} kg/m³  |  "
            f"μ = {info['viscosity_pa_s']:.4e} Pa·s"
        )

    def _on_tree_item_clicked(self, item: QTreeWidgetItem, col: int):
        eid = item.data(0, Qt.ItemDataRole.UserRole)
        if eid:
            self.element_selected.emit(eid)

    # ── Styling helpers ───────────────────────────────────────────────────

    @staticmethod
    def _style_root(item: QTreeWidgetItem, colour: str):
        item.setForeground(0, QBrush(QColor(colour)))
        f = item.font(0)
        f.setBold(True)
        item.setFont(0, f)
        item.setExpanded(True)

    @staticmethod
    def _apply_status_color(item: QTreeWidgetItem, status: str):
        colour = {
            "OK":     COLOR["accent"],
            "ALARM":  COLOR["alarm"],
            "WARN":   COLOR["warning"],
            "OFF":    "#888888",
            "CLOSED": "#e74c3c",
            "—":      "#555566",
        }.get(status, "#e8edf2")
        item.setForeground(3, QBrush(QColor(colour)))

    @staticmethod
    def _status_for_node(node) -> str:
        p = node.result_pressure_bar
        if p is None:
            return "—"
        if (node.alarm_min_pressure_bar is not None
                and p < node.alarm_min_pressure_bar):
            return "ALARM"
        if (node.alarm_max_pressure_bar is not None
                and p > node.alarm_max_pressure_bar):
            return "ALARM"
        return "OK"

    @staticmethod
    def _status_for_branch(el) -> str:
        v  = getattr(el, 'result_velocity_ms', None)
        dp = getattr(el, 'result_delta_p_bar', None)
        if v is None:
            return "—"
        if (getattr(el, 'alarm_max_velocity_ms', None) is not None
                and v > el.alarm_max_velocity_ms):
            return "ALARM"
        if (getattr(el, 'alarm_max_delta_p_bar', None) is not None
                and dp is not None
                and dp > el.alarm_max_delta_p_bar):
            return "ALARM"
        return "OK"
