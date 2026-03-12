"""LDropIndicator — semi-transparent overlay shown during drags."""
from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPalette
from PySide6.QtWidgets import QWidget


class LDropIndicator(QWidget):
    """Frameless semi-transparent blue rectangle shown over drop targets."""

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
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        highlight = self.palette().color(QPalette.ColorRole.Highlight)
        fill = QColor(highlight)
        fill.setAlpha(60)
        outline = QColor(highlight)
        outline.setAlpha(180)
        painter.fillRect(self.rect(), fill)
        painter.setPen(outline)
        painter.drawRect(self.rect().adjusted(1, 1, -1, -1))
