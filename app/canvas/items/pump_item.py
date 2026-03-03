"""
OpenPipeFlow — PumpItem: ISA-5.1 / ISO 10628 centrifugal pump symbol.

Standard P&ID centrifugal pump symbol:
  - Circle (pump casing / volute)
  - Filled crescent inside (impeller blade sweep)
  - Suction enters from the left; discharge exits to the right
  - When OFF the symbol is shown in alarm red
"""

from __future__ import annotations
import math
from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtGui import (QPainter, QPen, QBrush, QColor, QPainterPath,
                          QRadialGradient)
from PyQt6.QtCore import Qt

from app.canvas.items.pipe_item import PipeItem
from app.utils.styles import COLOR


class PumpItem(PipeItem):
    """
    Pipe item with an ISA-5.1 centrifugal pump symbol at its midpoint.

    The symbol rotates to align with the pipe direction so that the suction
    (notch) always faces the upstream node and the discharge faces downstream.
    """

    PIPE_TYPE = "pump"
    SYM_R     = 16   # radius of the pump circle (px)

    def __init__(self, element_id: str, element_name: str,
                 start_node, end_node, parent=None):
        super().__init__(element_id, element_name, start_node, end_node, parent)
        self._on_off = True

    @property
    def on_off(self) -> bool:
        return self._on_off

    @on_off.setter
    def on_off(self, v: bool):
        self._on_off = v
        self.update()

    # ── Paint ─────────────────────────────────────────────────────────────

    def paint(self, painter: QPainter, option, widget=None):
        # Draw the underlying animated pipe first
        super().paint(painter, option, widget)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        s_pt = self._start_pos()
        e_pt = self._end_pos()
        mid  = QPointF((s_pt.x() + e_pt.x()) / 2,
                       (s_pt.y() + e_pt.y()) / 2)
        dx = e_pt.x() - s_pt.x()
        dy = e_pt.y() - s_pt.y()
        length = math.sqrt(dx * dx + dy * dy)
        if length < 1.0:
            return
        angle_deg = math.degrees(math.atan2(dy, dx))

        painter.save()
        painter.translate(mid)
        painter.rotate(angle_deg)

        r = self.SYM_R
        running_colour = QColor(COLOR["accent"])
        off_colour     = QColor(COLOR["alarm"])
        border_colour  = running_colour if self._on_off else off_colour
        bg_colour      = QColor(COLOR["canvas_bg"])

        # ── Outer circle (pump casing) ─────────────────────────────────────
        painter.setPen(QPen(border_colour, 2))
        painter.setBrush(QBrush(bg_colour))
        painter.drawEllipse(QRectF(-r, -r, r * 2, r * 2))

        # ── Impeller crescent (ISA centrifugal pump symbol) ────────────────
        # A filled arc segment representing the impeller sweep.
        # The crescent spans from ~120° to ~300° inside the circle.
        crescent = QPainterPath()
        # Outer arc: follows the inside of the casing circle (radius = r*0.82)
        ir = r * 0.82
        crescent.moveTo(QPointF(ir * math.cos(math.radians(120)),
                                ir * math.sin(math.radians(120))))
        crescent.arcTo(QRectF(-ir, -ir, ir * 2, ir * 2), 120, 180)

        # Inner arc: tighter radius (radius = r*0.45) swept back
        inner_r = r * 0.42
        crescent.arcTo(QRectF(-inner_r, -inner_r,
                               inner_r * 2, inner_r * 2), 300, -180)
        crescent.closeSubpath()

        painter.setBrush(QBrush(border_colour))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(crescent)

        # ── Suction nozzle notch (left side, where flow enters) ────────────
        # A small notch indicating the suction eye
        nozzle_pen = QPen(border_colour, 2)
        nozzle_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(nozzle_pen)
        painter.drawLine(QPointF(-r, 0), QPointF(-r - 4, 0))

        # ── Discharge nozzle (right side, where flow exits) ────────────────
        painter.drawLine(QPointF(r, 0), QPointF(r + 4, 0))

        # ── Centre dot (shaft / bearing centre) ───────────────────────────
        painter.setBrush(QBrush(border_colour))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(-2, -2, 4, 4))

        # ── Rotation arc (animated CW sweep when running) ─────────────────
        if self._on_off:
            rot_pen = QPen(QColor(255, 255, 255, 80), 1)
            painter.setPen(rot_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            rot_r = r * 0.58
            painter.drawArc(QRectF(-rot_r, -rot_r, rot_r * 2, rot_r * 2),
                             40 * 16, 280 * 16)
        else:
            # OFF label
            off_pen = QPen(off_colour, 1)
            painter.setPen(off_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            # Cross through the circle to indicate OFF
            painter.drawLine(QPointF(-r * 0.5, -r * 0.5),
                              QPointF( r * 0.5,  r * 0.5))
            painter.drawLine(QPointF( r * 0.5, -r * 0.5),
                              QPointF(-r * 0.5,  r * 0.5))

        painter.restore()
