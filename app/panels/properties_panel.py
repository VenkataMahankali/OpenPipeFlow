"""
OpenPipeFlow — PropertiesPanel: dockable panel for editing element parameters.

Sections per element type:
  Node     — tag, elevation, pressure (source/sink), alarm thresholds
  Pipe     — tag, DN/schedule preset, diameter, length, roughness, material, K
  Valve    — tag, type, Cv/Kv, K-factor, open%, diameter, bore (orifice), Cd
  Pump     — tag, type (centrifugal/fixed-displacement), on/off, curve/flow

All physical values are displayed in the user's chosen unit system via UNITS.
"""

from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QLineEdit, QDoubleSpinBox, QComboBox, QCheckBox, QGroupBox,
    QPushButton, QScrollArea, QSpinBox, QTableWidget,
    QTableWidgetItem, QSizePolicy, QFrame, QHeaderView
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont

from app.project.model import (
    NetworkModel, NodeData, PipeData, ValveData, PumpData
)
from app.utils.units import (
    UNITS,
    PRESSURE_DECIMALS, FLOW_DECIMALS, LENGTH_DECIMALS, VELOCITY_DECIMALS,
    PRESSURE_RESULT_DEC, FLOW_RESULT_DEC,
    PRESSURE_STEP, FLOW_STEP, LENGTH_STEP, VELOCITY_STEP,
)

# ---------------------------------------------------------------------------
# DN size presets (nominal diameter → inner diameter in metres)
# ---------------------------------------------------------------------------
DN_PRESETS: dict[str, float] = {
    "Custom":      0.0,
    "DN 15  (½\")":  0.01588,
    "DN 20  (¾\")":  0.02116,
    "DN 25  (1\")":  0.02664,
    "DN 32  (1¼\")": 0.03505,
    "DN 40  (1½\")": 0.04154,
    "DN 50  (2\")":  0.05252,
    "DN 65  (2½\")": 0.06858,
    "DN 80  (3\")":  0.07792,
    "DN 100 (4\")":  0.10226,
    "DN 125 (5\")":  0.12827,
    "DN 150 (6\")":  0.15412,
    "DN 200 (8\")":  0.20272,
    "DN 250 (10\")": 0.25450,
    "DN 300 (12\")": 0.30480,
    "DN 400 (16\")": 0.39624,
    "DN 500 (20\")": 0.49022,
}

# Material roughness presets (mm) — roughness is always shown in mm
MATERIAL_ROUGHNESS: dict[str, float] = {
    "Steel (commercial)":    0.045,
    "Steel (drawn)":         0.015,
    "Stainless steel":       0.015,
    "Cast iron":             0.26,
    "Galvanised iron":       0.15,
    "Concrete":              1.0,
    "PVC / Plastic":         0.0015,
    "Copper":                0.0015,
    "HDPE":                  0.007,
    "Custom":                0.045,
}

# Default K-factors for valve types
VALVE_K_DEFAULTS: dict[str, float] = {
    "gate":      0.1,
    "ball":      0.05,
    "butterfly": 0.3,
    "globe":     5.0,
    "check":     2.0,
    "orifice":   8.0,
}


# ---------------------------------------------------------------------------
# _NoScrollSpinBox — QDoubleSpinBox that never steals scroll events
# ---------------------------------------------------------------------------

class _NoScrollSpinBox(QDoubleSpinBox):
    """QDoubleSpinBox that ignores scroll wheel and selects all on focus."""

    def wheelEvent(self, event):
        event.ignore()  # Don't change value on scroll

    def focusInEvent(self, event):
        super().focusInEvent(event)
        QTimer.singleShot(0, self.selectAll)  # Select all text on click


class _SectionHeader(QLabel):
    def __init__(self, text, parent=None):
        super().__init__(text.upper(), parent)
        self.setStyleSheet(
            "color: #00d4aa; font-weight: bold; font-size: 9px;"
            " letter-spacing: 1px; padding: 5px 0 2px 0;"
        )


