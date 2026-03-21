"""LDropIndicator — semi-transparent overlay shown during drags."""
from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QRubberBand, QStyle, QStyleOptionRubberBand, QWidget


class LDropIndicator(QWidget):
    """Frameless overlay shown over drop targets during drag, styled as a rubber band."""

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowTransparentForInput,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setVisible(False)

    def show_at(self, global_rect: QRect) -> None:
        self.setGeometry(global_rect)
        self.show()
        self.raise_()

    def hide_indicator(self) -> None:
        self.hide()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        opt = QStyleOptionRubberBand()
        opt.initFrom(self)
        opt.shape = QRubberBand.Shape.Rectangle
        opt.opaque = False
        opt.rect = self.rect()
        self.style().drawControl(QStyle.ControlElement.CE_RubberBand, opt, painter, self)
