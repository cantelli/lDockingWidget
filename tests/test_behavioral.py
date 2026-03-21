"""Behavioral parity tests: signals, feature-flag enforcement, toggleViewAction,
resizeDocks, and other QDockWidget/QMainWindow contract items.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLabel, QWidget

import ldocking.monkey as monkey
from ldocking import (
    LDockWidget,
    LDragManager,
    LMainWindow,
    AllowNestedDocks,
    GroupedDragging,
    LeftDockWidgetArea,
    RightDockWidgetArea,
    TopDockWidgetArea,
    BottomDockWidgetArea,
    DockWidgetClosable,
    DockWidgetMovable,
    DockWidgetFloatable,
    NoDockWidgetFeatures,
    AllDockWidgetFeatures,
    ForceTabbedDocks,
    AnimatedDocks,
)
from ldocking.ldrag_manager import _DropTarget

NativeQDockWidget = monkey._ORIG["QDockWidget"]
NativeQMainWindow = monkey._ORIG["QMainWindow"]


def _dock(name: str) -> LDockWidget:
    d = LDockWidget(name)
    d.setObjectName(name)
    d.setWidget(QLabel(name))
    return d


def _native_dock(name: str) -> NativeQDockWidget:
    d = NativeQDockWidget(name)
    d.setObjectName(name)
    d.setWidget(QLabel(name))
    return d


def _tree_shape(node) -> tuple:
    if hasattr(node, "widget") and hasattr(node, "key"):
        return ("leaf", node.key)
    return (
        "split",
        int(node.orientation.value),
        tuple(_tree_shape(child) for child in node.children),
    )


# ------------------------------------------------------------------
# Signal: featuresChanged
# ------------------------------------------------------------------

def test_features_changed_fires(qapp):
    """featuresChanged emits when features actually change."""
    dock = _dock("d")
    received = []
    dock.featuresChanged.connect(lambda v: received.append(v))

    dock.setFeatures(DockWidgetClosable)
    assert len(received) == 1
    assert received[0] == DockWidgetClosable


def test_features_changed_no_fire_on_same_value(qapp):
    """featuresChanged does NOT emit when the same features are set again."""
    dock = _dock("d")
    dock.setFeatures(DockWidgetClosable)

    received = []
    dock.featuresChanged.connect(lambda v: received.append(v))
    dock.setFeatures(DockWidgetClosable)  # same value — no signal

    assert received == []


# ------------------------------------------------------------------
# Signal: allowedAreasChanged
# ------------------------------------------------------------------

def test_allowed_areas_changed_fires(qapp):
    """allowedAreasChanged emits when areas actually change."""
    dock = _dock("d")
    received = []
    dock.allowedAreasChanged.connect(lambda v: received.append(v))

    dock.setAllowedAreas(LeftDockWidgetArea)
    assert len(received) == 1


def test_allowed_areas_changed_no_fire_on_same_value(qapp):
    """allowedAreasChanged does NOT emit for a no-change setAllowedAreas."""
    dock = _dock("d")
    dock.setAllowedAreas(LeftDockWidgetArea)

    received = []
    dock.allowedAreasChanged.connect(lambda v: received.append(v))
    dock.setAllowedAreas(LeftDockWidgetArea)

    assert received == []


# ------------------------------------------------------------------
# Signal: visibilityChanged
# ------------------------------------------------------------------

def test_visibility_changed_on_hide_show(qapp):
    """visibilityChanged fires True on show and False on hide."""
    win = LMainWindow()
    dock = _dock("d")
    win.addDockWidget(LeftDockWidgetArea, dock)

    received = []
    dock.visibilityChanged.connect(lambda v: received.append(v))

    dock.hide()
    dock.show()

    assert False in received
    assert True in received


# ------------------------------------------------------------------
# Signal: dockLocationChanged
# ------------------------------------------------------------------

def test_dock_location_changed_fires(qapp):
    """dockLocationChanged emits the correct area when dock is added."""
    win = LMainWindow()
    dock = _dock("d")

    received = []
    dock.dockLocationChanged.connect(lambda a: received.append(a))

    win.addDockWidget(LeftDockWidgetArea, dock)
    assert received == [LeftDockWidgetArea]

    win.addDockWidget(RightDockWidgetArea, dock)
    assert received[-1] == RightDockWidgetArea


# ------------------------------------------------------------------
# Signal: topLevelChanged
# ------------------------------------------------------------------

def test_top_level_changed_on_float(qapp):
    """topLevelChanged(True) fires when dock floats, False when re-docked."""
    win = LMainWindow()
    win.resize(800, 600)
    dock = _dock("d")
    win.addDockWidget(LeftDockWidgetArea, dock)

    received = []
    dock.topLevelChanged.connect(lambda v: received.append(v))

    dock.setFloating(True)
    assert True in received

    dock.setFloating(False)
    assert False in received


def test_floating_title_drag_preserves_cursor_offset(qapp):
    """Dragging a floating dock moves it relative to the cursor's original hit point."""
    win = LMainWindow()
    win.resize(800, 600)
    dock = _dock("d")
    win.addDockWidget(LeftDockWidgetArea, dock)
    dock.setFloating(True)
    qapp.processEvents()

    start_global = dock.mapToGlobal(QPoint(17, 9))
    dock._on_drag_started(start_global)
    assert dock._float_drag_offset == QPoint(17, 9)

    move_global = start_global + QPoint(40, 30)
    dock._on_title_bar_move(move_global)
    assert dock.pos() == move_global - QPoint(17, 9)


def test_floating_cycle_clears_transient_resize_and_drag_state(qapp):
    """Repeated float/dock cycles clear stale drag and resize state."""
    win = LMainWindow()
    win.resize(800, 600)
    dock = _dock("d")
    win.addDockWidget(LeftDockWidgetArea, dock)

    dock.setFloating(True)
    dock._float_moving = True
    dock._resize_dir = 3
    dock.setFloating(False)

    assert not dock.isFloating()
    assert dock._float_moving is False
    assert dock._resize_dir == 0
    assert dock._float_drag_offset == QPoint()

    dock._float_moving = True
    dock._resize_dir = 5
    dock.setFloating(True)

    assert dock.isFloating()
    assert dock._float_moving is False
    assert dock._resize_dir == 0
    assert dock._float_drag_offset == QPoint()


