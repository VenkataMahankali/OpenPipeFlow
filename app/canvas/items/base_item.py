"""
OpenPipeFlow — BaseItem: abstract base for all canvas graphics items.

Provides:
  - element_id / element_name properties
  - selection highlight
  - in-place ID label rendering
  - double-click → properties dialog signal
"""

from __future__ import annotations
from PyQt6.QtWidgets import QGraphicsObject, QGraphicsItem
from PyQt6.QtCore import Qt, QRectF, pyqtSignal
from PyQt6.QtGui import QFont, QPainterPath, QColor, QPen, QBrush, QFontMetricsF


class BaseItem(QGraphicsObject):
    """
    Abstract base class for all interactive canvas items.
    Subclasses must implement boundingRect() and paint().
    """

    # Emitted when the item is double-clicked (carries the element id)
    double_clicked = pyqtSignal(str)
    # Emitted when the item is moved (by dragging)
    position_changed = pyqtSignal(str, float, float)

    # Font used for ID labels
    LABEL_FONT = QFont("Segoe UI", 8)
    LABEL_FONT_SMALL = QFont("Segoe UI", 7)

    def __init__(self, element_id: str, element_name: str,
                 parent=None):
        super().__init__(parent)
        self._element_id   = element_id
        self._element_name = element_name
        self._show_label   = True
        self._alarm_active = False

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)

    # ── Properties ────────────────────────────────────────────────────────

    @property
    def element_id(self) -> str:
        return self._element_id

    @property
    def element_name(self) -> str:
        return self._element_name

    @element_name.setter
    def element_name(self, value: str):
        self._element_name = value
        self.update()

    @property
    def alarm_active(self) -> bool:
        return self._alarm_active

    @alarm_active.setter
    def alarm_active(self, value: bool):
        if value != self._alarm_active:
            self._alarm_active = value
            self.update()

    # ── Interaction ───────────────────────────────────────────────────────

    def mouseDoubleClickEvent(self, event):
        self.double_clicked.emit(self._element_id)
        super().mouseDoubleClickEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            pos = value
            self.position_changed.emit(self._element_id, pos.x(), pos.y())
        return super().itemChange(change, value)

    # ── Label rendering helper ────────────────────────────────────────────

    def _paint_label(self, painter, text: str, x: float, y: float,
                     align_center: bool = True):
        """Draw the ID/name label at (x, y) scene-local coordinates."""
        painter.save()
        painter.setFont(self.LABEL_FONT)
        fm = QFontMetricsF(self.LABEL_FONT)
        w = fm.horizontalAdvance(text)
        h = fm.height()
        if align_center:
            x -= w / 2
        # Background pill
        pad_x, pad_y = 3, 1
        bg_rect = QRectF(x - pad_x, y - pad_y, w + 2*pad_x, h + 2*pad_y)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#0e111788")))
        painter.drawRoundedRect(bg_rect, 2, 2)
        # Text
        if self._alarm_active:
            painter.setPen(QColor("#e74c3c"))
        else:
            painter.setPen(QColor("#e8edf2"))
        painter.drawText(QRectF(x, y, w, h), text)
        painter.restore()

    # ── Selection highlight helper ────────────────────────────────────────

    def _paint_selection_ring(self, painter, path_or_rect, color="#00d4aa"):
        """Draw a glowing selection outline."""
        if not self.isSelected():
            return
        painter.save()
        pen = QPen(QColor(color))
        pen.setWidth(2)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if isinstance(path_or_rect, QPainterPath):
            painter.drawPath(path_or_rect)
        else:
            painter.drawRect(path_or_rect)
        painter.restore()
