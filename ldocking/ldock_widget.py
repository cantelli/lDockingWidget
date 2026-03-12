"""LDockWidget — drop-in replacement for QDockWidget.

Uses QWidget as base to avoid QMainWindow's C++ type check on addDockWidget.
Floating uses Qt.Tool + FramelessWindowHint with a QSizeGrip for resizing.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QSizeGrip,
    QVBoxLayout,
    QWidget,
)

from .enums import (
    AllDockWidgetAreas,
    AllDockWidgetFeatures,
    BottomDockWidgetArea,
    DockWidgetArea,
    DockWidgetClosable,
    DockWidgetFeature,
    DockWidgetFloatable,
    DockWidgetMovable,
    DockWidgetVerticalTitleBar,
    LeftDockWidgetArea,
    NoDockWidgetArea,
    NoDockWidgetFeatures,
    RightDockWidgetArea,
    TopDockWidgetArea,
)
from .ltitle_bar import LTitleBar

if TYPE_CHECKING:
    from .ldock_area import LDockArea
    from .lmain_window import LMainWindow


# Resize handle width in pixels
_RESIZE_MARGIN = 5

# Resize direction bitmask helpers
_RESIZE_LEFT = 1
_RESIZE_RIGHT = 2
_RESIZE_TOP = 4
_RESIZE_BOTTOM = 8


class LDockWidget(QWidget):
    """Drop-in replacement for QDockWidget.

    Signals
    -------
    featuresChanged(DockWidgetFeature)
    allowedAreasChanged(Qt.DockWidgetArea)
    visibilityChanged(bool)
    topLevelChanged(bool)
    dockLocationChanged(Qt.DockWidgetArea)
    """

    featuresChanged = Signal(object)          # DockWidgetFeature
    allowedAreasChanged = Signal(object)      # Qt.DockWidgetArea
    visibilityChanged = Signal(bool)
    topLevelChanged = Signal(bool)
    dockLocationChanged = Signal(object)      # Qt.DockWidgetArea

    # Mirror QDockWidget class-level enum attributes (monkey-patch compatibility)
    DockWidgetFeature = DockWidgetFeature
    DockWidgetClosable = DockWidgetClosable
    DockWidgetMovable = DockWidgetMovable
    DockWidgetFloatable = DockWidgetFloatable
    DockWidgetVerticalTitleBar = DockWidgetVerticalTitleBar
    NoDockWidgetFeatures = NoDockWidgetFeatures
    AllDockWidgetFeatures = AllDockWidgetFeatures
    DockWidgetArea = DockWidgetArea
    LeftDockWidgetArea = LeftDockWidgetArea
    RightDockWidgetArea = RightDockWidgetArea
    TopDockWidgetArea = TopDockWidgetArea
    BottomDockWidgetArea = BottomDockWidgetArea
    AllDockWidgetAreas = AllDockWidgetAreas
    NoDockWidgetArea = NoDockWidgetArea

    def __init__(self, title: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._title = title
        self._content_widget: QWidget | None = None
        self._custom_title_bar: QWidget | None = None
        self._features: DockWidgetFeature = AllDockWidgetFeatures
        self._allowed_areas = AllDockWidgetAreas
        self._floating = False
        self._current_area: LDockArea | None = None
        self._main_window: LMainWindow | None = None
        self._toggle_action: QAction | None = None
        self._pre_float_area_side = None
        self._pre_float_position: int | None = None
        self._size_grip: QSizeGrip | None = None
        self._float_moving = False
        self._float_drag_offset = QPoint()

        # Resize drag state
        self._resize_dir = 0
        self._resize_start_pos = QPoint()
        self._resize_start_geom = QRect()

        self._build_ui()
        self.setWindowTitle(title)

    # ------------------------------------------------------------------
    # Public API (mirrors QDockWidget)
    # ------------------------------------------------------------------

    def setWidget(self, widget: QWidget | None) -> None:
        if self._content_widget is not None:
            self._content_widget.setParent(None)
        self._content_widget = widget
        if widget is not None:
            self._content_layout.addWidget(widget)

    def widget(self) -> QWidget | None:
        return self._content_widget

    def setTitleBarWidget(self, widget: QWidget | None) -> None:
        if self._custom_title_bar is not None:
            self._custom_title_bar.setParent(None)
        self._custom_title_bar = widget
        # Remove default title bar
        if widget is None:
            if self._title_bar.parent() is None:
                self._outer_layout.insertWidget(0, self._title_bar)
            self._title_bar.show()
        else:
            self._title_bar.hide()
            self._title_bar.setParent(None)
            self._outer_layout.insertWidget(0, widget)

    def titleBarWidget(self) -> QWidget | None:
        return self._custom_title_bar

    def setFeatures(self, features: DockWidgetFeature) -> None:
        if features == self._features:
            return
        self._features = features
        self._sync_feature_ui()
        self.featuresChanged.emit(features)

    def features(self) -> DockWidgetFeature:
        return self._features

    def setAllowedAreas(self, areas) -> None:
        if areas == self._allowed_areas:
            return
        self._allowed_areas = areas
        self.allowedAreasChanged.emit(areas)

    def allowedAreas(self):
        return self._allowed_areas

    def isAreaAllowed(self, area: Qt.DockWidgetArea) -> bool:
        return bool(self._allowed_areas & area)

    def isFloating(self) -> bool:
        return self._floating

    def setFloating(self, floating: bool) -> None:
        if floating == self._floating:
            return
        if floating:
            if not bool(self._features & DockWidgetFloatable):
                return
            self._float_out()
        else:
            self._dock_back()

    def setWindowTitle(self, title: str) -> None:  # type: ignore[override]
        self._title = title
        self._title_bar.set_title(title)
        super().setWindowTitle(title)
        if self._toggle_action is not None:
            self._toggle_action.setText(title)

    def windowTitle(self) -> str:
        return self._title

    def toggleViewAction(self) -> QAction:
        if self._toggle_action is None:
            self._toggle_action = QAction(self._title, self)
            self._toggle_action.setCheckable(True)
            self._toggle_action.setChecked(self.isVisible())
            self._toggle_action.toggled.connect(self.setVisible)
            self.visibilityChanged.connect(self._toggle_action.setChecked)
        return self._toggle_action

    # ------------------------------------------------------------------
    # Internal: float / dock transitions
    # ------------------------------------------------------------------

    def _float_out(self, pos: QPoint | None = None) -> None:
        """Detach from dock area and become a floating top-level window."""
        # Capture geometry BEFORE detaching (mapToGlobal needs a live parent chain)
        snap_pos = self.mapToGlobal(QPoint(0, 0))
        snap_size = self.size()

        if self._current_area is not None:
            self._pre_float_position = self._current_area._docks.index(self)  # store BEFORE remove_dock clears _current_area
            self._pre_float_area_side = self._current_area._area_side
            self._current_area.remove_dock(self)

        self.setParent(None)
        flags = (
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setWindowFlags(flags)
        self.setWindowTitle(self._title)

        # Add size grip only when not already in layout
        if self._size_grip is None:
            self._size_grip = QSizeGrip(self)
        if self._outer_layout.indexOf(self._size_grip) < 0:
            self._outer_layout.addWidget(self._size_grip)
        self._size_grip.show()

        if pos is not None:
            self.move(pos)
        else:
            self.move(snap_pos)

        if snap_size.isValid() and snap_size.width() >= 80 and snap_size.height() >= 40:
            self.resize(snap_size)

        self._floating = True
        self._title_bar.set_float_button_icon(True)
        self.show()
        self.topLevelChanged.emit(True)

    def _dock_back(self) -> None:
        """Re-dock into the main window (last known area, or Left)."""
        if self._main_window is None:
            return
        area = self._pre_float_area_side or Qt.DockWidgetArea.LeftDockWidgetArea

        # Remove size grip from layout
        if self._size_grip is not None:
            self._outer_layout.removeWidget(self._size_grip)
            self._size_grip.hide()

        self._floating = False
        self._main_window.addDockWidget(area, self)
        self.setWindowFlags(Qt.WindowType.Widget)   # clear stale floating flags
        self._title_bar.set_float_button_icon(False)
        self.topLevelChanged.emit(False)

    # ------------------------------------------------------------------
    # Internal: UI setup
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self._outer_layout = QVBoxLayout(self)
        self._outer_layout.setContentsMargins(0, 0, 0, 0)
        self._outer_layout.setSpacing(0)

        self._title_bar = LTitleBar(self._title)
        self._title_bar.float_requested.connect(self._on_float_requested)
        self._title_bar.close_requested.connect(self.close)
        self._title_bar.drag_started.connect(self._on_drag_started)
        self._title_bar.move_dragging.connect(self._on_title_bar_move)
        self._title_bar.drag_released.connect(lambda: setattr(self, '_float_moving', False))

        self._outer_layout.addWidget(self._title_bar)

        # Content area
        self._content_container = QWidget()
        self._content_container.setObjectName("dockContent")
        self._content_container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._content_layout = QVBoxLayout(self._content_container)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._outer_layout.addWidget(self._content_container, 1)

        self._sync_feature_ui()

    def _sync_feature_ui(self) -> None:
        closable = bool(self._features & DockWidgetClosable)
        floatable = bool(self._features & DockWidgetFloatable)
        self._title_bar.show_close_button(closable)
        self._title_bar.show_float_button(floatable)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_float_requested(self) -> None:
        if self._floating:
            self._dock_back()
        else:
            if bool(self._features & DockWidgetFloatable):
                self._float_out()

    def _on_drag_started(self, global_pos: QPoint) -> None:
        if self._floating:
            self._float_drag_offset = global_pos - self.pos()
            self._float_moving = True       # native window move mode
        else:
            from .ldrag_manager import LDragManager
            LDragManager.instance().begin_drag(self, global_pos)

    def _on_title_bar_move(self, global_pos: QPoint) -> None:
        if not self._floating or not self._float_moving:
            return
        self.move(global_pos - self._float_drag_offset)
        # Hand off to LDragManager when cursor enters a main-window edge zone
        if self._main_window is not None:
            local = self._main_window.mapFromGlobal(global_pos)
            if self._main_window.rect().contains(local):
                from .ldrag_manager import LDragManager
                dm = LDragManager.instance()
                if dm._classify_drop_zone(self._main_window, local) is not None:
                    self._float_moving = False
                    dm.begin_drag(self, global_pos)

    # ------------------------------------------------------------------
    # Visibility
    # ------------------------------------------------------------------

    def setVisible(self, visible: bool) -> None:
        super().setVisible(visible)
        self.visibilityChanged.emit(visible)

    # ------------------------------------------------------------------
    # Mouse events for border-resize when floating
    # ------------------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        if self._floating and event.button() == Qt.MouseButton.LeftButton:
            self._resize_dir = self._hit_test_border(
                event.position().toPoint()
            )
            if self._resize_dir:
                self._resize_start_pos = event.globalPosition().toPoint()
                self._resize_start_geom = self.geometry()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._floating:
            pos = event.position().toPoint()
            if self._resize_dir and (event.buttons() & Qt.MouseButton.LeftButton):
                self._do_resize(event.globalPosition().toPoint())
                event.accept()
                return
            # Update cursor
            direction = self._hit_test_border(pos)
            self._set_resize_cursor(direction)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._resize_dir:
            self._resize_dir = 0
            self.unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _hit_test_border(self, local_pos: QPoint) -> int:
        m = _RESIZE_MARGIN
        w, h = self.width(), self.height()
        x, y = local_pos.x(), local_pos.y()
        direction = 0
        if x < m:
            direction |= _RESIZE_LEFT
        elif x > w - m:
            direction |= _RESIZE_RIGHT
        if y < m:
            direction |= _RESIZE_TOP
        elif y > h - m:
            direction |= _RESIZE_BOTTOM
        return direction

    def _set_resize_cursor(self, direction: int) -> None:
        cursors = {
            _RESIZE_LEFT: Qt.CursorShape.SizeHorCursor,
            _RESIZE_RIGHT: Qt.CursorShape.SizeHorCursor,
            _RESIZE_TOP: Qt.CursorShape.SizeVerCursor,
            _RESIZE_BOTTOM: Qt.CursorShape.SizeVerCursor,
            _RESIZE_LEFT | _RESIZE_TOP: Qt.CursorShape.SizeFDiagCursor,
            _RESIZE_RIGHT | _RESIZE_BOTTOM: Qt.CursorShape.SizeFDiagCursor,
            _RESIZE_RIGHT | _RESIZE_TOP: Qt.CursorShape.SizeBDiagCursor,
            _RESIZE_LEFT | _RESIZE_BOTTOM: Qt.CursorShape.SizeBDiagCursor,
        }
        cursor = cursors.get(direction)
        if cursor is not None:
            self.setCursor(cursor)
        else:
            self.unsetCursor()

    def _do_resize(self, global_pos: QPoint) -> None:
        delta = global_pos - self._resize_start_pos
        geom = QRect(self._resize_start_geom)
        min_w, min_h = 100, 60

        if self._resize_dir & _RESIZE_LEFT:
            new_left = geom.left() + delta.x()
            if geom.right() - new_left >= min_w:
                geom.setLeft(new_left)
        if self._resize_dir & _RESIZE_RIGHT:
            new_right = geom.right() + delta.x()
            if new_right - geom.left() >= min_w:
                geom.setRight(new_right)
        if self._resize_dir & _RESIZE_TOP:
            new_top = geom.top() + delta.y()
            if geom.bottom() - new_top >= min_h:
                geom.setTop(new_top)
        if self._resize_dir & _RESIZE_BOTTOM:
            new_bottom = geom.bottom() + delta.y()
            if new_bottom - geom.top() >= min_h:
                geom.setBottom(new_bottom)

        self.setGeometry(geom)