def test_floating_resize_respects_minimum_size(qapp):
    """Floating border resize honors the dock's configured minimum size."""
    win = LMainWindow()
    dock = _dock("d")
    dock.setMinimumSize(180, 120)
    win.addDockWidget(LeftDockWidgetArea, dock)
    dock.setFloating(True)
    qapp.processEvents()

    start = dock.geometry()
    dock._resize_dir = 1 | 4
    dock._resize_start_pos = QPoint(0, 0)
    dock._resize_start_geom = QRect(start)
    dock._do_resize(QPoint(start.width(), start.height()))

    assert dock.width() >= 180
    assert dock.height() >= 120


def test_floating_resize_top_left_clamps_like_native_qt(qapp):
    """Top/left floating resize overshoot clamps to native Qt min/max geometry."""
    native_win = NativeQMainWindow()
    native_win.setCentralWidget(QLabel("center"))
    native = _native_dock("native")
    native.setMinimumSize(180, 120)
    native.setMaximumSize(220, 160)
    native_win.addDockWidget(LeftDockWidgetArea, native)
    native.setFloating(True)

    win = LMainWindow()
    win.setCentralWidget(QLabel("center"))
    dock = _dock("dock")
    dock.setMinimumSize(180, 120)
    dock.setMaximumSize(220, 160)
    win.addDockWidget(LeftDockWidgetArea, dock)
    dock.setFloating(True)
    qapp.processEvents()

    start_rect = QRect(100, 100, 220, 160)
    native.setGeometry(start_rect)
    dock.setGeometry(start_rect)
    qapp.processEvents()

    native_target = QRect(start_rect)
    native_target.setLeft(native_target.left() + 80)
    native_target.setTop(native_target.top() + 80)
    native.setGeometry(native_target)

    dock._resize_dir = 1 | 4
    dock._resize_start_pos = QPoint(0, 0)
    dock._resize_start_geom = QRect(start_rect)
    dock._do_resize(QPoint(80, 80))
    qapp.processEvents()

    assert dock.geometry() == native.geometry()


def test_floating_resize_top_left_grow_clamps_to_maximum_like_native_qt(qapp):
    """Growing a floating dock from top/left clamps to maximum size like native Qt."""
    native_win = NativeQMainWindow()
    native_win.setCentralWidget(QLabel("center"))
    native = _native_dock("native")
    native.setMinimumSize(180, 120)
    native.setMaximumSize(220, 160)
    native_win.addDockWidget(LeftDockWidgetArea, native)
    native.setFloating(True)

    win = LMainWindow()
    win.setCentralWidget(QLabel("center"))
    win.resize(800, 600)
    dock = _dock("dock")
    dock.setMinimumSize(180, 120)
    dock.setMaximumSize(220, 160)
    win.addDockWidget(LeftDockWidgetArea, dock)
    dock.setFloating(True)
    qapp.processEvents()

    start_rect = QRect(100, 100, 200, 140)
    native.setGeometry(start_rect)
    dock.setGeometry(start_rect)
    qapp.processEvents()

    native_target = QRect(start_rect)
    native_target.setLeft(native_target.left() - 80)
    native_target.setTop(native_target.top() - 80)
    native.setGeometry(native_target)

    dock._resize_dir = 1 | 4
    dock._resize_start_pos = QPoint(0, 0)
    dock._resize_start_geom = QRect(start_rect)
    dock._do_resize(QPoint(-80, -80))
    qapp.processEvents()

    assert dock.geometry() == native.geometry()


def test_tabified_hidden_peer_respects_maximum_size_like_native_qt(qapp):
    """Tabified dock peers keep native-like constrained sizes after initial tabify."""
    native_win = NativeQMainWindow()
    native_win.setCentralWidget(QLabel("center"))
    native_a = _native_dock("native_a")
    native_a.setMinimumWidth(120)
    native_a.setMaximumWidth(160)
    native_b = _native_dock("native_b")
    native_b.setMinimumWidth(220)
    native_b.setMaximumWidth(260)
    native_win.addDockWidget(LeftDockWidgetArea, native_a)
    native_win.addDockWidget(LeftDockWidgetArea, native_b)
    native_win.show()
    qapp.processEvents()
    native_win.tabifyDockWidget(native_a, native_b)

    win = LMainWindow()
    win.setCentralWidget(QLabel("center"))
    dock_a = _dock("dock_a")
    dock_a.setMinimumWidth(120)
    dock_a.setMaximumWidth(160)
    dock_b = _dock("dock_b")
    dock_b.setMinimumWidth(220)
    dock_b.setMaximumWidth(260)
    win.addDockWidget(LeftDockWidgetArea, dock_a)
    win.addDockWidget(LeftDockWidgetArea, dock_b)
    win.show()
    qapp.processEvents()
    win.tabifyDockWidget(dock_a, dock_b)
    qapp.processEvents()

    assert dock_a.width() == native_a.width()
    assert dock_b.width() == native_b.width()


def test_title_bar_button_press_does_not_start_drag_tracking(qapp):
    """Pressing the float button does not arm title-bar drag tracking."""
    dock = _dock("d")
    title_bar = dock._title_bar
    dock.show()
    qapp.processEvents()

    button_center = title_bar._float_btn.rect().center()
    QTest.mousePress(title_bar._float_btn, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, button_center)

    assert title_bar._press_pos is None
    assert title_bar._dragging is False

    QTest.mouseRelease(title_bar._float_btn, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, button_center)
    dock.hide()


# ------------------------------------------------------------------
# Feature flag enforcement: Floatable
# ------------------------------------------------------------------

def test_floatable_flag_controls_float_button(qapp):
    """Float button is hidden when DockWidgetFloatable is cleared."""
    dock = _dock("d")
    dock.setFeatures(DockWidgetClosable | DockWidgetMovable)  # no Floatable
    assert dock._title_bar._float_btn.isHidden()

    dock.setFeatures(AllDockWidgetFeatures)
    assert not dock._title_bar._float_btn.isHidden()


def test_floatable_flag_prevents_float(qapp):
    """Dock cannot float when DockWidgetFloatable is cleared."""
    win = LMainWindow()
    win.resize(800, 600)
    dock = _dock("d")
    win.addDockWidget(LeftDockWidgetArea, dock)
    dock.setFeatures(DockWidgetClosable | DockWidgetMovable)

    dock.setFloating(True)
    # setFloating should be a no-op because Floatable is off
    assert not dock.isFloating()


# ------------------------------------------------------------------
# Feature flag enforcement: Closable
# ------------------------------------------------------------------

def test_closable_flag_controls_close_button(qapp):
    """Close button is hidden when DockWidgetClosable is cleared."""
    dock = _dock("d")
    dock.setFeatures(DockWidgetMovable | DockWidgetFloatable)  # no Closable
    assert dock._title_bar._close_btn.isHidden()

    dock.setFeatures(AllDockWidgetFeatures)
    assert not dock._title_bar._close_btn.isHidden()


