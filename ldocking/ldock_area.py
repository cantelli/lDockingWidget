"""LDockArea — one dock strip (LEFT / RIGHT / TOP / BOTTOM).

When empty → hides itself (splitter collapses).
1 dock → shows dock directly.
2+ docks → creates/reuses LDockTabArea.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSizePolicy, QSplitter, QVBoxLayout, QWidget

if TYPE_CHECKING:
    from .ldock_widget import LDockWidget

from .ldock_tab_area import LDockTabArea


class LDockArea(QWidget):
    """One side of an LMainWindow's docking layout."""

    def __init__(
        self,
        area_side: Qt.DockWidgetArea,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._area_side = area_side
        self._docks: list[LDockWidget] = []
        self._tab_area: LDockTabArea | None = None
        self._split_area: QSplitter | None = None
        self._allow_tabs: bool = True
        self._vertical_tabs_opt: bool = False
        self._insertion_order: dict[LDockWidget, int] = {}

        # Determine orientation for tab bar / vertical title bar
        self._vertical = area_side in (
            Qt.DockWidgetArea.LeftDockWidgetArea,
            Qt.DockWidgetArea.RightDockWidgetArea,
        )

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        # Default sizing: expand in docking direction
        if self._vertical:
            self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
            self.setMinimumWidth(40)
        else:
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.setMinimumHeight(40)

        self.hide()  # Start hidden (no docks yet)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    @property
    def area_side(self) -> Qt.DockWidgetArea:
        return self._area_side

    def add_dock(self, dock: LDockWidget, index: int | None = None) -> None:
        if dock in self._docks:
            return
        dock._current_area = self
        if dock not in self._insertion_order:
            self._insertion_order[dock] = len(self._insertion_order)
        self._docks.append(dock)
        self._docks.sort(key=lambda d: self._insertion_order.get(d, 9999))
        self._update_layout()

    def remove_dock(self, dock: LDockWidget) -> None:
        if dock not in self._docks:
            return
        if dock._current_area is self:
            dock._current_area = None
        self._docks.remove(dock)
        self._update_layout()

    def contains(self, dock: LDockWidget) -> bool:
        return dock in self._docks

    def all_docks(self) -> list[LDockWidget]:
        return list(self._docks)

    def set_options(self, allow_tabs: bool, vertical_tabs: bool) -> None:
        changed = allow_tabs != self._allow_tabs or vertical_tabs != self._vertical_tabs_opt
        self._allow_tabs = allow_tabs
        self._vertical_tabs_opt = vertical_tabs
        if self._tab_area is not None:
            self._tab_area.set_vertical_tabs(vertical_tabs)
        if changed:
            self._update_layout()

    # ------------------------------------------------------------------
    # Private: layout transitions
    # ------------------------------------------------------------------

    def _update_layout(self) -> None:
        """Rebuild the area content based on dock count."""
        n = len(self._docks)

        if n == 0:
            self._clear_layout()
            self.hide()
            return

        if n == 1:
            self._destroy_tab_area()
            self._destroy_split_area()
            self._clear_layout()
            dock = self._docks[0]
            dock.setParent(self)
            self._layout.addWidget(dock)
            dock.show()
            self.show()
            return

        # n >= 2: tab mode or split mode
        if self._allow_tabs:
            self._destroy_split_area()
            if self._tab_area is None:
                self._tab_area = LDockTabArea(self, vertical_tabs=self._vertical_tabs_opt)
                self._clear_layout()
                self._layout.addWidget(self._tab_area)

            existing = set(self._tab_area.all_docks())
            for dock in self._docks:
                if dock not in existing:
                    self._layout.removeWidget(dock)
                    self._tab_area.add_dock(dock)
            for dock in list(existing):
                if dock not in self._docks:
                    self._tab_area.remove_dock(dock)
        else:
            self._destroy_tab_area()
            if self._split_area is None:
                orient = (Qt.Orientation.Vertical if self._vertical
                          else Qt.Orientation.Horizontal)
                self._split_area = QSplitter(orient)
                self._clear_layout()
                self._layout.addWidget(self._split_area)

            in_splitter = {self._split_area.widget(i)
                           for i in range(self._split_area.count())}
            for dock in self._docks:
                if dock not in in_splitter:
                    self._layout.removeWidget(dock)
                    dock.setParent(self._split_area)
                    self._split_area.addWidget(dock)
                    dock._title_bar.show()
                    dock.show()
            for dock in list(in_splitter):
                if dock not in self._docks:
                    dock.setParent(None)

        self.show()

    def _clear_layout(self) -> None:
        """Remove all widgets from layout without destroying them."""
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item and item.widget():
                item.widget().hide()
                item.widget().setParent(None)

    def _destroy_tab_area(self) -> None:
        if self._tab_area is not None:
            for dock in self._tab_area.all_docks():
                self._tab_area.remove_dock(dock)
            self._tab_area.setParent(None)
            self._tab_area.deleteLater()
            self._tab_area = None

    def _destroy_split_area(self) -> None:
        if self._split_area is not None:
            for i in range(self._split_area.count()):
                w = self._split_area.widget(i)
                if w is not None:
                    w.setParent(None)
            self._split_area.setParent(None)
            self._split_area.deleteLater()
            self._split_area = None
