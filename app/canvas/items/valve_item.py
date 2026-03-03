"""
OpenPipeFlow — ValveItem: P&ID-standard valve and orifice symbols.

Valve types rendered (ISO 10628 / ISA-5.1 inspired):
  gate      — hourglass (two triangles touching at tips)
  ball      — circle body with bore indicator
  check     — filled triangle with upstream plate (one-way)
  butterfly — circle with angled disc line
  globe     — circle with horizontal seat + vertical stem
  orifice   — two close parallel vertical bars (orifice plate) + bubble
"""

from __future__ import annotations
import math
from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QPainterPath
from PyQt6.QtCore import Qt

from app.canvas.items.pipe_item import PipeItem
from app.utils.styles import COLOR


class ValveItem(PipeItem):
    """Pipe item with a P&ID valve or orifice symbol drawn at mid-point."""

    PIPE_TYPE = "valve"
    SYM_SIZE  = 10   # half-size of symbol bounding box (px)

    def __init__(self, element_id: str, element_name: str,
                 start_node, end_node, valve_type: str = "gate", parent=None):
        super().__init__(element_id, element_name, start_node, end_node, parent)
        self._valve_type = valve_type
        self._open_pct   = 100.0

    # ── Properties ────────────────────────────────────────────────────────

    @property
    def valve_type(self) -> str:
        return self._valve_type

    @valve_type.setter
    def valve_type(self, v: str):
        self._valve_type = v
        self.update()

    @property
    def open_pct(self) -> float:
        return self._open_pct

    @open_pct.setter
    def open_pct(self, v: float):
        self._open_pct = max(0.0, min(100.0, v))
        self.update()

    # ── Paint ─────────────────────────────────────────────────────────────

    def paint(self, painter: QPainter, option, widget=None):
        # Draw the underlying animated pipe line first
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

        # Symbol colour by valve state / type
        if self._valve_type == "orifice":
            sym_colour = QColor("#a0c8ff")   # light blue — instrument colour
        elif self._open_pct <= 0.0:
            sym_colour = QColor(COLOR["alarm"])
        elif self._open_pct < 100.0:
            sym_colour = QColor(COLOR["warning"])
        else:
            sym_colour = QColor("#e8edf2")

        bg_colour = QColor(COLOR["canvas_bg"])
        pen = QPen(sym_colour)
        pen.setWidth(2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(QBrush(bg_colour))

        s = self.SYM_SIZE
        draw_fn = {
            "gate":      self._draw_gate,
            "ball":      self._draw_ball,
            "check":     self._draw_check,
            "butterfly": self._draw_butterfly,
            "globe":     self._draw_globe,
            "orifice":   self._draw_orifice,
        }.get(self._valve_type, self._draw_gate)
        draw_fn(painter, s, sym_colour, bg_colour)

        # Partial-open indicator: small amber progress bar above symbol
        if self._valve_type != "orifice" and 0.0 < self._open_pct < 100.0:
            total_w = s * 2
            filled_w = total_w * self._open_pct / 100.0
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(COLOR["panel_bg"])))
            painter.drawRect(QRectF(-s, -s - 6, total_w, 3))
            painter.setBrush(QBrush(QColor(COLOR["warning"])))
            painter.drawRect(QRectF(-s, -s - 6, filled_w, 3))

        painter.restore()

    # ── Gate valve ────────────────────────────────────────────────────────

    def _draw_gate(self, painter, s, colour, bg):
        """Two solid triangles pointing inward — classic ISO gate-valve hourglass."""
        path = QPainterPath()
        path.moveTo(-s, -s)
        path.lineTo( s, -s)
        path.lineTo( 0,  0)
        path.closeSubpath()
        path.moveTo(-s,  s)
        path.lineTo( s,  s)
        path.lineTo( 0,  0)
        path.closeSubpath()
        painter.setBrush(QBrush(colour))
        painter.setPen(QPen(colour.darker(130), 1))
        painter.drawPath(path)

    # ── Ball valve ────────────────────────────────────────────────────────

    def _draw_ball(self, painter, s, colour, bg):
        """Circle (ball body) with a bore rectangle showing open/closed state."""
        # Circle body
        painter.setPen(QPen(colour, 2))
        painter.setBrush(QBrush(bg))
        painter.drawEllipse(QRectF(-s, -s, s * 2, s * 2))

        bore_w = s * 0.38
        bore_h = s * 1.7

        if self._open_pct >= 100.0:
            # Open: bore aligned with flow — thin horizontal slot
            painter.setBrush(QBrush(colour))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(QRectF(-s * 0.85, -bore_w * 0.5,
                                     s * 1.7,   bore_w))
        else:
            # Partial / closed: bore rotated showing the ball has turned
            rot = 90.0 * (1.0 - self._open_pct / 100.0)
            painter.save()
            painter.rotate(rot)
            painter.setBrush(QBrush(colour))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(QRectF(-bore_w * 0.5, -bore_h * 0.5,
                                     bore_w,         bore_h))
            painter.restore()

    # ── Check valve ───────────────────────────────────────────────────────

    def _draw_check(self, painter, s, colour, bg):
        """Filled triangle (allowed direction) + upstream stop plate."""
        # Upstream stop plate
        painter.setPen(QPen(colour, 2, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.FlatCap))
        painter.drawLine(QPointF(-s, -s), QPointF(-s, s))

        # Filled flow-direction triangle
        path = QPainterPath()
        path.moveTo(-s + 3,  s)
        path.lineTo( s,      0)
        path.lineTo(-s + 3, -s)
        path.closeSubpath()
        painter.setBrush(QBrush(colour))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(path)

    # ── Butterfly valve ───────────────────────────────────────────────────

    def _draw_butterfly(self, painter, s, colour, bg):
        """Circle body + angled disc line (disc rotates with open %)."""
        painter.setPen(QPen(colour, 2))
        painter.setBrush(QBrush(bg))
        painter.drawEllipse(QRectF(-s, -s, s * 2, s * 2))

        # Disc: vertical line (closed) rotates towards horizontal (open)
        disc_rot = 80.0 * (self._open_pct / 100.0)
        painter.save()
        painter.rotate(disc_rot)
        disc_pen = QPen(colour, 3)
        disc_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(disc_pen)
        painter.drawLine(QPointF(0, -s * 0.82), QPointF(0, s * 0.82))
        painter.restore()

    # ── Globe valve ───────────────────────────────────────────────────────

    def _draw_globe(self, painter, s, colour, bg):
        """Circle globe body with horizontal seat and vertical plug stem."""
        painter.setPen(QPen(colour, 2))
        painter.setBrush(QBrush(bg))
        painter.drawEllipse(QRectF(-s, -s, s * 2, s * 2))
        # Horizontal seat line
        painter.drawLine(QPointF(-s, 0), QPointF(s, 0))
        # Vertical stem (plug travels up/down)
        stem_y = -s * 1.0 + (s * 0.8) * (self._open_pct / 100.0)
        painter.drawLine(QPointF(0, stem_y), QPointF(0, -s))

    # ── Orifice plate ─────────────────────────────────────────────────────

    def _draw_orifice(self, painter, s, colour, bg):
        """
        Orifice plate (ISA-5.1 inspired):
        Two parallel vertical lines with a central bore gap + instrument bubble.
        """
        gap  = 4          # half-gap between the upstream/downstream faces
        bore = s * 0.42   # half-height of the orifice bore hole

        plate_pen = QPen(colour, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap)
        painter.setPen(plate_pen)

        # Upstream plate face (-gap x)
        painter.drawLine(QPointF(-gap, -s),    QPointF(-gap, -bore))
        painter.drawLine(QPointF(-gap,  bore), QPointF(-gap,  s))
        # Downstream plate face (+gap x)
        painter.drawLine(QPointF( gap, -s),    QPointF( gap, -bore))
        painter.drawLine(QPointF( gap,  bore), QPointF( gap,  s))
        # Top and bottom caps
        painter.drawLine(QPointF(-gap, -s), QPointF( gap, -s))
        painter.drawLine(QPointF(-gap,  s), QPointF( gap,  s))

        # Bore edge indicators (thin lines at bore boundary)
        thin_pen = QPen(colour.lighter(150), 1)
        painter.setPen(thin_pen)
        painter.drawLine(QPointF(-gap, -bore), QPointF(gap, -bore))
        painter.drawLine(QPointF(-gap,  bore), QPointF(gap,  bore))

        # Instrument bubble above the plate (circle = flow element FE)
        bub_r = s * 0.45
        bub_cx = 0.0
        bub_cy = -s - 4 - bub_r
        painter.setPen(QPen(colour, 1))
        painter.setBrush(QBrush(bg))
        painter.drawEllipse(QRectF(bub_cx - bub_r, bub_cy - bub_r,
                                    bub_r * 2,        bub_r * 2))
        # Leader line from plate top to bubble
        painter.drawLine(QPointF(0, -s), QPointF(bub_cx, bub_cy + bub_r))