# ------------------------------------------------------------------
# toggleViewAction
# ------------------------------------------------------------------

def test_toggle_view_action_is_checkable(qapp):
    """toggleViewAction() returns a checkable QAction."""
    dock = _dock("d")
    action = dock.toggleViewAction()
    assert action.isCheckable()


def test_toggle_view_action_same_instance(qapp):
    """toggleViewAction() returns the same QAction on repeated calls."""
    dock = _dock("d")
    assert dock.toggleViewAction() is dock.toggleViewAction()


def test_toggle_view_action_text_matches_title(qapp):
    """Action text matches the dock's window title."""
    dock = _dock("MyTitle")
    assert dock.toggleViewAction().text() == "MyTitle"


def test_toggle_view_action_text_updates_on_rename(qapp):
    """Renaming the dock updates the action text."""
    dock = _dock("OldName")
    dock.setWindowTitle("NewName")
    assert dock.toggleViewAction().text() == "NewName"


def test_toggle_view_action_hides_dock(qapp):
    """Triggering the action (unchecked) hides the dock."""
    win = LMainWindow()
    dock = _dock("d")
    win.addDockWidget(LeftDockWidgetArea, dock)
    dock.show()

    action = dock.toggleViewAction()
    action.setChecked(False)
    assert not dock.isVisible()


def test_toggle_view_action_created_before_show_starts_checked(qapp):
    """A pre-show toggleViewAction matches Qt and hides on the first trigger."""
    win = LMainWindow()
    dock = _dock("d")
    win.addDockWidget(LeftDockWidgetArea, dock)
    action = dock.toggleViewAction()

    win.show()
    qapp.processEvents()

    assert action.isChecked()
    action.trigger()
    qapp.processEvents()
    assert not dock.isVisible()


def test_hidden_dock_stays_hidden_across_unrelated_area_rebuild(qapp):
    """Tabifying sibling docks does not resurrect another explicitly hidden dock."""
    win = LMainWindow()
    flags = _dock("Flags")
    annotations = _dock("Annotation List")
    hidden = _dock("Label List")
    extra = _dock("File List")
    for dock in (flags, annotations, hidden, extra):
        win.addDockWidget(RightDockWidgetArea, dock)
    win.show()
    qapp.processEvents()

    hidden.toggleViewAction().trigger()
    qapp.processEvents()
    assert not hidden.isVisible()

    win.tabifyDockWidget(flags, annotations)
    qapp.processEvents()
    assert not hidden.isVisible()


def test_toggle_view_action_shows_dock(qapp):
    """Triggering the action (checked) shows the dock."""
    win = LMainWindow()
    dock = _dock("d")
    win.addDockWidget(LeftDockWidgetArea, dock)
    dock.hide()

    action = dock.toggleViewAction()
    action.setChecked(True)
    assert not dock.isHidden()


def test_toggle_view_action_show_restores_hidden_tab_visibility_without_reselecting(qapp):
    """Showing a hidden non-current tab matches Qt: visible again, but not reselected."""
    win = LMainWindow()
    da = _dock("da")
    db = _dock("db")
    win.addDockWidget(LeftDockWidgetArea, da)
    win.addDockWidget(LeftDockWidgetArea, db)
    win.tabifyDockWidget(da, db)
    win.show()
    qapp.processEvents()

    area = win._dock_areas[LeftDockWidgetArea]
    area.set_current_tab_dock(da)
    db.hide()

    db.toggleViewAction().setChecked(True)

    assert db.isVisible()
    assert area.current_tab_dock() is da


def test_tabified_non_current_dock_remains_visible_like_qt(qapp):
    """Non-current tabified docks still report visible, matching native Qt."""
    native = NativeQMainWindow()
    native.setCentralWidget(QLabel("central"))
    native_a = _native_dock("a")
    native_b = _native_dock("b")
    native.addDockWidget(LeftDockWidgetArea, native_a)
    native.addDockWidget(LeftDockWidgetArea, native_b)
    native.tabifyDockWidget(native_a, native_b)
    native.show()

    win = LMainWindow()
    win.setCentralWidget(QLabel("central"))
    dock_a = _dock("a")
    dock_b = _dock("b")
    win.addDockWidget(LeftDockWidgetArea, dock_a)
    win.addDockWidget(LeftDockWidgetArea, dock_b)
    win.tabifyDockWidget(dock_a, dock_b)
    win.show()
    qapp.processEvents()

    assert dock_a.isVisible() is native_a.isVisible()
    assert dock_b.isVisible() is native_b.isVisible()


def test_tabified_tab_switch_visibility_signals_match_qt(qapp):
    """Tab switching keeps both docks visible and toggles visibilityChanged like Qt."""
    native = NativeQMainWindow()
    native.setCentralWidget(QLabel("central"))
    native_a = _native_dock("a")
    native_b = _native_dock("b")
    native_log = []
    native_a.visibilityChanged.connect(lambda value: native_log.append(("a", value)))
    native_b.visibilityChanged.connect(lambda value: native_log.append(("b", value)))
    native.addDockWidget(LeftDockWidgetArea, native_a)
    native.addDockWidget(LeftDockWidgetArea, native_b)
    native.tabifyDockWidget(native_a, native_b)
    native.show()

    win = LMainWindow()
    win.setCentralWidget(QLabel("central"))
    dock_a = _dock("a")
    dock_b = _dock("b")
    signal_log = []
    dock_a.visibilityChanged.connect(lambda value: signal_log.append(("a", value)))
    dock_b.visibilityChanged.connect(lambda value: signal_log.append(("b", value)))
    win.addDockWidget(LeftDockWidgetArea, dock_a)
    win.addDockWidget(LeftDockWidgetArea, dock_b)
    win.tabifyDockWidget(dock_a, dock_b)
    win.show()
    qapp.processEvents()

    native_b.raise_()
    win._dock_areas[LeftDockWidgetArea].set_current_tab_dock(dock_b)
    qapp.processEvents()

    native_log.clear()
    signal_log.clear()
    native_a.raise_()
    win._dock_areas[LeftDockWidgetArea].set_current_tab_dock(dock_a)
    qapp.processEvents()

    assert dock_a.isVisible() is native_a.isVisible()
    assert dock_b.isVisible() is native_b.isVisible()
    assert signal_log == native_log


