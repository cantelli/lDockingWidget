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
        self.setExpanding(False)
        self.setElideMode(Qt.TextElideMode.ElideRight)
        self.setDocumentMode(False)
        self.setDrawBase(True)
        self.setUsesScrollButtons(True)

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
        self._hidden_docks: set[LDockWidget] = set()
        self._exposed_docks: dict[LDockWidget, bool] = {}
        self._last_current_index = -1

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
        self._tab_bar.addTab(dock.windowTitle())
        self._hidden_docks.discard(dock)
        dock._explicitly_hidden = False
        self._exposed_docks.setdefault(dock, False)
        if hasattr(dock, "windowTitleChanged"):
            conn = dock.windowTitleChanged.connect(
                lambda t, d=dock: self._tab_bar.setTabText(self._docks.index(d), t)
            )
            self._title_connections[dock] = conn
        self._sync_visibility()

    def remove_dock(self, dock: LDockWidget) -> None:
        if dock not in self._docks:
            return
        idx = self._docks.index(dock)
        self._docks.pop(idx)
        self._stack.removeWidget(dock)
        dock._title_bar.show()
        dock._set_tabbed_visibility_override(None)
        dock._tab_visibility_sync = True
        dock.show()
        dock._tab_visibility_sync = False
        self._tab_bar.removeTab(idx)
        self._title_connections.pop(dock, None)
        self._hidden_docks.discard(dock)
        self._exposed_docks.pop(dock, None)
        self._sync_visibility()

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
        self._hidden_docks.discard(dock)
        self._tab_bar.setCurrentIndex(self._docks.index(dock))
        self._sync_visibility()

    def set_vertical_tabs(self, vertical: bool) -> None:
        pos = QTabWidget.TabPosition.West if vertical else QTabWidget.TabPosition.South
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
        previous = self.dock_at(self._last_current_index)
        desired = self._normalized_current_index(index)
        self._apply_current_index(desired)
        dock = self.dock_at(desired)
        if dock is not None and dock is not previous:
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

    def handle_dock_visibility_request(self, dock: LDockWidget, visible: bool) -> None:
        if dock not in self._docks:
            return
        current_before = self.current_dock
        was_visible = dock.isVisible()
        if visible:
            self._hidden_docks.discard(dock)
        else:
            self._hidden_docks.add(dock)
            dock._reset_interaction_state()
        desired = self._tab_bar.currentIndex()
        if not visible and current_before is dock:
            desired = self._first_unhidden_index()
        elif visible and desired < 0:
            desired = self._docks.index(dock)
        self._apply_current_index(self._normalized_current_index(desired))
        is_visible = dock.isVisible()
        if visible and not is_visible:
            dock.visibilityChanged.emit(False)
        elif was_visible != is_visible:
            dock._sync_toggle_action_checked()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync_visibility()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._sync_visibility()

    def _first_unhidden_index(self) -> int:
        for index, dock in enumerate(self._docks):
            if dock not in self._hidden_docks:
                return index
        return -1

    def _normalized_current_index(self, preferred: int) -> int:
        if 0 <= preferred < len(self._docks) and self._docks[preferred] not in self._hidden_docks:
            return preferred
        return self._first_unhidden_index()

    def _apply_current_index(self, index: int) -> None:
        if self._tab_bar.currentIndex() != index:
            was_blocked = self._tab_bar.blockSignals(True)
            self._tab_bar.setCurrentIndex(index)
            self._tab_bar.blockSignals(was_blocked)
        self._set_stack_current_index(index)
        self._sync_visibility()

    def _sync_visibility(self) -> None:
        current_index = self._normalized_current_index(self._tab_bar.currentIndex())
        if current_index != self._tab_bar.currentIndex():
            was_blocked = self._tab_bar.blockSignals(True)
            self._tab_bar.setCurrentIndex(current_index)
            self._tab_bar.blockSignals(was_blocked)
        self._set_stack_current_index(current_index)

        tab_area_visible = super().isVisible()
        for index, dock in enumerate(self._docks):
            externally_visible = tab_area_visible and dock not in self._hidden_docks
            exposed = externally_visible and index == current_index
            dock._set_tabbed_visibility_override(externally_visible)
            dock._tab_visibility_sync = True
            if exposed:
                dock.show()
            else:
                dock.hide()
            dock._tab_visibility_sync = False
            previous_exposed = self._exposed_docks.get(dock)
            if previous_exposed is None:
                self._exposed_docks[dock] = exposed
                continue
            if previous_exposed != exposed:
                self._exposed_docks[dock] = exposed
                dock.visibilityChanged.emit(exposed)
        self._last_current_index = current_index

    def _set_stack_current_index(self, index: int) -> None:
        for dock in self._docks:
            dock._tab_visibility_sync = True
        self._stack.setCurrentIndex(index)
        for dock in self._docks:
            dock._tab_visibility_sync = False
