"""
OpenPipeFlow — PipeItem: animated pipe segment between two NodeItems.

Features:
  - Straight line connecting start_node ↔ end_node
  - Velocity-based colour (blue → yellow → red)
  - Animated dashed arrow showing flow direction and speed
  - Alarm highlight
  - Selection outline
"""

from __future__ import annotations
import math
from PyQt6.QtWidgets import QGraphicsItem, QMenu
from PyQt6.QtCore import Qt, QRectF, QPointF, QLineF, QTimer
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QPainterPath, QLinearGradient,
    QPolygonF
)
from app.utils.units import UNITS, VELOCITY_DECIMALS, PRESSURE_DECIMALS

from app.canvas.items.base_item import BaseItem
from app.utils.constants import (
    PIPE_WIDTH_PX, VEL_COLOUR_LOW, VEL_COLOUR_HIGH, NODE_RADIUS_PX
)
from app.utils.styles import COLOR


def _safe_float(v) -> float | None:
    """Return v as float if finite, else None."""
    if v is None:
        return None
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def _velocity_colour(v_ms: float | None) -> QColor:
    """Map velocity to a colour along blue → yellow → red gradient."""
    v_ms = _safe_float(v_ms)
    if v_ms is None or v_ms <= 0.0:
        return QColor(COLOR["pipe_static"])
    t = min(max((v_ms - 0.0) / max(VEL_COLOUR_HIGH, 1e-6), 0.0), 1.0)
    if t < 0.5:
        # blue (0,102,255) → yellow (255,170,0)
        s = t * 2
        r = int(0   + s * 255)
        g = int(102 + s * 68)
        b = int(255 - s * 255)
    else:
        # yellow (255,170,0) → red (255,34,0)
        s = (t - 0.5) * 2
        r = 255
        g = int(170 - s * 170)
        b = 0
    return QColor(r, g, b)


