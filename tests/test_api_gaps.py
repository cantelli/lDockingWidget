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
    """Default addToolBar places toolbars in the top area."""
    win = LMainWindow()
    tb = win.addToolBar("A")
    assert win.toolBarArea(tb) == Qt.ToolBarArea.TopToolBarArea


def test_add_toolbar_bottom_area(qapp):
    """addToolBar(area, toolbar) honors BottomToolBarArea."""
    win = LMainWindow()
    tb = QToolBar("Bottom")
    win.addToolBar(Qt.ToolBarArea.BottomToolBarArea, tb)
    assert win.toolBarArea(tb) == Qt.ToolBarArea.BottomToolBarArea
    assert tb in win.toolBars()


def test_add_toolbar_left_area(qapp):
    """addToolBar(area, toolbar) honors LeftToolBarArea."""
    win = LMainWindow()
    tb = QToolBar("Left")
    win.addToolBar(Qt.ToolBarArea.LeftToolBarArea, tb)
    assert win.toolBarArea(tb) == Qt.ToolBarArea.LeftToolBarArea


def test_add_toolbar_right_area(qapp):
    """addToolBar(area, toolbar) honors RightToolBarArea."""
    win = LMainWindow()
    tb = QToolBar("Right")
    win.addToolBar(Qt.ToolBarArea.RightToolBarArea, tb)
    assert win.toolBarArea(tb) == Qt.ToolBarArea.RightToolBarArea


def test_toolbar_breaks_round_trip(qapp):
    """Toolbar break APIs create and remove row boundaries in supported areas."""
    win = LMainWindow()
    tb1 = win.addToolBar("A")
    win.addToolBarBreak()
    tb2 = win.addToolBar("B")
    assert win.toolBarBreak(tb1) is False
    assert win.toolBarBreak(tb2) is True
    win.removeToolBarBreak(tb2)
    assert win.toolBarBreak(tb2) is False


def test_insert_toolbar_break_before_toolbar(qapp):
    """insertToolBarBreak marks the given toolbar as the start of a new row."""
    win = LMainWindow()
    tb1 = win.addToolBar("A")
    tb2 = win.addToolBar("B")
    win.insertToolBarBreak(tb2)
    assert win.toolBarBreak(tb1) is False
    assert win.toolBarBreak(tb2) is True


def test_bottom_toolbar_breaks_round_trip(qapp):
    """Toolbar breaks also work in the bottom toolbar area."""
    win = LMainWindow()
    tb1 = QToolBar("Bottom A")
    tb2 = QToolBar("Bottom B")
    win.addToolBar(Qt.ToolBarArea.BottomToolBarArea, tb1)
    win.addToolBarBreak(Qt.ToolBarArea.BottomToolBarArea)
    win.addToolBar(Qt.ToolBarArea.BottomToolBarArea, tb2)
    assert win.toolBarArea(tb1) == Qt.ToolBarArea.BottomToolBarArea
    assert win.toolBarArea(tb2) == Qt.ToolBarArea.BottomToolBarArea
    assert win.toolBarBreak(tb1) is False
    assert win.toolBarBreak(tb2) is True
    win.removeToolBarBreak(tb2)
    assert win.toolBarBreak(tb2) is False


def test_left_toolbar_breaks_round_trip(qapp):
    """Toolbar breaks also work in the left toolbar area."""
    win = LMainWindow()
    tb1 = QToolBar("Left A")
    tb2 = QToolBar("Left B")
    win.addToolBar(Qt.ToolBarArea.LeftToolBarArea, tb1)
    win.addToolBarBreak(Qt.ToolBarArea.LeftToolBarArea)
    win.addToolBar(Qt.ToolBarArea.LeftToolBarArea, tb2)
    assert win.toolBarArea(tb1) == Qt.ToolBarArea.LeftToolBarArea
    assert win.toolBarArea(tb2) == Qt.ToolBarArea.LeftToolBarArea
    assert win.toolBarBreak(tb1) is False
    assert win.toolBarBreak(tb2) is True
    win.removeToolBarBreak(tb2)
    assert win.toolBarBreak(tb2) is False


