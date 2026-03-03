"""
OpenPipeFlow — Hydraulic Resistance Diagram

Renders the pipe network as an equivalent electrical-circuit diagram:
  • Nodes       → junctions (voltage = pressure in bar)
  • Pipes/valves→ resistors, width+colour proportional to hydraulic resistance
  • Pumps       → EMF sources (voltage-source symbol)
  • Source nodes→ voltage source (battery)
  • Sink nodes  → ground symbol

Opens as a floating, resizable dialog.
Requires a solved network (results must be present) for resistance values;
falls back to uniform display if results are absent.
"""

from __future__ import annotations
import math

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGraphicsScene, QGraphicsView, QGraphicsItem,
    QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsTextItem,
)
from PyQt6.QtCore import Qt, QRectF, QPointF, QLineF, QSizeF
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QPainterPath,
    QLinearGradient,
)

from app.project.model import NetworkModel, PumpData, ValveData, PipeData
from app.utils.units import UNITS, PRESSURE_DECIMALS


# ── Colour helpers ────────────────────────────────────────────────────────────

def _resistance_colour(r_norm: float) -> QColor:
    """Map normalised resistance (0–1) to green → yellow → red."""
    t = max(0.0, min(r_norm, 1.0))
    if t < 0.5:
        s = t * 2.0
        return QColor(int(s * 255), 200, int((1 - s) * 60 + 60))
    else:
        s = (t - 0.5) * 2.0
        return QColor(255, int((1 - s) * 200), 0)


# ── Node rendering ────────────────────────────────────────────────────────────

_NODE_R = 18   # radius of junction circle in diagram pixels


def _draw_node(scene: QGraphicsScene, cx: float, cy: float,
               node_data, label: str) -> None:
    """Draw a node circle with label."""
    nt = node_data.node_type

    if nt == "source":
        # Battery symbol: two vertical bars
        _draw_battery(scene, cx, cy, node_data)
    elif nt == "sink":
        # Ground symbol: horizontal lines converging to a point
        _draw_ground(scene, cx, cy)
    else:
        # Junction circle
        col = QColor("#00b3a4") if nt == "junction" else QColor("#c8a000")
        pen = QPen(QColor("#ffffff"))
        pen.setWidth(1)
        e = scene.addEllipse(QRectF(cx - _NODE_R, cy - _NODE_R,
                                    _NODE_R * 2, _NODE_R * 2),
                             pen, QBrush(col))

    # Pressure label
    if node_data.result_pressure_bar is not None:
        dec = PRESSURE_DECIMALS[UNITS.pressure]
        pval = f"{UNITS.p(node_data.result_pressure_bar):.{dec}f} {UNITS.pressure}"
        _scene_text(scene, cx, cy - _NODE_R - 14, pval,
                    QColor("#c8f0ff"), 8)

    # Node name
    _scene_text(scene, cx, cy + _NODE_R + 4, label, QColor("#e0e0e0"), 8)


def _draw_battery(scene: QGraphicsScene, cx: float, cy: float, nd) -> None:
    """Simple battery symbol: two rectangles."""
    pen_b = QPen(QColor("#40ff80"))
    pen_b.setWidth(2)
    scene.addLine(cx, cy - 16, cx, cy + 16, pen_b)
    scene.addLine(cx - 12, cy - 8, cx + 12, cy - 8, pen_b)
    scene.addLine(cx - 8,  cy + 8, cx + 8,  cy + 8, pen_b)
    dec = PRESSURE_DECIMALS[UNITS.pressure]
    pval = f"{UNITS.p(nd.pressure_bar):.{dec}f} {UNITS.pressure}"
    _scene_text(scene, cx, cy - 26, pval, QColor("#40ff80"), 8)
    _scene_text(scene, cx, cy + 20, nd.name,  QColor("#40ff80"), 8)


