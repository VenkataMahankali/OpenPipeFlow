"""
OpenPipeFlow — NodeItem: visual representation of a junction,
source, sink, or measurement node on the canvas.
"""

from __future__ import annotations
import math
from PyQt6.QtWidgets import QGraphicsItem, QMenu
from PyQt6.QtCore import Qt, QRectF, QPointF, QTimer
from PyQt6.QtGui import (QPainter, QPen, QBrush, QColor,
                          QPainterPath, QRadialGradient)
from app.utils.units import UNITS

from app.canvas.items.base_item import BaseItem
from app.utils.constants import NODE_RADIUS_PX, MEAS_NODE_RADIUS_PX
from app.utils.styles import COLOR


class NodeItem(BaseItem):
    """
    A node (junction / source / sink / measurement point) on the pipe canvas.

    Visual conventions:
      junction    — filled teal circle
      source      — filled green upward triangle (pressure inlet)
      sink        — filled red downward triangle (pressure outlet)
      measurement — amber circle with crosshair
    """

    def __init__(self, element_id: str, element_name: str,
                 node_type: str, parent=None):
        super().__init__(element_id, element_name, parent)
        self._node_type = node_type      # "junction"|"source"|"sink"|"measurement"
        self._result_pressure_bar: float | None = None
        self._connected_pipe_items: list = []   # PipeItem refs, updated by scene

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setZValue(10)  # nodes sit above pipes

    # ── Geometry ──────────────────────────────────────────────────────────

    @property
    def node_type(self) -> str:
        return self._node_type

    def _radius(self) -> float:
        return MEAS_NODE_RADIUS_PX if self._node_type == "measurement" \
               else NODE_RADIUS_PX

    def boundingRect(self) -> QRectF:
        r = self._radius() + 4   # include selection/label space
        return QRectF(-r, -r, r*2, r*2)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        r = self._radius() + 2
        path.addEllipse(QRectF(-r, -r, r*2, r*2))
        return path

    # ── Connected pipes ───────────────────────────────────────────────────

    def add_pipe(self, pipe_item) -> None:
        if pipe_item not in self._connected_pipe_items:
            self._connected_pipe_items.append(pipe_item)

    def remove_pipe(self, pipe_item) -> None:
        if pipe_item in self._connected_pipe_items:
            self._connected_pipe_items.remove(pipe_item)

    @property
    def connected_pipes(self) -> list:
        return list(self._connected_pipe_items)

    # ── Result update ─────────────────────────────────────────────────────

    def set_result(self, pressure_bar: float | None):
        self._result_pressure_bar = pressure_bar
        self.update()

    # ── Context menu ──────────────────────────────────────────────────────

    def contextMenuEvent(self, event):
        menu = QMenu()
        menu.addAction("Properties",
                       lambda: self.double_clicked.emit(self._element_id))
        menu.addSeparator()
        act_del = menu.addAction("Delete")
        chosen = menu.exec(event.screenPos())
        if chosen == act_del:
            sc = self.scene()
            if sc:
                sc.clearSelection()
                self.setSelected(True)
                QTimer.singleShot(0, sc.delete_selected)
        event.accept()

    # ── itemChange: propagate position to connected pipes ─────────────────

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for pipe in self._connected_pipe_items:
                pipe.update_geometry()
        return super().itemChange(change, value)

    # ── Paint ─────────────────────────────────────────────────────────────

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self._radius()
        colour_str = {
            "junction":    COLOR["node_junction"],
            "source":      COLOR["node_source"],
            "sink":        COLOR["node_sink"],
            "measurement": COLOR["node_measurement"],
        }.get(self._node_type, COLOR["node_junction"])
        colour = QColor(colour_str)

        if self._alarm_active:
            colour = QColor(COLOR["alarm"])

        if self.isSelected():
            # Glowing ring
            pen = QPen(QColor("#ffffff"))
            pen.setWidth(2)
            painter.setPen(pen)
        else:
            painter.setPen(Qt.PenStyle.NoPen)

        if self._node_type in ("junction", "measurement"):
            self._draw_circle(painter, r, colour)
        elif self._node_type == "source":
            self._draw_triangle(painter, r, colour, pointing_up=True)
        elif self._node_type == "sink":
            self._draw_triangle(painter, r, colour, pointing_up=False)

        if self._node_type == "measurement":
            self._draw_crosshair(painter, r, colour)

        # ── Tag / name label below node ────────────────────────────────────
        # If element_name == element_id (default) just show the ID once
        label = self._element_name
        self._paint_label(painter, label, 0, r + 3, align_center=True)

        # ── Pressure result above node ─────────────────────────────────────
        if self._result_pressure_bar is not None:
            from app.utils.units import PRESSURE_DECIMALS
            dec = PRESSURE_DECIMALS[UNITS.pressure]
            val_str = f"{UNITS.p(self._result_pressure_bar):.{dec}f} {UNITS.pressure}"
            self._paint_label(painter, val_str, 0, -(r + 16), align_center=True)

    def _draw_circle(self, painter: QPainter, r: float, colour: QColor):
        # Radial gradient for 3-D feel
        grad = QRadialGradient(QPointF(-r*0.3, -r*0.3), r * 1.4)
        lighter = colour.lighter(160)
        grad.setColorAt(0.0, lighter)
        grad.setColorAt(1.0, colour.darker(120))
        painter.setBrush(QBrush(grad))
        painter.drawEllipse(QRectF(-r, -r, r*2, r*2))

    def _draw_triangle(self, painter: QPainter, r: float, colour: QColor,
                        pointing_up: bool):
        path = QPainterPath()
        if pointing_up:
            path.moveTo(0, -r)
            path.lineTo(r * 0.866, r * 0.5)
            path.lineTo(-r * 0.866, r * 0.5)
        else:
            path.moveTo(0, r)
            path.lineTo(r * 0.866, -r * 0.5)
            path.lineTo(-r * 0.866, -r * 0.5)
        path.closeSubpath()
        painter.setBrush(QBrush(colour))
        painter.drawPath(path)

    def _draw_crosshair(self, painter: QPainter, r: float, colour: QColor):
        pen = QPen(colour.darker(150))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawLine(QPointF(-r*0.6, 0), QPointF(r*0.6, 0))
        painter.drawLine(QPointF(0, -r*0.6), QPointF(0, r*0.6))
