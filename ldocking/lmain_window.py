"""LMainWindow - drop-in for QMainWindow using a tree-backed splitter layout."""
from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
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

        self._content_host = QWidget()
        self._content_layout = QVBoxLayout(self._content_host)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(0)
        self._root_layout.addWidget(self._content_host, 1)

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

        self._status_bar_widget = QStatusBar()
        self._root_layout.addWidget(self._status_bar_widget)
        self._status_bar = self._status_bar_widget

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

    def _dock_id(self, dock: LDockWidget) -> str | None:
        return dock.objectName() or dock.windowTitle() or None

    def _area_state(self, area: Qt.DockWidgetArea) -> object | None:
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
        allow_tabs = bool(
            self._dock_options
            & (
                QMainWindow.DockOption.AllowTabbedDocks
                | QMainWindow.DockOption.ForceTabbedDocks
            )
        )
        if current is None:
            return deepcopy(payload)
        if allow_tabs:
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
        states: dict[Qt.DockWidgetArea, object],
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
        allow_tabs = bool(
            options
            & (
                QMainWindow.DockOption.AllowTabbedDocks
                | QMainWindow.DockOption.ForceTabbedDocks
            )
        )
        vertical_tabs = bool(options & QMainWindow.DockOption.VerticalTabs)
        grouped_dragging = bool(options & QMainWindow.DockOption.GroupedDragging)
        allow_nested = bool(options & QMainWindow.DockOption.AllowNestedDocks)
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
        return QTabWidget.TabPosition.North

    def setCorner(self, corner: Qt.Corner, area: Qt.DockWidgetArea) -> None:
        """No-op: corner ownership is implicit in the current compatibility layout."""

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
        if old_area != Qt.DockWidgetArea.NoDockWidgetArea:
            self._set_area_state(
                old_area,
                self._state_remove_ids(self._area_state(old_area), {dock_id}),
            )

        self._dock_map[dock] = resolved_area
        payload = {"type": "dock", "id": dock_id}
        self._set_area_state(resolved_area, self._state_add(resolved_area, payload, pos))
        self._project_areas_from_content_tree()
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
        self._set_area_state(area, self._state_remove_ids(self._area_state(area), {dock_id}))
        self._project_areas_from_content_tree()

    def dockWidgetArea(self, dock: LDockWidget) -> Qt.DockWidgetArea:
        return self._area_for_dock(dock)

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
        if old_area != Qt.DockWidgetArea.NoDockWidgetArea:
            self._set_area_state(
                old_area,
                self._state_remove_ids(self._area_state(old_area), {second_id}),
            )
        self._dock_map[second] = area
        self._set_area_state(
            area,
            self._state_tabify(self._area_state(area), first_id, {"type": "dock", "id": second_id}),
        )
        self._project_areas_from_content_tree()
        second._main_window = self
        second._floating = False
        second.setWindowFlags(Qt.WindowType.Widget)
        second.dockLocationChanged.emit(area)
        second._title_bar.set_float_button_icon(False)

    def tabifiedDockWidgets(self, dock: LDockWidget) -> list[LDockWidget]:
        area = self._area_for_dock(dock)
        if area == Qt.DockWidgetArea.NoDockWidgetArea:
            return []
        return [d for d in self._dock_areas[area].all_docks() if d is not dock]

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
        current = splitter.sizes()
        if not current:
            return
        total = sum(current)
        if total <= 0:
            total = (
                splitter.size().width()
                if orientation == Qt.Orientation.Horizontal
                else splitter.size().height()
            )
        requested: dict[int, int] = {}
        for dock, size in zip(docks, sizes):
            area = self._area_for_dock(dock)
            if area == Qt.DockWidgetArea.NoDockWidgetArea:
                continue
            idx = splitter.indexOf(self._dock_areas[area])
            if 0 <= idx < len(current):
                requested[idx] = size
        if not requested:
            return
        remainder_indices = [idx for idx in range(len(current)) if idx not in requested]
        remaining = max(0, total - sum(requested.values()))
        if remainder_indices:
            base, extra = divmod(remaining, len(remainder_indices))
            for offset, idx in enumerate(remainder_indices):
                current[idx] = base + (1 if offset < extra else 0)
        for idx, size in requested.items():
            current[idx] = size
        splitter.setSizes(current)
        if splitter is self._outer_splitter:
            outer = self._find_split(self._content_tree, "outer")
            if outer is not None:
                outer.sizes = splitter.sizes()
        if splitter is self._inner_splitter:
            inner = self._find_split(self._content_tree, "inner")
            if inner is not None:
                inner.sizes = splitter.sizes()

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
        resolved_area = self._resolve_dock_area(docks[0], area)
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
                self._set_area_state(
                    old_area,
                    self._state_remove_ids(self._area_state(old_area), dock_ids),
                )
            self._dock_map[dock] = resolved_area
        target_id = target_id or (self._dock_id(target_dock) if target_dock is not None else None)
        allow_nested = bool(self._dock_options & QMainWindow.DockOption.AllowNestedDocks)
        if mode == "tab" and target_id is not None:
            new_state = self._state_tabify(
                self._area_state(resolved_area),
                target_id,
                payload_state,
            )
        elif mode == "side" and target_id is not None and side is not None:
            new_state = self._state_split(
                self._area_state(resolved_area),
                target_id,
                payload_state,
                side,
                allow_nested,
            )
        else:
            new_state = self._state_add(resolved_area, payload_state)
        self._set_area_state(resolved_area, new_state)
        self._project_areas_from_content_tree()
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

    def saveState(self, version: int = 0) -> QByteArray:
        docks_state = []
        self._sync_dock_map()
        for area in (
            LeftDockWidgetArea,
            RightDockWidgetArea,
            TopDockWidgetArea,
            BottomDockWidgetArea,
        ):
            self._update_area_leaf_state(area)
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
            if current_dock is not None:
                ident = current_dock.objectName() or current_dock.windowTitle()
                if ident:
                    current_tabs[str(area.value)] = ident

        payload = {
            "format_version": _STATE_FORMAT_VERSION,
            "state_version": version,
            "outer_splitter": self._outer_splitter.sizes() if self._outer_splitter else [],
            "inner_splitter": self._inner_splitter.sizes() if self._inner_splitter else [],
            "content_tree": self._export_content_tree(self._content_tree),
            "docks": docks_state,
            "current_tabs": current_tabs,
            "area_trees": {
                str(area.value): area_obj.export_state()
                for area, area_obj in self._dock_areas.items()
            },
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

            for area_obj in self._dock_areas.values():
                area_obj.restore_state(None, lookup)
            self._dock_map.clear()

            entries = sorted(data.get("docks", []), key=lambda e: e.get("tab_index", 0))
            content_tree = data.get("content_tree")
            embedded_area_states: dict[Qt.DockWidgetArea, object] = {}
            if content_tree is not None:
                self._content_tree = self._restore_content_tree(content_tree)
                embedded_area_states = self._content_tree_area_states(content_tree)
            else:
                self._content_tree = _WidgetLeaf(self._central_placeholder, "central")

            if embedded_area_states:
                self._restore_area_states(embedded_area_states, lookup)
            else:
                area_trees = data.get("area_trees")
                if isinstance(area_trees, dict):
                    states = {
                        Qt.DockWidgetArea(int(area_value)): tree
                        for area_value, tree in area_trees.items()
                    }
                    self._restore_area_states(states, lookup)
                else:
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

            for entry in entries:
                dock = lookup.get(entry["id"])
                if dock is None or not entry.get("floating"):
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

            for area_value, dock_id in data.get("current_tabs", {}).items():
                dock = lookup.get(dock_id)
                if dock is not None:
                    area = Qt.DockWidgetArea(int(area_value))
                    area_obj = self._dock_areas.get(area)
                    if area_obj is not None:
                        area_obj.set_current_tab_dock(dock)

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

            return True
        except Exception:
            return False
