"""LMainWindow - drop-in for QMainWindow using a tree-backed splitter layout."""
from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QHBoxLayout,
    QLabel,
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
from .stylesheet_compat import translate_stylesheet

if TYPE_CHECKING:
    from .ldock_widget import LDockWidget


_STATE_FORMAT_VERSION = 1
_DEFAULT_DOCK_OPTIONS = (
    QMainWindow.DockOption.AnimatedDocks
    | QMainWindow.DockOption.AllowTabbedDocks
)


@dataclass
class _WidgetLeaf:
    widget: QWidget
    key: str
    area_state: object | None = None


@dataclass
class _SplitTree:
    orientation: Qt.Orientation
    children: list[object] = field(default_factory=list)
    key: str = ""
    sizes: list[int] = field(default_factory=list)


class _CompatSplitter(QSplitter):
    def __init__(self, orientation: Qt.Orientation, parent: QWidget | None = None) -> None:
        super().__init__(orientation, parent)
        self._reported_sizes: list[int] | None = None

    def setSizes(self, list_: list[int]) -> None:  # type: ignore[override]
        self._reported_sizes = list(list_)
        super().setSizes(list_)

    def sizes(self) -> list[int]:  # type: ignore[override]
        return list(self._reported_sizes) if self._reported_sizes is not None else super().sizes()


