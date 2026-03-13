"""LTitleBar — custom title bar widget for LDockWidget."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QStyle,
    QToolButton,
    QWidget,
)


class LTitleBar(QWidget):
    """Drag handle + float/close buttons for LDockWidget.

    Signals
    -------
    drag_started(global_pos)   — user has dragged past startDragDistance
    float_requested()          — float/restore button clicked
    close_requested()          — close button clicked
    """

    drag_started = Signal(QPoint)
    move_dragging = Signal(QPoint)
    drag_released = Signal()
    float_requested = Signal()
    close_requested = Signal()

    def __init__(self, title: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._title = title
        self._vertical = False
        self._press_pos: QPoint | None = None
        self._dragging = False
        self._press_target: QWidget | None = None

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("dockTitleBar")
        self._build_ui()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def set_title(self, title: str) -> None:
        self._title = title
        self._label.setText(title)

    def title(self) -> str:
        return self._title

    def set_vertical(self, vertical: bool) -> None:
        """Switch between horizontal and vertical layout."""
        self._vertical = vertical
        if vertical:
            self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        else:
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.update()

    def set_float_button_icon(self, floating: bool) -> None:
        icon_name = (
            QStyle.StandardPixmap.SP_TitleBarNormalButton
            if floating
            else QStyle.StandardPixmap.SP_TitleBarMaxButton
        )
        icon = self.style().standardIcon(icon_name)
        self._float_btn.setIcon(icon)

    def show_close_button(self, show: bool) -> None:
        self._close_btn.setVisible(show)

    def show_float_button(self, show: bool) -> None:
        self._float_btn.setVisible(show)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        m = self.style().pixelMetric(QStyle.PixelMetric.PM_DockWidgetTitleMargin)
        layout.setContentsMargins(m, 1, 1, 1)
        layout.setSpacing(1)

        self._label = QLabel(self._title)
        self._label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        icon_size = self.style().pixelMetric(QStyle.PixelMetric.PM_SmallIconSize)
        btn_size = QSize(icon_size, icon_size)

        self._float_btn = QToolButton()
        self._float_btn.setFixedSize(btn_size)
        self._float_btn.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarMaxButton)
        )
        self._float_btn.setAutoRaise(True)
        self._float_btn.clicked.connect(self.float_requested)

        self._close_btn = QToolButton()
        self._close_btn.setFixedSize(btn_size)
        self._close_btn.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarCloseButton)
        )
        self._close_btn.setAutoRaise(True)
        self._close_btn.clicked.connect(self.close_requested)

        layout.addWidget(self._label)
        layout.addWidget(self._float_btn)
        layout.addWidget(self._close_btn)

        self.setMinimumHeight(0)
        self.setMaximumHeight(16777215)

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def _drag_blocked_widget(self, widget: QWidget | None) -> bool:
        return widget in {self._float_btn, self._close_btn}

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            local_pos = event.position().toPoint()
            self._press_target = self.childAt(local_pos)
            if not self._drag_blocked_widget(self._press_target):
                self._press_pos = event.globalPosition().toPoint()
                self._dragging = False
            else:
                self._press_pos = None
                self._dragging = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._press_pos is not None:
            global_pos = event.globalPosition().toPoint()
            if not self._dragging:
                delta = global_pos - self._press_pos
                if delta.manhattanLength() >= QApplication.startDragDistance():
                    self._dragging = True
                    self.drag_started.emit(self._press_pos)
            if self._dragging:
                self.move_dragging.emit(global_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._press_pos = None
        self._press_target = None
        self._dragging = False
        self.drag_released.emit()
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and not self._drag_blocked_widget(self.childAt(event.position().toPoint()))
        ):
            self.float_requested.emit()
        super().mouseDoubleClickEvent(event)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self._vertical:
            # For vertical mode, we paint the title rotated.
            # Buttons are hidden; title is painted manually.
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.rotate(-90)
            rect = self.rect()
            painter.drawText(
                -rect.height(), 0, rect.height(), rect.width(),
                Qt.AlignmentFlag.AlignCenter,
                self._title,
            )

    def sizeHint(self) -> QSize:
        if self._vertical:
            sh = super().sizeHint()
            return QSize(sh.height(), sh.width())
        return super().sizeHint()
