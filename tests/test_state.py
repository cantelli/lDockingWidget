"""Tests for LMainWindow.saveState() / restoreState()."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtWidgets import QLabel, QToolBar

from ldocking import (
    LDockWidget,
    LMainWindow,
    LeftDockWidgetArea,
    RightDockWidgetArea,
    TopDockWidgetArea,
    BottomDockWidgetArea,
)


def _make_dock(name: str) -> LDockWidget:
    d = LDockWidget(name)
    d.setObjectName(name)
    d.setWidget(QLabel(name))
    return d


def _make_toolbar(name: str) -> QToolBar:
    toolbar = QToolBar(name)
    toolbar.setObjectName(name)
    toolbar.addAction(name)
    return toolbar


def test_save_restore_basic(qapp):
    """State round-trip preserves dock areas and tab order."""
    win = LMainWindow()
    win.resize(800, 600)

    da = _make_dock("da")
    db = _make_dock("db")
    dc = _make_dock("dc")
    win.addDockWidget(LeftDockWidgetArea, da)
    win.addDockWidget(LeftDockWidgetArea, db)
    win.addDockWidget(RightDockWidgetArea, dc)

    state = win.saveState()
    assert isinstance(state, QByteArray)
    assert len(state) > 0

    # Move docks to wrong areas
    win.addDockWidget(RightDockWidgetArea, da)
    win.addDockWidget(LeftDockWidgetArea, dc)

    assert win.restoreState(state) is True

    assert win.dockWidgetArea(da) == LeftDockWidgetArea
    assert win.dockWidgetArea(db) == LeftDockWidgetArea
    assert win.dockWidgetArea(dc) == RightDockWidgetArea

    # Tab order within left area must be da=0, db=1
    left_docks = win._dock_areas[LeftDockWidgetArea]._docks
    assert left_docks.index(da) < left_docks.index(db)


def test_save_restore_tab_order(qapp):
    """Restoring state preserves insertion order within a tab area."""
    win = LMainWindow()
    docks = [_make_dock(f"d{i}") for i in range(4)]
    for d in docks:
        win.addDockWidget(LeftDockWidgetArea, d)

    state = win.saveState()

    # Shuffle by re-adding in reverse
    for d in reversed(docks):
        win.addDockWidget(RightDockWidgetArea, d)

    win.restoreState(state)

    left_docks = win._dock_areas[LeftDockWidgetArea]._docks
    for i, d in enumerate(docks):
        assert left_docks.index(d) == i, f"d{i} not at position {i}"


def test_restore_floating(qapp):
    """Floating docks are restored to floating with correct geometry."""
    win = LMainWindow()
    win.resize(800, 600)

    da = _make_dock("da")
    db = _make_dock("db")
    win.addDockWidget(LeftDockWidgetArea, da)
    win.addDockWidget(RightDockWidgetArea, db)

    # Float da and set a specific geometry
    da.setFloating(True)
    da.setGeometry(100, 200, 300, 250)

    state = win.saveState()

    # Dock da back then restore
    win.addDockWidget(LeftDockWidgetArea, da)
    assert not da.isFloating()

    win.restoreState(state)

    assert da.isFloating()
    g = da.geometry()
    assert g.x() == 100
    assert g.y() == 200
    assert g.width() == 300
    assert g.height() == 250
    # db must still be docked
    assert not db.isFloating()
    assert win.dockWidgetArea(db) == RightDockWidgetArea


def test_restore_unknown_id_skipped(qapp):
    """restoreState silently skips IDs not present in the window."""
    win = LMainWindow()
    da = _make_dock("da")
    win.addDockWidget(LeftDockWidgetArea, da)

    # Craft state that references a nonexistent dock
    payload = {
        "version": 1,
        "outer_splitter": [0, 800, 0],
        "inner_splitter": [0, 600, 0],
        "docks": [
            {"id": "da", "area": LeftDockWidgetArea.value, "tab_index": 0, "floating": False},
            {"id": "ghost", "area": RightDockWidgetArea.value, "tab_index": 0, "floating": False},
        ],
    }
    state = QByteArray(json.dumps(payload).encode())

    result = win.restoreState(state)
    assert result is True
    assert win.dockWidgetArea(da) == LeftDockWidgetArea


def test_restore_invalid_data(qapp):
    """restoreState returns False for garbage or wrong-version input."""
    win = LMainWindow()

    assert win.restoreState(QByteArray(b"not json")) is False
    assert win.restoreState(QByteArray(b"")) is False

    wrong_version = QByteArray(json.dumps({"format_version": 99, "docks": []}).encode())
    assert win.restoreState(wrong_version) is False


def test_save_restore_state_version_round_trip(qapp):
    """restoreState requires the same caller-provided state version."""
    win = LMainWindow()
    dock = _make_dock("da")
    win.addDockWidget(LeftDockWidgetArea, dock)

    state = win.saveState(version=7)

    assert win.restoreState(state, version=7) is True
    assert win.restoreState(state, version=3) is False


def test_save_restore_tab_order_after_tab_move(qapp):
    """saveState persists user tab reordering from the tab bar."""
    win = LMainWindow()
    docks = [_make_dock(name) for name in ("a", "b", "c")]
    for dock in docks:
        win.addDockWidget(LeftDockWidgetArea, dock)

    tab_area = win._dock_areas[LeftDockWidgetArea]._tab_area
    tab_area._on_tab_moved(2, 0)

    state = win.saveState()

    for dock in docks:
        win.addDockWidget(RightDockWidgetArea, dock)

    assert win.restoreState(state) is True
    left_docks = win._dock_areas[LeftDockWidgetArea]._docks
    assert [dock.windowTitle() for dock in left_docks] == ["c", "a", "b"]


def test_save_restore_current_tab_selection(qapp):
    """saveState persists the currently selected tab in a dock area."""
    win = LMainWindow()
    docks = [_make_dock(name) for name in ("a", "b", "c")]
    for dock in docks:
        win.addDockWidget(LeftDockWidgetArea, dock)

    area = win._dock_areas[LeftDockWidgetArea]
    area.set_current_tab_dock(docks[1])

    state = win.saveState()

    area.set_current_tab_dock(docks[2])
    assert area.current_tab_dock() is docks[2]

    assert win.restoreState(state) is True
    assert area.current_tab_dock() is docks[1]


def test_save_state_uses_live_layout_membership(qapp):
    """saveState serializes actual area membership even if the cache is stale."""
    win = LMainWindow()
    dock = _make_dock("da")
    win.addDockWidget(LeftDockWidgetArea, dock)

    win._dock_map[dock] = RightDockWidgetArea

    payload = json.loads(bytes(win.saveState()).decode())

    assert payload["docks"][0]["area"] == LeftDockWidgetArea.value


def test_restore_prefers_content_tree_area_state_over_area_trees(qapp):
    """restoreState uses embedded content_tree area state even if area_trees is wrong."""
    win = LMainWindow()
    da = _make_dock("da")
    db = _make_dock("db")
    win.addDockWidget(LeftDockWidgetArea, da)
    win.addDockWidget(RightDockWidgetArea, db)

    payload = json.loads(bytes(win.saveState()).decode())
    payload["area_trees"] = {
        str(LeftDockWidgetArea.value): None,
        str(RightDockWidgetArea.value): None,
        str(TopDockWidgetArea.value): None,
        str(BottomDockWidgetArea.value): None,
    }
    state = QByteArray(json.dumps(payload).encode())

    win.addDockWidget(LeftDockWidgetArea, db)
    assert win.restoreState(state) is True
    assert win.dockWidgetArea(da) == LeftDockWidgetArea
    assert win.dockWidgetArea(db) == RightDockWidgetArea


def test_content_tree_leaf_state_tracks_docked_mutations(qapp):
    """Docked mutations update the in-memory content_tree leaf area state."""
    win = LMainWindow()
    da = _make_dock("da")
    db = _make_dock("db")
    win.addDockWidget(LeftDockWidgetArea, da)
    win.addDockWidget(LeftDockWidgetArea, db)

    leaf = win._leaf_for_key("left")

    assert leaf is not None
    assert leaf.area_state["type"] == "tabs"
    assert [child["id"] for child in leaf.area_state["children"]] == ["da", "db"]


def test_save_restore_toolbar_state_round_trip(qapp):
    """saveState persists toolbar areas, ordering, breaks, and corner ownership."""
    win = LMainWindow()
    win.resize(800, 600)
    top = _make_toolbar("top")
    top2 = _make_toolbar("top2")
    left = _make_toolbar("left")
    right = _make_toolbar("right")
    bottom = _make_toolbar("bottom")

    win.addToolBar(Qt.ToolBarArea.TopToolBarArea, top)
    win.addToolBar(Qt.ToolBarArea.TopToolBarArea, top2)
    win.insertToolBarBreak(top2)
    win.addToolBar(Qt.ToolBarArea.LeftToolBarArea, left)
    win.addToolBar(Qt.ToolBarArea.RightToolBarArea, right)
    win.addToolBar(Qt.ToolBarArea.BottomToolBarArea, bottom)
    win.setCorner(Qt.Corner.TopLeftCorner, LeftDockWidgetArea)
    win.setCorner(Qt.Corner.BottomRightCorner, RightDockWidgetArea)

    state = win.saveState()

    win.removeToolBar(top)
    win.removeToolBar(top2)
    win.removeToolBar(left)
    win.removeToolBar(right)
    win.removeToolBar(bottom)
    win.addToolBar(Qt.ToolBarArea.BottomToolBarArea, top)
    win.addToolBar(Qt.ToolBarArea.RightToolBarArea, top2)
    win.addToolBar(Qt.ToolBarArea.TopToolBarArea, left)
    win.addToolBar(Qt.ToolBarArea.LeftToolBarArea, right)
    win.addToolBar(Qt.ToolBarArea.TopToolBarArea, bottom)
    win.setCorner(Qt.Corner.TopLeftCorner, TopDockWidgetArea)
    win.setCorner(Qt.Corner.BottomRightCorner, BottomDockWidgetArea)

    assert win.restoreState(state) is True
    assert win.toolBarArea(top) == Qt.ToolBarArea.TopToolBarArea
    assert win.toolBarArea(top2) == Qt.ToolBarArea.TopToolBarArea
    assert win.toolBarArea(left) == Qt.ToolBarArea.LeftToolBarArea
    assert win.toolBarArea(right) == Qt.ToolBarArea.RightToolBarArea
    assert win.toolBarArea(bottom) == Qt.ToolBarArea.BottomToolBarArea
    assert win.toolBarBreak(top2) is True
    assert win._tool_bars[:5] == [top, top2, left, right, bottom]
    assert win._corner_owners[Qt.Corner.TopLeftCorner] == LeftDockWidgetArea
    assert win._corner_owners[Qt.Corner.BottomRightCorner] == RightDockWidgetArea


def test_restore_state_without_toolbar_data_keeps_current_toolbar_shell(qapp):
    """Older state payloads without toolbar data still restore successfully."""
    win = LMainWindow()
    top = _make_toolbar("top")
    left = _make_toolbar("left")
    win.addToolBar(Qt.ToolBarArea.TopToolBarArea, top)
    win.addToolBar(Qt.ToolBarArea.LeftToolBarArea, left)
    win.setCorner(Qt.Corner.TopLeftCorner, LeftDockWidgetArea)

    payload = json.loads(bytes(win.saveState()).decode())
    payload.pop("toolbars", None)
    payload.pop("corners", None)
    state = QByteArray(json.dumps(payload).encode())

    assert win.restoreState(state) is True
    assert win.toolBarArea(top) == Qt.ToolBarArea.TopToolBarArea
    assert win.toolBarArea(left) == Qt.ToolBarArea.LeftToolBarArea
    assert win._corner_owners[Qt.Corner.TopLeftCorner] == LeftDockWidgetArea


def test_restore_state_skips_missing_toolbar_ids(qapp):
    """Unknown toolbar ids in saved state do not fail restore."""
    win = LMainWindow()
    top = _make_toolbar("top")
    win.addToolBar(Qt.ToolBarArea.TopToolBarArea, top)

    payload = json.loads(bytes(win.saveState()).decode())
    payload["toolbars"].append(
        {
            "id": "ghost",
            "area": int(Qt.ToolBarArea.RightToolBarArea.value),
            "row": 0,
            "index": 0,
        }
    )
    state = QByteArray(json.dumps(payload).encode())

    assert win.restoreState(state) is True
    assert win.toolBarArea(top) == Qt.ToolBarArea.TopToolBarArea


def test_restore_dock_widget_late_docked_restore(qapp):
    """restoreDockWidget restores a dock created after restoreState()."""
    source = LMainWindow()
    da = _make_dock("da")
    db = _make_dock("db")
    source.addDockWidget(LeftDockWidgetArea, da)
    source.addDockWidget(RightDockWidgetArea, db)
    state = source.saveState()

    win = LMainWindow()
    da2 = _make_dock("da")
    win.addDockWidget(TopDockWidgetArea, da2)

    assert win.restoreState(state) is True
    late = _make_dock("db")
    assert win.restoreDockWidget(late) is True
    assert win.dockWidgetArea(late) == RightDockWidgetArea
    assert win.restoreDockWidget(_make_dock("ghost")) is False


def test_restore_dock_widget_late_floating_restore(qapp):
    """restoreDockWidget restores floating docks with saved geometry."""
    source = LMainWindow()
    dock = _make_dock("floaty")
    source.addDockWidget(LeftDockWidgetArea, dock)
    dock.setFloating(True)
    dock.setGeometry(50, 60, 220, 180)
    state = source.saveState()

    win = LMainWindow()
    assert win.restoreState(state) is True
    late = _make_dock("floaty")
    assert win.restoreDockWidget(late) is True
    assert late.isFloating()
    geometry = late.geometry()
    assert (geometry.x(), geometry.y(), geometry.width(), geometry.height()) == (50, 60, 220, 180)


def test_restore_dock_widget_late_tabbed_restore(qapp):
    """restoreDockWidget restores a late dock into the saved tabbed area."""
    source = LMainWindow()
    first = _make_dock("first")
    second = _make_dock("second")
    source.addDockWidget(LeftDockWidgetArea, first)
    source.addDockWidget(LeftDockWidgetArea, second)
    state = source.saveState()

    win = LMainWindow()
    first_live = _make_dock("first")
    win.addDockWidget(RightDockWidgetArea, first_live)

    assert win.restoreState(state) is True
    second_live = _make_dock("second")
    assert win.restoreDockWidget(second_live) is True
    assert win.dockWidgetArea(second_live) == LeftDockWidgetArea
    assert second_live in win.tabifiedDockWidgets(first_live)