def test_toggle_view_action_restores_hidden_floating_dock(qapp):
    """Showing a hidden floating dock keeps it floating."""
    win = LMainWindow()
    dock = _dock("d")
    win.addDockWidget(LeftDockWidgetArea, dock)
    dock.setFloating(True)
    dock.hide()

    dock.toggleViewAction().setChecked(True)

    assert dock.isVisible()
    assert dock.isFloating()


def test_frameless_main_window_preserves_dock_float_cycle(qapp):
    win = LMainWindow()
    win.setWindowFlags(win.windowFlags() | Qt.WindowType.FramelessWindowHint)
    dock = _dock("dock")
    win.addDockWidget(LeftDockWidgetArea, dock)
    win.show()
    qapp.processEvents()

    assert bool(win.windowFlags() & Qt.WindowType.FramelessWindowHint)
    assert dock.isVisible()
    assert win.dockWidgetArea(dock) == LeftDockWidgetArea

    dock.setFloating(True)
    qapp.processEvents()

    assert dock.isFloating()
    assert dock.isVisible()
    assert bool(win.windowFlags() & Qt.WindowType.FramelessWindowHint)

    dock.setFloating(False)
    qapp.processEvents()

    assert not dock.isFloating()
    assert dock.isVisible()
    assert win.dockWidgetArea(dock) == LeftDockWidgetArea


def test_custom_title_bar_widget_survives_float_redock_in_frameless_window(qapp):
    win = LMainWindow()
    win.setWindowFlags(win.windowFlags() | Qt.WindowType.FramelessWindowHint)
    dock = _dock("dock")
    custom_title = QWidget()
    custom_title.setObjectName("customTitleBar")
    custom_title.setMinimumHeight(28)
    dock.setTitleBarWidget(custom_title)
    dock.setWindowTitle("Renamed Dock")
    win.addDockWidget(LeftDockWidgetArea, dock)
    win.show()
    qapp.processEvents()

    assert dock.titleBarWidget() is custom_title
    assert custom_title.isVisible()
    assert custom_title.parent() is dock
    assert dock._title_bar.isHidden()

    dock.setFloating(True)
    qapp.processEvents()

    assert dock.isFloating()
    assert dock.isVisible()
    assert dock.titleBarWidget() is custom_title
    assert custom_title.isVisible()
    assert custom_title.parent() is dock

    dock.setFloating(False)
    qapp.processEvents()

    assert not dock.isFloating()
    assert dock.isVisible()
    assert win.dockWidgetArea(dock) == LeftDockWidgetArea
    assert dock.titleBarWidget() is custom_title
    assert custom_title.isVisible()
    assert custom_title.parent() is dock


def test_tabified_dock_remains_visible_when_floated_like_native_qt(qapp):
    """Floating the active tab from a tab group keeps the floated dock visible."""
    native_win = NativeQMainWindow()
    native_first = _native_dock("first")
    native_second = _native_dock("second")
    native_win.addDockWidget(RightDockWidgetArea, native_first)
    native_win.addDockWidget(RightDockWidgetArea, native_second)
    native_win.tabifyDockWidget(native_first, native_second)
    native_win.show()

    win = LMainWindow()
    first = _dock("first")
    second = _dock("second")
    win.addDockWidget(RightDockWidgetArea, first)
    win.addDockWidget(RightDockWidgetArea, second)
    win.tabifyDockWidget(first, second)
    win.show()
    qapp.processEvents()

    native_second.setFloating(True)
    second.setFloating(True)
    qapp.processEvents()

    assert second.isFloating() is native_second.isFloating()
    assert second.isVisible() is native_second.isVisible()
    assert first.isVisible() is native_first.isVisible()

    native_win.close()
    win.close()


def test_same_area_initial_split_heights_match_native_qt(qapp):
    """Sequential same-area docks start with Qt-like balanced heights."""
    native_win = NativeQMainWindow()
    native_first = _native_dock("first")
    native_second = _native_dock("second")
    native_win.addDockWidget(RightDockWidgetArea, native_first)
    native_win.addDockWidget(RightDockWidgetArea, native_second)
    native_win.show()

    win = LMainWindow()
    first = _dock("first")
    second = _dock("second")
    win.addDockWidget(RightDockWidgetArea, first)
    win.addDockWidget(RightDockWidgetArea, second)
    win.show()
    qapp.processEvents()

    native_delta = abs(native_first.height() - native_second.height())
    delta = abs(first.height() - second.height())

    assert delta <= 12
    assert abs(first.height() - native_first.height()) <= 12
    assert abs(second.height() - native_second.height()) <= 12
    assert delta <= native_delta + 12

    native_win.close()
    win.close()


def test_force_tabbed_docks_tabs_same_area(qapp):
    """ForceTabbedDocks keeps same-area docks in a tab group."""
    win = LMainWindow()
    win.setDockOptions(ForceTabbedDocks)
    da = _dock("da")
    db = _dock("db")

    win.addDockWidget(LeftDockWidgetArea, da)
    win.addDockWidget(LeftDockWidgetArea, db)

    assert db in win.tabifiedDockWidgets(da)


def test_add_dock_widget_same_area_does_not_auto_tabify(qapp):
    """Same-area addDockWidget matches Qt: split by default, tabify only when requested."""
    win = LMainWindow()
    da = _dock("da")
    db = _dock("db")

    win.addDockWidget(RightDockWidgetArea, da)
    win.addDockWidget(RightDockWidgetArea, db)

    assert win.tabifiedDockWidgets(da) == []
    leaf = win._leaf_for_key("right")
    assert leaf is not None
    assert leaf.area_state["type"] == "split"


def test_drag_manager_classifies_area_center_as_tab_target(qapp):
    """Dragging over the center of a visible dock area yields a tab target."""
    win = LMainWindow()
    win.resize(900, 700)
    win.show()
    dock = _dock("d")
    win.addDockWidget(LeftDockWidgetArea, dock)
    qapp.processEvents()

    dm = LDragManager.instance()
    area = win._dock_areas[LeftDockWidgetArea]
    center_global = area.mapToGlobal(area.rect().center())
    local = win.mapFromGlobal(center_global)

    dm._dock = dock
    target = dm._classify_drop_zone(win, local)

    assert target is not None
    assert target.area_side == LeftDockWidgetArea
    assert target.mode == "tab"
    assert target.target_id == "d"
    win.hide()


def test_drag_manager_classifies_window_edge_as_side_target(qapp):
    """Dragging near the main-window edge yields a side-dock target."""
    win = LMainWindow()
    win.resize(900, 700)
    win.show()
    dock = _dock("d")
    win.addDockWidget(LeftDockWidgetArea, dock)
    qapp.processEvents()

    dm = LDragManager.instance()
    dm._dock = dock
    target = dm._classify_drop_zone(win, win.rect().topLeft() + QPoint(5, 100))

    assert target is not None
    assert target.area_side == LeftDockWidgetArea
    assert target.mode == "side"
    win.hide()


