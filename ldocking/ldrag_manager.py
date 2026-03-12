"""LDragManager — singleton drag state machine + global event filter.

Lifecycle:
  1. LTitleBar.drag_started → LDragManager.begin_drag(dock, global_pos)
  2. Global event filter: mouseMoveEvent → move dock + show LDropIndicator
  3. Global event filter: mouseReleaseEvent → drop or keep floating
  4. Key Escape → cancel drag, restore dock to origin
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QPoint, QRect, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from .ldrop_indicator import LDropIndicator

if TYPE_CHECKING:
    from .ldock_area import LDockArea
    from .ldock_widget import LDockWidget
    from .lmain_window import LMainWindow


# Edge threshold fraction (20% of dimension)
_EDGE_FRACTION = 0.20


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
        self._origin_area: LDockArea | None = None
        self._origin_area_side = None
        self._origin_main_window = None
        self._drag_offset = QPoint()
        self._active = False
        self._indicator = LDropIndicator()
        self._drop_target: tuple[LMainWindow, object] | None = None  # (mw, area_side)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def begin_drag(self, dock: LDockWidget, global_pos: QPoint) -> None:
        """Start a drag operation for ``dock``."""
        if self._active:
            return

        self._dock = dock
        self._origin_area = dock._current_area
        self._origin_area_side = (
            dock._current_area._area_side if dock._current_area else None
        )
        self._origin_main_window = dock._main_window
        if dock._current_area is not None:
            dock._pre_float_area_side = dock._current_area._area_side

        # Detach from dock area, make floating
        if dock._current_area is not None:
            dock._current_area.remove_dock(dock)

        dock.setParent(None)
        flags = (
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        dock.setWindowFlags(flags)
        dock.resize(dock.sizeHint().expandedTo(dock.minimumSize()))
        # Center dock window under cursor
        self._drag_offset = QPoint(dock.width() // 2, 12)
        dock.move(global_pos - self._drag_offset)
        dock.show()
        dock._floating = True

        self._active = True
        QApplication.instance().installEventFilter(self)
        QApplication.setOverrideCursor(Qt.CursorShape.ClosedHandCursor)

    def cancel_drag(self) -> None:
        """Cancel the current drag, restoring dock to origin."""
        if not self._active or self._dock is None:
            return
        self._indicator.hide_indicator()
        QApplication.restoreOverrideCursor()
        QApplication.instance().removeEventFilter(self)

        dock = self._dock
        mw = self._origin_main_window
        side = self._origin_area_side
        self._reset()

        if mw is not None and side is not None:
            dock._floating = False
            mw.addDockWidget(side, dock)
            dock.topLevelChanged.emit(False)
        else:
            dock._floating = True
            dock.show()
            dock.topLevelChanged.emit(True)

    # ------------------------------------------------------------------
    # QObject event filter
    # ------------------------------------------------------------------

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
                self._on_mouse_release(event.globalPosition().toPoint())
                return True

        if etype == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                self.cancel_drag()
                return True

        return False

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _on_mouse_move(self, global_pos: QPoint) -> None:
        if self._dock is None:
            return
        self._dock.move(global_pos - self._drag_offset)

        mw, area_side = self._find_drop_target(global_pos)
        if mw is not None and area_side is not None:
            self._drop_target = (mw, area_side)
            rect = self._compute_indicator_rect(mw, area_side)
            self._indicator.show_at(rect)
        else:
            self._drop_target = None
            self._indicator.hide_indicator()

    def _on_mouse_release(self, global_pos: QPoint) -> None:
        self._indicator.hide_indicator()
        QApplication.restoreOverrideCursor()
        QApplication.instance().removeEventFilter(self)

        dock = self._dock
        drop = self._drop_target
        self._reset()

        if dock is None:
            return

        if drop is not None:
            mw, area_side = drop
            dock._floating = False
            mw.addDockWidget(area_side, dock)
            dock.topLevelChanged.emit(False)
        else:
            # Drop in empty space → keep floating
            dock._floating = True
            dock.topLevelChanged.emit(True)

    def _find_drop_target(
        self, global_pos: QPoint
    ) -> tuple[LMainWindow | None, object]:
        """Return (main_window, area_side) for the given global position."""
        from .lmain_window import LMainWindow

        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, LMainWindow) and widget.isVisible():
                local = widget.mapFromGlobal(global_pos)
                if widget.rect().contains(local):
                    area_side = self._classify_drop_zone(widget, local)
                    return widget, area_side
        return None, None

    def _classify_drop_zone(self, mw: LMainWindow, local: QPoint):
        """Return Qt.DockWidgetArea for the drop zone, or None."""
        from PySide6.QtCore import Qt as _Qt

        w = mw.width()
        h = mw.height()
        x, y = local.x(), local.y()
        f = _EDGE_FRACTION

        if x < w * f:
            return _Qt.DockWidgetArea.LeftDockWidgetArea
        if x > w * (1 - f):
            return _Qt.DockWidgetArea.RightDockWidgetArea
        if y < h * f:
            return _Qt.DockWidgetArea.TopDockWidgetArea
        if y > h * (1 - f):
            return _Qt.DockWidgetArea.BottomDockWidgetArea

        # Check if over a dock area for tab-drop
        for area in mw._dock_areas.values():
            if area.isVisible():
                area_local = area.mapFromGlobal(mw.mapToGlobal(local))
                if area.rect().contains(area_local):
                    return area._area_side

        return None

    def _compute_indicator_rect(self, mw: LMainWindow, area_side) -> QRect:
        from PySide6.QtCore import Qt as _Qt

        mw_rect = mw.geometry()
        # Map to global
        tl = mw.mapToGlobal(mw.rect().topLeft())
        mw_global = QRect(tl, mw.size())
        w, h = mw_global.width(), mw_global.height()
        f = _EDGE_FRACTION

        if area_side == _Qt.DockWidgetArea.LeftDockWidgetArea:
            return QRect(mw_global.left(), mw_global.top(), int(w * f), h)
        if area_side == _Qt.DockWidgetArea.RightDockWidgetArea:
            return QRect(mw_global.right() - int(w * f), mw_global.top(), int(w * f), h)
        if area_side == _Qt.DockWidgetArea.TopDockWidgetArea:
            return QRect(mw_global.left(), mw_global.top(), w, int(h * f))
        if area_side == _Qt.DockWidgetArea.BottomDockWidgetArea:
            return QRect(mw_global.left(), mw_global.bottom() - int(h * f), w, int(h * f))

        # Fallback: full main window
        return mw_global

    def _reset(self) -> None:
        self._dock = None
        self._origin_area = None
        self._origin_area_side = None
        self._origin_main_window = None
        self._drop_target = None
        self._active = False
