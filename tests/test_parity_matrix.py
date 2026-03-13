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