def test_drag_manager_classifies_central_edge_as_area_target(qapp):
    """Dragging over a central-widget edge yields a root-tree area target."""
    win = LMainWindow()
    win.resize(900, 700)
    win.setCentralWidget(QLabel("central"))
    win.show()
    dock = _dock("d")
    qapp.processEvents()

    dm = LDragManager.instance()
    dm._dock = dock
    central = win.centralWidget()
    local = central.rect().center()
    local.setX(5)
    target = dm._classify_drop_zone(win, central.mapToGlobal(local), win.mapFromGlobal(central.mapToGlobal(local)))

    assert target is not None
    assert target.area_side == LeftDockWidgetArea
    assert target.mode == "area"
    assert target.target_key == "central"
    win.hide()


def test_allow_nested_docks_creates_nested_split(qapp):
    """AllowNestedDocks enables relative splits inside an occupied dock area."""
    win = LMainWindow()
    win.setDockOptions(AllowNestedDocks | AnimatedDocks)
    da = _dock("da")
    db = _dock("db")
    dc = _dock("dc")
    win.addDockWidget(LeftDockWidgetArea, da)
    win.addDockWidget(LeftDockWidgetArea, db)

    area = win._dock_areas[LeftDockWidgetArea]
    area.split_docks(da, [dc], RightDockWidgetArea)

    assert area._split_area is not None
    assert dc in area.all_docks()


def test_force_tabbed_docks_prevents_side_split_in_occupied_area(qapp):
    """ForceTabbedDocks turns a same-area side drop into tabbing instead of a split."""
    win = LMainWindow()
    win.setDockOptions(ForceTabbedDocks | AllowNestedDocks)
    anchor = _dock("anchor")
    moved = _dock("moved")
    win.addDockWidget(RightDockWidgetArea, anchor)

    win._drop_docks(
        RightDockWidgetArea,
        [moved],
        mode="side",
        target_id="anchor",
        side=BottomDockWidgetArea,
    )

    right_leaf = win._leaf_for_key("right")
    assert right_leaf is not None
    assert right_leaf.area_state["type"] == "tabs"
    assert [child["id"] for child in right_leaf.area_state["children"]] == ["anchor", "moved"]


def test_allow_nested_docks_off_collapses_side_drop_to_top_level(qapp):
    """Without AllowNestedDocks, a targeted side drop splits the whole area rather than nesting."""
    win = LMainWindow()
    win.setDockOptions(AnimatedDocks)
    anchor = _dock("anchor")
    sibling = _dock("sibling")
    moved = _dock("moved")
    win.addDockWidget(RightDockWidgetArea, anchor)
    win.addDockWidget(RightDockWidgetArea, sibling)

    win._drop_docks(
        RightDockWidgetArea,
        [moved],
        mode="side",
        target_id="anchor",
        side=BottomDockWidgetArea,
    )

    right_leaf = win._leaf_for_key("right")
    assert right_leaf is not None
    assert right_leaf.area_state["type"] == "split"
    assert len(right_leaf.area_state["children"]) == 2
    assert right_leaf.area_state["children"][0]["type"] == "split"
    assert right_leaf.area_state["children"][1]["id"] == "moved"


def test_grouped_dragging_uses_full_tab_payload(qapp):
    """GroupedDragging tears off the whole tab group rather than one dock."""
    win = LMainWindow()
    win.setDockOptions(ForceTabbedDocks | GroupedDragging)
    da = _dock("da")
    db = _dock("db")
    win.addDockWidget(LeftDockWidgetArea, da)
    win.addDockWidget(LeftDockWidgetArea, db)

    payload = win._dock_areas[LeftDockWidgetArea].docks_for_group_drag(da)

    assert payload == [da, db]


def test_drag_manager_targets_tab_group_bounds(qapp):
    """Hovering a tab group's tab bar targets the whole group, not only the visible dock body."""
    win = LMainWindow()
    win.resize(900, 700)
    da = _dock("da")
    db = _dock("db")
    win.addDockWidget(LeftDockWidgetArea, da)
    win.addDockWidget(LeftDockWidgetArea, db)
    win.tabifyDockWidget(da, db)
    area = win._dock_areas[LeftDockWidgetArea]
    area.set_current_tab_dock(da)
    win.show()
    qapp.processEvents()

    dm = LDragManager.instance()
    dm._dock = _dock("dragging")
    tab_bar = area._tab_area._tab_bar
    global_pos = tab_bar.mapToGlobal(tab_bar.rect().center())
    target = dm._classify_drop_zone(win, global_pos, win.mapFromGlobal(global_pos))

    assert target is not None
    assert target.mode == "tab"
    assert target.target_id == "da"
    assert target.target_rect is not None
    assert target.target_rect.height() == area._tab_area.height()
    win.hide()


def test_drag_indicator_tab_rect_stays_inside_hovered_group_bounds(qapp):
    """Tab preview rectangle is centered inside the hovered target bounds with margin."""
    win = LMainWindow()
    win.resize(900, 700)
    target_rect = QRect(100, 120, 300, 180)
    dm = LDragManager.instance()
    target = _DropTarget(
        win,
        LeftDockWidgetArea,
        "tab",
        target_id="anchor",
        target_rect=target_rect,
    )

    rect = dm._compute_indicator_rect(target)

    assert target_rect.contains(rect.center())
    assert rect.left() >= target_rect.left()
    assert rect.top() >= target_rect.top()
    assert rect.right() <= target_rect.right()
    assert rect.bottom() <= target_rect.bottom()


def test_drag_indicator_side_rect_uses_target_subtree_bounds(qapp):
    """Side preview rectangle stays inside the hovered subtree bounds, not full-window strips."""
    win = LMainWindow()
    win.resize(900, 700)
    target_rect = QRect(100, 120, 300, 180)
    dm = LDragManager.instance()
    target = _DropTarget(
        win,
        LeftDockWidgetArea,
        "side",
        target_id="anchor",
        target_rect=target_rect,
        relative_side=BottomDockWidgetArea,
    )

    rect = dm._compute_indicator_rect(target)

    assert rect.left() >= target_rect.left()
    assert rect.right() <= target_rect.right()
    assert rect.top() >= target_rect.top()
    assert rect.bottom() <= target_rect.bottom()
    assert rect.width() < target_rect.width()


