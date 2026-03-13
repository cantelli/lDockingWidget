"""API surface compatibility tests.

Verifies LDockWidget and LMainWindow expose the same public interface
as QDockWidget and QMainWindow.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget, QLabel, QMainWindow

from ldocking import (
    AllDockWidgetFeatures,
    AllowTabbedDocks,
    AnimatedDocks,
    BottomDockWidgetArea,
    DockOption,
    DockWidgetClosable,
    DockWidgetFeature,
    DockWidgetFloatable,
    DockWidgetMovable,
    ForceTabbedDocks,
    LeftDockWidgetArea,
    LDockWidget,
    LMainWindow,
    NoDockWidgetFeatures,
    RightDockWidgetArea,
    TopDockWidgetArea,
    VerticalTabs,
)


def test_dock_widget_methods(qapp):
    dock = LDockWidget("Test")
    required = [
        "setWidget", "widget",
        "setTitleBarWidget", "titleBarWidget",
        "setFeatures", "features",
        "setAllowedAreas", "allowedAreas",
        "setFloating", "isFloating",
        "setWindowTitle", "windowTitle",
        "toggleViewAction",
        "show", "hide", "setVisible", "isVisible",
        "resize", "move", "geometry",
    ]
    for method in required:
        assert hasattr(dock, method), f"LDockWidget missing method: {method}"


def test_dock_widget_signals(qapp):
    dock = LDockWidget("Test")
    for sig in ["featuresChanged", "allowedAreasChanged", "visibilityChanged",
                "topLevelChanged", "dockLocationChanged"]:
        assert hasattr(dock, sig), f"LDockWidget missing signal: {sig}"


def test_enum_identity(qapp):
    assert DockWidgetFeature is QDockWidget.DockWidgetFeature
    assert DockWidgetClosable is QDockWidget.DockWidgetFeature.DockWidgetClosable
    assert DockWidgetFloatable is QDockWidget.DockWidgetFeature.DockWidgetFloatable
    assert DockWidgetMovable is QDockWidget.DockWidgetFeature.DockWidgetMovable


def test_set_features(qapp):
    dock = LDockWidget("Test")
    dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable)
    dock.setFeatures(AllDockWidgetFeatures)
    dock.setFeatures(NoDockWidgetFeatures)


def test_set_widget(qapp):
    dock = LDockWidget("Test")
    label = QLabel("content")
    dock.setWidget(label)
    assert dock.widget() is label


def test_toggle_view_action(qapp):
    dock = LDockWidget("Test")
    action = dock.toggleViewAction()
    assert action is not None
    assert action.isCheckable()
    assert action.text() == "Test"


def test_floating_default(qapp):
    dock = LDockWidget("Test")
    assert not dock.isFloating()


def test_window_title(qapp):
    dock = LDockWidget("Test")
    dock.setWindowTitle("New Title")
    assert dock.windowTitle() == "New Title"


def test_area_enums(qapp):
    assert LeftDockWidgetArea == Qt.DockWidgetArea.LeftDockWidgetArea
    assert RightDockWidgetArea == Qt.DockWidgetArea.RightDockWidgetArea
    assert TopDockWidgetArea == Qt.DockWidgetArea.TopDockWidgetArea
    assert BottomDockWidgetArea == Qt.DockWidgetArea.BottomDockWidgetArea


def test_main_window_dock_options(qapp):
    win = LMainWindow()
    assert hasattr(win, "setDockOptions")
    assert hasattr(win, "dockOptions")
    assert hasattr(win, "setCorner")
    assert hasattr(win, "corner")
    assert hasattr(win, "tabifiedDockWidgets")
    assert hasattr(win, "restoreDockWidget")
    assert hasattr(win, "saveQtState")
    assert hasattr(win, "setTabPosition")
    assert hasattr(win, "tabPosition")

    opts = win.dockOptions()
    assert bool(opts & QMainWindow.DockOption.AnimatedDocks)
    assert bool(opts & QMainWindow.DockOption.AllowTabbedDocks)

    new_opts = QMainWindow.DockOption.AnimatedDocks | QMainWindow.DockOption.AllowTabbedDocks
    win.setDockOptions(new_opts)
    assert win.dockOptions() == new_opts


def test_main_window_tab_position(qapp):
    from PySide6.QtWidgets import QTabWidget
    win = LMainWindow()
    # Default matches Qt dock-tab rendering more closely with bottom tabs.
    assert win.tabPosition(LeftDockWidgetArea) == QTabWidget.TabPosition.South
    # setTabPosition round-trips
    win.setTabPosition(LeftDockWidgetArea, QTabWidget.TabPosition.South)
    assert win.tabPosition(LeftDockWidgetArea) == QTabWidget.TabPosition.South
    # Unknown area returns the default without raising
    assert win.tabPosition(Qt.DockWidgetArea.NoDockWidgetArea) == QTabWidget.TabPosition.South


def test_tabified_dock_widgets(qapp):
    win = LMainWindow()
    da = LDockWidget("DA")
    da.setWidget(QLabel("DA"))
    db = LDockWidget("DB")
    db.setWidget(QLabel("DB"))
    win.addDockWidget(LeftDockWidgetArea, da)
    win.addDockWidget(LeftDockWidgetArea, db)

    assert db in win.tabifiedDockWidgets(da)
    assert da in win.tabifiedDockWidgets(db)
    assert da not in win.tabifiedDockWidgets(da)


def test_dock_option_enum_identity(qapp):
    assert DockOption is QMainWindow.DockOption
    assert AnimatedDocks is QMainWindow.DockOption.AnimatedDocks
    assert AllowTabbedDocks is QMainWindow.DockOption.AllowTabbedDocks
    assert ForceTabbedDocks is QMainWindow.DockOption.ForceTabbedDocks
    assert VerticalTabs is QMainWindow.DockOption.VerticalTabs
