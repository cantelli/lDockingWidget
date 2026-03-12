"""LDropIndicator — semi-transparent overlay shown during drags."""
from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter
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
        color = QColor(0, 100, 255, 80)
        painter.fillRect(self.rect(), color)
        # Outline
        outline = QColor(0, 100, 255, 200)
        painter.setPen(outline)
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