def _draw_ground(scene: QGraphicsScene, cx: float, cy: float) -> None:
    """Ground symbol (3 horizontal lines)."""
    pen_g = QPen(QColor("#ff6040"))
    pen_g.setWidth(2)
    scene.addLine(cx - 14, cy, cx + 14, cy, pen_g)
    scene.addLine(cx - 9, cy + 6, cx + 9, cy + 6, pen_g)
    scene.addLine(cx - 4, cy + 12, cx + 4, cy + 12, pen_g)


# ── Branch rendering ──────────────────────────────────────────────────────────

_MIN_PEN = 1
_MAX_PEN = 8     # max pen width for highest-resistance branch
_ZIGZAG  = 6     # half-height of resistor zig-zag, px
_ZIGZAG_SEGS = 7 # number of zig-zag segments (should be odd)


def _draw_resistor(scene: QGraphicsScene,
                   x1: float, y1: float, x2: float, y2: float,
                   r_norm: float, pen_w: float,
                   label_top: str, label_bot: str) -> None:
    """
    Draw a pipe/valve as a resistor symbol between (x1,y1) and (x2,y2).
    r_norm: normalised resistance 0..1 → colour
    pen_w:  line width (proportional to resistance)
    """
    col = _resistance_colour(r_norm)
    pen = QPen(col)
    pen.setWidth(max(1, int(pen_w)))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)

    dx, dy = x2 - x1, y2 - y1
    length = math.sqrt(dx * dx + dy * dy) or 1.0
    ux, uy = dx / length, dy / length
    nx, ny = -uy, ux   # normal

    # Straight line from node to start of resistor body
    body_frac = 0.30     # resistor body occupies middle 40% of length
    mid_frac  = 0.50
    s_frac = mid_frac - body_frac / 2
    e_frac = mid_frac + body_frac / 2

    px_s = QPointF(x1 + s_frac * dx, y1 + s_frac * dy)
    px_e = QPointF(x1 + e_frac * dx, y1 + e_frac * dy)

    # Lead wires
    scene.addLine(QLineF(QPointF(x1, y1), px_s), pen)
    scene.addLine(QLineF(px_e, QPointF(x2, y2)), pen)

    # Zig-zag body
    body_len = body_frac * length
    seg_len  = body_len / _ZIGZAG_SEGS
    path = QPainterPath()
    path.moveTo(px_s)
    for i in range(_ZIGZAG_SEGS):
        t = (i + 1) / _ZIGZAG_SEGS
        mid_pt = QPointF(
            px_s.x() + t * (px_e.x() - px_s.x()),
            px_s.y() + t * (px_e.y() - px_s.y()),
        )
        sign = +1 if i % 2 == 0 else -1
        off  = sign * _ZIGZAG
        path.lineTo(mid_pt.x() + nx * off, mid_pt.y() + ny * off)

    scene.addPath(path, pen)

    # Labels
    mid_x = (x1 + x2) / 2
    mid_y = (y1 + y2) / 2
    off_px = 18
    _scene_text(scene, mid_x + nx * off_px, mid_y + ny * off_px,
                label_top, QColor("#e0e0e0"), 8)
    if label_bot:
        _scene_text(scene, mid_x + nx * (off_px + 11), mid_y + ny * (off_px + 11),
                    label_bot, col, 8)


