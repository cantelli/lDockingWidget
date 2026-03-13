"""LDockTabArea - QTabBar + QStackedWidget container for dock groups."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QBoxLayout,
    QStackedWidget,
    QTabBar,
    QTabWidget,
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
                        dock,
                        event.globalPosition().toPoint(),
                        self._tab_area.drag_payload_for(dock),
                    )
                    return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._press_pos = None
        self._drag_tab = -1
        super().mouseReleaseEvent(event)


class LDockTabArea(QWidget):
    """Tabbed container for multiple LDockWidgets sharing one dock area slot."""

    currentDockChanged = Signal(object)

    def __init__(self, parent: QWidget | None = None, vertical_tabs: bool = False) -> None:
        super().__init__(parent)
        self._docks: list[LDockWidget] = []
        self._title_connections: dict = {}
        self._grouped_dragging = False

        self._layout = QBoxLayout(QBoxLayout.Direction.TopToBottom, self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        self._tab_bar = LTearOffTabBar(self)
        self._tab_bar.currentChanged.connect(self._on_tab_changed)
        self._tab_bar.tabMoved.connect(self._on_tab_moved)
        self._layout.addWidget(self._tab_bar)

        self._stack = QStackedWidget()
        self._layout.addWidget(self._stack, 1)

        if vertical_tabs:
            self.set_vertical_tabs(True)

    def add_dock(self, dock: LDockWidget) -> None:
        if dock in self._docks:
            return
        self._docks.append(dock)
        self._stack.addWidget(dock)
        dock._title_bar.hide()
        dock.show()
        self._tab_bar.addTab(dock.windowTitle())
        if hasattr(dock, "windowTitleChanged"):
            conn = dock.windowTitleChanged.connect(
                lambda t, d=dock: self._tab_bar.setTabText(self._docks.index(d), t)
            )
            self._title_connections[dock] = conn

    def remove_dock(self, dock: LDockWidget) -> None:
        if dock not in self._docks:
            return
        idx = self._docks.index(dock)
        self._docks.pop(idx)
        self._stack.removeWidget(dock)
        dock._title_bar.show()
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
        return self.dock_at(self._tab_bar.currentIndex())

    def dock_count(self) -> int:
        return len(self._docks)

    def all_docks(self) -> list[LDockWidget]:
        return list(self._docks)

    def current_index(self) -> int:
        return self._tab_bar.currentIndex()

    def set_current_dock(self, dock: LDockWidget) -> None:
        if dock not in self._docks:
            return
        self._tab_bar.setCurrentIndex(self._docks.index(dock))

    def set_vertical_tabs(self, vertical: bool) -> None:
        pos = QTabWidget.TabPosition.West if vertical else QTabWidget.TabPosition.North
        self.set_tab_position(pos)

    def set_grouped_dragging(self, grouped_dragging: bool) -> None:
        self._grouped_dragging = grouped_dragging

    def drag_payload_for(self, dock: LDockWidget) -> list[LDockWidget]:
        if self._grouped_dragging and dock in self._docks:
            return list(self._docks)
        return [dock]

    def set_tab_position(self, position: QTabWidget.TabPosition) -> None:
        shape_map = {
            QTabWidget.TabPosition.North: (
                QBoxLayout.Direction.TopToBottom,
                QTabBar.Shape.RoundedNorth,
            ),
            QTabWidget.TabPosition.South: (
                QBoxLayout.Direction.BottomToTop,
                QTabBar.Shape.RoundedSouth,
            ),
            QTabWidget.TabPosition.West: (
                QBoxLayout.Direction.LeftToRight,
                QTabBar.Shape.RoundedWest,
            ),
            QTabWidget.TabPosition.East: (
                QBoxLayout.Direction.RightToLeft,
                QTabBar.Shape.RoundedEast,
            ),
        }
        direction, shape = shape_map.get(
            position, shape_map[QTabWidget.TabPosition.North]
        )
        self._layout.setDirection(direction)
        self._tab_bar.setShape(shape)

    def _on_tab_changed(self, index: int) -> None:
        if 0 <= index < self._stack.count():
            self._stack.setCurrentIndex(index)
            dock = self.dock_at(index)
            if dock is not None:
                self.currentDockChanged.emit(dock)

    def _on_tab_moved(self, from_index: int, to_index: int) -> None:
        if from_index == to_index:
            return
        current_dock = self.current_dock
        self._docks.insert(to_index, self._docks.pop(from_index))
        if current_dock is not None and current_dock in self._docks:
            self._tab_bar.setCurrentIndex(self._docks.index(current_dock))
        parent_area = self.parent()
        if parent_area is not None and hasattr(parent_area, "sync_tab_order"):
            parent_area.sync_tab_order(self._docks)
