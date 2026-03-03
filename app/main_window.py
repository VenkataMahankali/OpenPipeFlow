"""
OpenPipeFlow — MainWindow: top-level window assembling all panels.

Layout:
  Left dock  — PID panel (collapsible)
  Centre     — pipe network canvas
  Right dock — Properties panel
  Bottom dock — Results panel
  Top        — menu bar + toolbar
"""

from __future__ import annotations
import os
from PyQt6.QtWidgets import (
    QMainWindow, QDockWidget, QToolBar, QStatusBar,
    QMessageBox, QFileDialog, QLabel, QWidget, QSizePolicy, QComboBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot, QSize
from PyQt6.QtGui import QAction, QKeySequence, QIcon, QColor

from app.canvas.scene        import PipeNetworkScene, PipeNetworkView
from app.panels.properties_panel  import PropertiesPanel
from app.panels.results_panel     import ResultsPanel
from app.panels.pid_panel         import PIDPanel
from app.panels.resistance_diagram import ResistanceDiagramDialog
from app.project.model           import NetworkModel
from app.project                 import serializer, id_generator
from app.physics.network_bridge  import solve_network, SolverError
from app.utils.styles            import DARK_THEME_QSS, COLOR


# Recent files list — stored in a simple text file next to the exe
_RECENT_FILE = os.path.join(
    os.path.expanduser("~"), ".openpipeflow_recent.txt"
)
MAX_RECENT = 5


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("OpenPipeFlow")
        self.resize(1400, 900)
        self.setStyleSheet(DARK_THEME_QSS)

        # ── Data model ────────────────────────────────────────────────────
        self._model    = NetworkModel()
        self._filepath: str | None = None
        self._modified = False

        # ── Canvas ────────────────────────────────────────────────────────
        self._scene = PipeNetworkScene(self._model)
        self._view  = PipeNetworkView(self._scene)
        self.setCentralWidget(self._view)

        # ── Panels ────────────────────────────────────────────────────────
        self._props_panel   = PropertiesPanel(self._model)
        self._results_panel = ResultsPanel(self._model)
        self._pid_panel     = PIDPanel(self._model)

        self._setup_docks()

        # ── Toolbar + menus ───────────────────────────────────────────────
        self._setup_toolbar()
        self._setup_menus()

        # ── Status bar ────────────────────────────────────────────────────
        self._sb = QStatusBar()
        self.setStatusBar(self._sb)
        self._solver_lbl = QLabel("Solver: idle")
        self._solver_lbl.setStyleSheet(f"color: {COLOR['text_dim']}; padding: 0 6px;")
        self._sb.addPermanentWidget(self._solver_lbl)

        # ── Solver debounce timer ─────────────────────────────────────────
        from app.utils.constants import SOLVER_DEBOUNCE_MS
        self._solve_timer = QTimer(self)
        self._solve_timer.setSingleShot(True)
        self._solve_timer.setInterval(SOLVER_DEBOUNCE_MS)
        self._solve_timer.timeout.connect(self._run_solver)

        # ── Wire up signals ───────────────────────────────────────────────
        self._scene.network_changed.connect(self._on_network_changed)
        self._scene.element_selected.connect(self._on_element_selected)
        self._scene.element_double_clicked.connect(self._on_element_selected)
        self._scene.status_message.connect(self._sb.showMessage)

        self._props_panel.properties_changed.connect(self._on_properties_changed)
        self._pid_panel.global_settings_changed.connect(self._on_network_changed)
        self._pid_panel.element_selected.connect(self._on_pid_element_selected)
        self._pid_panel.system_off_requested.connect(self._system_off)

        self._results_panel.element_selected.connect(self._on_results_element_selected)

        # ── Recent files menu ─────────────────────────────────────────────
        self._recent_paths: list[str] = self._load_recent()
        self._update_recent_menu()

        self._sb.showMessage("Welcome to OpenPipeFlow — draw your network to begin.")

    # ── Dock setup ────────────────────────────────────────────────────────

    def _setup_docks(self):
        # Properties dock (right)
        self._props_dock = QDockWidget("Properties", self)
        self._props_dock.setWidget(self._props_panel)
        self._props_dock.setMinimumWidth(250)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea,
                           self._props_dock)

        # PID panel dock (left)
        self._pid_dock = QDockWidget("P&ID Control Panel", self)
        self._pid_dock.setWidget(self._pid_panel)
        self._pid_dock.setMinimumWidth(260)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea,
                           self._pid_dock)

        # Results dock (bottom)
        self._results_dock = QDockWidget("Results", self)
        self._results_dock.setWidget(self._results_panel)
        self._results_dock.setMinimumHeight(140)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea,
                           self._results_dock)

    # ── Toolbar ───────────────────────────────────────────────────────────

    def _setup_toolbar(self):
        tb = QToolBar("Tools")
        tb.setMovable(False)
        tb.setIconSize(QSize(20, 20))
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb)

        def make_action(label, shortcut, mode_or_slot, checkable=False):
            act = QAction(label, self)
            if shortcut:
                act.setShortcut(QKeySequence(shortcut))
            act.setCheckable(checkable)
            if isinstance(mode_or_slot, str):
                mode = mode_or_slot
                act.triggered.connect(lambda: self._set_mode(mode))
            else:
                act.triggered.connect(mode_or_slot)
            return act

        self._act_select   = make_action("Select",    "S", "select",       True)
        self._act_junction = make_action("Junction",  "J", "add_junction", True)
        self._act_source   = make_action("Source",    "R", "add_source",   True)
        self._act_sink     = make_action("Sink",      "K", "add_sink",     True)
        self._act_pipe     = make_action("Pipe",      "P", "add_pipe",     True)
        self._act_valve    = make_action("Valve",     "V", "add_valve",    True)
        self._act_pump     = make_action("Pump",      "U", "add_pump",     True)
        self._act_orifice  = make_action("Orifice",   "O", "add_orifice",  True)

        self._mode_actions = [
            self._act_select, self._act_junction, self._act_source,
            self._act_sink, self._act_pipe, self._act_valve,
            self._act_pump, self._act_orifice,
        ]

        tb.addActions([self._act_select, self._act_junction,
                       self._act_source, self._act_sink])
        tb.addSeparator()
        tb.addActions([self._act_pipe, self._act_valve,
                       self._act_pump, self._act_orifice])
        tb.addSeparator()

        # Solve button
        act_solve = QAction("Solve", self)
        act_solve.setShortcut(QKeySequence("F5"))
        act_solve.triggered.connect(self._run_solver)
        tb.addAction(act_solve)

        # Resistance diagram
        act_rdiag = QAction("R-Diagram", self)
        act_rdiag.setShortcut(QKeySequence("F6"))
        act_rdiag.triggered.connect(self._show_resistance_diagram)
        tb.addAction(act_rdiag)

        # Grid toggle
        self._act_grid = QAction("Grid", self)
        self._act_grid.setCheckable(True)
        self._act_grid.setChecked(True)
        self._act_grid.triggered.connect(
            lambda v: self._scene.toggle_grid(v))
        tb.addAction(self._act_grid)

        # Snap toggle
        self._act_snap = QAction("Snap", self)
        self._act_snap.setCheckable(True)
        self._act_snap.setChecked(True)
        self._act_snap.triggered.connect(
            lambda v: self._scene.toggle_snap(v))
        tb.addAction(self._act_snap)

        # Start in select mode
        self._act_select.setChecked(True)

        # ── Units toolbar ─────────────────────────────────────────────────
        self._setup_units_toolbar()

    def _setup_units_toolbar(self):
        from app.utils.units import UNITS, PRESSURE_UNITS, FLOW_UNITS, LENGTH_UNITS, VELOCITY_UNITS
        utb = QToolBar("Units")
        utb.setMovable(False)
        utb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, utb)

        def _unit_combo(choices, current, width, unit_type):
            cb = QComboBox()
            cb.addItems(list(choices.keys()))
            cb.setCurrentText(current)
            cb.setMaximumWidth(width)
            cb.setStyleSheet("font-size: 11px;")
            cb.currentTextChanged.connect(
                lambda t, ut=unit_type: self._on_unit_changed(ut, t))
            return cb

        utb.addWidget(QLabel("  Units — P:"))
        utb.addWidget(_unit_combo(PRESSURE_UNITS, UNITS.pressure, 55, "pressure"))
        utb.addWidget(QLabel("  Q:"))
        utb.addWidget(_unit_combo(FLOW_UNITS,     UNITS.flow,     75, "flow"))
        utb.addWidget(QLabel("  L:"))
        utb.addWidget(_unit_combo(LENGTH_UNITS,   UNITS.length,   50, "length"))
        utb.addWidget(QLabel("  V:"))
        utb.addWidget(_unit_combo(VELOCITY_UNITS, UNITS.velocity, 60, "velocity"))

    def _on_unit_changed(self, unit_type: str, value: str):
        from app.utils.units import UNITS
        setattr(UNITS, unit_type, value)
        self._props_panel.refresh()
        self._scene.update()   # repaint canvas labels in new units

    def _set_mode(self, mode: str):
        for act in self._mode_actions:
            act.setChecked(False)
        mode_to_action = {
            "select":       self._act_select,
            "add_junction": self._act_junction,
            "add_source":   self._act_source,
            "add_sink":     self._act_sink,
            "add_pipe":     self._act_pipe,
            "add_valve":    self._act_valve,
            "add_pump":     self._act_pump,
            "add_orifice":  self._act_orifice,
        }
        if mode in mode_to_action:
            mode_to_action[mode].setChecked(True)
        self._scene.set_mode(mode)

    # ── Menus ─────────────────────────────────────────────────────────────

    def _setup_menus(self):
        mb = self.menuBar()

        def act(label, slot, shortcut=None) -> QAction:
            a = QAction(label, self)
            a.triggered.connect(slot)
            if shortcut:
                a.setShortcut(shortcut)
            return a

        # File
        fm = mb.addMenu("&File")
        fm.addAction(act("&New Project",      self._new_project,
                         QKeySequence.StandardKey.New))
        fm.addAction(act("&Open Project…",    self._open_project,
                         QKeySequence.StandardKey.Open))
        fm.addAction(act("&Save Project",     self._save_project,
                         QKeySequence.StandardKey.Save))
        fm.addAction(act("Save Project &As…", self._save_project_as,
                         QKeySequence("Ctrl+Shift+S")))
        fm.addSeparator()
        fm.addAction(act("Export Results as CSV…", self._results_panel._export_csv))
        fm.addAction(act("Export Canvas as PNG…",  self._export_png))
        fm.addSeparator()
        self._recent_menu = fm.addMenu("Recent Files")
        fm.addSeparator()
        fm.addAction(act("E&xit", self.close,
                         QKeySequence.StandardKey.Quit))

        # Edit
        em = mb.addMenu("&Edit")
        em.addAction(act("Undo", self._scene.undo_stack.undo,
                         QKeySequence.StandardKey.Undo))
        em.addAction(act("Redo", self._scene.undo_stack.redo,
                         QKeySequence.StandardKey.Redo))
        em.addSeparator()
        em.addAction(act("Delete Selected", self._scene.delete_selected,
                         QKeySequence.StandardKey.Delete))
        em.addAction(act("Select All", self._select_all,
                         QKeySequence.StandardKey.SelectAll))

        # View
        vm = mb.addMenu("&View")
        vm.addAction(self._act_grid)
        vm.addAction(self._act_snap)
        vm.addSeparator()
        vm.addAction(act("Reset View", self._view.reset_view,
                         QKeySequence("Ctrl+0")))
        vm.addSeparator()
        vm.addAction(self._props_dock.toggleViewAction())
        vm.addAction(self._pid_dock.toggleViewAction())
        vm.addAction(self._results_dock.toggleViewAction())
        vm.addSeparator()
        vm.addAction(act("Resistance Diagram (F6)",
                         self._show_resistance_diagram,
                         QKeySequence("F6")))

        # Simulation
        sm = mb.addMenu("&Simulation")
        sm.addAction(act("&Solve (F5)", self._run_solver, QKeySequence("F5")))
        sm.addSeparator()
        sm.addAction(act("&Clear Results", self._clear_results))

        # Help
        hm = mb.addMenu("&Help")
        hm.addAction(act("About OpenPipeFlow", self._show_about))

    # ── Signal handlers ───────────────────────────────────────────────────

    def _on_network_changed(self):
        self._modified = True
        self._update_title()
        self._pid_panel.refresh()
        # Debounce solve
        self._solve_timer.start()

    def _on_properties_changed(self, element_id: str):
        self._modified = True
        self._update_title()
        self._solve_timer.start()

    def _on_element_selected(self, element_id: str):
        self._props_panel.show_element(element_id)
        if element_id:
            self._results_panel.highlight_element(element_id)

    def _on_pid_element_selected(self, element_id: str):
        self._scene.select_item(element_id)
        self._props_panel.show_element(element_id)

    def _on_results_element_selected(self, element_id: str):
        self._scene.select_item(element_id)
        self._props_panel.show_element(element_id)

    def _system_off(self):
        """Close all valves in the network."""
        for valve in self._model.valves.values():
            valve.open_pct = 0.0
        self._on_network_changed()

    # ── Solver ────────────────────────────────────────────────────────────

    @pyqtSlot()
    def _run_solver(self):
        self._solver_lbl.setText("Solver: running…")
        self._solver_lbl.setStyleSheet(
            f"color: {COLOR['warning']}; padding: 0 6px;")
        self.repaint()

        try:
            warnings = solve_network(self._model)
            self._scene.update_results()
            self._results_panel.refresh()
            self._pid_panel.refresh()
            self._props_panel.update_results()

            msg = "Solved OK"
            if warnings:
                msg += f" | {len(warnings)} warning(s)"
                self._sb.showMessage("; ".join(warnings), 8000)
            else:
                self._sb.showMessage("Network solved successfully.", 3000)

            self._solver_lbl.setText(f"Solver: {msg}")
            self._solver_lbl.setStyleSheet(
                f"color: {COLOR['accent']}; padding: 0 6px;")

        except SolverError as exc:
            self._solver_lbl.setText("Solver: incomplete")
            self._solver_lbl.setStyleSheet(
                f"color: {COLOR['warning']}; padding: 0 6px;")
            self._sb.showMessage(str(exc), 6000)

        except Exception as exc:
            self._solver_lbl.setText("Solver: ERROR")
            self._solver_lbl.setStyleSheet(
                f"color: {COLOR['alarm']}; padding: 0 6px;")
            self._sb.showMessage(f"Unexpected error: {exc}", 10000)

    def _clear_results(self):
        for el in self._model.all_elements():
            for attr in ("result_pressure_bar", "result_velocity_ms",
                         "result_flow_m3s", "result_mdot_kgs",
                         "result_p_from_bar", "result_p_to_bar",
                         "result_delta_p_bar", "result_reynolds",
                         "result_regime", "result_head_m"):
                if hasattr(el, attr):
                    setattr(el, attr, None)
        self._scene.update_results()
        self._results_panel.refresh()
        self._pid_panel.refresh()
        self._solver_lbl.setText("Solver: idle")
        self._solver_lbl.setStyleSheet(
            f"color: {COLOR['text_dim']}; padding: 0 6px;")

    # ── File operations ───────────────────────────────────────────────────

    def _new_project(self):
        if self._modified:
            if not self._confirm_discard():
                return
        self._model.clear()
        id_generator.reset()
        self._scene.rebuild_from_model()
        self._filepath = None
        self._modified = False
        self._update_title()
        self._pid_panel.refresh()
        self._results_panel.refresh()
        self._props_panel.show_element("")
        self._sb.showMessage("New project created.", 3000)

    def _open_project(self):
        if self._modified:
            if not self._confirm_discard():
                return
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", "",
            "OpenPipeFlow Projects (*.opf);;All Files (*)"
        )
        if path:
            self._load_file(path)

    def _load_file(self, path: str):
        try:
            canvas_state: dict
            self._model.clear()
            model, canvas_state = serializer.load_project(path)
            self._model.nodes  = model.nodes
            self._model.pipes  = model.pipes
            self._model.valves = model.valves
            self._model.pumps  = model.pumps
            self._model.fluid_name  = model.fluid_name
            self._model.unit_system = model.unit_system

            self._scene.rebuild_from_model()
            self._filepath = path
            self._modified = False
            self._update_title()
            self._pid_panel.refresh()
            self._results_panel.refresh()
            self._add_recent(path)
            self._sb.showMessage(f"Opened: {path}", 4000)
        except Exception as exc:
            QMessageBox.critical(self, "Open Failed",
                                 f"Could not open file:\n{exc}")

    def _save_project(self):
        if self._filepath is None:
            self._save_project_as()
        else:
            self._do_save(self._filepath)

    def _save_project_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Project As", "",
            "OpenPipeFlow Projects (*.opf);;All Files (*)"
        )
        if path:
            if not path.endswith(".opf"):
                path += ".opf"
            self._do_save(path)

    def _do_save(self, path: str):
        try:
            canvas_state = {
                "zoom": self._view._zoom_level,
            }
            serializer.save_project(self._model, path, canvas_state)
            self._filepath = path
            self._modified = False
            self._update_title()
            self._add_recent(path)
            self._sb.showMessage(f"Saved: {path}", 3000)
        except Exception as exc:
            QMessageBox.critical(self, "Save Failed",
                                 f"Could not save file:\n{exc}")

    def _export_png(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Canvas", "network.png",
            "PNG Images (*.png)"
        )
        if path:
            self._scene.export_png(path)
            self._sb.showMessage(f"Exported: {path}", 3000)

    # ── Recent files ──────────────────────────────────────────────────────

    def _load_recent(self) -> list[str]:
        try:
            if os.path.exists(_RECENT_FILE):
                lines = open(_RECENT_FILE).read().splitlines()
                return [l for l in lines if os.path.exists(l)][:MAX_RECENT]
        except Exception:
            pass
        return []

    def _add_recent(self, path: str):
        if path in self._recent_paths:
            self._recent_paths.remove(path)
        self._recent_paths.insert(0, path)
        self._recent_paths = self._recent_paths[:MAX_RECENT]
        try:
            open(_RECENT_FILE, "w").write("\n".join(self._recent_paths))
        except Exception:
            pass
        self._update_recent_menu()

    def _update_recent_menu(self):
        self._recent_menu.clear()
        for path in self._recent_paths:
            act = self._recent_menu.addAction(
                os.path.basename(path))
            act.setData(path)
            act.triggered.connect(
                lambda checked, p=path: self._load_file(p))
        if not self._recent_paths:
            self._recent_menu.addAction("(no recent files)").setEnabled(False)

    # ── Utility ───────────────────────────────────────────────────────────

    def _select_all(self):
        for item in self._scene.items():
            item.setSelected(True)

    def _update_title(self):
        name = (os.path.basename(self._filepath)
                if self._filepath else "Untitled")
        dirty = " *" if self._modified else ""
        self.setWindowTitle(f"OpenPipeFlow — {name}{dirty}")

    def _confirm_discard(self) -> bool:
        reply = QMessageBox.question(
            self, "Unsaved Changes",
            "You have unsaved changes. Discard them?",
            QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel
        )
        return reply == QMessageBox.StandardButton.Discard

    def _show_resistance_diagram(self):
        dlg = ResistanceDiagramDialog(self._model, self)
        dlg.show()   # non-modal — stays open while user works

    def _show_about(self):
        QMessageBox.about(
            self, "About OpenPipeFlow",
            "<h2>OpenPipeFlow v1.0</h2>"
            "<p>Free, open-source portable pipe network simulator.</p>"
            "<p><b>Original code:</b> MIT License</p>"
            "<hr>"
            "<p><b>Third-party components:</b></p>"
            "<ul>"
            "<li>Hydraulic solver: <b>pandapipes</b> (Fraunhofer IEE / "
            "University of Kassel) — BSD-3-Clause<br>"
            "<a href='https://github.com/e2nIEE/pandapipes'>"
            "github.com/e2nIEE/pandapipes</a></li>"
            "<li>GUI framework: <b>PyQt6</b> (Riverbank Computing) — GPL v3</li>"
            "<li>Numerics: <b>NumPy, SciPy</b> — BSD</li>"
            "</ul>"
        )

    def closeEvent(self, event):
        if self._modified:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "Save changes before closing?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel
            )
            if reply == QMessageBox.StandardButton.Save:
                self._save_project()
                event.accept()
            elif reply == QMessageBox.StandardButton.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