def _draw_pump_symbol(scene: QGraphicsScene,
                      x1: float, y1: float, x2: float, y2: float,
                      label: str, on: bool) -> None:
    """Draw a pump (EMF source) symbol between two points."""
    col  = QColor("#00d4aa") if on else QColor("#888888")
    pen  = QPen(col)
    pen.setWidth(2)

    mx = (x1 + x2) / 2
    my = (y1 + y2) / 2
    r  = 14

    # Lead wires
    dx, dy = x2 - x1, y2 - y1
    L = math.sqrt(dx * dx + dy * dy) or 1.0
    ux, uy = dx / L, dy / L

    scene.addLine(QLineF(QPointF(x1, y1),
                         QPointF(mx - ux * r, my - uy * r)), pen)
    scene.addLine(QLineF(QPointF(mx + ux * r, my + uy * r),
                         QPointF(x2, y2)), pen)

    # Circle
    scene.addEllipse(QRectF(mx - r, my - r, r * 2, r * 2),
                     pen, QBrush(QColor(0, 0, 0, 0)))

    # Arrow inside circle (direction of flow)
    if on:
        ax  = mx + ux * (r * 0.5)
        ay  = my + uy * (r * 0.5)
        bx  = mx - ux * (r * 0.5)
        by  = my - uy * (r * 0.5)
        pen_arr = QPen(col)
        pen_arr.setWidth(2)
        scene.addLine(QLineF(QPointF(bx, by), QPointF(ax, ay)), pen_arr)
        # arrowhead
        nx_, ny_ = -uy, ux
        hx, hy = ax - ux * 5, ay - uy * 5
        scene.addLine(QLineF(QPointF(ax, ay),
                             QPointF(hx + nx_ * 4, hy + ny_ * 4)), pen_arr)
        scene.addLine(QLineF(QPointF(ax, ay),
                             QPointF(hx - nx_ * 4, hy - ny_ * 4)), pen_arr)

    # Label
    nx_, ny_ = -uy, ux
    _scene_text(scene, mx + nx_ * 22, my + ny_ * 22,
                label, col, 8)


# ── Text helper ───────────────────────────────────────────────────────────────

def _scene_text(scene: QGraphicsScene, cx: float, cy: float,
                text: str, colour: QColor, pt: int) -> None:
    item = QGraphicsTextItem(text)
    item.setDefaultTextColor(colour)
    item.setFont(QFont("Consolas", pt))
    bw = item.boundingRect().width()
    bh = item.boundingRect().height()
    item.setPos(cx - bw / 2, cy - bh / 2)
    scene.addItem(item)


# ── Main dialog ───────────────────────────────────────────────────────────────

