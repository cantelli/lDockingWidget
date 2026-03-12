"""LMainWindow - drop-in for QMainWindow using nested QSplitters.

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
    QMainWindow,
    QMenu,
    QMenuBar,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

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
from .ldock_area import LDockArea

if TYPE_CHECKING:
    from .ldock_widget import LDockWidget


_STATE_FORMAT_VERSION = 1
_DEFAULT_DOCK_OPTIONS = (
    QMainWindow.DockOption.AnimatedDocks
    | QMainWindow.DockOption.AllowTabbedDocks
)


class LMainWindow(QWidget):
    """Top-level window with splitter-based dock layout."""

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
        self._menu_bar: QWidget | None = None
        self._status_bar: QStatusBar | None = None
        self._tool_bars: list[QToolBar] = []
        self._dock_map: dict[LDockWidget, Qt.DockWidgetArea] = {}
        self._dock_options = _DEFAULT_DOCK_OPTIONS

        self._build_layout()

    def _build_layout(self) -> None:
        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(0)

        self._menu_bar_slot = QWidget()
        self._menu_bar_slot.setMaximumHeight(0)
        self._root_layout.addWidget(self._menu_bar_slot)

        self._toolbar_container = QWidget()
        self._toolbar_layout = QVBoxLayout(self._toolbar_container)
        self._toolbar_layout.setContentsMargins(0, 0, 0, 0)
        self._toolbar_layout.setSpacing(0)
        self._toolbar_container.setMaximumHeight(0)
        self._root_layout.addWidget(self._toolbar_container)

        self._outer_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._root_layout.addWidget(self._outer_splitter, 1)

        self._dock_areas: dict[Qt.DockWidgetArea, LDockArea] = {
            LeftDockWidgetArea: LDockArea(LeftDockWidgetArea),
            RightDockWidgetArea: LDockArea(RightDockWidgetArea),
            TopDockWidgetArea: LDockArea(TopDockWidgetArea),
            BottomDockWidgetArea: LDockArea(BottomDockWidgetArea),
        }

        self._inner_splitter = QSplitter(Qt.Orientation.Vertical)
        self._inner_splitter.addWidget(self._dock_areas[TopDockWidgetArea])

        self._central_placeholder = QWidget()
        self._inner_splitter.addWidget(self._central_placeholder)

        self._inner_splitter.addWidget(self._dock_areas[BottomDockWidgetArea])
        self._inner_splitter.setStretchFactor(1, 1)

        self._outer_splitter.addWidget(self._dock_areas[LeftDockWidgetArea])
        self._outer_splitter.addWidget(self._inner_splitter)
        self._outer_splitter.addWidget(self._dock_areas[RightDockWidgetArea])
        self._outer_splitter.setStretchFactor(1, 1)

        self._status_bar_widget = QStatusBar()
        self._root_layout.addWidget(self._status_bar_widget)
        self._status_bar = self._status_bar_widget

    def setDockOptions(self, options: QMainWindow.DockOption) -> None:
        self._dock_options = options
        allow_tabs = bool(
            options
            & (
                QMainWindow.DockOption.AllowTabbedDocks
                | QMainWindow.DockOption.ForceTabbedDocks
            )
        )
        vertical_tabs = bool(options & QMainWindow.DockOption.VerticalTabs)
        for area in self._dock_areas.values():
            area.set_options(allow_tabs=allow_tabs, vertical_tabs=vertical_tabs)

    def dockOptions(self) -> QMainWindow.DockOption:
        return self._dock_options

    def setTabPosition(
        self, area: Qt.DockWidgetArea, position: QTabWidget.TabPosition
    ) -> None:
        dock_area = self._dock_areas.get(area)
        if dock_area is not None:
            dock_area.set_tab_position(position)

    def tabPosition(self, area: Qt.DockWidgetArea) -> QTabWidget.TabPosition:
        dock_area = self._dock_areas.get(area)
        if dock_area is not None:
            return dock_area.get_tab_position()
        return QTabWidget.TabPosition.North

    def setCorner(self, corner: Qt.Corner, area: Qt.DockWidgetArea) -> None:
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

    def addDockWidget(self, area: Qt.DockWidgetArea, dock: LDockWidget) -> None:
        resolved_area = self._resolve_dock_area(dock, area)
        if resolved_area is None:
            return
        if resolved_area not in self._dock_areas:
            raise ValueError(f"Unsupported dock area: {area!r}")

        dock._main_window = self

        pos = None
        if (
            dock._floating
            and getattr(dock, "_pre_float_area_side", None) == resolved_area
            and getattr(dock, "_pre_float_position", None) is not None
        ):
            pos = dock._pre_float_position

        if self._dock_map.get(dock) == resolved_area and not dock._floating:
            return

        dock._floating = False
        dock.setParent(None)

        if dock in self._dock_map:
            old_area = self._dock_map[dock]
            self._dock_areas[old_area].remove_dock(dock)

        self._dock_map[dock] = resolved_area
        self._dock_areas[resolved_area].add_dock(dock, index=pos)
        dock.setWindowFlags(Qt.WindowType.Widget)
        dock.dockLocationChanged.emit(resolved_area)
        dock._title_bar.set_float_button_icon(False)

    def removeDockWidget(self, dock: LDockWidget) -> None:
        if dock not in self._dock_map:
            return
        area = self._dock_map.pop(dock)
        self._dock_areas[area].remove_dock(dock)

    def dockWidgetArea(self, dock: LDockWidget) -> Qt.DockWidgetArea:
        return self._dock_map.get(dock, Qt.DockWidgetArea.NoDockWidgetArea)

    def tabifyDockWidget(self, first: LDockWidget, second: LDockWidget) -> None:
        if first not in self._dock_map:
            return
        area = self._dock_map[first]
        if not second.isAreaAllowed(area):
            return
        self.addDockWidget(area, second)

    def tabifiedDockWidgets(self, dock: LDockWidget) -> list[LDockWidget]:
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
        splitter = (
            self._outer_splitter
            if orientation == Qt.Orientation.Horizontal
            else self._inner_splitter
        )
        current = splitter.sizes()
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
        idx = self._root_layout.indexOf(self._menu_bar_slot)
        self._menu_bar_slot.setParent(None)
        self._root_layout.insertWidget(idx, menu_bar)

    def menuBar(self) -> QMenuBar:
        if self._menu_bar is None:
            self._menu_bar = QMenuBar(self)
            idx = self._root_layout.indexOf(self._menu_bar_slot)
            self._menu_bar_slot.setParent(None)
            self._root_layout.insertWidget(idx, self._menu_bar)
        return self._menu_bar  # type: ignore[return-value]

    def setMenuWidget(self, widget: QWidget) -> None:
        if self._menu_bar is not None:
            self._menu_bar.setParent(None)
        self._menu_bar = widget
        idx = self._root_layout.indexOf(self._menu_bar_slot)
        self._menu_bar_slot.setParent(None)
        self._root_layout.insertWidget(idx, widget)

    def menuWidget(self) -> QWidget | None:
        return self._menu_bar

    def addToolBar(
        self, toolbar_or_title_or_area, toolbar: QToolBar | None = None
    ) -> QToolBar:
        if toolbar is not None:
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
        idx = (
            self._tool_bars.index(before)
            if before in self._tool_bars
            else len(self._tool_bars)
        )
        self._tool_bars.insert(idx, toolbar)
        self._toolbar_layout.insertWidget(idx, toolbar)
        self._toolbar_container.setMaximumHeight(16777215)

    def toolBars(self) -> list[QToolBar]:
        return list(self._tool_bars)

    def toolBarArea(self, toolbar: QToolBar) -> Qt.ToolBarArea:
        return Qt.ToolBarArea.TopToolBarArea

    def addToolBarBreak(
        self, area: Qt.ToolBarArea = Qt.ToolBarArea.TopToolBarArea
    ) -> None:
        pass

    def removeToolBarBreak(self, before: QToolBar) -> None:
        pass

    def insertToolBarBreak(self, before: QToolBar) -> None:
        pass

    def toolBarBreak(self, toolbar: QToolBar) -> bool:
        return False

    def statusBar(self) -> QStatusBar:
        return self._status_bar  # type: ignore[return-value]

    def setStatusBar(self, status_bar: QStatusBar) -> None:
        if self._status_bar is not None:
            self._status_bar.setParent(None)
        self._status_bar = status_bar
        self._root_layout.addWidget(status_bar)

    def createPopupMenu(self) -> QMenu | None:
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

    def _resolve_dock_area(
        self, dock: LDockWidget, preferred_area: Qt.DockWidgetArea
    ) -> Qt.DockWidgetArea | None:
        if dock.isAreaAllowed(preferred_area):
            return preferred_area
        for area in (
            LeftDockWidgetArea,
            RightDockWidgetArea,
            TopDockWidgetArea,
            BottomDockWidgetArea,
        ):
            if dock.isAreaAllowed(area):
                return area
        return None

    def saveState(self, version: int = 0) -> QByteArray:
        docks_state = []
        for dock, area in self._dock_map.items():
            ident = dock.objectName() or dock.windowTitle()
            if not ident:
                continue
            area_docks = self._dock_areas[area]._docks
            tab_index = area_docks.index(dock) if dock in area_docks else 0
            entry: dict[str, object] = {
                "id": ident,
                "area": area.value,
                "tab_index": tab_index,
                "floating": dock._floating,
            }
            if dock._floating:
                g = dock.geometry()
                entry["geometry"] = [g.x(), g.y(), g.width(), g.height()]
            docks_state.append(entry)

        current_tabs: dict[str, str] = {}
        for area, area_obj in self._dock_areas.items():
            current_dock = area_obj.current_tab_dock()
            if current_dock is None:
                continue
            ident = current_dock.objectName() or current_dock.windowTitle()
            if ident:
                current_tabs[str(area.value)] = ident

        payload = {
            "format_version": _STATE_FORMAT_VERSION,
            "state_version": version,
            "outer_splitter": self._outer_splitter.sizes(),
            "inner_splitter": self._inner_splitter.sizes(),
            "docks": docks_state,
            "current_tabs": current_tabs,
        }
        return QByteArray(json.dumps(payload).encode())

    def restoreState(self, state: QByteArray, version: int = 0) -> bool:
        try:
            data = json.loads(bytes(state).decode())
            if (
                data.get("format_version", data.get("version"))
                != _STATE_FORMAT_VERSION
            ):
                return False
            if data.get("state_version", 0) != version:
                return False

            lookup: dict[str, LDockWidget] = {}
            for dock in list(self._dock_map):
                ident = dock.objectName() or dock.windowTitle()
                if ident:
                    lookup[ident] = dock

            entries = sorted(
                data.get("docks", []), key=lambda e: e.get("tab_index", 0)
            )

            for entry in entries:
                dock = lookup.get(entry["id"])
                if dock is None:
                    continue
                area = Qt.DockWidgetArea(entry["area"])
                if entry.get("floating"):
                    dock._pre_float_area_side = area
                    dock._pre_float_position = entry.get("tab_index", 0)
                    dock._float_out()
                    g = entry.get("geometry")
                    if g:
                        dock.setGeometry(g[0], g[1], g[2], g[3])
                else:
                    self.addDockWidget(area, dock)

            area_saved: dict[Qt.DockWidgetArea, list[tuple[LDockWidget, int]]] = {}
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

            for area_value, dock_id in data.get("current_tabs", {}).items():
                dock = lookup.get(dock_id)
                if dock is None:
                    continue
                area = Qt.DockWidgetArea(int(area_value))
                area_obj = self._dock_areas.get(area)
                if area_obj is not None:
                    area_obj.set_current_tab_dock(dock)

            outer = data.get("outer_splitter")
            if outer:
                self._outer_splitter.setSizes(outer)
            inner = data.get("inner_splitter")
            if inner:
                self._inner_splitter.setSizes(inner)

            return True
        except Exception:
            return False
