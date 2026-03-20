"""LDragManager - singleton drag state machine + global event filter."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QPoint, QRect, Qt
from PySide6.QtWidgets import QApplication

from .ldrop_indicator import LDropIndicator

if TYPE_CHECKING:
    from .ldock_area import LDockArea
    from .ldock_widget import LDockWidget
    from .lmain_window import LMainWindow


_EDGE_FRACTION = 0.20
_AREA_CENTER_FRACTION = 0.55
_INDICATOR_MARGIN = 8


@dataclass(frozen=True)
class _DropTarget:
    main_window: LMainWindow
    area_side: object
    mode: str  # "side" | "tab" | "area"
    target_dock: LDockWidget | None = None
    target_id: str | None = None
    target_key: str | None = None
    target_rect: QRect | None = None
    relative_side: object | None = None


class LDragManager(QObject):
    """Singleton managing dock widget drag/drop operations."""

    _instance: LDragManager | None = None

    @classmethod
    def instance(cls) -> LDragManager:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        super().__init__()
        self._dock: LDockWidget | None = None
        self._payload: list[LDockWidget] = []
        self._origin_area: LDockArea | None = None
        self._origin_area_side = None
        self._origin_main_window = None
        self._drag_offset = QPoint()
        self._active = False
        self._indicator = LDropIndicator()
        self._drop_target: _DropTarget | None = None

    def begin_drag(
        self,
        dock: LDockWidget,
        global_pos: QPoint,
        payload: list[LDockWidget] | None = None,
    ) -> None:
        """Start a drag operation for ``dock`` or a grouped payload."""
        if self._active:
            return

        payload = payload or [dock]
        self._dock = dock
        self._payload = list(payload)
        self._origin_area = dock._current_area
        self._origin_area_side = (
            dock._current_area._area_side if dock._current_area else None
        )
        self._origin_main_window = dock._main_window
        if dock._current_area is not None:
            dock._pre_float_area_side = dock._current_area._area_side
            for payload_dock in list(self._payload):
                dock._current_area.remove_dock(payload_dock)
            if dock._main_window is not None:
                dock._main_window._sync_content_tree_to_areas()

        dock.setParent(None)
        flags = (
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        dock.setWindowFlags(flags)
        dock.resize(dock.sizeHint().expandedTo(dock.minimumSize()))
        dock_top_left = dock.mapToGlobal(QPoint(0, 0))
        self._drag_offset = global_pos - dock_top_left
        self._drag_offset.setX(max(0, min(self._drag_offset.x(), max(0, dock.width() - 1))))
        self._drag_offset.setY(max(0, min(self._drag_offset.y(), max(0, dock.height() - 1))))
        dock.move(global_pos - self._drag_offset)
        dock.show()
        dock.raise_()
        dock.activateWindow()
        dock._floating = True
        for payload_dock in self._payload:
            payload_dock._floating = True
            if payload_dock is not dock:
                payload_dock.hide()

        self._active = True
        QApplication.instance().installEventFilter(self)
        QApplication.setOverrideCursor(Qt.CursorShape.ClosedHandCursor)

    def cancel_drag(self) -> None:
        if not self._active or self._dock is None:
            return
        self._indicator.hide_indicator()
        QApplication.restoreOverrideCursor()
        QApplication.instance().removeEventFilter(self)

        dock = self._dock
        payload = list(self._payload)
        mw = self._origin_main_window
        side = self._origin_area_side
        self._reset()

        if mw is not None and side is not None:
            mw._drop_docks(side, payload)
            for payload_dock in payload:
                payload_dock.topLevelChanged.emit(False)
        else:
            for payload_dock in payload:
                payload_dock._floating = True
                if payload_dock is dock:
                    payload_dock.show()
                else:
                    payload_dock.hide()
                payload_dock.topLevelChanged.emit(True)

    def eventFilter(self, obj: QObject, event) -> bool:
        if not self._active or self._dock is None:
            return False

        from PySide6.QtCore import QEvent

        etype = event.type()
        if etype == QEvent.Type.MouseMove:
            self._on_mouse_move(event.globalPosition().toPoint())
            return True
        if etype == QEvent.Type.MouseButtonRelease:
            if event.button() == Qt.MouseButton.LeftButton:
                self._on_mouse_release()
                return True
        if etype == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
            self.cancel_drag()
            return True
        return False

    def _on_mouse_move(self, global_pos: QPoint) -> None:
        if self._dock is None:
            return
        self._dock.move(global_pos - self._drag_offset)

        target = self._find_drop_target(global_pos)
        if target is not None:
            self._drop_target = target
            self._indicator.show_at(self._compute_indicator_rect(target))
        else:
            self._drop_target = None
            self._indicator.hide_indicator()

    def _on_mouse_release(self) -> None:
        self._indicator.hide_indicator()
        QApplication.restoreOverrideCursor()
        QApplication.instance().removeEventFilter(self)

        dock = self._dock
        payload = list(self._payload)
        drop = self._drop_target
        self._reset()

        if dock is None:
            return

        if drop is not None:
            drop.main_window._drop_docks(
                drop.area_side,
                payload,
                mode=drop.mode,
                target_dock=drop.target_dock,
                target_id=drop.target_id,
                target_key=drop.target_key,
                side=drop.relative_side,
            )
            for payload_dock in payload:
                payload_dock.topLevelChanged.emit(False)
        else:
            for payload_dock in payload:
                payload_dock._floating = True
                if payload_dock is dock:
                    payload_dock.show()
                else:
                    payload_dock.hide()
                payload_dock.topLevelChanged.emit(True)

    def _find_drop_target(self, global_pos: QPoint) -> _DropTarget | None:
        from .lmain_window import LMainWindow

        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, LMainWindow) and widget.isVisible():
                local = widget.mapFromGlobal(global_pos)
                if widget.rect().contains(local):
                    target = self._classify_drop_zone(widget, global_pos, local)
                    if target is None or self._dock is None:
                        return target
                    if not widget._payload_allows_area(self._payload or [self._dock], target.area_side):
                        return None
                    return _DropTarget(
                        widget,
                        target.area_side,
                        target.mode,
                        target.target_dock,
                        target.target_id,
                        target.target_key,
                        target.target_rect,
                        target.relative_side,
                    )
        return None

    def _classify_drop_zone(
        self, mw: LMainWindow, global_or_local: QPoint, local: QPoint | None = None
    ) -> _DropTarget | None:
        from PySide6.QtCore import Qt as _Qt

        if local is None:
            local = global_or_local
            global_pos = mw.mapToGlobal(local)
        else:
            global_pos = global_or_local

        for area in mw._dock_areas.values():
            if not area.isVisible():
                continue
            area_local = area.mapFromGlobal(global_pos)
            if not area.rect().contains(area_local):
                continue
            if self._dock is not None and not self._dock.isAreaAllowed(area._area_side):
                return None

            target_info = area.drop_target_at_global_pos(global_pos)
            if target_info is not None:
                target_dock, target_rect, tab_bar_hit = target_info
                dock_local = global_pos - target_rect.topLeft()
                center_rect = QRect(
                    target_rect.width() // 4,
                    target_rect.height() // 4,
                    target_rect.width() // 2,
                    target_rect.height() // 2,
                )
                if tab_bar_hit or center_rect.contains(dock_local):
                    return _DropTarget(
                        mw,
                        area._area_side,
                        "tab",
                        target_dock=target_dock,
                        target_id=mw._dock_id(target_dock),
                        target_rect=target_rect,
                    )
                return _DropTarget(
                    mw,
                    area._area_side,
                    "side",
                    target_dock=target_dock,
                    target_id=mw._dock_id(target_dock),
                    target_rect=target_rect,
                    relative_side=self._relative_side(
                        QRect(QPoint(0, 0), target_rect.size()),
                        dock_local,
                    ),
                )

            if self._compute_area_tab_rect(area).contains(area_local):
                return _DropTarget(
                    mw,
                    area._area_side,
                    "tab",
                    target_rect=QRect(area.mapToGlobal(area.rect().topLeft()), area.size()),
                )
            return _DropTarget(
                mw,
                area._area_side,
                "area",
                target_rect=QRect(area.mapToGlobal(area.rect().topLeft()), area.size()),
            )

        central = mw.centralWidget() or getattr(mw, "_central_placeholder", None)
        if central is not None and central.isVisible():
            central_local = central.mapFromGlobal(global_pos)
            if central.rect().contains(central_local):
                rect = central.rect()
                edge = self._relative_side(rect, central_local)
                return _DropTarget(
                    mw,
                    edge,
                    "area",
                    target_key="central",
                    target_rect=QRect(central.mapToGlobal(rect.topLeft()), rect.size()),
                )

        w = mw.width()
        h = mw.height()
        mw_global = QRect(mw.mapToGlobal(mw.rect().topLeft()), mw.size())
        x, y = local.x(), local.y()
        f = _EDGE_FRACTION
        if x < w * f:
            return _DropTarget(
                mw,
                _Qt.DockWidgetArea.LeftDockWidgetArea,
                "area",
                target_rect=mw_global,
            )
        if x > w * (1 - f):
            return _DropTarget(
                mw,
                _Qt.DockWidgetArea.RightDockWidgetArea,
                "area",
                target_rect=mw_global,
            )
        if y < h * f:
            return _DropTarget(
                mw,
                _Qt.DockWidgetArea.TopDockWidgetArea,
                "area",
                target_rect=mw_global,
            )
        if y > h * (1 - f):
            return _DropTarget(
                mw,
                _Qt.DockWidgetArea.BottomDockWidgetArea,
                "area",
                target_rect=mw_global,
            )
        return None

    def _compute_indicator_rect(self, target: _DropTarget) -> QRect:
        from PySide6.QtCore import Qt as _Qt

        mw = target.main_window
        if target.mode == "tab":
            if target.target_rect is not None:
                bounded = target.target_rect.adjusted(
                    _INDICATOR_MARGIN,
                    _INDICATOR_MARGIN,
                    -_INDICATOR_MARGIN,
                    -_INDICATOR_MARGIN,
                )
                width = max(48, int(bounded.width() * _AREA_CENTER_FRACTION))
                height = max(32, int(bounded.height() * _AREA_CENTER_FRACTION))
                rect = QRect(0, 0, width, height)
                rect.moveCenter(bounded.center())
                return rect
            area = mw._dock_areas[target.area_side]
            local_rect = self._compute_area_tab_rect(area)
            return QRect(area.mapToGlobal(local_rect.topLeft()), local_rect.size())

        if (
            target.mode == "side"
            and target.target_rect is not None
            and target.relative_side is not None
        ):
            if target.relative_side == _Qt.DockWidgetArea.LeftDockWidgetArea:
                width = max(24, target.target_rect.width() // 3)
                return QRect(
                    target.target_rect.left() + _INDICATOR_MARGIN,
                    target.target_rect.top() + _INDICATOR_MARGIN,
                    width,
                    max(24, target.target_rect.height() - (_INDICATOR_MARGIN * 2)),
                )
            if target.relative_side == _Qt.DockWidgetArea.RightDockWidgetArea:
                width = max(24, target.target_rect.width() // 3)
                return QRect(
                    target.target_rect.right() - width - _INDICATOR_MARGIN + 1,
                    target.target_rect.top() + _INDICATOR_MARGIN,
                    width,
                    max(24, target.target_rect.height() - (_INDICATOR_MARGIN * 2)),
                )
            if target.relative_side == _Qt.DockWidgetArea.TopDockWidgetArea:
                height = max(24, target.target_rect.height() // 3)
                return QRect(
                    target.target_rect.left() + _INDICATOR_MARGIN,
                    target.target_rect.top() + _INDICATOR_MARGIN,
                    max(24, target.target_rect.width() - (_INDICATOR_MARGIN * 2)),
                    height,
                )
            height = max(24, target.target_rect.height() // 3)
            return QRect(
                target.target_rect.left() + _INDICATOR_MARGIN,
                target.target_rect.bottom() - height - _INDICATOR_MARGIN + 1,
                max(24, target.target_rect.width() - (_INDICATOR_MARGIN * 2)),
                height,
            )

        base_rect = target.target_rect
        if base_rect is None:
            tl = mw.mapToGlobal(mw.rect().topLeft())
            base_rect = QRect(tl, mw.size())
        w, h = base_rect.width(), base_rect.height()
        f = _EDGE_FRACTION
        if target.area_side == _Qt.DockWidgetArea.LeftDockWidgetArea:
            width = max(24, int(w * f))
            return QRect(
                base_rect.left() + _INDICATOR_MARGIN,
                base_rect.top() + _INDICATOR_MARGIN,
                width,
                max(24, h - (_INDICATOR_MARGIN * 2)),
            )
        if target.area_side == _Qt.DockWidgetArea.RightDockWidgetArea:
            width = max(24, int(w * f))
            return QRect(
                base_rect.right() - width - _INDICATOR_MARGIN + 1,
                base_rect.top() + _INDICATOR_MARGIN,
                width,
                max(24, h - (_INDICATOR_MARGIN * 2)),
            )
        if target.area_side == _Qt.DockWidgetArea.TopDockWidgetArea:
            height = max(24, int(h * f))
            return QRect(
                base_rect.left() + _INDICATOR_MARGIN,
                base_rect.top() + _INDICATOR_MARGIN,
                max(24, w - (_INDICATOR_MARGIN * 2)),
                height,
            )
        if target.area_side == _Qt.DockWidgetArea.BottomDockWidgetArea:
            height = max(24, int(h * f))
            return QRect(
                base_rect.left() + _INDICATOR_MARGIN,
                base_rect.bottom() - height - _INDICATOR_MARGIN + 1,
                max(24, w - (_INDICATOR_MARGIN * 2)),
                height,
            )
        return base_rect

    def _compute_area_tab_rect(self, area: LDockArea) -> QRect:
        rect = area.rect()
        bounded = rect.adjusted(
            _INDICATOR_MARGIN,
            _INDICATOR_MARGIN,
            -_INDICATOR_MARGIN,
            -_INDICATOR_MARGIN,
        )
        width = max(48, int(bounded.width() * _AREA_CENTER_FRACTION))
        height = max(32, int(bounded.height() * _AREA_CENTER_FRACTION))
        tab_rect = QRect(0, 0, width, height)
        tab_rect.moveCenter(bounded.center())
        return tab_rect

    def _relative_side(self, rect: QRect, point: QPoint):
        from PySide6.QtCore import Qt as _Qt

        left = point.x()
        right = rect.width() - point.x()
        top = point.y()
        bottom = rect.height() - point.y()
        smallest = min(left, right, top, bottom)
        if smallest == left:
            return _Qt.DockWidgetArea.LeftDockWidgetArea
        if smallest == right:
            return _Qt.DockWidgetArea.RightDockWidgetArea
        if smallest == top:
            return _Qt.DockWidgetArea.TopDockWidgetArea
        return _Qt.DockWidgetArea.BottomDockWidgetArea

    def _reset(self) -> None:
        self._dock = None
        self._payload = []
        self._origin_area = None
        self._origin_area_side = None
        self._origin_main_window = None
        self._drop_target = None
        self._active = False
