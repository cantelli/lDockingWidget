"""LDockWidget — drop-in replacement for QDockWidget.

Uses QWidget as base to avoid QMainWindow's C++ type check on addDockWidget.
Floating stays in a frameless Qt.Tool window with a QSizeGrip for resizing.
That keeps the implementation independent from Qt's native dock internals, but
means floating chrome is only approximately Qt-like rather than pixel-identical.
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
    DockWidgetFeatures,
    DockWidgetFloatable,
    DockWidgetMovable,
    DockWidgetVerticalTitleBar,
    LeftDockWidgetArea,
    NoDockWidgetArea,
    NoDockWidgetFeatures,
    RightDockWidgetArea,
    TopDockWidgetArea,
)
from .stylesheet_compat import translate_stylesheet
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
_DEFAULT_FLOATING_SIZE = QSize(260, 180)


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
    DockWidgetFeatures = DockWidgetFeatures
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
        self.setProperty("class", "QDockWidget")
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
        self._tabbed_visibility_override: bool | None = None
        self._tab_visibility_sync = False
        self._explicitly_hidden = False
        self._pre_float_restore_hint: dict[str, object] | None = None
        self._pre_float_selected = False
        self._pre_float_save_as_docked = False
        self._restored_docked_size: QSize | None = None
        self._pending_float_pos: QPoint | None = None
        self._pending_float_size: QSize | None = None

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

    def sizeHint(self) -> QSize:  # type: ignore[override]
        base = super().sizeHint()
        content_widget = getattr(self, "_content_widget", None)
        title_bar = getattr(self, "_title_bar", None)
        if content_widget is None:
            return base
        content_hint = content_widget.sizeHint()
        title_h = title_bar.sizeHint().height() if title_bar is not None else 0
        return QSize(
            max(base.width(), content_hint.width()),
            max(base.height(), content_hint.height() + title_h),
        )

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

    def isVisible(self) -> bool:  # type: ignore[override]
        if self._tabbed_visibility_override is not None:
            return self._tabbed_visibility_override
        return super().isVisible()

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

    def setStyleSheet(self, styleSheet: str) -> None:  # type: ignore[override]
        super().setStyleSheet(translate_stylesheet(styleSheet))

    def toggleViewAction(self) -> QAction:
        if self._toggle_action is None:
            self._toggle_action = QAction(self._title, self)
            self._toggle_action.setCheckable(True)
            self._toggle_action.setChecked(self._toggle_action_checked_value())
            self._toggle_action.toggled.connect(self.setVisible)
        return self._toggle_action

    def close(self) -> bool:  # type: ignore[override]
        if (
            self._current_area is not None
            and self._current_area.handle_tabified_visibility_request(self, False)
        ):
            return True
        return super().close()

    # ------------------------------------------------------------------
    # Internal: float / dock transitions
    # ------------------------------------------------------------------

    def _reset_interaction_state(self) -> None:
        self._float_moving = False
        self._float_drag_offset = QPoint()
        self._resize_dir = 0
        self._resize_start_pos = QPoint()
        self._resize_start_geom = QRect()
        self.unsetCursor()

    def _float_out(self, pos: QPoint | None = None) -> None:
        """Detach from dock area and become a floating top-level window."""
        self._reset_interaction_state()
        if self._main_window is not None:
            self._main_window._snapshot_floating_geometries()

        # Capture geometry BEFORE detaching (mapToGlobal needs a live parent chain)
        snap_pos = self._pending_float_pos or self.mapToGlobal(QPoint(0, 0))
        snap_size = self._pending_float_size or self.size()
        self._pending_float_pos = None
        self._pending_float_size = None
        # Retain the actual docked size (matches Qt QDockWidget behaviour).
        # Only expand to minimumSizeHint so the title bar remains usable when
        # a dock was extremely narrow in its docked position.
        floating_size = snap_size.expandedTo(
            self.minimumSizeHint().expandedTo(self.minimumSize())
        )

        if self._current_area is not None:
            dock_id = self._main_window._dock_id(self) if self._main_window is not None else None
            self._pre_float_restore_hint = None
            self._pre_float_selected = False
            self._pre_float_save_as_docked = False
            if self._main_window is not None and dock_id is not None:
                hints: dict[str, dict[str, object]] = {}
                area_state = self._current_area.export_state()
                self._main_window._collect_restore_hints(area_state, hints)
                self._pre_float_restore_hint = hints.get(dock_id)
                current = self._current_area.current_tab_dock()
                current_id = self._main_window._dock_id(current) if current is not None else None
                self._pre_float_selected = current_id == dock_id
                self._pre_float_save_as_docked = bool(
                    self._pre_float_restore_hint
                    and self._pre_float_restore_hint.get("restore_mode") == "tab"
                )
            self._pre_float_position = self._current_area._insertion_order.get(
                self,
                self._current_area._docks.index(self),
            )
            self._pre_float_area_side = self._current_area._area_side
            self._current_area.remove_dock(self)
            if self._main_window is not None:
                self._main_window._sync_content_tree_to_areas()

        flags = (
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        # Keep the main window as the native owner of the Tool window.
        # On Windows, a Tool window with no owner has no z-order relationship
        # with the application and may disappear behind the main window.
        if self._main_window is not None:
            self.setParent(self._main_window, flags)
        else:
            self.setParent(None, flags)
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

        if floating_size.isValid() and floating_size.width() >= 80 and floating_size.height() >= 40:
            self.resize(floating_size)

        self._floating = True
        self._title_bar.set_float_button_icon(True)
        self.show()
        self.raise_()
        self.activateWindow()
        self.topLevelChanged.emit(True)

    def _dock_back(self) -> None:
        """Re-dock into the main window (last known area, or Left)."""
        if self._main_window is None:
            return
        self._reset_interaction_state()
        preferred_area = self._pre_float_area_side or Qt.DockWidgetArea.LeftDockWidgetArea
        area = self._main_window._resolve_dock_area(self, preferred_area)
        if area is None:
            return

        # Remove size grip from layout
        if self._size_grip is not None:
            self._outer_layout.removeWidget(self._size_grip)
            self._size_grip.hide()

        hint = getattr(self, "_pre_float_restore_hint", None)
        mode = hint.get("restore_mode") if hint else None
        target_id = hint.get("restore_target_id") if hint else None
        restore_side = None
        if hint and hint.get("restore_side") is not None:
            try:
                restore_side = Qt.DockWidgetArea(int(hint["restore_side"]))
            except (TypeError, ValueError):
                restore_side = None
        target_available = (
            isinstance(target_id, str)
            and self._main_window._state_contains_id(
                self._main_window._area_state(area), target_id
            )
        )
        if mode in {"tab", "side"} and target_available:
            self._main_window._drop_docks(
                area, [self], mode=mode, target_id=target_id, side=restore_side,
            )
            self.dockLocationChanged.emit(area)
        else:
            self._main_window.addDockWidget(area, self)
        self._title_bar.set_float_button_icon(False)
        if self._main_window is not None:
            self._main_window.raise_()
            self._main_window.activateWindow()
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
        self._title_bar.drag_released.connect(self._reset_interaction_state)

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
        if not bool(self._features & DockWidgetMovable):
            return
        if self._floating:
            self._resize_dir = 0
            self.unsetCursor()
            top_left = self.frameGeometry().topLeft()
            self._float_drag_offset = global_pos - top_left
            self._float_moving = True       # native window move mode
            self.raise_()
            self.activateWindow()
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

    def _set_tabbed_visibility_override(self, visible: bool | None) -> None:
        self._tabbed_visibility_override = visible
        self._sync_toggle_action_checked()

    def _sync_toggle_action_checked(self) -> None:
        if not hasattr(self, "_toggle_action") or self._toggle_action is None:
            return
        checked = self._toggle_action_checked_value()
        if self._toggle_action.isChecked() == checked:
            return
        was_blocked = self._toggle_action.blockSignals(True)
        self._toggle_action.setChecked(checked)
        self._toggle_action.blockSignals(was_blocked)

    def _toggle_action_checked_value(self) -> bool:
        return not self._explicitly_hidden

    def setVisible(self, visible: bool) -> None:
        if self._tab_visibility_sync:
            super().setVisible(visible)
            if not visible:
                self._reset_interaction_state()
            return
        self._explicitly_hidden = not visible
        if (
            self._current_area is not None
            and self._current_area.handle_tabified_visibility_request(self, visible)
        ):
            return
        previous_visible = self.isVisible()
        super().setVisible(visible)
        if (
            visible
            and self._current_area is not None
            and self._tabbed_visibility_override is None
        ):
            self._current_area.set_current_tab_dock(self)
        if not visible:
            self._reset_interaction_state()
        if previous_visible != self.isVisible():
            self._sync_toggle_action_checked()
        self.visibilityChanged.emit(visible)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync_toggle_action_checked()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._sync_toggle_action_checked()

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
            self._reset_interaction_state()
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
        start = QRect(self._resize_start_geom)
        minimum = self.minimumSizeHint().expandedTo(self.minimumSize())
        maximum = self.maximumSize()
        min_w = minimum.width()
        min_h = minimum.height()
        max_w = max(min_w, maximum.width())
        max_h = max(min_h, maximum.height())

        new_x = start.x()
        new_y = start.y()
        new_w = start.width()
        new_h = start.height()

        if self._resize_dir & _RESIZE_LEFT:
            requested_w = start.width() - delta.x()
            new_w = max(min_w, min(requested_w, max_w))
            new_x = start.x() + delta.x()
        elif self._resize_dir & _RESIZE_RIGHT:
            requested_w = start.width() + delta.x()
            new_w = max(min_w, min(requested_w, max_w))

        if self._resize_dir & _RESIZE_TOP:
            requested_h = start.height() - delta.y()
            new_h = max(min_h, min(requested_h, max_h))
            new_y = start.y() + delta.y()
        elif self._resize_dir & _RESIZE_BOTTOM:
            requested_h = start.height() + delta.y()
            new_h = max(min_h, min(requested_h, max_h))

        self.setGeometry(new_x, new_y, new_w, new_h)
