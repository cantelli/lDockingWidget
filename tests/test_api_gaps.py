"""Tests for API gaps: isAreaAllowed, toolbar management, createPopupMenu."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMenu, QToolBar

from ldocking import (
    LDockWidget,
    LMainWindow,
    LeftDockWidgetArea,
    RightDockWidgetArea,
    TopDockWidgetArea,
    BottomDockWidgetArea,
    AllDockWidgetAreas,
    NoDockWidgetArea,
)


# ------------------------------------------------------------------
# LDockWidget.isAreaAllowed
# ------------------------------------------------------------------

def test_is_area_allowed_default(qapp):
    """New dock allows all areas by default."""
    dock = LDockWidget("D")
    for area in (LeftDockWidgetArea, RightDockWidgetArea,
                 TopDockWidgetArea, BottomDockWidgetArea):
        assert dock.isAreaAllowed(area)


def test_is_area_allowed_restricted(qapp):
    """Dock with restricted areas returns correct True/False."""
    dock = LDockWidget("D")
    dock.setAllowedAreas(LeftDockWidgetArea | RightDockWidgetArea)
    assert dock.isAreaAllowed(LeftDockWidgetArea)
    assert dock.isAreaAllowed(RightDockWidgetArea)
    assert not dock.isAreaAllowed(TopDockWidgetArea)
    assert not dock.isAreaAllowed(BottomDockWidgetArea)


def test_is_area_allowed_none(qapp):
    """Dock with NoDockWidgetArea allows nothing."""
    dock = LDockWidget("D")
    dock.setAllowedAreas(NoDockWidgetArea)
    for area in (LeftDockWidgetArea, RightDockWidgetArea,
                 TopDockWidgetArea, BottomDockWidgetArea):
        assert not dock.isAreaAllowed(area)


# ------------------------------------------------------------------
# Toolbar management
# ------------------------------------------------------------------

def test_add_toolbar_by_string(qapp):
    """addToolBar(str) creates and registers a new QToolBar."""
    win = LMainWindow()
    tb = win.addToolBar("Edit")
    assert isinstance(tb, QToolBar)
    assert tb.windowTitle() == "Edit"
    assert tb in win.toolBars()


def test_add_toolbar_by_instance(qapp):
    """addToolBar(QToolBar) registers existing toolbar and returns it."""
    win = LMainWindow()
    tb = QToolBar("File")
    result = win.addToolBar(tb)
    assert result is tb
    assert tb in win.toolBars()


def test_toolbar_list(qapp):
    """toolBars() returns all added toolbars in order."""
    win = LMainWindow()
    tb1 = win.addToolBar("A")
    tb2 = win.addToolBar("B")
    tb3 = win.addToolBar("C")
    assert win.toolBars() == [tb1, tb2, tb3]


def test_remove_toolbar(qapp):
    """removeToolBar removes from toolBars() list."""
    win = LMainWindow()
    tb1 = win.addToolBar("A")
    tb2 = win.addToolBar("B")
    win.removeToolBar(tb1)
    assert tb1 not in win.toolBars()
    assert tb2 in win.toolBars()


def test_remove_toolbar_noop_unknown(qapp):
    """removeToolBar on unknown toolbar does not raise."""
    win = LMainWindow()
    tb = QToolBar("X")
    win.removeToolBar(tb)  # should not raise


def test_insert_toolbar(qapp):
    """insertToolBar places toolbar before the reference toolbar."""
    win = LMainWindow()
    tb1 = win.addToolBar("A")
    tb2 = win.addToolBar("B")
    tb_new = QToolBar("New")
    win.insertToolBar(tb2, tb_new)
    bars = win.toolBars()
    assert bars.index(tb_new) < bars.index(tb2)
    assert bars.index(tb1) < bars.index(tb_new)


def test_toolbar_area_always_top(qapp):
    """toolBarArea always returns TopToolBarArea."""
    win = LMainWindow()
    tb = win.addToolBar("A")
    assert win.toolBarArea(tb) == Qt.ToolBarArea.TopToolBarArea


def test_toolbar_break_noops(qapp):
    """toolBarBreak returns False; addToolBarBreak/etc do not raise."""
    win = LMainWindow()
    tb = win.addToolBar("A")
    assert win.toolBarBreak(tb) is False
    win.addToolBarBreak()
    win.removeToolBarBreak(tb)
    win.insertToolBarBreak(tb)


# ------------------------------------------------------------------
# createPopupMenu
# ------------------------------------------------------------------

def test_create_popup_menu_empty(qapp):
    """Returns None when no docks or toolbars are registered."""
    win = LMainWindow()
    assert win.createPopupMenu() is None


def test_create_popup_menu_docks_only(qapp):
    """Menu contains one action per dock."""
    win = LMainWindow()
    da = LDockWidget("Alpha")
    da.setObjectName("Alpha")
    db = LDockWidget("Beta")
    db.setObjectName("Beta")
    win.addDockWidget(LeftDockWidgetArea, da)
    win.addDockWidget(RightDockWidgetArea, db)

    menu = win.createPopupMenu()
    assert isinstance(menu, QMenu)
    action_texts = [a.text() for a in menu.actions()]
    assert "Alpha" in action_texts
    assert "Beta" in action_texts


def test_create_popup_menu_with_toolbars(qapp):
    """Menu contains dock actions + separator + toolbar actions."""
    win = LMainWindow()
    dock = LDockWidget("MyDock")
    dock.setObjectName("MyDock")
    win.addDockWidget(LeftDockWidgetArea, dock)
    tb = win.addToolBar("MyToolbar")

    menu = win.createPopupMenu()
    actions = menu.actions()
    # Should have at least: dock action, separator, toolbar action
    assert any(a.isSeparator() for a in actions)
    texts = [a.text() for a in actions if not a.isSeparator()]
    assert "MyDock" in texts
    assert "MyToolbar" in texts