class PipeItem(BaseItem):
    """
    Pipe segment between two NodeItems.
    Also used as the base for ValveItem and PumpItem.
    """

    PIPE_TYPE = "pipe"   # overridden by subclasses

    def __init__(self, element_id: str, element_name: str,
                 start_node, end_node, parent=None):
        super().__init__(element_id, element_name, parent)
        self._start_node = start_node
        self._end_node   = end_node

        # Simulation results
        self._velocity_ms: float | None = None
        self._flow_m3s:    float | None = None
        self._dp_bar:      float | None = None
        self._reynolds:    float | None = None
        self._regime:      str | None   = None

        # Animation state
        self._anim_offset: float = 0.0   # 0..1 dash phase

        self.setZValue(5)   # below nodes, above grid
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.update_geometry()

    # ── Geometry ──────────────────────────────────────────────────────────

    def _start_pos(self) -> QPointF:
        return self._start_node.scenePos()

    def _end_pos(self) -> QPointF:
        return self._end_node.scenePos()

    def _line(self) -> QLineF:
        return QLineF(self._start_pos(), self._end_pos())

    def update_geometry(self):
        self.prepareGeometryChange()
        self.update()

    def boundingRect(self) -> QRectF:
        s, e = self._start_pos(), self._end_pos()
        pad = 20
        x1, y1 = min(s.x(), e.x()) - pad, min(s.y(), e.y()) - pad
        x2, y2 = max(s.x(), e.x()) + pad, max(s.y(), e.y()) + pad
        # Convert to local coords (item position is 0,0 for scene items)
        return QRectF(x1, y1, x2 - x1, y2 - y1)

    def shape(self) -> QPainterPath:
        line = self._line()
        path = QPainterPath()
        path.moveTo(line.p1())
        path.lineTo(line.p2())
        # Stroke the path for hit-testing
        from PyQt6.QtGui import QPainterPathStroker
        stroker = QPainterPathStroker()
        stroker.setWidth(14)
        return stroker.createStroke(path)

    # ── Results update ────────────────────────────────────────────────────

    def set_result(self, velocity_ms: float | None, flow_m3s: float | None,
                   dp_bar: float | None, reynolds: float | None,
                   regime: str | None):
        # Guard against NaN/inf from solver
        self._velocity_ms = _safe_float(velocity_ms)
        self._flow_m3s    = _safe_float(flow_m3s)
        self._dp_bar      = _safe_float(dp_bar)
        self._reynolds    = _safe_float(reynolds)
        self._regime      = regime
        self.update()

    # ── Animation ─────────────────────────────────────────────────────────

    def advance_animation(self, dt_s: float):
        """Advance dash offset. Called by the scene timer."""
        v = _safe_float(self._velocity_ms)
        if v is None or abs(v) < 1e-6:
            return
        # Speed: offset advances faster for higher velocity
        speed = min(abs(v) / VEL_COLOUR_HIGH, 1.0) * 0.8 + 0.1  # 0.1..0.9 /s
        delta = speed * dt_s
        if v < 0:
            delta = -delta
        self._anim_offset = (self._anim_offset + delta) % 1.0
        self.update()

    # ── Paint ─────────────────────────────────────────────────────────────

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        s, e = self._start_pos(), self._end_pos()
        line = QLineF(s, e)
        if line.length() < 1.0:
            return

        colour = _velocity_colour(self._velocity_ms)
        if self._alarm_active:
            colour = QColor(COLOR["alarm"])

        # ── Main pipe line ─────────────────────────────────────────────────
        pen = QPen(colour)
        pen.setWidth(PIPE_WIDTH_PX)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        if self.isSelected():
            pen.setWidth(PIPE_WIDTH_PX + 2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawLine(s, e)

        # ── Animated flow arrows ───────────────────────────────────────────
        v = self._velocity_ms
        if v is not None and abs(v) > 1e-6:
            self._draw_flow_arrows(painter, s, e, colour)

        # ── Labels — tag name above pipe, results below ────────────────────
        mid = QPointF((s.x() + e.x()) / 2, (s.y() + e.y()) / 2)

        # Perpendicular offset so labels don't sit on the pipe line
        dx = e.x() - s.x()
        dy = e.y() - s.y()
        length = math.sqrt(dx*dx + dy*dy) or 1.0
        # Normal vector (perpendicular, pointing "up" in screen space)
        nx, ny = -dy / length, dx / length
        # Prefer the normal that points upward (ny < 0 in screen coords)
        if ny > 0:
            nx, ny = -nx, -ny
        label_offset = 14   # px away from pipe line

        lx = mid.x() + nx * label_offset
        ly = mid.y() + ny * label_offset

        # Tag name — above the pipe
        self._paint_label(painter, self._element_name,
                          lx, ly - 9, align_center=True)

        # Velocity / ΔP — just below the tag name
        if self._velocity_ms is not None:
            v_dec = VELOCITY_DECIMALS[UNITS.velocity]
            ann = f"{UNITS.v(self._velocity_ms):.{v_dec}f} {UNITS.velocity}"
            if self._dp_bar is not None:
                p_dec = PRESSURE_DECIMALS[UNITS.pressure]
                ann += f"  dP={UNITS.p(self._dp_bar):.{p_dec}f} {UNITS.pressure}"
            self._paint_label(painter, ann,
                              lx, ly + 3, align_center=True)

        # ── Selection highlight ────────────────────────────────────────────
        if self.isSelected():
            sel_pen = QPen(QColor("#00d4aa"))
            sel_pen.setWidth(1)
            sel_pen.setStyle(Qt.PenStyle.DotLine)
            painter.setPen(sel_pen)
            painter.drawLine(s, e)

    # ── Context menu (inherited by ValveItem and PumpItem) ─────────────────

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

    def _draw_flow_arrows(self, painter: QPainter, s: QPointF, e: QPointF,
                          colour: QColor):
        """Draw small chevron arrows animated along the pipe."""
        dx = e.x() - s.x()
        dy = e.y() - s.y()
        length = math.sqrt(dx*dx + dy*dy)
        if length < 1.0:
            return

        # Unit vector along pipe
        ux, uy = dx / length, dy / length
        # Normal vector
        nx, ny = -uy, ux

        arrow_spacing = 40.0   # px between arrows
        arrow_half    = 6.0    # half-width of chevron
        arrow_depth   = 8.0    # depth of chevron

        # Number of arrows that fit
        n_arrows = max(int(length / arrow_spacing), 1)

        painter.save()
        pen = QPen(colour.lighter(140))
        pen.setWidth(2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        for i in range(n_arrows):
            # Base position along pipe (0..1), offset by animation phase
            t_base = (i + 0.5 + self._anim_offset) / n_arrows
            t_base = t_base % 1.0
            # Keep arrows away from node circles
            margin = NODE_RADIUS_PX / length
            t = margin + t_base * (1.0 - 2 * margin)

            cx = s.x() + t * dx
            cy = s.y() + t * dy

            # Chevron: two lines meeting at a point
            tip_x = cx + ux * arrow_depth / 2
            tip_y = cy + uy * arrow_depth / 2
            l1x = cx - ux * arrow_depth / 2 + nx * arrow_half
            l1y = cy - uy * arrow_depth / 2 + ny * arrow_half
            l2x = cx - ux * arrow_depth / 2 - nx * arrow_half
            l2y = cy - uy * arrow_depth / 2 - ny * arrow_half

            painter.drawLine(QPointF(l1x, l1y), QPointF(tip_x, tip_y))
            painter.drawLine(QPointF(l2x, l2y), QPointF(tip_x, tip_y))

        painter.restore()
