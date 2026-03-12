"""LDockTabArea — QTabBar + QStackedWidget container for 2+ docked widgets."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import (
    QApplication,
    QBoxLayout,
    QStackedWidget,
    QTabBar,
    QWidget,
)

if TYPE_CHECKING:
    from .ldock_widget import LDockWidget


class LTearOffTabBar(QTabBar):
    """QTabBar that initiates a drag when a tab is pulled outside bounds."""

    def __init__(self, tab_area: LDockTabArea) -> None:
        super().__init__(tab_area)
        self._tab_area = tab_area
        self._press_pos: QPoint | None = None
        self._drag_tab: int = -1
        self.setMovable(True)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.globalPosition().toPoint()
            self._drag_tab = self.tabAt(event.position().toPoint())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if (
            self._press_pos is not None
            and self._drag_tab >= 0
            and (event.buttons() & Qt.MouseButton.LeftButton)
        ):
            delta = event.globalPosition().toPoint() - self._press_pos
            if delta.manhattanLength() >= QApplication.startDragDistance():
                dock = self._tab_area.dock_at(self._drag_tab)
                if dock is not None:
                    self._press_pos = None
                    self._drag_tab = -1
                    from .ldrag_manager import LDragManager
                    LDragManager.instance().begin_drag(
                        dock, event.globalPosition().toPoint()
                    )
                    return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._press_pos = None
        self._drag_tab = -1
        super().mouseReleaseEvent(event)


class LDockTabArea(QWidget):
    """Tabbed container for multiple LDockWidgets sharing one dock area slot."""

    def __init__(self, parent: QWidget | None = None, vertical_tabs: bool = False) -> None:
        super().__init__(parent)
        self._docks: list[LDockWidget] = []
        self._title_connections: dict = {}

        self._layout = QBoxLayout(QBoxLayout.Direction.TopToBottom, self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        self._tab_bar = LTearOffTabBar(self)
        self._tab_bar.currentChanged.connect(self._on_tab_changed)
        self._tab_bar.tabMoved.connect(lambda f, t: self._docks.insert(t, self._docks.pop(f)))
        self._layout.addWidget(self._tab_bar)

        self._stack = QStackedWidget()
        self._layout.addWidget(self._stack, 1)

        if vertical_tabs:
            self.set_vertical_tabs(True)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def add_dock(self, dock: LDockWidget) -> None:
        if dock in self._docks:
            return
        self._docks.append(dock)
        self._stack.addWidget(dock)   # dock itself goes in stack (handles reparenting)
        dock._title_bar.hide()        # tab label replaces title bar
        dock.show()
        self._tab_bar.addTab(dock.windowTitle())
        # Keep tab label in sync with dock title
        if hasattr(dock, 'windowTitleChanged'):
            conn = dock.windowTitleChanged.connect(
                lambda t, d=dock: self._tab_bar.setTabText(self._docks.index(d), t)
            )
            self._title_connections[dock] = conn

    def remove_dock(self, dock: LDockWidget) -> None:
        if dock not in self._docks:
            return
        idx = self._docks.index(dock)
        self._docks.pop(idx)
        self._stack.removeWidget(dock)   # unparents dock; content stays inside
        dock._title_bar.show()           # restore title bar
        self._tab_bar.removeTab(idx)
        self._title_connections.pop(dock, None)

    def contains(self, dock: LDockWidget) -> bool:
        return dock in self._docks

    def dock_at(self, index: int) -> LDockWidget | None:
        if 0 <= index < len(self._docks):
            return self._docks[index]
        return None

    @property
    def current_dock(self) -> LDockWidget | None:
        idx = self._tab_bar.currentIndex()
        return self.dock_at(idx)

    def dock_count(self) -> int:
        return len(self._docks)

    def all_docks(self) -> list[LDockWidget]:
        return list(self._docks)

    def set_vertical_tabs(self, vertical: bool) -> None:
        if vertical:
            self._layout.setDirection(QBoxLayout.Direction.LeftToRight)
            self._tab_bar.setShape(QTabBar.Shape.RoundedWest)
        else:
            self._layout.setDirection(QBoxLayout.Direction.TopToBottom)
            self._tab_bar.setShape(QTabBar.Shape.RoundedNorth)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _on_tab_changed(self, index: int) -> None:
        if 0 <= index < self._stack.count():
            self._stack.setCurrentIndex(index)