def test_right_toolbar_breaks_round_trip(qapp):
    """Toolbar breaks also work in the right toolbar area."""
    win = LMainWindow()
    tb1 = QToolBar("Right A")
    tb2 = QToolBar("Right B")
    win.addToolBar(Qt.ToolBarArea.RightToolBarArea, tb1)
    win.addToolBarBreak(Qt.ToolBarArea.RightToolBarArea)
    win.addToolBar(Qt.ToolBarArea.RightToolBarArea, tb2)
    assert win.toolBarArea(tb1) == Qt.ToolBarArea.RightToolBarArea
    assert win.toolBarArea(tb2) == Qt.ToolBarArea.RightToolBarArea
    assert win.toolBarBreak(tb1) is False
    assert win.toolBarBreak(tb2) is True
    win.removeToolBarBreak(tb2)
    assert win.toolBarBreak(tb2) is False


def test_insert_toolbar_preserves_target_area(qapp):
    """insertToolBar inserts into the reference toolbar's area."""
    win = LMainWindow()
    tb1 = QToolBar("Bottom A")
    tb2 = QToolBar("Bottom B")
    tb_new = QToolBar("Bottom New")
    win.addToolBar(Qt.ToolBarArea.BottomToolBarArea, tb1)
    win.addToolBar(Qt.ToolBarArea.BottomToolBarArea, tb2)
    win.insertToolBar(tb2, tb_new)
    assert win.toolBarArea(tb_new) == Qt.ToolBarArea.BottomToolBarArea
    bars = win.toolBars()
    assert bars.index(tb_new) < bars.index(tb2)


def test_insert_toolbar_preserves_left_area(qapp):
    """insertToolBar inserts into the reference toolbar's left area."""
    win = LMainWindow()
    tb1 = QToolBar("Left A")
    tb2 = QToolBar("Left B")
    tb_new = QToolBar("Left New")
    win.addToolBar(Qt.ToolBarArea.LeftToolBarArea, tb1)
    win.addToolBar(Qt.ToolBarArea.LeftToolBarArea, tb2)
    win.insertToolBar(tb2, tb_new)
    assert win.toolBarArea(tb_new) == Qt.ToolBarArea.LeftToolBarArea
    bars = win.toolBars()
    assert bars.index(tb_new) < bars.index(tb2)


def test_remove_toolbar_from_right_area(qapp):
    """removeToolBar also works for toolbars placed in the right area."""
    win = LMainWindow()
    tb1 = QToolBar("Right A")
    tb2 = QToolBar("Right B")
    win.addToolBar(Qt.ToolBarArea.RightToolBarArea, tb1)
    win.addToolBar(Qt.ToolBarArea.RightToolBarArea, tb2)
    win.removeToolBar(tb1)
    assert tb1 not in win.toolBars()
    assert tb2 in win.toolBars()
    assert win.toolBarArea(tb2) == Qt.ToolBarArea.RightToolBarArea


def _toolbar_anchor(win, toolbar):
    point = toolbar.mapTo(win, toolbar.rect().topLeft())
    return point.x(), point.y(), toolbar.width(), toolbar.height()


def _sized_toolbar(title):
    toolbar = QToolBar(title)
    toolbar.addAction(title)
    return toolbar


def test_set_corner_top_left_prefers_left(qapp):
    """Top-left corner ownership shifts the top toolbar away from the left side."""
    win = LMainWindow()
    win.resize(600, 400)
    top = _sized_toolbar("Top")
    left = _sized_toolbar("Left")
    win.addToolBar(Qt.ToolBarArea.TopToolBarArea, top)
    win.addToolBar(Qt.ToolBarArea.LeftToolBarArea, left)
    win.show()
    qapp.processEvents()
    before_x, _, _, _ = _toolbar_anchor(win, top)
    win.setCorner(Qt.Corner.TopLeftCorner, LeftDockWidgetArea)
    qapp.processEvents()
    after_x, _, _, _ = _toolbar_anchor(win, top)
    assert after_x > before_x