class ResistanceDiagramDialog(QDialog):
    """
    A floating window showing the hydraulic equivalent of an electrical
    resistance circuit.

    Branch thickness + colour → hydraulic resistance (ΔP / Q).
    The highest-resistance branch is always drawn widest/reddest.
    """

    def __init__(self, model: NetworkModel, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Hydraulic Resistance Diagram")
        self.resize(900, 680)
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint)

        self._model = model

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Info bar
        info = QLabel(
            "Branch width & colour = hydraulic resistance (ΔP/Q). "
            "Red/thick = high resistance.  Green/thin = low resistance.")
        info.setStyleSheet("color: #a0c8e0; font-size: 11px; padding: 2px 4px;")
        layout.addWidget(info)

        # Graphics view
        self._gscene = QGraphicsScene()
        self._gscene.setBackgroundBrush(QBrush(QColor("#1a1e24")))
        self._gview  = QGraphicsView(self._gscene)
        self._gview.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._gview.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._gview.setTransformationAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        layout.addWidget(self._gview, 1)

        # Button bar
        btn_bar = QHBoxLayout()
        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self._build)
        btn_fit = QPushButton("Fit View")
        btn_fit.clicked.connect(self._fit)
        btn_close  = QPushButton("Close")
        btn_close.clicked.connect(self.close)
        btn_bar.addWidget(btn_refresh)
        btn_bar.addWidget(btn_fit)
        btn_bar.addStretch()
        btn_bar.addWidget(btn_close)
        layout.addLayout(btn_bar)

        for btn in (btn_refresh, btn_fit, btn_close):
            btn.setStyleSheet(
                "QPushButton { background: #2a2e36; color: #e0e0e0; "
                "border: 1px solid #44484f; border-radius: 3px; "
                "padding: 3px 10px; }"
                "QPushButton:hover { background: #3a3e46; }"
            )

        self._build()

    # ── Build scene ───────────────────────────────────────────────────────────

    def _build(self) -> None:
        self._gscene.clear()
        model = self._model

        if not model.nodes:
            _scene_text(self._gscene, 0, 0, "No network loaded.",
                        QColor("#888888"), 12)
            return

        # ── Scale node positions to diagram space ─────────────────────────
        # Use the canvas coordinates but scaled to fit a ~800×600 box
        xs = [n.x for n in model.nodes.values()]
        ys = [n.y for n in model.nodes.values()]
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)
        span_x = max(x_max - x_min, 1.0)
        span_y = max(y_max - y_min, 1.0)
        scale  = min(700.0 / span_x, 500.0 / span_y, 1.5)
        pad    = 80

        def _pos(node) -> tuple[float, float]:
            return (
                pad + (node.x - x_min) * scale,
                pad + (node.y - y_min) * scale,
            )

        node_pos: dict[str, tuple[float, float]] = {
            nid: _pos(n) for nid, n in model.nodes.items()
        }

        # ── Compute hydraulic resistance for each branch ───────────────────
        # R = |ΔP| / Q  (bar per m³/s).  Use 0 if results absent.
        branch_R: list[float] = []
        for b in model.all_branch_elements():
            dp = getattr(b, "result_delta_p_bar", None)
            q  = getattr(b, "result_flow_m3s",    None)
            if dp is not None and q is not None and abs(q) > 1e-9:
                branch_R.append(abs(dp) / abs(q))
            else:
                branch_R.append(0.0)

        R_max = max(branch_R) if branch_R else 1.0
        if R_max < 1e-12:
            R_max = 1.0

        # ── Render branches ───────────────────────────────────────────────
        idx = 0
        for b in model.all_branch_elements():
            sn = b.start_node_id
            en = b.end_node_id
            if sn not in node_pos or en not in node_pos:
                idx += 1
                continue

            x1, y1 = node_pos[sn]
            x2, y2 = node_pos[en]

            R = branch_R[idx]
            r_norm = R / R_max
            pen_w  = _MIN_PEN + r_norm * (_MAX_PEN - _MIN_PEN)

            # Element-type-specific rendering
            if isinstance(b, PumpData):
                _draw_pump_symbol(self._gscene, x1, y1, x2, y2,
                                  b.name, b.on_off)
            else:
                # Build labels
                v = getattr(b, "result_velocity_ms", None)
                dp = getattr(b, "result_delta_p_bar", None)
                q  = getattr(b, "result_flow_m3s",    None)

                top_label = b.name

                if R > 0:
                    # Show R in bar/(L/s) for human readability
                    r_display = R * 1000.0   # bar per L/s
                    if r_display < 0.01:
                        r_str = f"R={R:.2e} bar·s/L"
                    else:
                        r_str = f"R={r_display:.3f} bar/L·s⁻¹"
                else:
                    r_str = ""

                _draw_resistor(self._gscene, x1, y1, x2, y2,
                               r_norm, pen_w, top_label, r_str)

            idx += 1

        # ── Render nodes ──────────────────────────────────────────────────
        for nid, node in model.nodes.items():
            cx, cy = node_pos[nid]
            _draw_node(self._gscene, cx, cy, node, node.name)

        # ── Legend ────────────────────────────────────────────────────────
        self._draw_legend()

        self._fit()

    def _draw_legend(self) -> None:
        """Draw a colour scale legend at a fixed position."""
        scene = self._gscene
        bx, by = -60, -30
        _scene_text(scene, bx + 60, by - 10, "Resistance scale:",
                    QColor("#a0c8e0"), 9)

        steps = 8
        sw = 120 / steps
        for i in range(steps):
            t = i / (steps - 1)
            col = _resistance_colour(t)
            pen = QPen(col)
            pen.setWidth(3)
            scene.addLine(
                QLineF(QPointF(bx + i * sw, by + 8),
                       QPointF(bx + (i + 1) * sw, by + 8)),
                pen,
            )
        _scene_text(scene, bx,       by + 20, "Low", QColor("#40c060"), 8)
        _scene_text(scene, bx + 115, by + 20, "High", QColor("#ff4020"), 8)

    def _fit(self) -> None:
        self._gview.fitInView(self._gscene.itemsBoundingRect(),
                              Qt.AspectRatioMode.KeepAspectRatio)

    def wheelEvent(self, event) -> None:
        """Zoom on mouse-wheel."""
        factor = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
        self._gview.scale(factor, factor)
