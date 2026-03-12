"""Behavioral parity tests: signals, feature-flag enforcement, toggleViewAction,
resizeDocks, and other QDockWidget/QMainWindow contract items.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from ldocking import (
    LDockWidget,
    LMainWindow,
    LeftDockWidgetArea,
    RightDockWidgetArea,
    TopDockWidgetArea,
    BottomDockWidgetArea,
    DockWidgetClosable,
    DockWidgetMovable,
    DockWidgetFloatable,
    NoDockWidgetFeatures,
    AllDockWidgetFeatures,
)


def _dock(name: str) -> LDockWidget:
    d = LDockWidget(name)
    d.setObjectName(name)
    d.setWidget(QLabel(name))
    return d


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


def test_toggle_view_action_shows_dock(qapp):
    """Triggering the action (checked) shows the dock."""
    win = LMainWindow()
    dock = _dock("d")
    win.addDockWidget(LeftDockWidgetArea, dock)
    dock.hide()

    action = dock.toggleViewAction()
    action.setChecked(True)
    assert not dock.isHidden()


# ------------------------------------------------------------------
# resizeDocks
# ------------------------------------------------------------------

def test_resize_docks_horizontal(qapp):
    """resizeDocks changes the outer splitter size for a left dock."""
    win = LMainWindow()
    win.resize(800, 600)
    win.show()

    dock = _dock("d")
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
    win.addDockWidget(TopDockWidgetArea, dock)

    win.resizeDocks([dock], [150], Qt.Orientation.Vertical)
    sizes = win._inner_splitter.sizes()
    top_idx = win._inner_splitter.indexOf(win._dock_areas[TopDockWidgetArea])
    assert sizes[top_idx] == 150

    win.hide()


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
