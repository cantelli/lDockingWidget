"""Collected parity matrix for LDocking vs native Qt."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QToolBar, QWidget

import ldocking.monkey as monkey
from ldocking import LDockWidget, LMainWindow
from parity_test import (
    Bottom,
    BottomTB,
    Left,
    LeftTB,
    Right,
    RightTB,
    SCENARIOS,
    TopTB,
    _corner_snap,
    _toolbar_snap,
    compare,
    l_snap,
    qt_snap,
    run_scenario,
)

NativeQMainWindow = monkey._ORIG["QMainWindow"]
NativeQDockWidget = monkey._ORIG["QDockWidget"]


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[scenario["name"] for scenario in SCENARIOS])
def test_parity_scenario_matrix(qapp, scenario):
    mismatches = run_scenario(scenario, qapp)
    assert mismatches == []


def test_native_qt_restore_state_import_parity(qapp):
    native = NativeQMainWindow()
    native.setCentralWidget(QWidget())
    qt_docks: list[NativeQDockWidget] = []
    for title, area in (("A", Left), ("B", Left), ("C", Right)):
        dock = NativeQDockWidget(title)
        dock.setObjectName(title)
        dock.setWidget(QLabel(title))
        native.addDockWidget(area, dock)
        qt_docks.append(dock)
    native.tabifyDockWidget(qt_docks[0], qt_docks[1])
    qt_toolbars: list[QToolBar] = []
    for title, area in (("Top", TopTB), ("Left", LeftTB), ("Right", RightTB), ("Bottom", BottomTB)):
        toolbar = QToolBar(title)
        toolbar.setObjectName(title)
        toolbar.addAction(title)
        native.addToolBar(area, toolbar)
        qt_toolbars.append(toolbar)
    native.setCorner(Qt.Corner.TopLeftCorner, Left)
    native.setCorner(Qt.Corner.BottomRightCorner, Right)
    native.show()
    qapp.processEvents()

    state = native.saveState()

    l_win = LMainWindow()
    l_docks: list[LDockWidget] = []
    for title in ("A", "B", "C"):
        dock = LDockWidget(title)
        dock.setObjectName(title)
        dock.setWidget(QLabel(title))
        l_win.addDockWidget(Bottom, dock)
        l_docks.append(dock)
    l_toolbars: list[QToolBar] = []
    for title in ("Top", "Left", "Right", "Bottom"):
        toolbar = QToolBar(title)
        toolbar.setObjectName(title)
        toolbar.addAction(title)
        l_win.addToolBar(TopTB, toolbar)
        l_toolbars.append(toolbar)

    assert l_win.restoreState(state) is True
    qapp.processEvents()

    qt_state = qt_snap(native, qt_docks)
    qt_state["toolbars"] = _toolbar_snap(native, qt_toolbars)
    qt_state["corners"] = _corner_snap(native)
    l_state = l_snap(l_win, l_docks, l_toolbars)
    assert compare(
        qt_state,
        l_state,
        ["area", "floating", "tabs", "toolbar_area", "toolbar_order", "corners"],
    ) == []


def test_ldocking_save_qt_state_export_parity(qapp):
    l_win = LMainWindow()
    l_docks: list[LDockWidget] = []
    for title, area in (("A", Left), ("B", Left), ("C", Right)):
        dock = LDockWidget(title)
        dock.setObjectName(title)
        dock.setWidget(QLabel(title))
        l_win.addDockWidget(area, dock)
        l_docks.append(dock)
    l_win.tabifyDockWidget(l_docks[0], l_docks[1])
    l_toolbars: list[QToolBar] = []
    for title, area in (("Top", TopTB), ("Left", LeftTB), ("Right", RightTB), ("Bottom", BottomTB)):
        toolbar = QToolBar(title)
        toolbar.setObjectName(title)
        toolbar.addAction(title)
        l_win.addToolBar(area, toolbar)
        l_toolbars.append(toolbar)
    l_win.setCorner(Qt.Corner.TopLeftCorner, Left)
    l_win.setCorner(Qt.Corner.BottomRightCorner, Right)
    l_win.show()
    qapp.processEvents()

    state = l_win.saveQtState()

    native = NativeQMainWindow()
    native.setCentralWidget(QWidget())
    qt_docks: list[NativeQDockWidget] = []
    for title in ("A", "B", "C"):
        dock = NativeQDockWidget(title)
        dock.setObjectName(title)
        dock.setWidget(QLabel(title))
        native.addDockWidget(Bottom, dock)
        qt_docks.append(dock)
    qt_toolbars: list[QToolBar] = []
    for title in ("Top", "Left", "Right", "Bottom"):
        toolbar = QToolBar(title)
        toolbar.setObjectName(title)
        toolbar.addAction(title)
        native.addToolBar(TopTB, toolbar)
        qt_toolbars.append(toolbar)

    assert native.restoreState(state) is True
    native.show()
    qapp.processEvents()

    qt_state = qt_snap(native, qt_docks)
    qt_state["toolbars"] = _toolbar_snap(native, qt_toolbars)
    qt_state["corners"] = _corner_snap(native)
    l_state = l_snap(l_win, l_docks, l_toolbars)
    assert compare(
        qt_state,
        l_state,
        ["area", "floating", "tabs", "toolbar_area", "toolbar_order", "corners"],
    ) == []


def test_constrained_tabified_dock_size_parity(qapp):
    native = NativeQMainWindow()
    native.setCentralWidget(QWidget())
    qt_first = NativeQDockWidget("first")
    qt_first.setObjectName("first")
    qt_first.setWidget(QLabel("first"))
    qt_first.setMinimumWidth(120)
    qt_first.setMaximumWidth(160)
    qt_second = NativeQDockWidget("second")
    qt_second.setObjectName("second")
    qt_second.setWidget(QLabel("second"))
    qt_second.setMinimumWidth(220)
    qt_second.setMaximumWidth(260)
    native.addDockWidget(Left, qt_first)
    native.addDockWidget(Left, qt_second)
    native.show()
    qapp.processEvents()
    native.tabifyDockWidget(qt_first, qt_second)
    qapp.processEvents()

    l_win = LMainWindow()
    l_win.setCentralWidget(QWidget())
    l_first = LDockWidget("first")
    l_first.setObjectName("first")
    l_first.setWidget(QLabel("first"))
    l_first.setMinimumWidth(120)
    l_first.setMaximumWidth(160)
    l_second = LDockWidget("second")
    l_second.setObjectName("second")
    l_second.setWidget(QLabel("second"))
    l_second.setMinimumWidth(220)
    l_second.setMaximumWidth(260)
    l_win.addDockWidget(Left, l_first)
    l_win.addDockWidget(Left, l_second)
    l_win.show()
    qapp.processEvents()
    l_win.tabifyDockWidget(l_first, l_second)
    qapp.processEvents()

    assert (l_first.width(), l_second.width()) == (qt_first.width(), qt_second.width())


def test_resize_docks_constraint_parity(qapp):
    native = NativeQMainWindow()
    native.setCentralWidget(QWidget())
    qt_left = NativeQDockWidget("left")
    qt_left.setObjectName("left")
    qt_left.setWidget(QLabel("left"))
    qt_left.setMinimumWidth(100)
    qt_left.setMaximumWidth(150)
    qt_right = NativeQDockWidget("right")
    qt_right.setObjectName("right")
    qt_right.setWidget(QLabel("right"))
    native.addDockWidget(Left, qt_left)
    native.addDockWidget(Right, qt_right)
    native.resize(800, 600)
    native.show()
    qapp.processEvents()

    l_win = LMainWindow()
    l_win.setCentralWidget(QWidget())
    l_left = LDockWidget("left")
    l_left.setObjectName("left")
    l_left.setWidget(QLabel("left"))
    l_left.setMinimumWidth(100)
    l_left.setMaximumWidth(150)
    l_right = LDockWidget("right")
    l_right.setObjectName("right")
    l_right.setWidget(QLabel("right"))
    l_win.addDockWidget(Left, l_left)
    l_win.addDockWidget(Right, l_right)
    l_win.resize(800, 600)
    l_win.show()
    qapp.processEvents()

    right_before = l_right.width()
    native.resizeDocks([qt_left], [400], Qt.Horizontal)
    l_win.resizeDocks([l_left], [400], Qt.Horizontal)
    qapp.processEvents()
    assert l_left.width() == qt_left.width()
    assert l_right.width() == right_before

    native.resizeDocks([qt_left], [20], Qt.Horizontal)
    l_win.resizeDocks([l_left], [20], Qt.Horizontal)
    qapp.processEvents()
    assert l_left.width() == qt_left.width()
    assert l_right.width() == right_before
