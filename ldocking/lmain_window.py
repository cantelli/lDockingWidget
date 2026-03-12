"""LMainWindow — drop-in for QMainWindow using nested QSplitters.

No QDockAreaLayout is ever created.

Layout:
    outer_splitter (Horizontal):
        left_area | inner_splitter | right_area

    inner_splitter (Vertical):
        top_area | central_widget | bottom_area
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMenu,
    QMenuBar,
    QSplitter,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

_DEFAULT_DOCK_OPTIONS = (
    QMainWindow.DockOption.AnimatedDocks
    | QMainWindow.DockOption.AllowTabbedDocks
)

from .ldock_area import LDockArea
from .enums import (
    AllDockWidgetAreas,
    AllowNestedDocks,
    AllowTabbedDocks,
    AnimatedDocks,
    BottomDockWidgetArea,
    DockOption,
    DockOptions,
    DockWidgetArea,
    ForceTabbedDocks,
    GroupedDragging,
    LeftDockWidgetArea,
    NoDockWidgetArea,
    RightDockWidgetArea,
    TopDockWidgetArea,
    VerticalTabs,
)

if TYPE_CHECKING:
    from .ldock_widget import LDockWidget


class LMainWindow(QWidget):
    """Top-level window with splitter-based dock layout.

    Replaces QMainWindow to avoid QDockAreaLayout entirely.
    """

    # Mirror QMainWindow class-level enum attributes (monkey-patch compatibility)
    DockOption = DockOption
    DockOptions = DockOptions
    AnimatedDocks = AnimatedDocks
    AllowNestedDocks = AllowNestedDocks
    AllowTabbedDocks = AllowTabbedDocks
    ForceTabbedDocks = ForceTabbedDocks
    VerticalTabs = VerticalTabs
    GroupedDragging = GroupedDragging
    DockWidgetArea = DockWidgetArea
    LeftDockWidgetArea = LeftDockWidgetArea
    RightDockWidgetArea = RightDockWidgetArea
    TopDockWidgetArea = TopDockWidgetArea
    BottomDockWidgetArea = BottomDockWidgetArea
    AllDockWidgetAreas = AllDockWidgetAreas
    NoDockWidgetArea = NoDockWidgetArea

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._central_widget: QWidget | None = None
        self._menu_bar: QMenuBar | None = None
        self._status_bar: QStatusBar | None = None
        self._tool_bars: list[QToolBar] = []
        self._dock_map: dict[LDockWidget, Qt.DockWidgetArea] = {}
        self._dock_options = _DEFAULT_DOCK_OPTIONS

        self._build_layout()

    # ------------------------------------------------------------------
    # Layout setup
    # ------------------------------------------------------------------

    def _build_layout(self) -> None:
        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(0)

        # Menu bar placeholder (inserted dynamically)
        self._menu_bar_slot = QWidget()
        self._menu_bar_slot.setMaximumHeight(0)
        self._root_layout.addWidget(self._menu_bar_slot)

        # Tool bar container
        self._toolbar_container = QWidget()
        self._toolbar_layout = QVBoxLayout(self._toolbar_container)
        self._toolbar_layout.setContentsMargins(0, 0, 0, 0)
        self._toolbar_layout.setSpacing(0)
        self._toolbar_container.setMaximumHeight(0)
        self._root_layout.addWidget(self._toolbar_container)

        # Main content: outer_splitter
        self._outer_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._root_layout.addWidget(self._outer_splitter, 1)

        # Dock areas
        self._dock_areas: dict[Qt.DockWidgetArea, LDockArea] = {
            LeftDockWidgetArea: LDockArea(LeftDockWidgetArea),
            RightDockWidgetArea: LDockArea(RightDockWidgetArea),
            TopDockWidgetArea: LDockArea(TopDockWidgetArea),
            BottomDockWidgetArea: LDockArea(BottomDockWidgetArea),
        }

        # Inner splitter (vertical: top + central + bottom)
        self._inner_splitter = QSplitter(Qt.Orientation.Vertical)

        self._inner_splitter.addWidget(self._dock_areas[TopDockWidgetArea])

        # Central widget placeholder
        self._central_placeholder = QWidget()
        self._inner_splitter.addWidget(self._central_placeholder)

        self._inner_splitter.addWidget(self._dock_areas[BottomDockWidgetArea])
        self._inner_splitter.setStretchFactor(1, 1)  # central gets stretch

        # Outer splitter: left | inner | right
        self._outer_splitter.addWidget(self._dock_areas[LeftDockWidgetArea])
        self._outer_splitter.addWidget(self._inner_splitter)
        self._outer_splitter.addWidget(self._dock_areas[RightDockWidgetArea])
        self._outer_splitter.setStretchFactor(1, 1)  # inner gets stretch

        # Status bar
        self._status_bar_widget = QStatusBar()
        self._root_layout.addWidget(self._status_bar_widget)
        self._status_bar = self._status_bar_widget

    # ------------------------------------------------------------------
    # Public API (mirrors QMainWindow)
    # ------------------------------------------------------------------

    def setDockOptions(self, options: QMainWindow.DockOption) -> None:
        self._dock_options = options
        allow_tabs = bool(options & (
            QMainWindow.DockOption.AllowTabbedDocks
            | QMainWindow.DockOption.ForceTabbedDocks
        ))
        vertical_tabs = bool(options & QMainWindow.DockOption.VerticalTabs)
        for area in self._dock_areas.values():
            area.set_options(allow_tabs=allow_tabs, vertical_tabs=vertical_tabs)

    def dockOptions(self) -> QMainWindow.DockOption:
        return self._dock_options

    def setCorner(
        self,
        corner: Qt.Corner,
        area: Qt.DockWidgetArea,
    ) -> None:
        """No-op: corner ownership is implicit in the splitter layout."""

    def setCentralWidget(self, widget: QWidget) -> None:
        if self._central_widget is not None:
            self._central_widget.setParent(None)
        self._central_widget = widget
        idx = self._inner_splitter.indexOf(self._central_placeholder)
        if idx >= 0:
            self._inner_splitter.replaceWidget(idx, widget)
            self._central_placeholder = widget
        else:
            self._inner_splitter.addWidget(widget)
        widget.show()

    def centralWidget(self) -> QWidget | None:
        return self._central_widget

    def addDockWidget(
        self, area: Qt.DockWidgetArea, dock: LDockWidget
    ) -> None:
        from .ldock_widget import LDockWidget as _LDW

        dock._main_window = self

        # Determine re-insertion index for floating docks returning to their original area
        pos = None
        if (dock._floating
                and getattr(dock, '_pre_float_area_side', None) == area
                and getattr(dock, '_pre_float_position', None) is not None):
            pos = dock._pre_float_position

        # Idempotent: already in this area and not floating — nothing to do
        if self._dock_map.get(dock) == area and not dock._floating:
            return

        dock._floating = False

        # Remove from wherever it currently lives
        if dock in self._dock_map:
            old_area = self._dock_map[dock]
            self._dock_areas[old_area].remove_dock(dock)

        self._dock_map[dock] = area
        self._dock_areas[area].add_dock(dock, index=pos)
        dock.setWindowFlags(Qt.WindowType.Widget)  # clear any stale floating flags
        dock.dockLocationChanged.emit(area)
        dock._title_bar.set_float_button_icon(False)

    def removeDockWidget(self, dock: LDockWidget) -> None:
        if dock not in self._dock_map:
            return
        area = self._dock_map.pop(dock)
        self._dock_areas[area].remove_dock(dock)

    def dockWidgetArea(self, dock: LDockWidget) -> Qt.DockWidgetArea:
        return self._dock_map.get(dock, Qt.DockWidgetArea.NoDockWidgetArea)

    def tabifyDockWidget(
        self, first: LDockWidget, second: LDockWidget
    ) -> None:
        """Place ``second`` in the same area as ``first``."""
        if first not in self._dock_map:
            return
        area = self._dock_map[first]
        self.addDockWidget(area, second)

    def tabifiedDockWidgets(self, dock: LDockWidget) -> list[LDockWidget]:
        """Return the list of dock widgets tabbed with *dock* (excluding *dock* itself)."""
        area = self._dock_map.get(dock)
        if area is None:
            return []
        dock_area = self._dock_areas[area]
        if dock_area._tab_area is None:
            return []
        return [d for d in dock_area._tab_area.all_docks() if d is not dock]

    def resizeDocks(
        self,
        docks: list[LDockWidget],
        sizes: list[int],
        orientation: Qt.Orientation,
    ) -> None:
        """Resize dock areas analogous to QMainWindow.resizeDocks."""
        splitter = (
            self._outer_splitter
            if orientation == Qt.Orientation.Horizontal
            else self._inner_splitter
        )
        current = splitter.sizes()
        # Map dock areas to splitter indices
        for dock, size in zip(docks, sizes):
            if dock not in self._dock_map:
                continue
            area = self._dock_map[dock]
            idx = splitter.indexOf(self._dock_areas[area])
            if 0 <= idx < len(current):
                current[idx] = size
        splitter.setSizes(current)

    def setMenuBar(self, menu_bar: QMenuBar) -> None:
        if self._menu_bar is not None:
            self._menu_bar.setParent(None)
        self._menu_bar = menu_bar
        # Replace slot widget with the real menu bar
        idx = self._root_layout.indexOf(self._menu_bar_slot)
        self._menu_bar_slot.setParent(None)
        self._root_layout.insertWidget(idx, menu_bar)

    def menuBar(self) -> QMenuBar:
        if self._menu_bar is None:
            self._menu_bar = QMenuBar(self)
            idx = self._root_layout.indexOf(self._menu_bar_slot)
            self._menu_bar_slot.setParent(None)
            self._root_layout.insertWidget(idx, self._menu_bar)
        return self._menu_bar

    def setMenuWidget(self, widget: QWidget) -> None:
        """Set a custom widget in the menu bar slot (QMainWindow compat)."""
        if self._menu_bar is not None:
            self._menu_bar.setParent(None)
        self._menu_bar = widget  # type: ignore[assignment]
        idx = self._root_layout.indexOf(self._menu_bar_slot)
        self._menu_bar_slot.setParent(None)
        self._root_layout.insertWidget(idx, widget)

    def menuWidget(self) -> QWidget | None:
        """Return the widget in the menu bar slot (QMainWindow compat)."""
        return self._menu_bar

    def addToolBar(self, toolbar_or_title_or_area, toolbar: QToolBar | None = None) -> QToolBar:
        # Overload: addToolBar(toolbar), addToolBar(title), addToolBar(area, toolbar)
        if toolbar is not None:
            # addToolBar(area, toolbar) — area is ignored (only top row supported)
            tb = toolbar
        elif isinstance(toolbar_or_title_or_area, str):
            tb = QToolBar(toolbar_or_title_or_area)
        else:
            tb = toolbar_or_title_or_area
        self._tool_bars.append(tb)
        self._toolbar_layout.addWidget(tb)
        self._toolbar_container.setMaximumHeight(16777215)
        return tb

    def removeToolBar(self, toolbar: QToolBar) -> None:
        if toolbar in self._tool_bars:
            self._tool_bars.remove(toolbar)
            toolbar.setParent(None)
            if not self._tool_bars:
                self._toolbar_container.setMaximumHeight(0)

    def insertToolBar(self, before: QToolBar, toolbar: QToolBar) -> None:
        if toolbar in self._tool_bars:
            self._tool_bars.remove(toolbar)
            toolbar.setParent(None)
        idx = self._tool_bars.index(before) if before in self._tool_bars else len(self._tool_bars)
        self._tool_bars.insert(idx, toolbar)
        self._toolbar_layout.insertWidget(idx, toolbar)
        self._toolbar_container.setMaximumHeight(16777215)

    def toolBars(self) -> list[QToolBar]:
        return list(self._tool_bars)

    def toolBarArea(self, toolbar: QToolBar) -> Qt.ToolBarArea:
        return Qt.ToolBarArea.TopToolBarArea

    def addToolBarBreak(self, area: Qt.ToolBarArea = Qt.ToolBarArea.TopToolBarArea) -> None:
        pass  # single toolbar row — line breaks not supported

    def removeToolBarBreak(self, before: QToolBar) -> None:
        pass

    def insertToolBarBreak(self, before: QToolBar) -> None:
        pass

    def toolBarBreak(self, toolbar: QToolBar) -> bool:
        return False

    def statusBar(self) -> QStatusBar:
        return self._status_bar

    def setStatusBar(self, status_bar: QStatusBar) -> None:
        if self._status_bar is not None:
            self._status_bar.setParent(None)
        self._status_bar = status_bar
        self._root_layout.addWidget(status_bar)

    def createPopupMenu(self) -> QMenu | None:
        """Return a QMenu with toggle actions for all docks and toolbars.

        Mirrors QMainWindow.createPopupMenu(). Returns None if there are
        no docks or toolbars registered.
        """
        docks = list(self._dock_map)
        toolbars = self._tool_bars
        if not docks and not toolbars:
            return None
        menu = QMenu(self)
        for dock in docks:
            menu.addAction(dock.toggleViewAction())
        if docks and toolbars:
            menu.addSeparator()
        for toolbar in toolbars:
            menu.addAction(toolbar.toggleViewAction())
        return menu

    # ------------------------------------------------------------------
    # State persistence (mirrors QMainWindow.saveState / restoreState)
    # ------------------------------------------------------------------

    def saveState(self, version: int = 0) -> QByteArray:
        """Serialize the current dock layout to a QByteArray.

        Docks are identified by objectName() (preferred, follows Qt convention)
        with windowTitle() as fallback. Docks that have neither are skipped.

        Pass the returned value to restoreState() to re-apply the layout.
        """
        docks_state = []
        for dock, area in self._dock_map.items():
            ident = dock.objectName() or dock.windowTitle()
            if not ident:
                continue
            area_docks = self._dock_areas[area]._docks
            tab_index = area_docks.index(dock) if dock in area_docks else 0
            entry: dict = {
                "id": ident,
                "area": area.value,
                "tab_index": tab_index,
                "floating": dock._floating,
            }
            if dock._floating:
                g = dock.geometry()
                entry["geometry"] = [g.x(), g.y(), g.width(), g.height()]
            docks_state.append(entry)

        payload = {
            "version": 1,
            "outer_splitter": self._outer_splitter.sizes(),
            "inner_splitter": self._inner_splitter.sizes(),
            "docks": docks_state,
        }
        return QByteArray(json.dumps(payload).encode())

    def restoreState(self, state: QByteArray, version: int = 0) -> bool:
        """Restore dock layout from a QByteArray produced by saveState().

        Docks are matched by objectName() (preferred) or windowTitle().
        Unrecognised dock IDs are silently skipped.
        Returns False if the data is invalid or the version does not match.
        """
        try:
            data = json.loads(bytes(state).decode())
            if data.get("version") != 1:
                return False

            # Build identity → dock lookup from currently registered docks
            lookup: dict[str, LDockWidget] = {}
            for dock in list(self._dock_map):
                ident = dock.objectName() or dock.windowTitle()
                if ident:
                    lookup[ident] = dock

            entries = sorted(
                data.get("docks", []), key=lambda e: e.get("tab_index", 0)
            )

            # Place each dock in its saved area (or float it)
            for entry in entries:
                dock = lookup.get(entry["id"])
                if dock is None:
                    continue
                area = Qt.DockWidgetArea(entry["area"])
                self.addDockWidget(area, dock)
                if entry.get("floating"):
                    g = entry.get("geometry")
                    dock._float_out()
                    if g:
                        dock.setGeometry(g[0], g[1], g[2], g[3])

            # Restore tab order within each area
            area_saved: dict = {}
            for entry in entries:
                if entry.get("floating"):
                    continue
                dock = lookup.get(entry["id"])
                if dock is None:
                    continue
                area = Qt.DockWidgetArea(entry["area"])
                area_saved.setdefault(area, []).append(
                    (dock, entry.get("tab_index", 0))
                )

            for area, pairs in area_saved.items():
                area_obj = self._dock_areas[area]
                for dock, idx in pairs:
                    area_obj._insertion_order[dock] = idx
                area_obj._docks.sort(
                    key=lambda d: area_obj._insertion_order.get(d, 9999)
                )
                area_obj._update_layout()

            # Restore splitter sizes
            outer = data.get("outer_splitter")
            if outer:
                self._outer_splitter.setSizes(outer)
            inner = data.get("inner_splitter")
            if inner:
                self._inner_splitter.setSizes(inner)

            return True
        except Exception:
            return False