# ---------------------------------------------------------------------------
# PropertiesPanel
# ---------------------------------------------------------------------------

class PropertiesPanel(QWidget):
    """Shows editable properties for the selected element."""

    properties_changed = pyqtSignal(str)    # element_id

    def __init__(self, model: NetworkModel, parent=None):
        super().__init__(parent)
        self._model       = model
        self._current_id: str | None = None
        self._suppress_signals = False

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(2)

        self._title_label = QLabel("No selection")
        self._title_label.setStyleSheet(
            "font-size: 12px; font-weight: bold; color: #e8edf2;"
            " padding: 4px 0;"
        )
        self._title_label.setWordWrap(True)
        root.addWidget(self._title_label)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #1e2d3d;")
        root.addWidget(sep)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(2, 2, 2, 2)
        self._content_layout.setSpacing(4)
        self._content_layout.addStretch()
        scroll.setWidget(self._content)
        root.addWidget(scroll)

    # ── Public API ─────────────────────────────────────────────────────────

    def show_element(self, element_id: str):
        self._current_id = element_id
        self._clear_content()
        if not element_id:
            self._title_label.setText("No selection")
            return
        if element_id in self._model.nodes:
            self._show_node(self._model.nodes[element_id])
        elif element_id in self._model.pipes:
            self._show_pipe(self._model.pipes[element_id])
        elif element_id in self._model.valves:
            self._show_valve(self._model.valves[element_id])
        elif element_id in self._model.pumps:
            self._show_pump(self._model.pumps[element_id])
        else:
            self._title_label.setText("Unknown element")

    def update_results(self):
        """Refresh result fields without rebuilding the full form."""
        if self._current_id:
            self.show_element(self._current_id)

    def refresh(self):
        """Redisplay the current element — called when units change."""
        if self._current_id:
            self.show_element(self._current_id)

    # ── Clear ──────────────────────────────────────────────────────────────

    def _clear_content(self):
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    # ── Node editor ────────────────────────────────────────────────────────

    def _show_node(self, node: NodeData):
        type_labels = {
            "junction":    "Junction Node",
            "source":      "Pressure Source (fixed inlet)",
            "sink":        "Pressure Sink (fixed outlet)",
            "measurement": "Measurement Point",
        }
        self._title_label.setText(
            f"{type_labels.get(node.node_type, 'Node')}  |  {node.id}"
        )

        grp = self._group("Identification")
        fl = QFormLayout(grp)
        fl.setSpacing(5)
        name_e = QLineEdit(node.name)
        name_e.textChanged.connect(lambda t: self._update_node(node, name=t))
        fl.addRow("Tag / Name:", name_e)

        elev = self._elev_spin(node.elevation_m)
        elev.valueChanged.connect(
            lambda v: self._update_node(node, elevation_m=UNITS.l_to_si(v)))
        fl.addRow("Elevation:", elev)
        self._insert(grp)

        if node.node_type in ("source", "sink"):
            grp2 = self._group("Boundary Condition")
            fl2 = QFormLayout(grp2)
            fl2.setSpacing(5)
            p = self._p_spin(node.pressure_bar)
            p.valueChanged.connect(
                lambda v: self._update_node(node, pressure_bar=UNITS.p_to_si(v)))
            fl2.addRow("Fixed pressure:", p)
            self._insert(grp2)

        # Alarm thresholds
        grp3 = self._group("Alarm Thresholds")
        fl3 = QFormLayout(grp3)
        fl3.setSpacing(5)
        mn = self._p_spin(node.alarm_min_pressure_bar or 0.0)
        mn.valueChanged.connect(
            lambda v: self._update_node(
                node, alarm_min_pressure_bar=None if v == 0 else UNITS.p_to_si(v)))
        fl3.addRow("Min pressure:", mn)
        mx = self._p_spin(node.alarm_max_pressure_bar or 0.0)
        mx.valueChanged.connect(
            lambda v: self._update_node(
                node, alarm_max_pressure_bar=None if v == 0 else UNITS.p_to_si(v)))
        fl3.addRow("Max pressure:", mx)
        self._insert(grp3)

        if node.result_pressure_bar is not None:
            rg = self._result_group()
            rl = QFormLayout(rg)
            rl.addRow("Pressure:", self._result_lbl(self._fmt_p(node.result_pressure_bar)))
            self._insert(rg)

        self._content_layout.addStretch()

    # ── Pipe editor ────────────────────────────────────────────────────────

    def _show_pipe(self, pipe: PipeData):
        self._title_label.setText(f"Pipe Segment  |  {pipe.id}")

        # Identification
        grp1 = self._group("Identification")
        fl1 = QFormLayout(grp1)
        fl1.setSpacing(5)
        name_e = QLineEdit(pipe.name)
        name_e.textChanged.connect(lambda t: self._update_pipe(pipe, name=t))
        fl1.addRow("Tag / Name:", name_e)
        self._insert(grp1)

        # Geometry — DN selector
        grp2 = self._group("Geometry")
        fl2 = QFormLayout(grp2)
        fl2.setSpacing(5)

        dn_box = QComboBox()
        dn_box.addItems(list(DN_PRESETS.keys()))
        dn_box.setCurrentIndex(0)
        fl2.addRow("DN / NPS:", dn_box)

        diam_spin = self._l_spin(pipe.diameter_m)
        fl2.addRow("Inner diameter:", diam_spin)

        def _on_dn_selected(txt):
            d = DN_PRESETS.get(txt, 0.0)
            if d > 0:
                self._suppress_signals = True
                diam_spin.setValue(UNITS.l(d))
                self._suppress_signals = False
                self._update_pipe(pipe, diameter_m=d)

        def _on_diam_changed(v):
            if not self._suppress_signals:
                self._update_pipe(pipe, diameter_m=UNITS.l_to_si(v))

        dn_box.currentTextChanged.connect(_on_dn_selected)
        diam_spin.valueChanged.connect(_on_diam_changed)

        length = self._plen_spin(pipe.length_m)
        length.valueChanged.connect(
            lambda v: self._update_pipe(pipe, length_m=UNITS.l_to_si(v)))
        fl2.addRow("Length:", length)

        self._insert(grp2)

        # Material / roughness (roughness always in mm)
        grp3 = self._group("Material & Roughness")
        fl3 = QFormLayout(grp3)
        fl3.setSpacing(5)

        mat_box = QComboBox()
        mat_box.addItems(list(MATERIAL_ROUGHNESS.keys()))
        mat_box.setEditable(True)
        if pipe.material in MATERIAL_ROUGHNESS:
            mat_box.setCurrentText(pipe.material)
        fl3.addRow("Material:", mat_box)

        rough_spin = self._dspin(0.0, 100.0, pipe.roughness_mm, "mm", 4)
        fl3.addRow("Roughness:", rough_spin)

        def _on_mat_selected(txt):
            r = MATERIAL_ROUGHNESS.get(txt)
            if r is not None:
                self._suppress_signals = True
                rough_spin.setValue(r)
                self._suppress_signals = False
                self._update_pipe(pipe, roughness_mm=r, material=txt)
            else:
                self._update_pipe(pipe, material=txt)

        def _on_rough_changed(v):
            if not self._suppress_signals:
                self._update_pipe(pipe, roughness_mm=v)

        mat_box.currentTextChanged.connect(_on_mat_selected)
        rough_spin.valueChanged.connect(_on_rough_changed)

        k = self._dspin(0.0, 10000, pipe.k_factor, "", 3)
        k.valueChanged.connect(lambda v: self._update_pipe(pipe, k_factor=v))
        fl3.addRow("Add. K-loss:", k)

        self._insert(grp3)

        # Results
        if pipe.result_velocity_ms is not None:
            rg = self._result_group()
            rl = QFormLayout(rg)
            rl.addRow("Velocity:",    self._result_lbl(self._fmt_v(pipe.result_velocity_ms)))
            if pipe.result_flow_m3s is not None:
                rl.addRow("Flow rate:",  self._result_lbl(self._fmt_q(pipe.result_flow_m3s)))
            if pipe.result_delta_p_bar is not None:
                rl.addRow("Pressure drop:", self._result_lbl(
                    self._fmt_p(pipe.result_delta_p_bar)))
            if pipe.result_reynolds is not None:
                rl.addRow("Reynolds:",  self._result_lbl(
                    f"{pipe.result_reynolds:.0f}  ({pipe.result_regime})"))
            self._insert(rg)

        self._content_layout.addStretch()

    # ── Valve editor ───────────────────────────────────────────────────────

    def _show_valve(self, valve: ValveData):
        is_orifice = (valve.valve_type == "orifice")
        prefix = "Orifice Plate" if is_orifice else "Valve"
        self._title_label.setText(f"{prefix}  |  {valve.id}")

        grp1 = self._group("Identification")
        fl1 = QFormLayout(grp1)
        fl1.setSpacing(5)
        name_e = QLineEdit(valve.name)
        name_e.textChanged.connect(lambda t: self._update_valve(valve, name=t))
        fl1.addRow("Tag / Name:", name_e)
        vtype_box = QComboBox()
        vtype_box.addItems(["gate", "ball", "check", "butterfly", "globe", "orifice"])
        vtype_box.setCurrentText(valve.valve_type)
        vtype_box.currentTextChanged.connect(
            lambda t: self._on_valve_type_changed(valve, t))
        fl1.addRow("Valve type:", vtype_box)
        self._insert(grp1)

        grp2 = self._group("Hydraulic Parameters")
        fl2 = QFormLayout(grp2)
        fl2.setSpacing(5)

        diam_spin = self._l_spin(valve.diameter_m)
        diam_spin.valueChanged.connect(
            lambda v: self._update_valve(valve, diameter_m=UNITS.l_to_si(v)))
        fl2.addRow("Line diameter:", diam_spin)

        if is_orifice:
            bore = valve.bore_diameter_m or valve.diameter_m * 0.5
            bore_spin = self._l_spin(bore)
            bore_spin.valueChanged.connect(
                lambda v: self._update_valve(valve, bore_diameter_m=UNITS.l_to_si(v)))
            fl2.addRow("Bore diameter:", bore_spin)

            cd_spin = self._dspin(0.1, 1.0, valve.cd, "", 3)
            cd_spin.valueChanged.connect(lambda v: self._update_valve(valve, cd=v))
            fl2.addRow("Cd (discharge):", cd_spin)

            if valve.bore_diameter_m and valve.diameter_m:
                beta = valve.bore_diameter_m / valve.diameter_m
                fl2.addRow("Beta ratio (d/D):", self._result_lbl(f"{beta:.3f}"))

            kf_spin = self._dspin(0.0, 100000, valve.k_factor, "", 3)
            kf_spin.valueChanged.connect(lambda v: self._update_valve(valve, k_factor=v))
            fl2.addRow("K-factor (override):", kf_spin)
        else:
            kf_spin = self._dspin(0.0, 100000, valve.k_factor, "", 3)
            kf_spin.valueChanged.connect(lambda v: self._update_valve(valve, k_factor=v))
            fl2.addRow("K-factor (fully open):", kf_spin)

            if valve.cv_usgpm is not None:
                fl2.addRow("Cv:", self._result_lbl(f"{valve.cv_usgpm:.1f} USgpm/psi½"))
                kv = valve.cv_usgpm * 0.8647
                fl2.addRow("Kv:", self._result_lbl(f"{kv:.2f} m³/h/bar½"))

            opct = self._dspin(0.0, 100.0, valve.open_pct, "%", 1)
            opct.setSingleStep(5.0)
            opct.valueChanged.connect(lambda v: self._update_valve(valve, open_pct=v))
            fl2.addRow("Open %:", opct)

            eff_k = valve.effective_k
            fl2.addRow("Effective K:", self._result_lbl(f"{eff_k:.2f}"))

        self._insert(grp2)

        # Results
        if valve.result_velocity_ms is not None:
            rg = self._result_group()
            rl = QFormLayout(rg)
            rl.addRow("Velocity:",     self._result_lbl(self._fmt_v(valve.result_velocity_ms)))
            if valve.result_flow_m3s is not None:
                rl.addRow("Flow rate:",    self._result_lbl(self._fmt_q(valve.result_flow_m3s)))
            if valve.result_delta_p_bar is not None:
                rl.addRow("Pressure drop:", self._result_lbl(
                    self._fmt_p(valve.result_delta_p_bar)))
            if valve.result_reynolds is not None:
                rl.addRow("Reynolds:",     self._result_lbl(
                    f"{valve.result_reynolds:.0f}  ({valve.result_regime})"))
            self._insert(rg)

        self._content_layout.addStretch()

    def _on_valve_type_changed(self, valve: ValveData, new_type: str):
        valve.valve_type = new_type
        default_k = VALVE_K_DEFAULTS.get(new_type, valve.k_factor)
        valve.k_factor = default_k
        self.properties_changed.emit(valve.id)
        self.show_element(valve.id)

    # ── Pump editor ────────────────────────────────────────────────────────

    def _show_pump(self, pump: PumpData):
        type_label = {
            "centrifugal":       "Centrifugal Pump",
            "fixed_displacement":"Fixed Displacement Pump",
        }.get(pump.pump_type, "Pump")
        self._title_label.setText(f"{type_label}  |  {pump.id}")

        # Identification + type
        grp1 = self._group("Identification")
        fl1 = QFormLayout(grp1)
        fl1.setSpacing(5)
        name_e = QLineEdit(pump.name)
        name_e.textChanged.connect(lambda t: self._update_pump(pump, name=t))
        fl1.addRow("Tag / Name:", name_e)

        ptype_box = QComboBox()
        ptype_box.addItems(["Centrifugal (H-Q curve)", "Fixed Displacement"])
        ptype_box.setCurrentIndex(0 if pump.pump_type == "centrifugal" else 1)
        ptype_box.currentIndexChanged.connect(
            lambda i: self._on_pump_type_changed(
                pump, "centrifugal" if i == 0 else "fixed_displacement"))
        fl1.addRow("Pump type:", ptype_box)
        self._insert(grp1)

        # Operating state
        grp2 = self._group("Operating State")
        fl2 = QFormLayout(grp2)
        fl2.setSpacing(5)
        on_off = QCheckBox("Running (ON)")
        on_off.setChecked(pump.on_off)
        on_off.toggled.connect(lambda v: self._update_pump(pump, on_off=v))
        fl2.addRow("State:", on_off)
        rpm = self._dspin(0, 10000, pump.speed_rpm, "RPM", 0)
        rpm.valueChanged.connect(lambda v: self._update_pump(pump, speed_rpm=v))
        fl2.addRow("Speed:", rpm)
        diam = self._l_spin(pump.diameter_m)
        diam.valueChanged.connect(
            lambda v: self._update_pump(pump, diameter_m=UNITS.l_to_si(v)))
        fl2.addRow("Nozzle diameter:", diam)
        self._insert(grp2)

        if pump.pump_type == "centrifugal":
            self._show_pump_hq_curve(pump)
        else:
            self._show_pump_fixed_displacement(pump)

        # Results
        if pump.result_flow_m3s is not None:
            rg = self._result_group()
            rl = QFormLayout(rg)
            rl.addRow("Flow rate:", self._result_lbl(self._fmt_q(pump.result_flow_m3s)))
            if pump.result_velocity_ms is not None:
                rl.addRow("Velocity:", self._result_lbl(self._fmt_v(pump.result_velocity_ms)))
            if pump.result_head_m is not None:
                dec = LENGTH_DECIMALS[UNITS.length]
                rl.addRow("Head delivered:", self._result_lbl(
                    f"{UNITS.l(pump.result_head_m):.{dec}f} {UNITS.length}"))
            if pump.result_p_from_bar is not None and pump.result_p_to_bar is not None:
                dp = pump.result_p_to_bar - pump.result_p_from_bar
                dec = PRESSURE_RESULT_DEC[UNITS.pressure]
                rl.addRow("Pressure gain:", self._result_lbl(
                    f"{UNITS.p(dp):+.{dec}f} {UNITS.pressure}"))
            self._insert(rg)

        self._content_layout.addStretch()

    def _show_pump_hq_curve(self, pump: PumpData):
        """Build the H-Q curve table section (centrifugal pumps)."""
        grp3 = self._group("Head-Flow Curve")
        v3 = QVBoxLayout(grp3)
        v3.setSpacing(3)
        note = QLabel(
            f"Q ({UNITS.flow}) vs H ({UNITS.length}) — edit cells then press Enter")
        note.setStyleSheet("color: #7f8fa6; font-size: 9px;")
        note.setWordWrap(True)
        v3.addWidget(note)

        dec_q = FLOW_DECIMALS[UNITS.flow]
        dec_h = LENGTH_DECIMALS[UNITS.length]

        tbl = QTableWidget(len(pump.curve_points), 2)
        tbl.setHorizontalHeaderLabels([f"Q ({UNITS.flow})", f"H ({UNITS.length})"])
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        tbl.verticalHeader().setVisible(False)
        tbl.setMaximumHeight(180)
        tbl.setMinimumHeight(80)
        for row, (q, h) in enumerate(pump.curve_points):
            tbl.setItem(row, 0, QTableWidgetItem(f"{UNITS.q(q):.{dec_q}f}"))
            tbl.setItem(row, 1, QTableWidgetItem(f"{UNITS.l(h):.{dec_h}f}"))

        def _curve_edited():
            pts = []
            for r in range(tbl.rowCount()):
                try:
                    q_disp = float(tbl.item(r, 0).text())
                    h_disp = float(tbl.item(r, 1).text())
                    pts.append((UNITS.q_to_si(q_disp), UNITS.l_to_si(h_disp)))
                except (ValueError, AttributeError):
                    pass
            pump.curve_points = sorted(pts, key=lambda p: p[0])
            self.properties_changed.emit(pump.id)

        tbl.cellChanged.connect(lambda *_: _curve_edited())
        v3.addWidget(tbl)

        btn_row = QWidget()
        bh = QHBoxLayout(btn_row)
        bh.setContentsMargins(0, 0, 0, 0)
        btn_add = QPushButton("+ Row")
        btn_add.setMaximumWidth(60)
        btn_del = QPushButton("- Row")
        btn_del.setMaximumWidth(60)

        def _add_row():
            tbl.blockSignals(True)
            r = tbl.rowCount()
            tbl.setRowCount(r + 1)
            tbl.setItem(r, 0, QTableWidgetItem("0.0000"))
            tbl.setItem(r, 1, QTableWidgetItem("0.00"))
            tbl.blockSignals(False)

        def _del_row():
            tbl.blockSignals(True)
            r = tbl.currentRow()
            if r >= 0 and tbl.rowCount() > 2:
                tbl.removeRow(r)
            tbl.blockSignals(False)
            _curve_edited()

        btn_add.clicked.connect(_add_row)
        btn_del.clicked.connect(_del_row)
        bh.addWidget(btn_add)
        bh.addWidget(btn_del)
        bh.addStretch()
        v3.addWidget(btn_row)
        self._insert(grp3)

    def _show_pump_fixed_displacement(self, pump: PumpData):
        """Build the fixed-flow section (fixed-displacement pumps)."""
        grp3 = self._group("Fixed Displacement Settings")
        fl3 = QFormLayout(grp3)
        fl3.setSpacing(5)

        note = QLabel(
            "Delivers a constant flow regardless of system pressure.")
        note.setStyleSheet("color: #7f8fa6; font-size: 9px;")
        note.setWordWrap(True)
        fl3.addRow(note)

        q_spin = self._q_spin(pump.fixed_flow_m3s)
        q_spin.valueChanged.connect(
            lambda v: self._update_pump(pump, fixed_flow_m3s=UNITS.q_to_si(v)))
        fl3.addRow("Fixed flow rate:", q_spin)

        h_spin = self._head_spin(pump.fixed_head_m)
        h_spin.valueChanged.connect(
            lambda v: self._update_pump(pump, fixed_head_m=UNITS.l_to_si(v)))
        fl3.addRow("Max head:", h_spin)

        self._insert(grp3)

    def _on_pump_type_changed(self, pump: PumpData, new_type: str):
        pump.pump_type = new_type
        self.properties_changed.emit(pump.id)
        self.show_element(pump.id)

    # ── Model update helpers ───────────────────────────────────────────────

    def _update_node(self, node: NodeData, **kw):
        for k, v in kw.items():
            setattr(node, k, v)
        self.properties_changed.emit(node.id)

    def _update_pipe(self, pipe: PipeData, **kw):
        for k, v in kw.items():
            setattr(pipe, k, v)
        self.properties_changed.emit(pipe.id)

    def _update_valve(self, valve: ValveData, **kw):
        for k, v in kw.items():
            setattr(valve, k, v)
        self.properties_changed.emit(valve.id)

    def _update_pump(self, pump: PumpData, **kw):
        for k, v in kw.items():
            setattr(pump, k, v)
        self.properties_changed.emit(pump.id)

    # ── Unit-aware spinbox factories ───────────────────────────────────────

    def _p_spin(self, si_bar) -> _NoScrollSpinBox:
        """Pressure spinbox in user's pressure unit."""
        sp = _NoScrollSpinBox()
        lo = 0.0
        hi = UNITS.p(1000.0)   # 1000 bar in display unit
        sp.setRange(lo, hi)
        sp.setDecimals(PRESSURE_DECIMALS[UNITS.pressure])
        sp.setSuffix(f" {UNITS.pressure}")
        sp.setValue(UNITS.p(float(si_bar) if si_bar is not None else 0.0))
        sp.setSingleStep(PRESSURE_STEP[UNITS.pressure])
        return sp

    def _l_spin(self, si_m, lo_m=0.001, hi_m=5.0) -> _NoScrollSpinBox:
        """Length/diameter spinbox in user's length unit."""
        f = UNITS.l_factor()
        sp = _NoScrollSpinBox()
        sp.setRange(lo_m * f, hi_m * f)
        sp.setDecimals(LENGTH_DECIMALS[UNITS.length])
        sp.setSuffix(f" {UNITS.length}")
        sp.setValue(UNITS.l(float(si_m) if si_m is not None else 0.0))
        sp.setSingleStep(LENGTH_STEP[UNITS.length])
        return sp

    def _plen_spin(self, si_m) -> _NoScrollSpinBox:
        """Pipe length spinbox (larger range than diameter)."""
        return self._l_spin(si_m, lo_m=0.01, hi_m=100_000.0)

    def _elev_spin(self, si_m) -> _NoScrollSpinBox:
        """Elevation spinbox (allows negative values)."""
        f = UNITS.l_factor()
        sp = _NoScrollSpinBox()
        sp.setRange(-1000.0 * f, 10_000.0 * f)
        sp.setDecimals(LENGTH_DECIMALS[UNITS.length])
        sp.setSuffix(f" {UNITS.length}")
        sp.setValue(UNITS.l(float(si_m) if si_m is not None else 0.0))
        sp.setSingleStep(LENGTH_STEP[UNITS.length] * 10)
        return sp

    def _q_spin(self, si_m3s) -> _NoScrollSpinBox:
        """Flow rate spinbox in user's flow unit."""
        sp = _NoScrollSpinBox()
        sp.setRange(0.0, UNITS.q(10.0))   # max 10 m³/s
        sp.setDecimals(FLOW_DECIMALS[UNITS.flow])
        sp.setSuffix(f" {UNITS.flow}")
        sp.setValue(UNITS.q(float(si_m3s) if si_m3s is not None else 0.0))
        sp.setSingleStep(FLOW_STEP[UNITS.flow])
        return sp

    def _head_spin(self, si_m) -> _NoScrollSpinBox:
        """Pump head spinbox (length unit, 0 to 10 000 m equiv)."""
        f = UNITS.l_factor()
        sp = _NoScrollSpinBox()
        sp.setRange(0.0, 10_000.0 * f)
        sp.setDecimals(LENGTH_DECIMALS[UNITS.length])
        sp.setSuffix(f" {UNITS.length}")
        sp.setValue(UNITS.l(float(si_m) if si_m is not None else 0.0))
        sp.setSingleStep(LENGTH_STEP[UNITS.length] * 100)
        return sp

    # ── Generic (non-unit) spinbox factory ────────────────────────────────

    @staticmethod
    def _dspin(mn, mx, val, suffix="", decimals=3) -> _NoScrollSpinBox:
        sp = _NoScrollSpinBox()
        sp.setRange(mn, mx)
        sp.setDecimals(decimals)
        if suffix:
            sp.setSuffix(f" {suffix}")
        sp.setValue(float(val) if val is not None else 0.0)
        sp.setSingleStep(0.001 if decimals >= 3 else 0.1)
        return sp

    # ── Unit-aware result string helpers ──────────────────────────────────

    def _fmt_p(self, si_bar: float | None) -> str:
        if si_bar is None:
            return "—"
        dec = PRESSURE_RESULT_DEC[UNITS.pressure]
        return f"{UNITS.p(si_bar):.{dec}f} {UNITS.pressure}"

    def _fmt_q(self, si_m3s: float | None) -> str:
        if si_m3s is None:
            return "—"
        dec = FLOW_RESULT_DEC[UNITS.flow]
        return f"{UNITS.q(si_m3s):.{dec}f} {UNITS.flow}"

    def _fmt_v(self, si_ms: float | None) -> str:
        if si_ms is None:
            return "—"
        dec = VELOCITY_DECIMALS[UNITS.velocity]
        return f"{UNITS.v(si_ms):.{dec}f} {UNITS.velocity}"

    # ── Widget helpers ────────────────────────────────────────────────────

    def _group(self, title: str) -> QGroupBox:
        grp = QGroupBox(title)
        grp.setStyleSheet(
            "QGroupBox { font-size: 9px; font-weight: bold; color: #00d4aa;"
            " border: 1px solid #1e2d3d; border-radius: 3px; margin-top: 6px;"
            " padding: 4px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 6px; top: -1px; }"
        )
        return grp

    def _result_group(self) -> QGroupBox:
        grp = QGroupBox("Solver Results")
        grp.setStyleSheet(
            "QGroupBox { font-size: 9px; font-weight: bold; color: #7ecfb0;"
            " border: 1px solid #0e2a20; border-radius: 3px; margin-top: 6px;"
            " padding: 4px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 6px; top: -1px; }"
        )
        return grp

    def _insert(self, widget: QWidget):
        """Insert widget before the trailing stretch."""
        pos = max(self._content_layout.count() - 1, 0)
        self._content_layout.insertWidget(pos, widget)

    @staticmethod
    def _result_lbl(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "font-family: 'Consolas', 'Courier New', monospace;"
            " color: #00d4aa; font-size: 11px;"
        )
        return lbl
