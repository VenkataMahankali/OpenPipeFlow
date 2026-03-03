"""
OpenPipeFlow — ResultsPanel: dockable bottom table showing solver results.
"""

from __future__ import annotations
import csv
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QLabel, QHeaderView,
    QFileDialog, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QBrush, QFont

from app.project.model import NetworkModel
from app.utils.styles import COLOR


class ResultsPanel(QWidget):
    """Tabular display of all solver results."""

    # Emitted when a row is clicked (element_id)
    element_selected = pyqtSignal(str)

    HEADERS = [
        "Tag", "Name", "Type",
        "Flow Rate (L/min)", "Velocity (m/s)", "ΔP (bar)",
        "P_in (bar)", "P_out (bar)",
        "Reynolds", "Regime"
    ]
    _MONO = QFont("Consolas", 10)

    def __init__(self, model: NetworkModel, parent=None):
        super().__init__(parent)
        self._model = model
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Toolbar row
        bar = QHBoxLayout()
        self._status_lbl = QLabel("No results yet — run solver first.")
        self._status_lbl.setStyleSheet("color: #aab3be; font-size: 11px;")
        bar.addWidget(self._status_lbl)
        bar.addStretch()

        self._export_btn = QPushButton("Export CSV")
        self._export_btn.clicked.connect(self._export_csv)
        bar.addWidget(self._export_btn)
        layout.addLayout(bar)

        # Table
        self._table = QTableWidget(0, len(self.HEADERS))
        self._table.setHorizontalHeaderLabels(self.HEADERS)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSortingEnabled(True)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        self._table.verticalHeader().hide()
        self._table.itemSelectionChanged.connect(self._on_row_selected)
        layout.addWidget(self._table)

    # ── Public API ────────────────────────────────────────────────────────

    def refresh(self):
        """Repopulate the table from current model results."""
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)

        rows = []
        # Branch elements
        for branch_dict in (self._model.pipes, self._model.valves,
                             self._model.pumps):
            for eid, el in branch_dict.items():
                if el.result_velocity_ms is None:
                    continue
                q_lpm = (el.result_flow_m3s or 0.0) * 60000
                rows.append({
                    "id":      eid,
                    "tag":     eid,
                    "name":    el.name,
                    "type":    getattr(el, 'pipe_type',
                                       getattr(el, 'valve_type', 'pump')),
                    "flow":    f"{q_lpm:.2f}",
                    "vel":     f"{el.result_velocity_ms:.3f}",
                    "dp":      f"{el.result_delta_p_bar:.4f}"
                               if el.result_delta_p_bar is not None else "—",
                    "p_in":    f"{el.result_p_from_bar:.4f}"
                               if el.result_p_from_bar is not None else "—",
                    "p_out":   f"{el.result_p_to_bar:.4f}"
                               if el.result_p_to_bar is not None else "—",
                    "re":      f"{el.result_reynolds:.0f}"
                               if el.result_reynolds is not None else "—",
                    "regime":  el.result_regime or "—",
                    "alarm":   self._has_alarm(el),
                })

        # Node elements
        for nid, node in self._model.nodes.items():
            if node.result_pressure_bar is None:
                continue
            rows.append({
                "id":     nid,
                "tag":    nid,
                "name":   node.name,
                "type":   node.node_type,
                "flow":   "—",
                "vel":    "—",
                "dp":     "—",
                "p_in":   f"{node.result_pressure_bar:.4f}",
                "p_out":  "—",
                "re":     "—",
                "regime": "—",
                "alarm":  False,
            })

        self._table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            vals = [row["tag"], row["name"], row["type"],
                    row["flow"], row["vel"], row["dp"],
                    row["p_in"], row["p_out"], row["re"], row["regime"]]
            for c, v in enumerate(vals):
                item = QTableWidgetItem(v)
                item.setData(Qt.ItemDataRole.UserRole, row["id"])
                item.setFont(self._MONO)
                if row.get("alarm"):
                    item.setForeground(QBrush(QColor(COLOR["alarm"])))
                self._table.setItem(r, c, item)

        self._table.setSortingEnabled(True)
        n = len([r for r in rows if r["type"] not in
                 ("junction", "source", "sink", "measurement")])
        self._status_lbl.setText(
            f"Showing results for {n} pipe/valve/pump elements.")

    def highlight_element(self, element_id: str):
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == element_id:
                self._table.selectRow(row)
                self._table.scrollToItem(item)
                return

    # ── Signals ───────────────────────────────────────────────────────────

    def _on_row_selected(self):
        rows = self._table.selectedItems()
        if rows:
            eid = rows[0].data(Qt.ItemDataRole.UserRole)
            if eid:
                self.element_selected.emit(eid)

    # ── Export ────────────────────────────────────────────────────────────

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Results", "results.csv",
            "CSV Files (*.csv)"
        )
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(self.HEADERS)
            for row in range(self._table.rowCount()):
                writer.writerow(
                    [self._table.item(row, col).text() if self._table.item(row, col)
                     else "" for col in range(len(self.HEADERS))]
                )

    # ── Alarm helper ──────────────────────────────────────────────────────

    @staticmethod
    def _has_alarm(el) -> bool:
        v = getattr(el, 'result_velocity_ms', None)
        dp = getattr(el, 'result_delta_p_bar', None)
        if (v is not None
                and getattr(el, 'alarm_max_velocity_ms', None) is not None
                and v > el.alarm_max_velocity_ms):
            return True
        if (dp is not None
                and getattr(el, 'alarm_max_delta_p_bar', None) is not None
                and dp > el.alarm_max_delta_p_bar):
            return True
        return False