def test_drag_indicator_central_edge_rect_uses_central_bounds(qapp):
    """Central-edge previews are bounded by the central widget, not the full main window."""
    win = LMainWindow()
    win.resize(900, 700)
    central = QLabel("central")
    central.resize(500, 360)
    win.setCentralWidget(central)
    win.show()
    qapp.processEvents()

    dm = LDragManager.instance()
    central_rect = QRect(central.mapToGlobal(central.rect().topLeft()), central.size())
    target = _DropTarget(
        win,
        LeftDockWidgetArea,
        "area",
        target_key="central",
        target_rect=central_rect,
    )

    rect = dm._compute_indicator_rect(target)

    assert rect.left() >= central_rect.left()
    assert rect.top() >= central_rect.top()
    assert rect.right() <= central_rect.right()
    assert rect.bottom() <= central_rect.bottom()
    assert rect.width() < central_rect.width()
    win.hide()


def test_drag_indicator_root_edge_rect_uses_window_bounds(qapp):
    """Root-edge previews still use the larger main-window frame bounds."""
    win = LMainWindow()
    win.resize(900, 700)
    win.show()
    qapp.processEvents()

    dm = LDragManager.instance()
    mw_global = QRect(win.mapToGlobal(win.rect().topLeft()), win.size())
    target = _DropTarget(
        win,
        LeftDockWidgetArea,
        "area",
        target_rect=mw_global,
    )

    rect = dm._compute_indicator_rect(target)

    assert rect.left() >= mw_global.left()
    assert rect.top() >= mw_global.top()
    assert rect.right() <= mw_global.right()
    assert rect.bottom() <= mw_global.bottom()
    assert rect.height() > mw_global.height() // 2
    win.hide()


def test_grouped_dragging_drop_preserves_current_tab(qapp):
    """Dropping a grouped tab payload keeps the selected tab in the moved group."""
    win = LMainWindow()
    win.setDockOptions(ForceTabbedDocks | GroupedDragging)
    da = _dock("da")
    db = _dock("db")
    target = _dock("target")
    win.addDockWidget(LeftDockWidgetArea, da)
    win.addDockWidget(LeftDockWidgetArea, db)
    win.addDockWidget(RightDockWidgetArea, target)
    win.tabifyDockWidget(da, db)

    source_area = win._dock_areas[LeftDockWidgetArea]
    source_area.set_current_tab_dock(db)
    payload = source_area.docks_for_group_drag(db)

    win._drop_docks(RightDockWidgetArea, payload, mode="side", target_dock=target, side=BottomDockWidgetArea)

    right_area = win._dock_areas[RightDockWidgetArea]
    assert [dock.windowTitle() for dock in right_area.all_docks()] == ["target", "da", "db"]
    assert right_area.current_tab_dock() is db


def test_grouped_dragging_rejects_drop_when_any_dock_disallows_area(qapp):
    """GroupedDragging rejects the whole drop if any dock in the group disallows the target area."""
    win = LMainWindow()
    win.setDockOptions(ForceTabbedDocks | GroupedDragging)
    da = _dock("da")
    db = _dock("db")
    target = _dock("target")
    db.setAllowedAreas(LeftDockWidgetArea)
    win.addDockWidget(LeftDockWidgetArea, da)
    win.addDockWidget(LeftDockWidgetArea, db)
    win.addDockWidget(RightDockWidgetArea, target)
    win.tabifyDockWidget(da, db)

    payload = win._dock_areas[LeftDockWidgetArea].docks_for_group_drag(da)
    before_left = [dock.windowTitle() for dock in win._dock_areas[LeftDockWidgetArea].all_docks()]
    before_right = [dock.windowTitle() for dock in win._dock_areas[RightDockWidgetArea].all_docks()]

    win._drop_docks(
        RightDockWidgetArea,
        payload,
        mode="side",
        target_id="target",
        side=BottomDockWidgetArea,
    )

    assert [dock.windowTitle() for dock in win._dock_areas[LeftDockWidgetArea].all_docks()] == before_left
    assert [dock.windowTitle() for dock in win._dock_areas[RightDockWidgetArea].all_docks()] == before_right


def test_drop_docks_accepts_target_id_without_target_widget(qapp):
    """Tree-driven drop accepts a stable target id without a live target widget object."""
    win = LMainWindow()
    win.setDockOptions(AllowNestedDocks | AnimatedDocks)
    anchor = _dock("anchor")
    moved = _dock("moved")
    win.addDockWidget(RightDockWidgetArea, anchor)

    win._drop_docks(
        RightDockWidgetArea,
        [moved],
        mode="side",
        target_id="anchor",
        side=BottomDockWidgetArea,
    )

    right_leaf = win._leaf_for_key("right")
    assert right_leaf is not None
    assert right_leaf.area_state["type"] == "split"
    assert [dock.windowTitle() for dock in win._dock_areas[RightDockWidgetArea].all_docks()] == ["anchor", "moved"]


def test_root_tree_grows_around_central_widget(qapp):
    """Top-level content tree wraps the full central shell when orientations change."""
    win = LMainWindow()
    left = _dock("left")
    top = _dock("top")
    right = _dock("right")

    win.addDockWidget(LeftDockWidgetArea, left)
    win.addDockWidget(TopDockWidgetArea, top)
    win.addDockWidget(RightDockWidgetArea, right)

    assert _tree_shape(win._content_tree) == (
        "split",
        int(Qt.Orientation.Vertical.value),
        (
            ("leaf", "top"),
            (
                "split",
                int(Qt.Orientation.Horizontal.value),
                (
                    ("leaf", "left"),
                    ("leaf", "central"),
                    ("leaf", "right"),
                ),
            ),
        ),
    )


def test_right_insert_stays_inside_top_owned_shell(qapp):
    """Adding a right dock after a top dock keeps top as the outer full-width owner."""
    win = LMainWindow()
    top = _dock("top")
    left = _dock("left")
    right = _dock("right")

    win.addDockWidget(TopDockWidgetArea, top)
    win.addDockWidget(LeftDockWidgetArea, left)
    win.addDockWidget(RightDockWidgetArea, right)

    assert _tree_shape(win._content_tree) == (
        "split",
        int(Qt.Orientation.Vertical.value),
        (
            ("leaf", "top"),
            (
                "split",
                int(Qt.Orientation.Horizontal.value),
                (
                    ("leaf", "left"),
                    ("leaf", "central"),
                    ("leaf", "right"),
                ),
            ),
        ),
    )