class LMainWindow(QWidget):
    """Top-level window with tree-backed splitter dock layout."""

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
        self.setProperty("class", "QMainWindow")
        self._central_widget: QWidget | None = None
        self._menu_bar: QWidget | None = None
        self._status_bar: QStatusBar | None = None
        self._tool_bars: list[QToolBar] = []
        self._toolbar_area_map: dict[QToolBar, Qt.ToolBarArea] = {}
        self._toolbar_rows: dict[Qt.ToolBarArea, list[list[QToolBar]]] = {}
        self._pending_toolbar_breaks: set[Qt.ToolBarArea] = set()
        self._corner_owners: dict[Qt.Corner, Qt.DockWidgetArea] = {
            Qt.Corner.TopLeftCorner: TopDockWidgetArea,
            Qt.Corner.TopRightCorner: TopDockWidgetArea,
            Qt.Corner.BottomLeftCorner: BottomDockWidgetArea,
            Qt.Corner.BottomRightCorner: BottomDockWidgetArea,
        }
        self._dock_map: dict[LDockWidget, Qt.DockWidgetArea] = {}
        self._pending_dock_restore: dict[str, dict[str, object]] = {}
        self._dock_options = _DEFAULT_DOCK_OPTIONS

        self._build_layout()

    def _build_layout(self) -> None:
        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(0)

        self._menu_bar_slot = QWidget()
        self._menu_bar_slot.setMaximumHeight(0)
        self._root_layout.addWidget(self._menu_bar_slot)

        self._toolbar_containers: dict[Qt.ToolBarArea, QWidget] = {}
        self._toolbar_layouts: dict[Qt.ToolBarArea, QHBoxLayout | QVBoxLayout] = {}
        for area in (
            Qt.ToolBarArea.TopToolBarArea,
            Qt.ToolBarArea.LeftToolBarArea,
            Qt.ToolBarArea.RightToolBarArea,
            Qt.ToolBarArea.BottomToolBarArea,
        ):
            container = QWidget()
            layout: QHBoxLayout | QVBoxLayout
            if area in (
                Qt.ToolBarArea.TopToolBarArea,
                Qt.ToolBarArea.BottomToolBarArea,
            ):
                layout = QVBoxLayout(container)
                container.setMaximumHeight(0)
            else:
                layout = QHBoxLayout(container)
                container.setMaximumWidth(0)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            self._toolbar_containers[area] = container
            self._toolbar_layouts[area] = layout
            self._toolbar_rows[area] = []
        self._root_layout.addWidget(self._toolbar_containers[Qt.ToolBarArea.TopToolBarArea])

        self._main_host = QWidget()
        self._main_layout = QHBoxLayout(self._main_host)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)
        self._main_layout.addWidget(self._toolbar_containers[Qt.ToolBarArea.LeftToolBarArea])

        self._content_host = QWidget()
        self._content_layout = QVBoxLayout(self._content_host)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(0)
        self._main_layout.addWidget(self._content_host, 1)
        self._main_layout.addWidget(self._toolbar_containers[Qt.ToolBarArea.RightToolBarArea])

        self._root_layout.addWidget(self._main_host, 1)
        self._root_layout.addWidget(self._toolbar_containers[Qt.ToolBarArea.BottomToolBarArea])

        self._dock_areas: dict[Qt.DockWidgetArea, LDockArea] = {
            LeftDockWidgetArea: LDockArea(LeftDockWidgetArea),
            RightDockWidgetArea: LDockArea(RightDockWidgetArea),
            TopDockWidgetArea: LDockArea(TopDockWidgetArea),
            BottomDockWidgetArea: LDockArea(BottomDockWidgetArea),
        }
        self._central_placeholder = QWidget()
        self._content_tree: object = _WidgetLeaf(self._central_placeholder, "central")
        self._outer_splitter: QSplitter | None = None
        self._inner_splitter: QSplitter | None = None
        self._rebuild_content_tree()

        self._status_bar: QStatusBar | None = None
        self._apply_corner_ownership()

    def _rebuild_content_tree(self) -> None:
        self._detach_reusable_widgets()
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item and item.widget():
                item.widget().setParent(None)

        self._outer_splitter = None
        self._inner_splitter = None
        self._refresh_split_keys()
        root_widget = self._build_tree_widget(self._content_tree, self._content_host)
        self._content_layout.addWidget(root_widget)

    def _detach_reusable_widgets(self) -> None:
        reusable = list(self._dock_areas.values())
        if self._central_placeholder is not None:
            reusable.append(self._central_placeholder)
        if self._central_widget is not None and self._central_widget not in reusable:
            reusable.append(self._central_widget)
        for widget in reusable:
            if widget.parent() is not None:
                widget.setParent(None)

    def _build_tree_widget(self, node: object, parent: QWidget) -> QWidget:
        if isinstance(node, _WidgetLeaf):
            node.widget.setParent(parent)
            node.widget.show()
            return node.widget

        splitter = _CompatSplitter(node.orientation, parent)
        if node.key == "outer":
            self._outer_splitter = splitter
        elif node.key == "inner":
            self._inner_splitter = splitter
        for child in node.children:
            splitter.addWidget(self._build_tree_widget(child, splitter))
        if node.sizes:
            splitter.setSizes(node.sizes)
        else:
            if node.key == "inner":
                splitter.setStretchFactor(1, 1)
            if node.key == "outer":
                splitter.setStretchFactor(1, 1)
        return splitter

    def _leaf_for_key(self, key: str) -> _WidgetLeaf | None:
        return self._find_leaf(self._content_tree, key)

    def _find_leaf(self, node: object, key: str) -> _WidgetLeaf | None:
        if isinstance(node, _WidgetLeaf):
            return node if node.key == key else None
        for child in node.children:
            found = self._find_leaf(child, key)
            if found is not None:
                return found
        return None

    def _refresh_split_keys(self) -> None:
        self._clear_split_keys(self._content_tree)
        horizontal = self._nearest_split_containing_key(
            self._content_tree, "central", Qt.Orientation.Horizontal
        )
        vertical = self._nearest_split_containing_key(
            self._content_tree, "central", Qt.Orientation.Vertical
        )
        if horizontal is not None:
            horizontal.key = "outer"
        if vertical is not None:
            vertical.key = "inner"

    def _clear_split_keys(self, node: object) -> None:
        if isinstance(node, _SplitTree):
            node.key = ""
            for child in node.children:
                self._clear_split_keys(child)

    def _nearest_split_containing_key(
        self,
        node: object,
        key: str,
        orientation: Qt.Orientation,
    ) -> _SplitTree | None:
        if isinstance(node, _WidgetLeaf):
            return None
        if not self._subtree_contains_key(node, key):
            return None
        if node.orientation == orientation:
            return node
        for child in node.children:
            found = self._nearest_split_containing_key(child, key, orientation)
            if found is not None:
                return found
        return None

    def _subtree_contains_key(self, node: object, key: str) -> bool:
        if isinstance(node, _WidgetLeaf):
            return node.key == key
        return any(self._subtree_contains_key(child, key) for child in node.children)

    def _side_key(self, area: Qt.DockWidgetArea) -> str:
        return {
            LeftDockWidgetArea: "left",
            RightDockWidgetArea: "right",
            TopDockWidgetArea: "top",
            BottomDockWidgetArea: "bottom",
        }[area]

    def _leaf_for_area(self, area: Qt.DockWidgetArea) -> _WidgetLeaf | None:
        return self._leaf_for_key(self._side_key(area))

    def _ensure_area_leaf(self, area: Qt.DockWidgetArea) -> None:
        key = self._side_key(area)
        if self._leaf_for_key(key) is not None:
            return
        leaf = _WidgetLeaf(self._dock_areas[area], key, self._dock_areas[area].export_state())
        self._content_tree = self._insert_leaf_beside_key(
            self._content_tree, "central", leaf, area
        )
        self._rebuild_content_tree()

    def _prune_area_leaf(self, area: Qt.DockWidgetArea) -> None:
        key = self._side_key(area)
        updated = self._remove_leaf_by_key(self._content_tree, key)
        if updated is None:
            updated = _WidgetLeaf(self._central_placeholder, "central")
        self._content_tree = updated
        self._rebuild_content_tree()

    def _insert_leaf_beside_key(
        self,
        node: object,
        target_key: str,
        leaf: _WidgetLeaf,
        side: Qt.DockWidgetArea,
    ) -> object:
        orientation = (
            Qt.Orientation.Horizontal
            if side in (LeftDockWidgetArea, RightDockWidgetArea)
            else Qt.Orientation.Vertical
        )
        if isinstance(node, _WidgetLeaf):
            if node.key != target_key:
                return node
            if side in (LeftDockWidgetArea, TopDockWidgetArea):
                return _SplitTree(orientation, [leaf, node])
            return _SplitTree(orientation, [node, leaf])

        # Top-level side-area insertion around the central widget should wrap the
        # whole existing root when the requested orientation changes. This matches
        # Qt's shell policy where, for example, a bottom dock spans the full width
        # beneath existing left/right side docks rather than only beneath central.
        if target_key == "central":
            if node.orientation != orientation:
                if side in (LeftDockWidgetArea, TopDockWidgetArea):
                    return _SplitTree(orientation, [leaf, node])
                return _SplitTree(orientation, [node, leaf])
            if self._subtree_contains_key(node, target_key):
                central_index = self._child_index_containing_key(node, target_key)
                if central_index is not None:
                    insert_at = (
                        central_index
                        if side in (LeftDockWidgetArea, TopDockWidgetArea)
                        else central_index + 1
                    )
                    node.children.insert(insert_at, leaf)
                    return node

        central_index = self._child_index_containing_key(node, target_key)
        if central_index is None:
            return node
        if node.orientation == orientation:
            insert_at = central_index if side in (LeftDockWidgetArea, TopDockWidgetArea) else central_index + 1
            node.children.insert(insert_at, leaf)
            return node
        node.children[central_index] = self._insert_leaf_beside_key(
            node.children[central_index], target_key, leaf, side
        )
        return node

    def _child_index_containing_key(self, node: _SplitTree, key: str) -> int | None:
        for index, child in enumerate(node.children):
            if self._subtree_contains_key(child, key):
                return index
        return None

    def _remove_leaf_by_key(self, node: object, key: str) -> object | None:
        if isinstance(node, _WidgetLeaf):
            return None if node.key == key else node
        remaining: list[object] = []
        for child in node.children:
            updated = self._remove_leaf_by_key(child, key)
            if updated is not None:
                remaining.append(updated)
        if not remaining:
            return None
        if len(remaining) == 1:
            return remaining[0]
        node.children = remaining
        return node

    def _sync_content_tree_to_areas(self) -> None:
        native_area_states: dict[Qt.DockWidgetArea, object | None] = {}
        for area in (
            LeftDockWidgetArea,
            RightDockWidgetArea,
            TopDockWidgetArea,
            BottomDockWidgetArea,
        ):
            has_docks = bool(self._dock_areas[area].all_docks())
            present = self._leaf_for_area(area) is not None
            if has_docks and not present:
                self._content_tree = self._insert_leaf_beside_key(
                    self._content_tree,
                    "central",
                    _WidgetLeaf(
                        self._dock_areas[area],
                        self._side_key(area),
                        self._dock_areas[area].export_state(),
                    ),
                    area,
                )
            elif present and not has_docks:
                updated = self._remove_leaf_by_key(self._content_tree, self._side_key(area))
                if updated is not None:
                    self._content_tree = updated
            elif present:
                self._update_area_leaf_state(area)
        if self._leaf_for_key("central") is None:
            self._content_tree = _WidgetLeaf(self._central_placeholder, "central")
        self._rebuild_content_tree()

    def _update_area_leaf_state(self, area: Qt.DockWidgetArea) -> None:
        leaf = self._leaf_for_area(area)
        if leaf is not None:
            leaf.area_state = self._dock_areas[area].export_state()

    def _project_area_from_leaf(self, area: Qt.DockWidgetArea) -> None:
        leaf = self._leaf_for_area(area)
        state = leaf.area_state if leaf is not None else None
        lookup = {
            (dock.objectName() or dock.windowTitle()): dock
            for dock in list(self._dock_map)
            if dock.objectName() or dock.windowTitle()
        }
        self._dock_areas[area].restore_state(state, lookup)

    def _project_areas_from_content_tree(self) -> None:
        for area in (
            LeftDockWidgetArea,
            RightDockWidgetArea,
            TopDockWidgetArea,
            BottomDockWidgetArea,
        ):
            self._project_area_from_leaf(area)
        self._sync_dock_map()

    def _dock_lookup(self) -> dict[str, LDockWidget]:
        return {
            ident: dock
            for dock in self._all_known_docks()
            if (ident := self._dock_id(dock)) is not None
        }

    def _apply_current_tab_ids(
        self,
        current_tabs: dict[str, str] | None,
        lookup: dict[str, LDockWidget] | None = None,
    ) -> None:
        if not current_tabs:
            return
        dock_lookup = lookup or self._dock_lookup()
        for area_value, dock_id in current_tabs.items():
            dock = dock_lookup.get(dock_id)
            if dock is None:
                continue
            area = Qt.DockWidgetArea(int(area_value))
            area_obj = self._dock_areas.get(area)
            if area_obj is not None:
                area_obj.set_current_tab_dock(dock)

    def _apply_restored_dock_sizes(
        self,
        entries: list[dict[str, object]],
        lookup: dict[str, LDockWidget],
    ) -> None:
        for dock in lookup.values():
            dock._restored_docked_size = None
        for entry in entries:
            dock = lookup.get(entry.get("id"))
            if dock is None or entry.get("floating"):
                continue
            size = entry.get("docked_size")
            if not (isinstance(size, list) and len(size) == 2):
                continue
            try:
                width = int(size[0])
                height = int(size[1])
            except (TypeError, ValueError):
                continue
            dock._restored_docked_size = QSize(width, height)

    def _apply_area_state_updates(
        self,
        updates: dict[Qt.DockWidgetArea, object | None],
        current_tabs: dict[str, str] | None = None,
    ) -> None:
        for area, state in updates.items():
            self._set_area_state(area, state)
        self._project_areas_from_content_tree()
        self._apply_current_tab_ids(current_tabs)

    def _restore_projected_area_states(
        self,
        states: dict[Qt.DockWidgetArea, object | None],
        lookup: dict[str, LDockWidget],
        current_tabs: dict[str, str] | None = None,
    ) -> None:
        for area, state in states.items():
            self._set_area_state(area, state)
        self._restore_area_states(states, lookup)
        self._sync_content_tree_to_areas()
        self._apply_current_tab_ids(current_tabs, lookup)

    def _empty_dock_restore_state(
        self, lookup: dict[str, LDockWidget]
    ) -> None:
        self._pending_dock_restore = {}
        for area_obj in self._dock_areas.values():
            area_obj.restore_state(None, lookup)
        self._dock_map.clear()

    def _restore_docked_layout_from_content_tree(
        self,
        content_tree: object,
        lookup: dict[str, LDockWidget],
    ) -> None:
        self._content_tree = self._restore_content_tree(content_tree)
        embedded_area_states = self._content_tree_area_states(content_tree)
        self._restore_projected_area_states(
            {
                area: embedded_area_states.get(area)
                for area in (
                    LeftDockWidgetArea,
                    RightDockWidgetArea,
                    TopDockWidgetArea,
                    BottomDockWidgetArea,
                )
            },
            lookup,
        )

    def _restore_docked_layout_from_area_trees(
        self,
        area_trees: dict[object, object],
        lookup: dict[str, LDockWidget],
    ) -> None:
        # Legacy compatibility: older ldocking states stored per-area trees only.
        states: dict[Qt.DockWidgetArea, object | None] = {
            Qt.DockWidgetArea(int(area_value)): tree
            for area_value, tree in area_trees.items()
        }
        self._restore_projected_area_states(
            {
                area: states.get(area)
                for area in (
                    LeftDockWidgetArea,
                    RightDockWidgetArea,
                    TopDockWidgetArea,
                    BottomDockWidgetArea,
                )
            },
            lookup,
        )

    def _restore_docked_layout_from_flat_entries(
        self,
        entries: list[dict[str, object]],
        lookup: dict[str, LDockWidget],
    ) -> None:
        # Oldest compatibility branch: restore from flat dock entries only.
        self._content_tree = _WidgetLeaf(self._central_placeholder, "central")
        area_saved: dict[Qt.DockWidgetArea, list[tuple[LDockWidget, int]]] = {}
        for entry in entries:
            if entry.get("floating"):
                continue
            dock = lookup.get(entry["id"])
            if dock is None:
                continue
            area = Qt.DockWidgetArea(entry["area"])
            area_saved.setdefault(area, []).append((dock, entry.get("tab_index", 0)))
        for area, pairs in area_saved.items():
            for dock, _ in pairs:
                self.addDockWidget(area, dock)
            area_obj = self._dock_areas[area]
            for dock, idx in pairs:
                area_obj._insertion_order[dock] = idx
        self._sync_content_tree_to_areas()

    def _dock_id(self, dock: LDockWidget) -> str | None:
        return dock.objectName() or dock.windowTitle() or None

    def _allow_tabs(self) -> bool:
        return bool(
            self._dock_options
            & (
                QMainWindow.DockOption.AllowTabbedDocks
                | QMainWindow.DockOption.ForceTabbedDocks
            )
        )

    def _force_tabbed_docks(self) -> bool:
        return bool(self._dock_options & QMainWindow.DockOption.ForceTabbedDocks)

    def _allow_nested_docks(self) -> bool:
        return bool(self._dock_options & QMainWindow.DockOption.AllowNestedDocks) and not self._force_tabbed_docks()

    def _payload_allows_area(
        self, docks: list[LDockWidget], area: Qt.DockWidgetArea
    ) -> bool:
        return all(dock.isAreaAllowed(area) for dock in docks)

    def _area_state(self, area: Qt.DockWidgetArea) -> object | None:
        area_obj = self._dock_areas.get(area)
        if area_obj is not None and area_obj.all_docks():
            return area_obj.export_state()
        leaf = self._leaf_for_area(area)
        return leaf.area_state if leaf is not None else None

    def _set_area_state(self, area: Qt.DockWidgetArea, state: object | None) -> None:
        if state is None:
            self._prune_area_leaf(area)
            return
        self._ensure_area_leaf(area)
        leaf = self._leaf_for_area(area)
        if leaf is not None:
            leaf.area_state = state

    def _state_contains_id(self, node: object | None, dock_id: str) -> bool:
        if not isinstance(node, dict):
            return False
        if node.get("type") == "dock":
            return node.get("id") == dock_id
        return any(self._state_contains_id(child, dock_id) for child in node.get("children", []))

    def _state_collect_ids(self, node: object | None) -> list[str]:
        if not isinstance(node, dict):
            return []
        if node.get("type") == "dock":
            dock_id = node.get("id")
            return [dock_id] if dock_id else []
        result: list[str] = []
        for child in node.get("children", []):
            result.extend(self._state_collect_ids(child))
        return result

    def _state_find_exact_tab_group(
        self, node: object | None, dock_ids: set[str]
    ) -> dict[str, object] | None:
        if not isinstance(node, dict):
            return None
        if node.get("type") == "tabs":
            ids = set(self._state_collect_ids(node))
            if ids == dock_ids:
                return node
        for child in node.get("children", []):
            found = self._state_find_exact_tab_group(child, dock_ids)
            if found is not None:
                return found
        return None

    def _state_current_dock_id(self, node: object | None) -> str | None:
        if not isinstance(node, dict):
            return None
        if node.get("type") == "dock":
            return node.get("id")
        if node.get("type") == "tabs":
            children = node.get("children", [])
            if not children:
                return None
            index = min(node.get("current_index", 0), len(children) - 1)
            child = children[index]
            return child.get("id") if isinstance(child, dict) else None
        for child in node.get("children", []):
            current = self._state_current_dock_id(child)
            if current is not None:
                return current
        return None

    def _state_remove_ids(self, node: object | None, dock_ids: set[str]) -> object | None:
        if not isinstance(node, dict):
            return None
        if node.get("type") == "dock":
            return None if node.get("id") in dock_ids else deepcopy(node)
        if node.get("type") == "tabs":
            children = [
                deepcopy(child)
                for child in node.get("children", [])
                if isinstance(child, dict) and child.get("id") not in dock_ids
            ]
            if not children:
                return None
            if len(children) == 1:
                return children[0]
            current_index = min(node.get("current_index", 0), len(children) - 1)
            return {"type": "tabs", "current_index": current_index, "children": children}
        children = []
        for child in node.get("children", []):
            updated = self._state_remove_ids(child, dock_ids)
            if updated is not None:
                children.append(updated)
        if not children:
            return None
        if len(children) == 1:
            return children[0]
        return {
            "type": "split",
            "orientation": node.get("orientation", int(Qt.Orientation.Horizontal.value)),
            "sizes": list(node.get("sizes", [])),
            "children": children,
        }

    def _payload_state_for_docks(
        self, area: Qt.DockWidgetArea, docks: list[LDockWidget]
    ) -> object | None:
        dock_ids = [dock_id for dock_id in (self._dock_id(dock) for dock in docks) if dock_id]
        if not dock_ids:
            return None
        state = self._area_state(area)
        exact = self._state_find_exact_tab_group(state, set(dock_ids))
        if exact is not None:
            return deepcopy(exact)
        if len(dock_ids) == 1:
            return {"type": "dock", "id": dock_ids[0]}
        current_id = self._dock_id(self._dock_areas[area].current_tab_dock()) if area in self._dock_areas else None
        current_index = dock_ids.index(current_id) if current_id in dock_ids else len(dock_ids) - 1
        return {
            "type": "tabs",
            "current_index": current_index,
            "children": [{"type": "dock", "id": dock_id} for dock_id in dock_ids],
        }

    def _payload_children(self, payload: object) -> list[dict[str, object]]:
        if not isinstance(payload, dict):
            return []
        if payload.get("type") == "tabs":
            return [deepcopy(child) for child in payload.get("children", []) if isinstance(child, dict)]
        if payload.get("type") == "dock":
            return [deepcopy(payload)]
        return [{"type": "dock", "id": dock_id} for dock_id in self._state_collect_ids(payload)]

    def _state_first_dock_id(self, node: object | None) -> str | None:
        ids = self._state_collect_ids(node)
        return ids[0] if ids else None

    def _split_child_side(
        self,
        orientation: int,
        child_index: int,
        sibling_index: int,
    ) -> Qt.DockWidgetArea:
        if orientation == int(Qt.Orientation.Horizontal.value):
            return LeftDockWidgetArea if child_index < sibling_index else RightDockWidgetArea
        return TopDockWidgetArea if child_index < sibling_index else BottomDockWidgetArea

    def _collect_restore_hints(
        self,
        node: object | None,
        hints: dict[str, dict[str, object]],
        inherited: dict[str, object] | None = None,
    ) -> None:
        if not isinstance(node, dict):
            return
        node_type = node.get("type")
        if node_type == "dock":
            dock_id = node.get("id")
            if dock_id:
                hints.setdefault(dock_id, {})
                if inherited is not None:
                    hints[dock_id].update(deepcopy(inherited))
            return
        if node_type == "tabs":
            children = [child for child in node.get("children", []) if isinstance(child, dict)]
            if len(children) == 1:
                self._collect_restore_hints(children[0], hints, inherited)
                return
            child_ids = [child.get("id") for child in children if child.get("id")]
            for child in children:
                dock_id = child.get("id")
                if not dock_id:
                    continue
                target_id = next((other for other in child_ids if other != dock_id), None)
                self._collect_restore_hints(
                    child,
                    hints,
                    {"restore_mode": "tab", "restore_target_id": target_id}
                    if target_id is not None
                    else inherited,
                )
            return
        if node_type == "split":
            children = [child for child in node.get("children", []) if isinstance(child, dict)]
            orientation = int(node.get("orientation", int(Qt.Orientation.Horizontal.value)))
            for index, child in enumerate(children):
                sibling_index = index - 1 if index > 0 else (1 if len(children) > 1 else -1)
                child_inherited = inherited
                if sibling_index >= 0:
                    target_id = self._state_first_dock_id(children[sibling_index])
                    if target_id is not None:
                        child_inherited = {
                            "restore_mode": "side",
                            "restore_target_id": target_id,
                            "restore_side": int(
                                self._split_child_side(
                                    orientation,
                                    index,
                                    sibling_index,
                                ).value
                            ),
                        }
                self._collect_restore_hints(child, hints, child_inherited)

    def _state_tabify(
        self,
        node: object | None,
        target_id: str,
        payload: object,
        index: int | None = None,
    ) -> object | None:
        if not isinstance(node, dict):
            return payload
        node_type = node.get("type")
        if node_type == "dock" and node.get("id") == target_id:
            children = [deepcopy(node)]
            insert_at = len(children) if index is None else max(0, min(index, len(children)))
            additions = self._payload_children(payload)
            for offset, child in enumerate(additions):
                children.insert(insert_at + offset, child)
            current_id = self._state_current_dock_id(payload) or target_id
            current_index = next(
                (i for i, child in enumerate(children) if child.get("id") == current_id),
                len(children) - 1,
            )
            return {"type": "tabs", "current_index": current_index, "children": children}
        if node_type == "tabs" and target_id in self._state_collect_ids(node):
            children = [deepcopy(child) for child in node.get("children", []) if isinstance(child, dict)]
            insert_at = len(children) if index is None else max(0, min(index, len(children)))
            additions = self._payload_children(payload)
            for offset, child in enumerate(additions):
                if child.get("id") not in {existing.get("id") for existing in children}:
                    children.insert(insert_at + offset, child)
            current_id = self._state_current_dock_id(payload) or target_id
            current_index = next(
                (i for i, child in enumerate(children) if child.get("id") == current_id),
                min(node.get("current_index", 0), len(children) - 1),
            )
            return {"type": "tabs", "current_index": current_index, "children": children}
        if node_type == "split":
            return {
                "type": "split",
                "orientation": node.get("orientation", int(Qt.Orientation.Horizontal.value)),
                "sizes": list(node.get("sizes", [])),
                "children": [
                    self._state_tabify(child, target_id, payload, index)
                    if self._state_contains_id(child, target_id)
                    else deepcopy(child)
                    for child in node.get("children", [])
                ],
            }
        return deepcopy(node)

    def _state_split(
        self,
        node: object | None,
        target_id: str | None,
        payload: object,
        side: Qt.DockWidgetArea,
        allow_nested: bool,
    ) -> object | None:
        if node is None:
            return deepcopy(payload)
        orientation = (
            int(Qt.Orientation.Horizontal.value)
            if side in (LeftDockWidgetArea, RightDockWidgetArea)
            else int(Qt.Orientation.Vertical.value)
        )
        if not allow_nested or target_id is None or not self._state_contains_id(node, target_id):
            children = [deepcopy(node), deepcopy(payload)]
            if side in (LeftDockWidgetArea, TopDockWidgetArea):
                children.reverse()
            return {"type": "split", "orientation": orientation, "sizes": [], "children": children}
        if isinstance(node, dict) and node.get("type") == "split":
            return {
                "type": "split",
                "orientation": node.get("orientation", orientation),
                "sizes": list(node.get("sizes", [])),
                "children": [
                    self._state_split(child, target_id, payload, side, allow_nested)
                    if self._state_contains_id(child, target_id)
                    else deepcopy(child)
                    for child in node.get("children", [])
                ],
            }
        children = [deepcopy(node), deepcopy(payload)]
        if side in (LeftDockWidgetArea, TopDockWidgetArea):
            children.reverse()
        return {"type": "split", "orientation": orientation, "sizes": [], "children": children}

    def _state_add(
        self,
        area: Qt.DockWidgetArea,
        payload: object,
        index: int | None = None,
    ) -> object | None:
        current = self._area_state(area)
        force_tabbed = self._force_tabbed_docks()
        if current is None:
            return deepcopy(payload)
        if force_tabbed:
            target_id = self._state_current_dock_id(current)
            if target_id is None:
                ids = self._state_collect_ids(current)
                target_id = ids[0] if ids else None
            if target_id is not None:
                return self._state_tabify(current, target_id, payload, index)
        orientation = (
            int(Qt.Orientation.Vertical.value)
            if area in (LeftDockWidgetArea, RightDockWidgetArea)
            else int(Qt.Orientation.Horizontal.value)
        )
        if isinstance(current, dict) and current.get("type") == "split" and current.get("orientation") == orientation:
            children = [deepcopy(child) for child in current.get("children", [])]
            insert_at = len(children) if index is None else max(0, min(index, len(children)))
            children.insert(insert_at, deepcopy(payload))
            return {
                "type": "split",
                "orientation": orientation,
                "sizes": list(current.get("sizes", [])),
                "children": children,
            }
        return {
            "type": "split",
            "orientation": orientation,
            "sizes": [],
            "children": [deepcopy(current), deepcopy(payload)],
        }

    def _export_content_tree(self, node: object) -> object:
        if isinstance(node, _WidgetLeaf):
            payload = {"type": "leaf", "key": node.key}
            area = {
                "left": LeftDockWidgetArea,
                "right": RightDockWidgetArea,
                "top": TopDockWidgetArea,
                "bottom": BottomDockWidgetArea,
            }.get(node.key)
            if area is not None:
                payload["area_state"] = node.area_state
            return payload
        return {
            "type": "split",
            "orientation": int(node.orientation.value),
            "sizes": list(node.sizes),
            "children": [self._export_content_tree(child) for child in node.children],
        }

    def _restore_content_tree(self, payload: object) -> object:
        if not isinstance(payload, dict):
            return _WidgetLeaf(self._central_placeholder, "central")
        if payload.get("type") == "leaf":
            key = payload.get("key")
            if key == "central":
                return _WidgetLeaf(self._central_placeholder, "central")
            area = {
                "left": LeftDockWidgetArea,
                "right": RightDockWidgetArea,
                "top": TopDockWidgetArea,
                "bottom": BottomDockWidgetArea,
            }.get(key)
            if area is None:
                return _WidgetLeaf(self._central_placeholder, "central")
            return _WidgetLeaf(self._dock_areas[area], key, payload.get("area_state"))
        if payload.get("type") == "split":
            children = [
                self._restore_content_tree(child) for child in payload.get("children", [])
            ]
            children = [child for child in children if child is not None]
            if not children:
                return _WidgetLeaf(self._central_placeholder, "central")
            if len(children) == 1:
                return children[0]
            return _SplitTree(
                Qt.Orientation(payload.get("orientation", int(Qt.Orientation.Horizontal.value))),
                children,
                sizes=list(payload.get("sizes", [])),
            )
        return _WidgetLeaf(self._central_placeholder, "central")

    def _content_tree_area_states(
        self, payload: object
    ) -> dict[Qt.DockWidgetArea, object]:
        result: dict[Qt.DockWidgetArea, object] = {}
        self._collect_content_tree_area_states(payload, result)
        return result

    def _collect_content_tree_area_states(
        self,
        payload: object,
        result: dict[Qt.DockWidgetArea, object],
    ) -> None:
        if not isinstance(payload, dict):
            return
        if payload.get("type") == "leaf":
            area = {
                "left": LeftDockWidgetArea,
                "right": RightDockWidgetArea,
                "top": TopDockWidgetArea,
                "bottom": BottomDockWidgetArea,
            }.get(payload.get("key"))
            if area is not None and "area_state" in payload:
                result[area] = payload.get("area_state")
            return
        for child in payload.get("children", []):
            self._collect_content_tree_area_states(child, result)

    def _restore_area_states(
        self,
        states: dict[Qt.DockWidgetArea, object | None],
        lookup: dict[str, LDockWidget],
    ) -> None:
        for area in (
            LeftDockWidgetArea,
            RightDockWidgetArea,
            TopDockWidgetArea,
            BottomDockWidgetArea,
        ):
            self._dock_areas[area].restore_state(states.get(area), lookup)
            for dock in self._dock_areas[area].all_docks():
                self._dock_map[dock] = area
                dock._main_window = self
                dock._floating = False

    def setDockOptions(self, options: QMainWindow.DockOption) -> None:
        self._dock_options = options
        allow_tabs = self._allow_tabs()
        vertical_tabs = bool(options & QMainWindow.DockOption.VerticalTabs)
        grouped_dragging = bool(options & QMainWindow.DockOption.GroupedDragging)
        allow_nested = self._allow_nested_docks()
        for area in self._dock_areas.values():
            area.set_options(
                allow_tabs=allow_tabs,
                vertical_tabs=vertical_tabs,
                grouped_dragging=grouped_dragging,
                allow_nested=allow_nested,
            )

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
        return QTabWidget.TabPosition.South

    def setCorner(self, corner: Qt.Corner, area: Qt.DockWidgetArea) -> None:
        valid_areas = {
            Qt.Corner.TopLeftCorner: {TopDockWidgetArea, LeftDockWidgetArea},
            Qt.Corner.TopRightCorner: {TopDockWidgetArea, RightDockWidgetArea},
            Qt.Corner.BottomLeftCorner: {BottomDockWidgetArea, LeftDockWidgetArea},
            Qt.Corner.BottomRightCorner: {BottomDockWidgetArea, RightDockWidgetArea},
        }
        if area not in valid_areas.get(corner, set()):
            return
        self._corner_owners[corner] = area
        self._apply_corner_ownership()

    def corner(self, corner: Qt.Corner) -> Qt.DockWidgetArea:
        return self._corner_owners.get(corner, TopDockWidgetArea)

    def setCentralWidget(self, widget: QWidget) -> None:
        if self._central_widget is not None:
            self._central_widget.setParent(None)
        self._central_widget = widget
        leaf = self._leaf_for_key("central")
        if leaf is not None:
            leaf.widget = widget
            self._central_placeholder = widget
            self._rebuild_content_tree()
        else:
            self._central_placeholder = widget
        widget.show()

    def centralWidget(self) -> QWidget | None:
        return self._central_widget

    def setStyleSheet(self, styleSheet: str) -> None:  # type: ignore[override]
        super().setStyleSheet(translate_stylesheet(styleSheet))

    def _area_for_dock(self, dock: LDockWidget) -> Qt.DockWidgetArea:
        for area, area_obj in self._dock_areas.items():
            if area_obj.contains(dock):
                return area
        return self._dock_map.get(dock, Qt.DockWidgetArea.NoDockWidgetArea)

    def _sync_dock_map(self) -> None:
        docked_map = {
            dock: area
            for area, area_obj in self._dock_areas.items()
            for dock in area_obj.all_docks()
        }
        floating_map = {
            dock: area
            for dock, area in self._dock_map.items()
            if dock._floating and dock not in docked_map
        }
        self._dock_map = {**docked_map, **floating_map}

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

        if self._area_for_dock(dock) == resolved_area and not dock._floating:
            return

        dock._floating = False
        dock.setParent(None)

        dock_id = self._dock_id(dock)
        if dock_id is None:
            return
        old_area = self._area_for_dock(dock)
        area_updates: dict[Qt.DockWidgetArea, object | None] = {}
        if old_area != Qt.DockWidgetArea.NoDockWidgetArea:
            area_updates[old_area] = self._state_remove_ids(self._area_state(old_area), {dock_id})

        self._dock_map[dock] = resolved_area
        payload = {"type": "dock", "id": dock_id}
        area_updates[resolved_area] = self._state_add(resolved_area, payload, pos)
        self._apply_area_state_updates(area_updates)
        dock.setWindowFlags(Qt.WindowType.Widget)
        dock.dockLocationChanged.emit(resolved_area)
        dock._title_bar.set_float_button_icon(False)

    def removeDockWidget(self, dock: LDockWidget) -> None:
        area = self._area_for_dock(dock)
        if area == Qt.DockWidgetArea.NoDockWidgetArea:
            return
        dock_id = self._dock_id(dock)
        if dock_id is None:
            return
        self._dock_map.pop(dock, None)
        self._apply_area_state_updates({
            area: self._state_remove_ids(self._area_state(area), {dock_id})
        })

    def dockWidgetArea(self, dock: LDockWidget) -> Qt.DockWidgetArea:
        return self._area_for_dock(dock)

    def restoreDockWidget(self, dock: LDockWidget) -> bool:
        ident = self._dock_id(dock)
        if ident is None:
            return False
        entry = self._pending_dock_restore.pop(ident, None)
        if entry is None:
            return False
        return self._restore_dock_entry(dock, entry)

    def _restore_dock_entry(
        self,
        dock: LDockWidget,
        entry: dict[str, object],
    ) -> bool:
        ident = self._dock_id(dock)
        if ident is None:
            return False
        try:
            area = Qt.DockWidgetArea(int(entry["area"]))
        except (KeyError, TypeError, ValueError):
            return False
        resolved_area = self._resolve_dock_area(dock, area)
        if resolved_area is None:
            return False

        dock._pre_float_area_side = resolved_area
        dock._pre_float_position = int(entry.get("tab_index", 0))
        dock._floating = True
        size = entry.get("docked_size")
        if isinstance(size, list) and len(size) == 2:
            try:
                dock._restored_docked_size = QSize(int(size[0]), int(size[1]))
            except (TypeError, ValueError):
                dock._restored_docked_size = None
        mode = entry.get("restore_mode")
        target_id = entry.get("restore_target_id")
        side = None
        if entry.get("restore_side") is not None:
            try:
                side = Qt.DockWidgetArea(int(entry["restore_side"]))
            except (TypeError, ValueError):
                side = None
        target_available = (
            isinstance(target_id, str)
            and self._state_contains_id(self._area_state(resolved_area), target_id)
        )
        if mode in {"tab", "side"} and target_available:
            self._drop_docks(
                resolved_area,
                [dock],
                mode=mode,
                target_id=target_id,
                side=side,
            )
        else:
            self.addDockWidget(resolved_area, dock)
        if entry.get("selected") and not entry.get("floating"):
            self._apply_current_tab_ids({str(int(resolved_area.value)): ident}, {ident: dock})
        if entry.get("floating"):
            geometry = entry.get("geometry")
            dock.setFloating(True)
            if isinstance(geometry, list) and len(geometry) == 4:
                dock.setGeometry(geometry[0], geometry[1], geometry[2], geometry[3])
        return True

    def tabifyDockWidget(self, first: LDockWidget, second: LDockWidget) -> None:
        area = self._area_for_dock(first)
        if area == Qt.DockWidgetArea.NoDockWidgetArea:
            return
        if not second.isAreaAllowed(area):
            return
        first_id = self._dock_id(first)
        second_id = self._dock_id(second)
        if first_id is None or second_id is None:
            return
        old_area = self._area_for_dock(second)
        area_updates: dict[Qt.DockWidgetArea, object | None] = {}
        target_state = self._area_state(area)
        if old_area != Qt.DockWidgetArea.NoDockWidgetArea:
            removed_state = self._state_remove_ids(self._area_state(old_area), {second_id})
            if old_area == area:
                target_state = removed_state
            else:
                area_updates[old_area] = removed_state
        self._dock_map[second] = area
        area_updates[area] = self._state_tabify(
            target_state, first_id, {"type": "dock", "id": second_id}
        )
        self._apply_area_state_updates(area_updates)
        second._main_window = self
        second._floating = False
        second.setWindowFlags(Qt.WindowType.Widget)
        second.dockLocationChanged.emit(area)
        second._title_bar.set_float_button_icon(False)

    def tabifiedDockWidgets(self, dock: LDockWidget) -> list[LDockWidget]:
        area = self._area_for_dock(dock)
        if area == Qt.DockWidgetArea.NoDockWidgetArea:
            return []
        return self._dock_areas[area].tabified_docks(dock)

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
        if splitter is None:
            return
        current = self._splitter_live_extents(splitter, orientation)
        if not current:
            return
        requested: dict[int, int] = {}
        for dock, size in zip(docks, sizes):
            area = self._area_for_dock(dock)
            if area == Qt.DockWidgetArea.NoDockWidgetArea:
                continue
            idx = splitter.indexOf(self._dock_areas[area])
            if 0 <= idx < len(current):
                requested[idx] = self._clamp_resize_dock_extent(
                    self._dock_areas[area],
                    size,
                    orientation,
                )
        if not requested:
            return
        for idx, size in requested.items():
            current[idx] = size
        splitter.setSizes(current)
        if splitter is self._outer_splitter:
            outer = self._find_split(self._content_tree, "outer")
            if outer is not None:
                outer.sizes = list(current)
        if splitter is self._inner_splitter:
            inner = self._find_split(self._content_tree, "inner")
            if inner is not None:
                inner.sizes = list(current)

    def _splitter_live_extents(
        self,
        splitter: QSplitter,
        orientation: Qt.Orientation,
    ) -> list[int]:
        extents: list[int] = []
        for idx in range(splitter.count()):
            widget = splitter.widget(idx)
            if widget is None:
                extents.append(0)
            elif orientation == Qt.Orientation.Horizontal:
                extents.append(widget.width())
            else:
                extents.append(widget.height())
        return extents

    def _clamp_resize_dock_extent(
        self,
        area_widget: QWidget,
        requested: int,
        orientation: Qt.Orientation,
    ) -> int:
        minimum, maximum = self._effective_area_extent_bounds(area_widget, orientation)
        return max(minimum, min(int(requested), maximum))

    def _effective_area_extent_bounds(
        self,
        area_widget: QWidget,
        orientation: Qt.Orientation,
    ) -> tuple[int, int]:
        if not isinstance(area_widget, LDockArea) or area_widget._root is None:
            if orientation == Qt.Orientation.Horizontal:
                minimum = max(area_widget.minimumWidth(), area_widget.minimumSizeHint().width())
                maximum = area_widget.maximumWidth()
            else:
                minimum = max(area_widget.minimumHeight(), area_widget.minimumSizeHint().height())
                maximum = area_widget.maximumHeight()
            return minimum, maximum if maximum < 16777215 else 16777215
        return self._node_extent_bounds(area_widget._root, orientation)

    def _node_extent_bounds(
        self,
        node: object,
        orientation: Qt.Orientation,
    ) -> tuple[int, int]:
        if hasattr(node, "dock"):
            dock = node.dock
            minimum = dock.minimumSizeHint().expandedTo(dock.minimumSize())
            maximum = dock.maximumSize()
            if orientation == Qt.Orientation.Horizontal:
                return minimum.width(), maximum.width()
            return minimum.height(), maximum.height()

        if hasattr(node, "docks"):
            mins: list[int] = []
            maxs: list[int] = []
            for dock in node.docks:
                minimum = dock.minimumSizeHint().expandedTo(dock.minimumSize())
                maximum = dock.maximumSize()
                if orientation == Qt.Orientation.Horizontal:
                    mins.append(minimum.width())
                    maxs.append(maximum.width())
                else:
                    mins.append(minimum.height())
                    maxs.append(maximum.height())
            if not mins:
                return 0, 16777215
            return min(mins), max(maxs)

        if hasattr(node, "children") and hasattr(node, "orientation"):
            child_bounds = [self._node_extent_bounds(child, orientation) for child in node.children]
            if not child_bounds:
                return 0, 16777215
            if node.orientation == orientation:
                return sum(bound[0] for bound in child_bounds), sum(bound[1] for bound in child_bounds)
            return max(bound[0] for bound in child_bounds), max(bound[1] for bound in child_bounds)

        return 0, 16777215

    def _find_split(self, node: object, key: str) -> _SplitTree | None:
        if isinstance(node, _SplitTree):
            if node.key == key:
                return node
            for child in node.children:
                found = self._find_split(child, key)
                if found is not None:
                    return found
        return None

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

    def _normalize_toolbar_area(self, area: Qt.ToolBarArea) -> Qt.ToolBarArea:
        if area in (
            Qt.ToolBarArea.TopToolBarArea,
            Qt.ToolBarArea.LeftToolBarArea,
            Qt.ToolBarArea.RightToolBarArea,
            Qt.ToolBarArea.BottomToolBarArea,
        ):
            return area
        return Qt.ToolBarArea.TopToolBarArea

    def _toolbar_extent(self, area: Qt.ToolBarArea) -> int:
        container = self._toolbar_containers[area]
        if not self._toolbar_rows[area]:
            return 0
        hint = container.sizeHint()
        if area in (
            Qt.ToolBarArea.TopToolBarArea,
            Qt.ToolBarArea.BottomToolBarArea,
        ):
            return max(container.height(), hint.height())
        return max(container.width(), hint.width())

    def _apply_corner_ownership(self) -> None:
        top = Qt.ToolBarArea.TopToolBarArea
        bottom = Qt.ToolBarArea.BottomToolBarArea
        left = Qt.ToolBarArea.LeftToolBarArea
        right = Qt.ToolBarArea.RightToolBarArea

        top_extent = self._toolbar_extent(top)
        bottom_extent = self._toolbar_extent(bottom)
        left_extent = self._toolbar_extent(left)
        right_extent = self._toolbar_extent(right)

        self._toolbar_layouts[top].setContentsMargins(
            left_extent if self._corner_owners[Qt.Corner.TopLeftCorner] == LeftDockWidgetArea else 0,
            0,
            right_extent if self._corner_owners[Qt.Corner.TopRightCorner] == RightDockWidgetArea else 0,
            0,
        )
        self._toolbar_layouts[bottom].setContentsMargins(
            left_extent if self._corner_owners[Qt.Corner.BottomLeftCorner] == LeftDockWidgetArea else 0,
            0,
            right_extent if self._corner_owners[Qt.Corner.BottomRightCorner] == RightDockWidgetArea else 0,
            0,
        )
        self._toolbar_layouts[left].setContentsMargins(
            0,
            top_extent if self._corner_owners[Qt.Corner.TopLeftCorner] == TopDockWidgetArea else 0,
            0,
            bottom_extent if self._corner_owners[Qt.Corner.BottomLeftCorner] == BottomDockWidgetArea else 0,
        )
        self._toolbar_layouts[right].setContentsMargins(
            0,
            top_extent if self._corner_owners[Qt.Corner.TopRightCorner] == TopDockWidgetArea else 0,
            0,
            bottom_extent if self._corner_owners[Qt.Corner.BottomRightCorner] == BottomDockWidgetArea else 0,
        )
        for container in self._toolbar_containers.values():
            container.updateGeometry()
            container.update()

    def _rebuild_toolbar_area(self, area: Qt.ToolBarArea) -> None:
        area = self._normalize_toolbar_area(area)
        layout = self._toolbar_layouts[area]
        container = self._toolbar_containers[area]
        for row in self._toolbar_rows[area]:
            for toolbar in row:
                if toolbar.parent() is not None:
                    toolbar.setParent(None)
        while layout.count():
            item = layout.takeAt(0)
            if item and item.widget():
                item.widget().setParent(None)
        for row in self._toolbar_rows[area]:
            row_widget = QWidget(container)
            if area in (
                Qt.ToolBarArea.TopToolBarArea,
                Qt.ToolBarArea.BottomToolBarArea,
            ):
                row_layout = QHBoxLayout(row_widget)
            else:
                row_layout = QVBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(0)
            for toolbar in row:
                toolbar.setParent(row_widget)
                row_layout.addWidget(toolbar)
            layout.addWidget(row_widget)
        if area in (
            Qt.ToolBarArea.TopToolBarArea,
            Qt.ToolBarArea.BottomToolBarArea,
        ):
            container.setMaximumHeight(16777215 if self._toolbar_rows[area] else 0)
        else:
            container.setMaximumWidth(16777215 if self._toolbar_rows[area] else 0)
        self._apply_corner_ownership()

    def _remove_toolbar_from_rows(self, toolbar: QToolBar) -> None:
        for area, rows in self._toolbar_rows.items():
            changed = False
            for row in list(rows):
                if toolbar in row:
                    if toolbar.parent() is not None:
                        toolbar.setParent(None)
                    row.remove(toolbar)
                    changed = True
                if not row:
                    rows.remove(row)
                    changed = True
            if changed:
                self._rebuild_toolbar_area(area)

    def addToolBar(
        self, toolbar_or_title_or_area, toolbar: QToolBar | None = None
    ) -> QToolBar:
        area = Qt.ToolBarArea.TopToolBarArea
        if isinstance(toolbar_or_title_or_area, Qt.ToolBarArea):
            area = self._normalize_toolbar_area(toolbar_or_title_or_area)
            tb = toolbar
        elif toolbar is not None:
            tb = toolbar
        elif isinstance(toolbar_or_title_or_area, str):
            tb = QToolBar(toolbar_or_title_or_area)
        else:
            tb = toolbar_or_title_or_area
        if tb is None:
            raise ValueError("toolbar must not be None")
        self._remove_toolbar_from_rows(tb)
        if tb not in self._tool_bars:
            self._tool_bars.append(tb)
        area = self._normalize_toolbar_area(area)
        self._toolbar_area_map[tb] = area
        rows = self._toolbar_rows[area]
        if not rows or area in self._pending_toolbar_breaks:
            rows.append([])
            self._pending_toolbar_breaks.discard(area)
        rows[-1].append(tb)
        self._rebuild_toolbar_area(area)
        return tb

    def removeToolBar(self, toolbar: QToolBar) -> None:
        if toolbar in self._tool_bars:
            self._tool_bars.remove(toolbar)
            self._toolbar_area_map.pop(toolbar, None)
            self._remove_toolbar_from_rows(toolbar)

    def insertToolBar(self, before: QToolBar, toolbar: QToolBar) -> None:
        if toolbar in self._tool_bars:
            self._tool_bars.remove(toolbar)
            toolbar.setParent(None)
        self._remove_toolbar_from_rows(toolbar)
        idx = (
            self._tool_bars.index(before)
            if before in self._tool_bars
            else len(self._tool_bars)
        )
        self._tool_bars.insert(idx, toolbar)
        area = self._normalize_toolbar_area(
            self._toolbar_area_map.get(before, Qt.ToolBarArea.TopToolBarArea)
        )
        self._toolbar_area_map[toolbar] = area
        inserted = False
        for row in self._toolbar_rows[area]:
            if before in row:
                row.insert(row.index(before), toolbar)
                inserted = True
                break
        if not inserted:
            if not self._toolbar_rows[area]:
                self._toolbar_rows[area].append([])
            self._toolbar_rows[area][-1].append(toolbar)
        self._rebuild_toolbar_area(area)

    def toolBars(self) -> list[QToolBar]:
        return list(self._tool_bars)

    def toolBarArea(self, toolbar: QToolBar) -> Qt.ToolBarArea:
        return self._toolbar_area_map.get(toolbar, Qt.ToolBarArea.TopToolBarArea)

    def addToolBarBreak(
        self, area: Qt.ToolBarArea = Qt.ToolBarArea.TopToolBarArea
    ) -> None:
        self._pending_toolbar_breaks.add(self._normalize_toolbar_area(area))

    def removeToolBarBreak(self, before: QToolBar) -> None:
        area = self._toolbar_area_map.get(before)
        if area is None:
            return
        rows = self._toolbar_rows[area]
        for idx, row in enumerate(rows):
            if before in row and idx > 0 and row and row[0] is before:
                rows[idx - 1].extend(row)
                rows.pop(idx)
                self._rebuild_toolbar_area(area)
                return

    def insertToolBarBreak(self, before: QToolBar) -> None:
        area = self._toolbar_area_map.get(before)
        if area is None:
            return
        rows = self._toolbar_rows[area]
        for idx, row in enumerate(rows):
            if before in row:
                pos = row.index(before)
                if pos == 0:
                    return
                rows.insert(idx + 1, row[pos:])
                del row[pos:]
                self._rebuild_toolbar_area(area)
                return

    def toolBarBreak(self, toolbar: QToolBar) -> bool:
        area = self._toolbar_area_map.get(toolbar)
        if area is None:
            return False
        for idx, row in enumerate(self._toolbar_rows[area]):
            if toolbar in row:
                return idx > 0 and row and row[0] is toolbar
        return False

    def _toolbar_id(self, toolbar: QToolBar) -> str | None:
        return toolbar.objectName() or toolbar.windowTitle() or None

    def _toolbar_areas(self) -> tuple[Qt.ToolBarArea, ...]:
        return (
            Qt.ToolBarArea.TopToolBarArea,
            Qt.ToolBarArea.LeftToolBarArea,
            Qt.ToolBarArea.RightToolBarArea,
            Qt.ToolBarArea.BottomToolBarArea,
        )

    def _export_toolbar_state(self) -> dict[str, object]:
        toolbars: list[dict[str, int | str]] = []
        for area in self._toolbar_areas():
            for row_index, row in enumerate(self._toolbar_rows[area]):
                for index, toolbar in enumerate(row):
                    ident = self._toolbar_id(toolbar)
                    if not ident:
                        continue
                    toolbars.append(
                        {
                            "id": ident,
                            "area": area.value,
                            "row": row_index,
                            "index": index,
                        }
                    )
        corners = {
            str(corner.value): area.value
            for corner, area in self._corner_owners.items()
        }
        return {"toolbars": toolbars, "corners": corners}

    def _restore_toolbar_state(self, payload: dict[str, object]) -> None:
        toolbar_entries = payload.get("toolbars")
        corners = payload.get("corners")

        if isinstance(corners, dict):
            valid_areas = {
                Qt.Corner.TopLeftCorner: {TopDockWidgetArea, LeftDockWidgetArea},
                Qt.Corner.TopRightCorner: {TopDockWidgetArea, RightDockWidgetArea},
                Qt.Corner.BottomLeftCorner: {BottomDockWidgetArea, LeftDockWidgetArea},
                Qt.Corner.BottomRightCorner: {BottomDockWidgetArea, RightDockWidgetArea},
            }
            for corner_value, area_value in corners.items():
                try:
                    corner = Qt.Corner(int(corner_value))
                    area = Qt.DockWidgetArea(int(area_value))
                except (TypeError, ValueError):
                    continue
                if area in valid_areas.get(corner, set()):
                    self._corner_owners[corner] = area

        if not isinstance(toolbar_entries, list):
            self._apply_corner_ownership()
            return

        lookup = {
            ident: toolbar
            for toolbar in self._tool_bars
            if (ident := self._toolbar_id(toolbar)) is not None
        }
        previous_area_map = {
            toolbar: self._toolbar_area_map.get(toolbar, Qt.ToolBarArea.TopToolBarArea)
            for toolbar in self._tool_bars
        }

        self._pending_toolbar_breaks.clear()
        for area in self._toolbar_areas():
            self._toolbar_rows[area] = []
        for toolbar in self._tool_bars:
            if toolbar.parent() is not None:
                toolbar.setParent(None)

        placed: set[QToolBar] = set()
        ordered_toolbars: list[QToolBar] = []
        by_area: dict[Qt.ToolBarArea, list[tuple[int, int, QToolBar]]] = {
            area: [] for area in self._toolbar_areas()
        }
        for entry in toolbar_entries:
            if not isinstance(entry, dict):
                continue
            toolbar = lookup.get(entry.get("id"))
            if toolbar is None:
                continue
            try:
                area = self._normalize_toolbar_area(Qt.ToolBarArea(int(entry["area"])))
                row_index = int(entry.get("row", 0))
                index = int(entry.get("index", 0))
            except (KeyError, TypeError, ValueError):
                continue
            by_area[area].append((row_index, index, toolbar))
            if toolbar not in placed:
                ordered_toolbars.append(toolbar)
                placed.add(toolbar)

        for area in self._toolbar_areas():
            rows: list[list[QToolBar]] = []
            for row_index, index, toolbar in sorted(by_area[area], key=lambda item: (item[0], item[1])):
                while len(rows) <= row_index:
                    rows.append([])
                rows[row_index].append(toolbar)
                self._toolbar_area_map[toolbar] = area
            self._toolbar_rows[area] = [row for row in rows if row]
            self._rebuild_toolbar_area(area)

        for toolbar in self._tool_bars:
            if toolbar in placed:
                continue
            area = self._normalize_toolbar_area(previous_area_map.get(toolbar, Qt.ToolBarArea.TopToolBarArea))
            if not self._toolbar_rows[area]:
                self._toolbar_rows[area].append([])
            self._toolbar_rows[area][-1].append(toolbar)
            self._toolbar_area_map[toolbar] = area
            ordered_toolbars.append(toolbar)
            self._rebuild_toolbar_area(area)

        self._tool_bars = ordered_toolbars
        self._apply_corner_ownership()

    def statusBar(self) -> QStatusBar:
        if self._status_bar is None:
            bar = QStatusBar(self)
            bar.setSizeGripEnabled(True)
            self._status_bar = bar
            self._root_layout.addWidget(bar)
        return self._status_bar

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

    def _drop_docks(
        self,
        area: Qt.DockWidgetArea,
        docks: list[LDockWidget],
        mode: str = "area",
        target_dock: LDockWidget | None = None,
        target_id: str | None = None,
        target_key: str | None = None,
        side: Qt.DockWidgetArea | None = None,
    ) -> None:
        if not docks:
            return
        if not self._payload_allows_area(docks, area):
            return
        resolved_area = area
        if resolved_area is None:
            return
        source_areas = {
            current_area: [dock for dock in docks if self._area_for_dock(dock) == current_area]
            for current_area in (
                LeftDockWidgetArea,
                RightDockWidgetArea,
                TopDockWidgetArea,
                BottomDockWidgetArea,
            )
        }
        source_areas = {area_key: payload for area_key, payload in source_areas.items() if payload}
        payload_state = None
        for source_area, source_docks in source_areas.items():
            payload_state = self._payload_state_for_docks(source_area, source_docks)
            if payload_state is not None:
                break
        if payload_state is None:
            payload_state = self._payload_state_for_docks(
                resolved_area, docks
            ) or {"type": "dock", "id": self._dock_id(docks[0])}
        area_updates: dict[Qt.DockWidgetArea, object | None] = {}
        for dock in docks:
            dock._main_window = self
            dock._floating = False
            dock.setParent(None)
            old_area = self._area_for_dock(dock)
            if old_area != Qt.DockWidgetArea.NoDockWidgetArea:
                dock_ids = {
                    dock_id
                    for dock_id in (self._dock_id(payload_dock) for payload_dock in source_areas.get(old_area, [dock]))
                    if dock_id
                }
                area_updates[old_area] = self._state_remove_ids(self._area_state(old_area), dock_ids)
            self._dock_map[dock] = resolved_area
        target_id = target_id or (self._dock_id(target_dock) if target_dock is not None else None)
        allow_nested = self._allow_nested_docks()
        force_tabbed = self._force_tabbed_docks()
        if mode == "tab" and target_id is not None:
            new_state = self._state_tabify(
                self._area_state(resolved_area),
                target_id,
                payload_state,
            )
        elif mode == "side" and target_id is not None and side is not None and not force_tabbed:
            new_state = self._state_split(
                self._area_state(resolved_area),
                target_id,
                payload_state,
                side,
                allow_nested,
            )
        else:
            new_state = self._state_add(resolved_area, payload_state)
        area_updates[resolved_area] = new_state
        self._apply_area_state_updates(area_updates)
        for dock in docks:
            dock.setWindowFlags(Qt.WindowType.Widget)
            dock.dockLocationChanged.emit(resolved_area)
            dock._title_bar.set_float_button_icon(False)

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

    def _all_known_docks(self) -> list[LDockWidget]:
        seen: set[LDockWidget] = set()
        result: list[LDockWidget] = []
        for area_obj in self._dock_areas.values():
            for dock in area_obj.all_docks():
                if dock not in seen:
                    seen.add(dock)
                    result.append(dock)
        for dock in self._dock_map:
            if dock not in seen:
                seen.add(dock)
                result.append(dock)
        return result

    def _extract_native_probe_dock_state(
        self,
        probe: QMainWindow,
        probe_docks: dict[str, QDockWidget],
    ) -> tuple[dict[Qt.DockWidgetArea, object | None], dict[str, str], list[dict[str, object]]]:
        current_tabs: dict[str, str] = {}
        native_area_states: dict[Qt.DockWidgetArea, object | None] = {}
        entries: list[dict[str, object]] = []
        for area in (
            LeftDockWidgetArea,
            RightDockWidgetArea,
            TopDockWidgetArea,
            BottomDockWidgetArea,
        ):
            area_ids = [
                ident
                for ident, probe_dock in probe_docks.items()
                if probe.dockWidgetArea(probe_dock) == area and not probe_dock.isFloating()
            ]
            groups: list[list[str]] = []
            seen_ids: set[str] = set()
            for ident in area_ids:
                if ident in seen_ids:
                    continue
                peers = {
                    peer.objectName() or peer.windowTitle()
                    for peer in probe.tabifiedDockWidgets(probe_docks[ident])
                }
                group = [dock_id for dock_id in area_ids if dock_id == ident or dock_id in peers]
                for dock_id in group:
                    seen_ids.add(dock_id)
                groups.append(group)

            area_state: object | None = None
            for group in groups:
                if not group:
                    continue
                visible_id = next(
                    (dock_id for dock_id in group if probe_docks[dock_id].isVisible()),
                    group[0],
                )
                group_state: object
                if len(group) == 1:
                    group_state = {"type": "dock", "id": group[0]}
                else:
                    group_state = {
                        "type": "tabs",
                        "current_index": group.index(visible_id),
                        "children": [{"type": "dock", "id": dock_id} for dock_id in group],
                    }
                    current_tabs[str(area.value)] = visible_id
                if area_state is None:
                    area_state = group_state
                else:
                    # Qt can represent richer same-area splitter shapes than ldocking.
                    # Import flattens multiple non-tab groups into the current side-area model.
                    orientation = (
                        int(Qt.Orientation.Vertical.value)
                        if area in (LeftDockWidgetArea, RightDockWidgetArea)
                        else int(Qt.Orientation.Horizontal.value)
                    )
                    area_state = {
                        "type": "split",
                        "orientation": orientation,
                        "sizes": [],
                        "children": [area_state, group_state],
                    }
            native_area_states[area] = area_state
        for ident, probe_dock in probe_docks.items():
            geometry = probe_dock.geometry()
            entries.append(
                {
                    "id": ident,
                    "area": int(probe.dockWidgetArea(probe_dock).value),
                    "floating": probe_dock.isFloating(),
                    "docked_size": [geometry.width(), geometry.height()],
                }
            )
        return native_area_states, current_tabs, entries

    def _extract_native_probe_toolbar_state(
        self,
        probe: QMainWindow,
        probe_toolbars: dict[str, QToolBar],
    ) -> dict[str, object]:
        toolbar_entries: list[dict[str, int | str]] = []
        by_area: dict[Qt.ToolBarArea, list[QToolBar]] = {area: [] for area in self._toolbar_areas()}
        for toolbar in self._tool_bars:
            ident = self._toolbar_id(toolbar)
            if ident is None or ident not in probe_toolbars:
                continue
            probe_toolbar = probe_toolbars[ident]
            area = probe.toolBarArea(probe_toolbar)
            by_area.setdefault(area, []).append(toolbar)

        for area in self._toolbar_areas():
            row_index = 0
            index = 0
            for toolbar in by_area.get(area, []):
                ident = self._toolbar_id(toolbar)
                if ident is None:
                    continue
                if index > 0 and probe.toolBarBreak(probe_toolbars[ident]):
                    row_index += 1
                    index = 0
                toolbar_entries.append(
                    {
                        "id": ident,
                        "area": int(area.value),
                        "row": row_index,
                        "index": index,
                    }
                )
                index += 1

        corners = {
            str(corner.value): int(probe.corner(corner).value)
            for corner in (
                Qt.Corner.TopLeftCorner,
                Qt.Corner.TopRightCorner,
                Qt.Corner.BottomLeftCorner,
                Qt.Corner.BottomRightCorner,
            )
        }
        return {"toolbars": toolbar_entries, "corners": corners}

    def _create_native_probe_docks(self) -> dict[str, QDockWidget]:
        probe_docks: dict[str, QDockWidget] = {}
        for ident in self._dock_lookup():
            dock = QDockWidget(ident)
            dock.setObjectName(ident)
            dock.setWidget(QLabel(ident))
            probe_docks[ident] = dock
        return probe_docks

    def _create_native_probe_toolbars(self) -> dict[str, QToolBar]:
        probe_toolbars: dict[str, QToolBar] = {}
        for toolbar in self._tool_bars:
            ident = self._toolbar_id(toolbar)
            if ident is None:
                continue
            probe_toolbar = QToolBar(ident)
            probe_toolbar.setObjectName(ident)
            probe_toolbar.addAction(ident)
            probe_toolbars[ident] = probe_toolbar
        return probe_toolbars

    def _materialize_native_probe_state(
        self,
        probe: QMainWindow,
        node: object | None,
        area: Qt.DockWidgetArea,
        probe_docks: dict[str, QDockWidget],
        anchor_id: str | None = None,
        orientation: Qt.Orientation | None = None,
    ) -> str | None:
        if not isinstance(node, dict):
            return None
        node_type = node.get("type")
        if node_type == "dock":
            dock_id = node.get("id")
            if not dock_id or dock_id not in probe_docks:
                return None
            dock = probe_docks[dock_id]
            if anchor_id is None:
                probe.addDockWidget(area, dock)
            else:
                probe.addDockWidget(area, dock)
                probe.splitDockWidget(probe_docks[anchor_id], dock, orientation or Qt.Orientation.Horizontal)
            return dock_id
        if node_type == "tabs":
            children = [child for child in node.get("children", []) if isinstance(child, dict)]
            if not children:
                return None
            representative = self._materialize_native_probe_state(
                probe, children[0], area, probe_docks, anchor_id, orientation
            )
            if representative is None:
                return None
            for child in children[1:]:
                dock_id = child.get("id")
                if not dock_id or dock_id not in probe_docks:
                    continue
                dock = probe_docks[dock_id]
                probe.addDockWidget(area, dock)
                probe.tabifyDockWidget(probe_docks[representative], dock)
            current_index = min(int(node.get("current_index", 0)), len(children) - 1)
            current_id = children[current_index].get("id")
            if current_id in probe_docks:
                probe_docks[current_id].raise_()
                probe_docks[current_id].show()
            return representative
        if node_type == "split":
            children = [child for child in node.get("children", []) if isinstance(child, dict)]
            if not children:
                return None
            split_orientation = Qt.Orientation(int(node.get("orientation", int(Qt.Orientation.Horizontal.value))))
            representative = self._materialize_native_probe_state(
                probe, children[0], area, probe_docks, anchor_id, orientation
            )
            previous_anchor = representative
            for child in children[1:]:
                previous_anchor = self._materialize_native_probe_state(
                    probe, child, area, probe_docks, previous_anchor, split_orientation
                ) or previous_anchor
            return representative
        return None

    def _apply_native_probe_toolbar_layout(
        self,
        probe: QMainWindow,
        probe_toolbars: dict[str, QToolBar],
    ) -> None:
        for corner, area in self._corner_owners.items():
            probe.setCorner(corner, area)
        for area in self._toolbar_areas():
            for row_index, row in enumerate(self._toolbar_rows[area]):
                for index, toolbar in enumerate(row):
                    ident = self._toolbar_id(toolbar)
                    if ident is None or ident not in probe_toolbars:
                        continue
                    probe_toolbar = probe_toolbars[ident]
                    probe.addToolBar(area, probe_toolbar)
                    if row_index > 0 and index == 0:
                        probe.insertToolBarBreak(probe_toolbar)

    def saveQtState(self, version: int = 0) -> QByteArray:
        probe = QMainWindow()
        probe.setCentralWidget(QWidget())
        probe.resize(self.width() or 800, self.height() or 600)

        probe_docks = self._create_native_probe_docks()
        probe_toolbars = self._create_native_probe_toolbars()

        for area in (
            LeftDockWidgetArea,
            RightDockWidgetArea,
            TopDockWidgetArea,
            BottomDockWidgetArea,
        ):
            self._materialize_native_probe_state(
                probe,
                self._area_state(area),
                area,
                probe_docks,
            )

        for dock, area in self._dock_map.items():
            ident = self._dock_id(dock)
            if ident is None or ident not in probe_docks or not dock._floating:
                continue
            probe_dock = probe_docks[ident]
            probe.addDockWidget(area, probe_dock)
            probe_dock.setFloating(True)
            geometry = dock.geometry()
            probe_dock.setGeometry(
                geometry.x(),
                geometry.y(),
                geometry.width(),
                geometry.height(),
            )

        self._apply_native_probe_toolbar_layout(probe, probe_toolbars)
        probe.show()
        app = QApplication.instance()
        if app is not None:
            app.processEvents()
        state = probe.saveState(version)
        probe.hide()
        probe.deleteLater()
        return state

    def _restore_native_qt_state(self, state: QByteArray, version: int = 0) -> bool:
        docks = self._all_known_docks()
        dock_lookup = {
            ident: dock
            for dock in docks
            if (ident := self._dock_id(dock)) is not None
        }
        toolbar_lookup = {
            ident: toolbar
            for toolbar in self._tool_bars
            if (ident := self._toolbar_id(toolbar)) is not None
        }

        probe = QMainWindow()
        probe.setCentralWidget(QWidget())

        probe_docks: dict[str, QDockWidget] = {}
        for ident in dock_lookup:
            dock = QDockWidget(ident)
            dock.setObjectName(ident)
            dock.setWidget(QLabel(ident))
            probe.addDockWidget(LeftDockWidgetArea, dock)
            probe_docks[ident] = dock

        probe_toolbars: dict[str, QToolBar] = {}
        for ident in toolbar_lookup:
            toolbar = QToolBar(ident)
            toolbar.setObjectName(ident)
            toolbar.addAction(ident)
            probe.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)
            probe_toolbars[ident] = toolbar

        if not probe.restoreState(state, version):
            probe.deleteLater()
            return False
        probe.show()
        app = QApplication.instance()
        if app is not None:
            app.processEvents()

        for area_obj in self._dock_areas.values():
            area_obj.restore_state(None, dock_lookup)
        self._dock_map.clear()
        self._pending_dock_restore = {}

        native_area_states, current_tabs, native_entries = self._extract_native_probe_dock_state(
            probe, probe_docks
        )
        self._apply_restored_dock_sizes(native_entries, dock_lookup)
        self._restore_projected_area_states(native_area_states, dock_lookup, current_tabs)

        for ident, dock in dock_lookup.items():
            probe_dock = probe_docks[ident]
            if probe_dock.isFloating():
                dock._pre_float_area_side = probe.dockWidgetArea(probe_dock)
                dock._pre_float_position = 0
                dock.setParent(None)
                dock.setWindowFlags(
                    Qt.WindowType.Tool
                    | Qt.WindowType.FramelessWindowHint
                    | Qt.WindowType.WindowStaysOnTopHint
                )
                dock._floating = True
                dock._title_bar.set_float_button_icon(True)
                geometry = probe_dock.geometry()
                dock.setGeometry(
                    geometry.x(),
                    geometry.y(),
                    geometry.width(),
                    geometry.height(),
                )
                dock.show()

        self._restore_toolbar_state(
            self._extract_native_probe_toolbar_state(probe, probe_toolbars)
        )
        probe.hide()
        probe.deleteLater()
        return True

    def saveState(self, version: int = 0) -> QByteArray:
        docks_state = []
        self._sync_dock_map()
        restore_hints: dict[str, dict[str, object]] = {}
        selected_overrides: dict[str, str] = {}
        for area in (
            LeftDockWidgetArea,
            RightDockWidgetArea,
            TopDockWidgetArea,
            BottomDockWidgetArea,
        ):
            self._update_area_leaf_state(area)
            self._collect_restore_hints(self._area_state(area), restore_hints)
        for dock, area in self._dock_map.items():
            ident = dock.objectName() or dock.windowTitle()
            if not ident:
                continue
            area_docks = self._dock_areas[area]._docks
            tab_index = area_docks.index(dock) if dock in area_docks else 0
            floating_from_tab = dock._floating and dock._pre_float_save_as_docked
            entry: dict[str, object] = {
                "id": ident,
                "area": area.value,
                "tab_index": dock._pre_float_position if floating_from_tab and dock._pre_float_position is not None else tab_index,
                "floating": dock._floating and not floating_from_tab,
                "visible": dock._toggle_action_checked_value(),
            }
            if not entry["floating"]:
                entry["docked_size"] = [dock.width(), dock.height()]
            if entry["floating"]:
                g = dock.geometry()
                entry["geometry"] = [g.x(), g.y(), g.width(), g.height()]
            entry.update(restore_hints.get(ident, {}))
            if floating_from_tab and dock._pre_float_restore_hint is not None:
                entry.update(deepcopy(dock._pre_float_restore_hint))
                if dock._pre_float_selected:
                    selected_overrides[str(int(area.value))] = ident
            docks_state.append(entry)

        current_tabs: dict[str, str] = {}
        for area, area_obj in self._dock_areas.items():
            current_dock = area_obj.current_tab_dock()
            if current_dock is not None:
                ident = current_dock.objectName() or current_dock.windowTitle()
                if ident:
                    current_tabs[str(area.value)] = ident
        current_tabs.update(selected_overrides)
        for entry in docks_state:
            entry["selected"] = current_tabs.get(str(entry["area"])) == entry["id"]

        payload = {
            "format_version": _STATE_FORMAT_VERSION,
            "state_version": version,
            "outer_splitter": self._outer_splitter.sizes() if self._outer_splitter else [],
            "inner_splitter": self._inner_splitter.sizes() if self._inner_splitter else [],
            "content_tree": self._export_content_tree(self._content_tree),
            "docks": docks_state,
            "current_tabs": current_tabs,
        }
        payload.update(self._export_toolbar_state())
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

            lookup = self._dock_lookup()
            self._empty_dock_restore_state(lookup)

            entries = sorted(data.get("docks", []), key=lambda e: e.get("tab_index", 0))
            self._apply_restored_dock_sizes(entries, lookup)
            content_tree = data.get("content_tree")
            if content_tree is not None:
                self._restore_docked_layout_from_content_tree(content_tree, lookup)
            else:
                self._content_tree = _WidgetLeaf(self._central_placeholder, "central")
                area_trees = data.get("area_trees")
                if isinstance(area_trees, dict):
                    self._restore_docked_layout_from_area_trees(area_trees, lookup)
                else:
                    self._restore_docked_layout_from_flat_entries(entries, lookup)

            for entry in entries:
                if entry.get("floating"):
                    continue
                dock = lookup.get(entry["id"])
                if dock is None:
                    continue
                if self._area_for_dock(dock) != Qt.DockWidgetArea.NoDockWidgetArea:
                    continue
                self._restore_dock_entry(dock, entry)

            for entry in entries:
                dock = lookup.get(entry["id"])
                if dock is None:
                    self._pending_dock_restore[entry["id"]] = dict(entry)
                    continue
                if not entry.get("floating"):
                    continue
                area = Qt.DockWidgetArea(entry["area"])
                dock._pre_float_area_side = area
                dock._pre_float_position = entry.get("tab_index", 0)
                dock.setParent(None)
                dock.setWindowFlags(
                    Qt.WindowType.Tool
                    | Qt.WindowType.FramelessWindowHint
                    | Qt.WindowType.WindowStaysOnTopHint
                )
                dock._floating = True
                dock._title_bar.set_float_button_icon(True)
                g = entry.get("geometry")
                if g:
                    dock.setGeometry(g[0], g[1], g[2], g[3])
                dock.show()

            self._apply_current_tab_ids(data.get("current_tabs", {}), lookup)

            for entry in entries:
                dock = lookup.get(entry["id"])
                if dock is None:
                    continue
                if entry.get("visible", True):
                    dock._explicitly_hidden = False
                    if dock._current_area is not None and dock._current_area._tab_area is not None:
                        dock._current_area._tab_area._sync_visibility()
                    elif not dock._floating:
                        dock.show()
                    dock._sync_toggle_action_checked()
                else:
                    dock.setVisible(False)

            outer = data.get("outer_splitter")
            if outer and self._outer_splitter is not None:
                self._outer_splitter.setSizes(outer)
                split = self._find_split(self._content_tree, "outer")
                if split is not None:
                    split.sizes = list(outer)
            inner = data.get("inner_splitter")
            if inner and self._inner_splitter is not None:
                self._inner_splitter.setSizes(inner)
                split = self._find_split(self._content_tree, "inner")
                if split is not None:
                    split.sizes = list(inner)

            if "toolbars" in data or "corners" in data:
                self._restore_toolbar_state(data)

            return True
        except Exception:
            return self._restore_native_qt_state(state, version)
