"""LDockArea - one top-level dock side with recursive nested layout support."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from PySide6.QtCore import QRect, Qt
from PySide6.QtWidgets import QSizePolicy, QSplitter, QTabWidget, QVBoxLayout, QWidget

from .ldock_tab_area import LDockTabArea
from .stylesheet_compat import translate_stylesheet

if TYPE_CHECKING:
    from .ldock_widget import LDockWidget


@dataclass
class _DockNode:
    dock: LDockWidget


@dataclass
class _TabNode:
    docks: list[LDockWidget]
    current_index: int = 0


@dataclass
class _SplitNode:
    orientation: Qt.Orientation
    children: list[object] = field(default_factory=list)
    sizes: list[int] = field(default_factory=list)


class LDockArea(QWidget):
    """One side of an LMainWindow docking layout."""

    def __init__(
        self,
        area_side: Qt.DockWidgetArea,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setProperty("class", "QDockArea")
        area_names = {
            Qt.DockWidgetArea.LeftDockWidgetArea: "dockAreaLeft",
            Qt.DockWidgetArea.RightDockWidgetArea: "dockAreaRight",
            Qt.DockWidgetArea.TopDockWidgetArea: "dockAreaTop",
            Qt.DockWidgetArea.BottomDockWidgetArea: "dockAreaBottom",
        }
        self.setObjectName(area_names.get(area_side, "dockArea"))
        self._area_side = area_side
        self._root: object | None = None
        self._docks: list[LDockWidget] = []
        self._tab_area: LDockTabArea | None = None
        self._split_area: QSplitter | None = None
        self._allow_tabs = True
        self._allow_nested = False
        self._grouped_dragging = False
        self._vertical_tabs_opt = False
        self._tab_position_opt = QTabWidget.TabPosition.South
        self._insertion_order: dict[LDockWidget, int] = {}
        self._dock_to_node: dict[LDockWidget, object] = {}
        self._node_tab_areas: dict[int, LDockTabArea] = {}
        self._needs_initial_sizes: bool = False

        self._vertical = area_side in (
            Qt.DockWidgetArea.LeftDockWidgetArea,
            Qt.DockWidgetArea.RightDockWidgetArea,
        )

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        if self._vertical:
            self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
            self.setMinimumWidth(40)
        else:
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.setMinimumHeight(40)

        self.hide()

    @property
    def area_side(self) -> Qt.DockWidgetArea:
        return self._area_side

    def sizeHint(self) -> "QSize":  # type: ignore[override]
        from PySide6.QtCore import QSize
        try:
            base = super().sizeHint()
        except RuntimeError:
            return QSize(40, 40)
        docks = getattr(self, "_docks", [])
        if not docks:
            return base
        if self._vertical:
            w = max(d.sizeHint().width() for d in docks)
            return QSize(max(base.width(), w), base.height())
        h = max(d.sizeHint().height() for d in docks)
        return QSize(base.width(), max(base.height(), h))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if getattr(self, '_needs_initial_sizes', False):
            self._needs_initial_sizes = False
            self._apply_initial_sizes()

    def _apply_initial_sizes(self) -> None:
        """Set initial split sizes to approximate Qt QDockAreaLayout behavior.

        Use a proportional split based on child size hints when no explicit
        sizes were restored. This keeps equal-hint docks balanced on first
        layout, matching native Qt's default same-area behavior more closely.
        """
        split = self._split_area
        if split is None or split.count() < 2:
            return
        if getattr(split, '_ldk_has_explicit_sizes', True):
            return
        is_vert = split.orientation() == Qt.Orientation.Vertical
        # Use the dock area's own dimensions: the inner split fills it completely
        # via QVBoxLayout and may not yet have propagated its own size.
        total = self.height() if is_vert else self.width()
        if total <= 0:
            return
        handles = split.handleWidth() * (split.count() - 1)
        available = total - handles
        if is_vert:
            hints = [max(split.widget(i).sizeHint().height(), 1)
                     for i in range(split.count())]
        else:
            hints = [max(split.widget(i).sizeHint().width(), 1)
                     for i in range(split.count())]
        sum_hints = max(sum(hints), 1)
        sizes = [max(h * available // sum_hints, 1) for h in hints]
        remainder = available - sum(sizes)
        if remainder > 0:
            sizes[0] += remainder
        split.setSizes(sizes)

    def setStyleSheet(self, styleSheet: str) -> None:  # type: ignore[override]
        super().setStyleSheet(translate_stylesheet(styleSheet))

    def add_dock(self, dock: LDockWidget, index: int | None = None) -> None:
        if dock in self._dock_to_node:
            return
        dock._current_area = self
        if dock not in self._insertion_order:
            self._insertion_order[dock] = len(self._insertion_order)

        if self._root is None:
            self._root = _DockNode(dock)
        elif self._allow_tabs:
            target = self.current_tab_dock() or self._first_dock(self._root)
            if target is None:
                self._root = _DockNode(dock)
            else:
                self.tabify_docks(target, [dock], index=index)
                return
        else:
            orientation = self._default_orientation()
            new_node = _DockNode(dock)
            if isinstance(self._root, _SplitNode) and self._root.orientation == orientation:
                insert_idx = len(self._root.children) if index is None else max(0, min(index, len(self._root.children)))
                self._root.children.insert(insert_idx, new_node)
            else:
                children = [self._root, new_node]
                if index == 0:
                    children.reverse()
                self._root = _SplitNode(orientation, children)

        self._rebuild()

    def remove_dock(self, dock: LDockWidget) -> None:
        if self._root is None or dock not in self._dock_to_node:
            return
        self._root = self._remove_from_node(self._root, dock)
        if dock._current_area is self:
            dock._current_area = None
        self._dock_to_node.pop(dock, None)
        self._rebuild()

    def contains(self, dock: LDockWidget) -> bool:
        return dock in self._dock_to_node

    def all_docks(self) -> list[LDockWidget]:
        return list(self._docks)

    def handle_tabified_visibility_request(self, dock: LDockWidget, visible: bool) -> bool:
        node = self._dock_to_node.get(dock)
        if not isinstance(node, _TabNode):
            return False
        tab_area = self._node_tab_areas.get(id(node))
        if tab_area is None:
            return False
        tab_area.handle_dock_visibility_request(dock, visible)
        return True

    def tabified_docks(self, dock: LDockWidget) -> list[LDockWidget]:
        node = self._dock_to_node.get(dock)
        if isinstance(node, _TabNode):
            return [candidate for candidate in node.docks if candidate is not dock]
        return []

    def drop_target_at_global_pos(
        self, global_pos
    ) -> tuple[LDockWidget, QRect, bool] | None:
        seen_nodes: set[int] = set()
        for dock in reversed(self.all_docks()):
            node = self._dock_to_node.get(dock)
            if node is None:
                continue
            node_id = id(node)
            if node_id in seen_nodes:
                continue
            seen_nodes.add(node_id)
            if isinstance(node, _TabNode):
                tab_area = self._node_tab_areas.get(node_id)
                if tab_area is None:
                    continue
                rect = QRect(
                    tab_area.mapToGlobal(tab_area.rect().topLeft()),
                    tab_area.size(),
                )
                if rect.contains(global_pos):
                    current = node.docks[node.current_index] if node.docks else dock
                    tab_bar_rect = QRect(
                        tab_area._tab_bar.mapToGlobal(tab_area._tab_bar.rect().topLeft()),
                        tab_area._tab_bar.size(),
                    )
                    return current, rect, tab_bar_rect.contains(global_pos)
                continue
            rect = QRect(dock.mapToGlobal(dock.rect().topLeft()), dock.size())
            if rect.contains(global_pos):
                return dock, rect, False
        return None

    def set_options(
        self,
        allow_tabs: bool,
        vertical_tabs: bool,
        grouped_dragging: bool = False,
        allow_nested: bool = False,
    ) -> None:
        changed = (
            allow_tabs != self._allow_tabs
            or vertical_tabs != self._vertical_tabs_opt
            or grouped_dragging != self._grouped_dragging
            or allow_nested != self._allow_nested
        )
        self._allow_tabs = allow_tabs
        self._vertical_tabs_opt = vertical_tabs
        self._grouped_dragging = grouped_dragging
        self._allow_nested = allow_nested
        if changed:
            self._rebuild()

    def set_tab_position(self, position: QTabWidget.TabPosition) -> None:
        self._tab_position_opt = position
        if self._tab_area is not None:
            self._tab_area.set_tab_position(position)

    def sync_tab_order(self, ordered_docks: list[LDockWidget]) -> None:
        for idx, dock in enumerate(ordered_docks):
            self._insertion_order[dock] = idx
        node = self._find_tab_node_by_docks(ordered_docks)
        if isinstance(node, _TabNode):
            node.docks = list(ordered_docks)
            if node.current_index >= len(node.docks):
                node.current_index = max(0, len(node.docks) - 1)
        self._sync_flat_state()

    def get_tab_position(self) -> QTabWidget.TabPosition:
        return self._tab_position_opt

    def current_tab_dock(self) -> LDockWidget | None:
        return self._current_tab_in_node(self._root)

    def set_current_tab_dock(self, dock: LDockWidget) -> None:
        node = self._dock_to_node.get(dock)
        if isinstance(node, _TabNode) and dock in node.docks:
            node.current_index = node.docks.index(dock)
            tab_area = self._node_tab_areas.get(id(node))
            if tab_area is not None and dock in tab_area.all_docks():
                tab_area.set_current_dock(dock)

    def tabify_docks(
        self, target_dock: LDockWidget, docks: list[LDockWidget], index: int | None = None
    ) -> None:
        if self._root is None:
            for dock in docks:
                self.add_dock(dock, index=index)
            return
        target_node = self._dock_to_node.get(target_dock)
        if target_node is None:
            for dock in docks:
                self.add_dock(dock)
            return
        self._root = self._tabify_node(self._root, target_node, docks, target_dock, index)
        self._rebuild()

    def split_docks(
        self,
        target_dock: LDockWidget,
        docks: list[LDockWidget],
        side: Qt.DockWidgetArea,
    ) -> None:
        if self._root is None:
            for dock in docks:
                self.add_dock(dock)
            return
        target_node = self._dock_to_node.get(target_dock)
        if target_node is None:
            for dock in docks:
                self.add_dock(dock)
            return
        target_for_split = target_node if self._allow_nested else self._root
        payload = self._payload_node(docks)
        self._root = self._split_node(self._root, target_for_split, payload, side)
        self._rebuild()

    def docks_for_group_drag(self, dock: LDockWidget) -> list[LDockWidget]:
        if not self._grouped_dragging:
            return [dock]
        node = self._dock_to_node.get(dock)
        if isinstance(node, _TabNode) and len(node.docks) > 1:
            return list(node.docks)
        return [dock]

    def export_state(self) -> object | None:
        return self._export_node(self._root)

    def restore_state(self, payload: object | None, lookup: dict[str, LDockWidget]) -> None:
        self._root = self._restore_node(payload, lookup)
        self._rebuild()

    def _default_orientation(self) -> Qt.Orientation:
        return Qt.Orientation.Vertical if self._vertical else Qt.Orientation.Horizontal

    def _payload_node(self, docks: list[LDockWidget]) -> object:
        if len(docks) == 1:
            return _DockNode(docks[0])
        current = 0
        anchor = docks[0]
        source = self._dock_to_node.get(anchor)
        if isinstance(source, _TabNode):
            current = min(source.current_index, len(docks) - 1)
        return _TabNode(list(docks), current)

    def _rebuild(self) -> None:
        self._detach_docks()
        self._clear_layout()
        self._dock_to_node.clear()
        self._node_tab_areas.clear()
        self._tab_area = None
        self._split_area = None

        if self._root is None:
            self._docks = []
            self.hide()
            return

        widget = self._build_widget(self._root, self)
        self._layout.addWidget(widget)
        self._sync_flat_state()
        self.show()

        if self._split_area is not None and self._split_area.count() > 1:
            if self.isVisible():
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, self._apply_initial_sizes)
            else:
                self._needs_initial_sizes = True

    def _detach_docks(self) -> None:
        for dock in self._docks:
            if dock.parent() is not None:
                dock._tab_visibility_sync = True
                dock.setParent(None)
                dock._tab_visibility_sync = False

    def _build_widget(self, node: object, parent: QWidget) -> QWidget:
        if isinstance(node, _DockNode):
            dock = node.dock
            self._dock_to_node[dock] = node
            dock._current_area = self
            dock._set_tabbed_visibility_override(None)
            dock.setParent(parent)
            restored_size = getattr(dock, "_restored_docked_size", None)
            if restored_size is not None and restored_size.isValid():
                bounded = restored_size.expandedTo(
                    dock.minimumSizeHint().expandedTo(dock.minimumSize())
                ).boundedTo(dock.maximumSize())
                dock.resize(bounded)
            if dock.titleBarWidget() is None:
                dock._title_bar.show()
            else:
                dock._title_bar.hide()
            dock._tab_visibility_sync = True
            if dock._explicitly_hidden:
                dock.hide()
            else:
                dock.show()
            dock._tab_visibility_sync = False
            return dock

        if isinstance(node, _TabNode):
            tab_area = LDockTabArea(parent, vertical_tabs=self._vertical_tabs_opt)
            tab_area.set_tab_position(self._tab_position_opt)
            tab_area.set_grouped_dragging(self._grouped_dragging)
            desired_current_index = min(node.current_index, len(node.docks) - 1) if node.docks else 0
            for dock in node.docks:
                self._dock_to_node[dock] = node
                dock._current_area = self
                tab_area.add_dock(dock)
            tab_area.currentDockChanged.connect(
                lambda dock, n=node: self._on_tab_current_changed(n, dock)
            )
            if node.docks:
                tab_area.set_current_dock(node.docks[desired_current_index])
                node.current_index = desired_current_index
            self._node_tab_areas[id(node)] = tab_area
            if self._root is node:
                self._tab_area = tab_area
            return tab_area

        split = QSplitter(node.orientation, parent)
        sep = self.style().pixelMetric(
            self.style().PixelMetric.PM_DockWidgetSeparatorExtent, None, self
        )
        split.setHandleWidth(sep)
        for child in node.children:
            split.addWidget(self._build_widget(child, split))
        if node.sizes:
            split.setSizes(node.sizes)
            split._ldk_has_explicit_sizes = True
        else:
            split.setStretchFactor(0, 1)
            split._ldk_has_explicit_sizes = False
        if self._root is node:
            self._split_area = split
        return split

    def _on_tab_current_changed(self, node: _TabNode, dock: LDockWidget) -> None:
        if dock in node.docks:
            node.current_index = node.docks.index(dock)

    def _sync_flat_state(self) -> None:
        self._docks = self._collect_docks(self._root)
        for idx, dock in enumerate(self._docks):
            self._insertion_order.setdefault(dock, idx)
            self._dock_to_node.setdefault(dock, _DockNode(dock))

    def _current_tab_in_node(self, node: object | None) -> LDockWidget | None:
        if node is None:
            return None
        if isinstance(node, _TabNode):
            if not node.docks:
                return None
            return node.docks[node.current_index]
        if isinstance(node, _DockNode):
            return None
        for child in node.children:
            current = self._current_tab_in_node(child)
            if current is not None:
                return current
        return None

    def _collect_docks(self, node: object | None) -> list[LDockWidget]:
        if node is None:
            return []
        if isinstance(node, _DockNode):
            return [node.dock]
        if isinstance(node, _TabNode):
            return list(node.docks)
        result: list[LDockWidget] = []
        for child in node.children:
            result.extend(self._collect_docks(child))
        return result

    def _first_dock(self, node: object | None) -> LDockWidget | None:
        docks = self._collect_docks(node)
        return docks[0] if docks else None

    def _find_tab_node_by_docks(self, docks: list[LDockWidget]) -> _TabNode | None:
        return self._find_tab_node(self._root, set(docks))

    def _find_tab_node(self, node: object | None, docks: set[LDockWidget]) -> _TabNode | None:
        if node is None:
            return None
        if isinstance(node, _TabNode):
            return node if set(node.docks) == docks else None
        if isinstance(node, _DockNode):
            return None
        for child in node.children:
            found = self._find_tab_node(child, docks)
            if found is not None:
                return found
        return None

    def _tabify_node(
        self,
        node: object,
        target_node: object,
        docks: list[LDockWidget],
        target_dock: LDockWidget,
        index: int | None,
    ) -> object:
        if node is target_node:
            if isinstance(node, _DockNode):
                merged = [node.dock]
                insert_idx = len(merged) if index is None else max(0, min(index, len(merged)))
                for offset, dock in enumerate(docks):
                    merged.insert(insert_idx + offset, dock)
                current_index = merged.index(target_dock if target_dock in merged else merged[0])
                return _TabNode(merged, current_index)
            if isinstance(node, _TabNode):
                merged = list(node.docks)
                insert_idx = len(merged) if index is None else max(0, min(index, len(merged)))
                for offset, dock in enumerate(docks):
                    if dock not in merged:
                        merged.insert(insert_idx + offset, dock)
                current_index = merged.index(target_dock if target_dock in merged else merged[0])
                return _TabNode(merged, current_index)

        if isinstance(node, _SplitNode):
            node.children = [
                self._tabify_node(child, target_node, docks, target_dock, index)
                for child in node.children
            ]
        return node

    def _split_node(
        self,
        node: object,
        target_node: object,
        payload: object,
        side: Qt.DockWidgetArea,
    ) -> object:
        if node is target_node:
            orientation = (
                Qt.Orientation.Horizontal
                if side in (Qt.DockWidgetArea.LeftDockWidgetArea, Qt.DockWidgetArea.RightDockWidgetArea)
                else Qt.Orientation.Vertical
            )
            if side in (Qt.DockWidgetArea.LeftDockWidgetArea, Qt.DockWidgetArea.TopDockWidgetArea):
                children = [payload, node]
            else:
                children = [node, payload]
            return _SplitNode(orientation, children)

        if isinstance(node, _SplitNode):
            node.children = [
                self._split_node(child, target_node, payload, side)
                for child in node.children
            ]
        return node

    def _remove_from_node(self, node: object, dock: LDockWidget) -> object | None:
        if isinstance(node, _DockNode):
            return None if node.dock is dock else node

        if isinstance(node, _TabNode):
            if dock not in node.docks:
                return node
            remaining = [d for d in node.docks if d is not dock]
            if not remaining:
                return None
            if len(remaining) == 1:
                return _DockNode(remaining[0])
            current_index = min(node.current_index, len(remaining) - 1)
            return _TabNode(remaining, current_index)

        remaining_children = []
        for child in node.children:
            updated = self._remove_from_node(child, dock)
            if updated is not None:
                remaining_children.append(updated)
        if not remaining_children:
            return None
        if len(remaining_children) == 1:
            return remaining_children[0]
        node.children = remaining_children
        return node

    def _export_node(self, node: object | None) -> object | None:
        if node is None:
            return None
        if isinstance(node, _DockNode):
            ident = node.dock.objectName() or node.dock.windowTitle()
            return {"type": "dock", "id": ident}
        if isinstance(node, _TabNode):
            return {
                "type": "tabs",
                "current_index": node.current_index,
                "children": [self._export_node(_DockNode(dock)) for dock in node.docks],
            }
        return {
            "type": "split",
            "orientation": int(node.orientation.value),
            "sizes": list(node.sizes),
            "children": [self._export_node(child) for child in node.children],
        }

    def _restore_node(self, payload: object | None, lookup: dict[str, LDockWidget]) -> object | None:
        if not isinstance(payload, dict):
            return None
        node_type = payload.get("type")
        if node_type == "dock":
            dock = lookup.get(payload.get("id"))
            return _DockNode(dock) if dock is not None else None
        if node_type == "tabs":
            docks: list[LDockWidget] = []
            for child in payload.get("children", []):
                restored = self._restore_node(child, lookup)
                if isinstance(restored, _DockNode):
                    docks.append(restored.dock)
            if not docks:
                return None
            if len(docks) == 1:
                return _DockNode(docks[0])
            current_index = min(payload.get("current_index", 0), len(docks) - 1)
            return _TabNode(docks, current_index)
        if node_type == "split":
            children = []
            for child in payload.get("children", []):
                restored = self._restore_node(child, lookup)
                if restored is not None:
                    children.append(restored)
            if not children:
                return None
            if len(children) == 1:
                return children[0]
            orientation = Qt.Orientation(
                payload.get("orientation", int(self._default_orientation().value))
            )
            return _SplitNode(orientation, children, list(payload.get("sizes", [])))
        return None

    def _clear_layout(self) -> None:
        from .ldock_widget import LDockWidget

        while self._layout.count():
            item = self._layout.takeAt(0)
            if item and item.widget():
                widget = item.widget()
                if isinstance(widget, LDockWidget):
                    widget._tab_visibility_sync = True
                    widget.hide()
                    widget._tab_visibility_sync = False
                else:
                    widget.hide()
                widget.setParent(None)