def test_root_tree_prunes_empty_area_leaves(qapp):
    """Removing the last dock from a side collapses that area out of the root tree."""
    win = LMainWindow()
    left = _dock("left")
    top = _dock("top")

    win.addDockWidget(LeftDockWidgetArea, left)
    win.addDockWidget(TopDockWidgetArea, top)
    win.removeDockWidget(left)

    assert win._leaf_for_key("left") is None
    assert _tree_shape(win._content_tree) == (
        "split",
        int(Qt.Orientation.Vertical.value),
        (
            ("leaf", "top"),
            ("leaf", "central"),
        ),
    )


# ------------------------------------------------------------------
# resizeDocks
# ------------------------------------------------------------------

def test_resize_docks_horizontal(qapp):
    """resizeDocks changes the outer splitter size for a left dock."""
    win = LMainWindow()
    win.resize(800, 600)
    win.show()

    dock = _dock("d")
    dock.setMinimumWidth(200)
    win.addDockWidget(LeftDockWidgetArea, dock)

    win.resizeDocks([dock], [200], Qt.Orientation.Horizontal)
    sizes = win._outer_splitter.sizes()
    left_idx = win._outer_splitter.indexOf(win._dock_areas[LeftDockWidgetArea])
    assert sizes[left_idx] == 200

    win.hide()


def test_resize_docks_vertical(qapp):
    """resizeDocks changes the inner splitter size for a top dock."""
    win = LMainWindow()
    win.resize(800, 600)
    win.show()

    dock = _dock("d")
    dock.setMinimumHeight(150)
    win.addDockWidget(TopDockWidgetArea, dock)

    win.resizeDocks([dock], [150], Qt.Orientation.Vertical)
    sizes = win._inner_splitter.sizes()
    top_idx = win._inner_splitter.indexOf(win._dock_areas[TopDockWidgetArea])
    assert sizes[top_idx] == 150

    win.hide()


def test_resize_docks_horizontal_matches_qt_with_constraints(qapp):
    """resizeDocks honors horizontal min/max constraints like native Qt."""
    native = NativeQMainWindow()
    native.setCentralWidget(QLabel("center"))
    native_left = _native_dock("native_left")
    native_left.setMinimumWidth(100)
    native_left.setMaximumWidth(150)
    native_right = _native_dock("native_right")
    native.addDockWidget(LeftDockWidgetArea, native_left)
    native.addDockWidget(RightDockWidgetArea, native_right)
    native.resize(800, 600)
    native.show()
    qapp.processEvents()

    win = LMainWindow()
    win.setCentralWidget(QLabel("center"))
    dock_left = _dock("dock_left")
    dock_left.setMinimumWidth(100)
    dock_left.setMaximumWidth(150)
    dock_right = _dock("dock_right")
    win.addDockWidget(LeftDockWidgetArea, dock_left)
    win.addDockWidget(RightDockWidgetArea, dock_right)
    win.resize(800, 600)
    win.show()
    qapp.processEvents()

    initial_right = dock_right.width()
    native.resizeDocks([native_left], [400], Qt.Orientation.Horizontal)
    win.resizeDocks([dock_left], [400], Qt.Orientation.Horizontal)
    qapp.processEvents()
    assert dock_left.width() == native_left.width()
    assert dock_right.width() == initial_right

    grown_width = dock_left.width()
    native.resizeDocks([native_left], [20], Qt.Orientation.Horizontal)
    win.resizeDocks([dock_left], [20], Qt.Orientation.Horizontal)
    qapp.processEvents()
    assert dock_left.width() < grown_width
    assert dock_left.width() >= dock_left.minimumWidth()
    assert dock_right.width() == initial_right


def test_resize_docks_vertical_matches_qt_with_constraints(qapp):
    """resizeDocks honors vertical min/max constraints like native Qt."""
    native = NativeQMainWindow()
    native.setCentralWidget(QLabel("center"))
    native_top = _native_dock("native_top")
    native_top.setMinimumHeight(90)
    native_top.setMaximumHeight(130)
    native_bottom = _native_dock("native_bottom")
    native.addDockWidget(TopDockWidgetArea, native_top)
    native.addDockWidget(BottomDockWidgetArea, native_bottom)
    native.resize(800, 600)
    native.show()
    qapp.processEvents()

    win = LMainWindow()
    win.setCentralWidget(QLabel("center"))
    dock_top = _dock("dock_top")
    dock_top.setMinimumHeight(90)
    dock_top.setMaximumHeight(130)
    dock_bottom = _dock("dock_bottom")
    win.addDockWidget(TopDockWidgetArea, dock_top)
    win.addDockWidget(BottomDockWidgetArea, dock_bottom)
    win.resize(800, 600)
    win.show()
    qapp.processEvents()

    initial_bottom = dock_bottom.height()
    native.resizeDocks([native_top], [300], Qt.Orientation.Vertical)
    win.resizeDocks([dock_top], [300], Qt.Orientation.Vertical)
    qapp.processEvents()
    assert dock_top.height() == native_top.height()
    assert dock_bottom.height() == initial_bottom

    native.resizeDocks([native_top], [20], Qt.Orientation.Vertical)
    win.resizeDocks([dock_top], [20], Qt.Orientation.Vertical)
    qapp.processEvents()
    assert dock_top.height() == native_top.height()
    assert dock_bottom.height() == initial_bottom


# ------------------------------------------------------------------
# tabifiedDockWidgets
# ------------------------------------------------------------------

def test_tabified_dock_widgets(qapp):
    """tabifiedDockWidgets returns peers excluding the queried dock."""
    win = LMainWindow()
    da = _dock("da")
    db = _dock("db")
    dc = _dock("dc")
    win.addDockWidget(LeftDockWidgetArea, da)
    win.addDockWidget(LeftDockWidgetArea, db)
    win.addDockWidget(LeftDockWidgetArea, dc)
    win.tabifyDockWidget(da, db)
    win.tabifyDockWidget(da, dc)

    peers_of_da = win.tabifiedDockWidgets(da)
    assert db in peers_of_da
    assert dc in peers_of_da
    assert da not in peers_of_da


def test_tabified_dock_widgets_empty_when_alone(qapp):
    """tabifiedDockWidgets returns [] for a dock that is the only one in its area."""
    win = LMainWindow()
    da = _dock("da")
    win.addDockWidget(LeftDockWidgetArea, da)
    assert win.tabifiedDockWidgets(da) == []


# ------------------------------------------------------------------
# dockWidgetArea
# ------------------------------------------------------------------

def test_dock_widget_area_tracks_moves(qapp):
    """dockWidgetArea returns the correct area after moving a dock."""
    win = LMainWindow()
    dock = _dock("d")
    win.addDockWidget(LeftDockWidgetArea, dock)
    assert win.dockWidgetArea(dock) == LeftDockWidgetArea

    win.addDockWidget(RightDockWidgetArea, dock)
    assert win.dockWidgetArea(dock) == RightDockWidgetArea