def test_set_corner_top_right_prefers_right(qapp):
    """Top-right corner ownership shortens the top toolbar span on the right."""
    win = LMainWindow()
    win.resize(600, 400)
    top = _sized_toolbar("Top")
    right = _sized_toolbar("Right")
    win.addToolBar(Qt.ToolBarArea.TopToolBarArea, top)
    win.addToolBar(Qt.ToolBarArea.RightToolBarArea, right)
    win.show()
    qapp.processEvents()
    before_x, _, before_w, _ = _toolbar_anchor(win, top)
    win.setCorner(Qt.Corner.TopRightCorner, RightDockWidgetArea)
    qapp.processEvents()
    after_x, _, after_w, _ = _toolbar_anchor(win, top)
    assert after_x == before_x
    assert after_w < before_w


def test_set_corner_bottom_left_prefers_left(qapp):
    """Bottom-left corner ownership shifts the bottom toolbar away from the left side."""
    win = LMainWindow()
    win.resize(600, 400)
    bottom = _sized_toolbar("Bottom")
    left = _sized_toolbar("Left")
    win.addToolBar(Qt.ToolBarArea.BottomToolBarArea, bottom)
    win.addToolBar(Qt.ToolBarArea.LeftToolBarArea, left)
    win.show()
    qapp.processEvents()
    before_x, _, _, _ = _toolbar_anchor(win, bottom)
    win.setCorner(Qt.Corner.BottomLeftCorner, LeftDockWidgetArea)
    qapp.processEvents()
    after_x, _, _, _ = _toolbar_anchor(win, bottom)
    assert after_x > before_x


def test_set_corner_bottom_right_prefers_right(qapp):
    """Bottom-right corner ownership shortens the bottom toolbar span on the right."""
    win = LMainWindow()
    win.resize(600, 400)
    bottom = _sized_toolbar("Bottom")
    right = _sized_toolbar("Right")
    win.addToolBar(Qt.ToolBarArea.BottomToolBarArea, bottom)
    win.addToolBar(Qt.ToolBarArea.RightToolBarArea, right)
    win.show()
    qapp.processEvents()
    before_x, _, before_w, _ = _toolbar_anchor(win, bottom)
    win.setCorner(Qt.Corner.BottomRightCorner, RightDockWidgetArea)
    qapp.processEvents()
    after_x, _, after_w, _ = _toolbar_anchor(win, bottom)
    assert after_x == before_x
    assert after_w < before_w


def test_set_corner_ignores_invalid_assignment(qapp):
    """Invalid corner-area combinations are ignored."""
    win = LMainWindow()
    win.resize(600, 400)
    top = _sized_toolbar("Top")
    left = _sized_toolbar("Left")
    win.addToolBar(Qt.ToolBarArea.TopToolBarArea, top)
    win.addToolBar(Qt.ToolBarArea.LeftToolBarArea, left)
    win.show()
    qapp.processEvents()
    before = _toolbar_anchor(win, top)
    win.setCorner(Qt.Corner.TopLeftCorner, BottomDockWidgetArea)
    qapp.processEvents()
    assert _toolbar_anchor(win, top) == before


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


def test_create_popup_menu_with_mixed_toolbar_areas(qapp):
    """Popup menu includes toolbars from mixed areas once each."""
    win = LMainWindow()
    top = win.addToolBar("TopToolbar")
    left = QToolBar("LeftToolbar")
    right = QToolBar("RightToolbar")
    bottom = QToolBar("BottomToolbar")
    win.addToolBar(Qt.ToolBarArea.LeftToolBarArea, left)
    win.addToolBar(Qt.ToolBarArea.RightToolBarArea, right)
    win.addToolBar(Qt.ToolBarArea.BottomToolBarArea, bottom)

    menu = win.createPopupMenu()
    texts = [a.text() for a in menu.actions() if not a.isSeparator()]
    assert texts.count(top.windowTitle()) == 1
    assert texts.count(left.windowTitle()) == 1
    assert texts.count(right.windowTitle()) == 1
    assert texts.count(bottom.windowTitle()) == 1