def test_dock_widget_area_unknown_returns_none(qapp):
    """dockWidgetArea returns NoDockWidgetArea for unregistered docks."""
    win = LMainWindow()
    dock = _dock("d")
    assert win.dockWidgetArea(dock) == Qt.DockWidgetArea.NoDockWidgetArea


def test_dock_widget_area_derives_from_live_layout_not_cache(qapp):
    """dockWidgetArea follows the live area contents even if the cache is stale."""
    win = LMainWindow()
    dock = _dock("d")
    win.addDockWidget(LeftDockWidgetArea, dock)

    win._dock_map[dock] = RightDockWidgetArea

    assert win.dockWidgetArea(dock) == LeftDockWidgetArea


def test_add_dock_widget_falls_back_to_first_allowed_area(qapp):
    """addDockWidget docks into the first allowed area when preferred area is invalid."""
    win = LMainWindow()
    dock = _dock("d")
    dock.setAllowedAreas(RightDockWidgetArea | BottomDockWidgetArea)

    win.addDockWidget(LeftDockWidgetArea, dock)

    assert win.dockWidgetArea(dock) == RightDockWidgetArea


def test_add_dock_widget_noops_when_no_areas_allowed(qapp):
    """addDockWidget leaves the dock untouched when no dock areas are allowed."""
    win = LMainWindow()
    dock = _dock("d")
    dock.setAllowedAreas(Qt.DockWidgetArea.NoDockWidgetArea)

    win.addDockWidget(LeftDockWidgetArea, dock)

    assert win.dockWidgetArea(dock) == Qt.DockWidgetArea.NoDockWidgetArea


# ------------------------------------------------------------------
# removeDockWidget
# ------------------------------------------------------------------

def test_remove_dock_widget(qapp):
    """removeDockWidget unregisters the dock from the window."""
    win = LMainWindow()
    dock = _dock("d")
    win.addDockWidget(LeftDockWidgetArea, dock)
    win.removeDockWidget(dock)
    assert win.dockWidgetArea(dock) == Qt.DockWidgetArea.NoDockWidgetArea


def test_remove_dock_widget_noop_unknown(qapp):
    """removeDockWidget on an unknown dock does not raise."""
    win = LMainWindow()
    dock = _dock("d")
    win.removeDockWidget(dock)  # should not raise


# ------------------------------------------------------------------
# tabifyDockWidget — tab order and active tab
# ------------------------------------------------------------------

def test_tabify_order_and_active_tab_matches_qt(qapp):
    """After sequential tabifyDockWidget calls ldocking tab order and active tab match Qt."""
    # --- ldocking side ---
    l_win = LMainWindow()
    da = _dock("A")
    db = _dock("B")
    dc = _dock("C")
    l_win.addDockWidget(LeftDockWidgetArea, da)
    l_win.addDockWidget(LeftDockWidgetArea, db)
    l_win.addDockWidget(LeftDockWidgetArea, dc)
    l_win.tabifyDockWidget(da, db)
    l_win.tabifyDockWidget(da, dc)
    l_win.show()
    qapp.processEvents()

    # Find the tab area for the left dock
    from ldocking.ldock_area import LDockArea
    from ldocking.ldock_tab_area import LDockTabArea
    left_area: LDockArea = l_win._dock_areas[Qt.DockWidgetArea.LeftDockWidgetArea]
    tab_widget = left_area._tab_area
    assert tab_widget is not None, "Expected LDockTabArea after tabify"

    l_count = tab_widget._tab_bar.count()
    l_titles = [tab_widget._tab_bar.tabText(i) for i in range(l_count)]
    l_current = tab_widget._tab_bar.currentIndex()

    # --- native Qt side ---
    qt_win = NativeQMainWindow()
    qa = _native_dock("A")
    qb = _native_dock("B")
    qc = _native_dock("C")
    qt_win.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, qa)
    qt_win.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, qb)
    qt_win.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, qc)
    qt_win.tabifyDockWidget(qa, qb)
    qt_win.tabifyDockWidget(qa, qc)
    qt_win.show()
    qapp.processEvents()

    qt_tabified = qt_win.tabifiedDockWidgets(qa)
    qt_titles_set = {qa.windowTitle()} | {d.windowTitle() for d in qt_tabified}

    # Tab count matches
    assert l_count == len(qt_titles_set), (
        f"ldocking tab count {l_count} != Qt tabified count {len(qt_titles_set)}"
    )
    # All expected titles present
    assert set(l_titles) == qt_titles_set, (
        f"ldocking tabs {l_titles} != Qt tabs {sorted(qt_titles_set)}"
    )
    # Active tab: Qt keeps the anchor (first) dock active; tabifyDockWidget does not
    # change the current tab when there are split siblings. Index 0 = anchor ("A").
    assert l_current == 0, f"Expected active tab index 0 (anchor, matching Qt), got {l_current}"


def test_drag_drop_back_to_emptied_area_no_phantom_split(qapp):
    """Dropping sole dock back to its source area fills the area completely."""
    win = LMainWindow()
    d = _dock("D")
    win.addDockWidget(LeftDockWidgetArea, d)

    # Simulate what the fixed begin_drag does: remove + sync
    win._dock_areas[LeftDockWidgetArea].remove_dock(d)
    win._sync_content_tree_to_areas()   # ← the fix

    win._drop_docks(LeftDockWidgetArea, [d], mode="area")
    qapp.processEvents()

    left = win._dock_areas[LeftDockWidgetArea]
    assert left.all_docks() == [d], "Expected sole dock, no phantom duplicate"
    assert win.dockWidgetArea(d) == LeftDockWidgetArea


def test_drag_drop_back_to_emptied_area_root_is_dock_node(qapp):
    """Area root after same-area redrop is a _DockNode, not a phantom _SplitNode."""
    from ldocking.ldock_area import _DockNode
    win = LMainWindow()
    d = _dock("D")
    win.addDockWidget(LeftDockWidgetArea, d)

    win._dock_areas[LeftDockWidgetArea].remove_dock(d)
    win._sync_content_tree_to_areas()

    win._drop_docks(LeftDockWidgetArea, [d], mode="area")
    qapp.processEvents()

    left = win._dock_areas[LeftDockWidgetArea]
    assert isinstance(left._root, _DockNode), (
        f"Expected _DockNode root (no phantom split), got {type(left._root).__name__}"
    )
