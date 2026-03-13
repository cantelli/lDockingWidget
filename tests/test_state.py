"""Tests for LMainWindow.saveState() / restoreState()."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtWidgets import QLabel, QToolBar, QWidget

import ldocking.monkey as monkey

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


def _make_native_dock(name: str) -> NativeQDockWidget:
    dock = NativeQDockWidget(name)
    dock.setObjectName(name)
    dock.setWidget(QLabel(name))
    return dock


def _make_native_main_window() -> NativeQMainWindow:
    win = NativeQMainWindow()
    win.setCentralWidget(QWidget())
    win.resize(800, 600)
    return win


def test_save_restore_basic(qapp):
    """State round-trip preserves dock areas and tab order."""
    win = LMainWindow()
    win.resize(800, 600)

    da = _make_dock("da")
    db = _make_dock("db")
    dc = _make_dock("dc")
    win.addDockWidget(LeftDockWidgetArea, da)
    win.addDockWidget(LeftDockWidgetArea, db)
    win.tabifyDockWidget(da, db)
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
    for dock in docks[1:]:
        win.tabifyDockWidget(docks[0], dock)

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
    for dock in docks[1:]:
        win.tabifyDockWidget(docks[0], dock)

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
    for dock in docks[1:]:
        win.tabifyDockWidget(docks[0], dock)

    area = win._dock_areas[LeftDockWidgetArea]
    area.set_current_tab_dock(docks[1])

    state = win.saveState()

    area.set_current_tab_dock(docks[2])
    assert area.current_tab_dock() is docks[2]

    assert win.restoreState(state) is True
    assert area.current_tab_dock() is docks[1]


def test_save_restore_tabified_docks_keep_non_current_visible(qapp):
    """Restored tab groups keep non-current docks visible like native Qt."""
    source = LMainWindow()
    first = _make_dock("first")
    second = _make_dock("second")
    source.addDockWidget(LeftDockWidgetArea, first)
    source.addDockWidget(LeftDockWidgetArea, second)
    source.tabifyDockWidget(first, second)
    source._dock_areas[LeftDockWidgetArea].set_current_tab_dock(first)
    state = source.saveState()

    win = LMainWindow()
    first_live = _make_dock("first")
    second_live = _make_dock("second")
    win.addDockWidget(RightDockWidgetArea, first_live)
    win.addDockWidget(TopDockWidgetArea, second_live)
    win.show()
    assert win.restoreState(state) is True
    qapp.processEvents()

    assert win._dock_areas[LeftDockWidgetArea].current_tab_dock() is first_live
    assert first_live.isVisible()
    assert second_live.isVisible()


def test_save_restore_hidden_dock_visibility(qapp):
    """restoreState preserves docks hidden through toggleViewAction or show/hide flows."""
    source = LMainWindow()
    visible = _make_dock("visible")
    hidden = _make_dock("hidden")
    source.addDockWidget(LeftDockWidgetArea, visible)
    source.addDockWidget(RightDockWidgetArea, hidden)
    source.show()
    qapp.processEvents()

    hidden.toggleViewAction().trigger()
    qapp.processEvents()
    assert not hidden.isVisible()

    state = source.saveState()

    restored = LMainWindow()
    visible_live = _make_dock("visible")
    hidden_live = _make_dock("hidden")
    restored.addDockWidget(TopDockWidgetArea, visible_live)
    restored.addDockWidget(TopDockWidgetArea, hidden_live)
    restored.show()
    qapp.processEvents()

    assert restored.restoreState(state) is True
    qapp.processEvents()
    assert visible_live.isVisible()
    assert not hidden_live.isVisible()


def test_save_state_uses_live_layout_membership(qapp):
    """saveState serializes actual area membership even if the cache is stale."""
    win = LMainWindow()
    dock = _make_dock("da")
    win.addDockWidget(LeftDockWidgetArea, dock)

    win._dock_map[dock] = RightDockWidgetArea

    payload = json.loads(bytes(win.saveState()).decode())

    assert payload["docks"][0]["area"] == LeftDockWidgetArea.value


def test_save_state_omits_legacy_area_trees(qapp):
    """Current saveState payloads use content_tree and no longer emit area_trees."""
    win = LMainWindow()
    win.addDockWidget(LeftDockWidgetArea, _make_dock("da"))
    win.addDockWidget(RightDockWidgetArea, _make_dock("db"))

    payload = json.loads(bytes(win.saveState()).decode())

    assert "content_tree" in payload
    assert "area_trees" not in payload


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


def test_restore_equivalent_layout_from_all_legacy_sources(qapp):
    """content_tree, legacy area_trees, and flat dock entries restore the same simple layout."""
    source = LMainWindow()
    da = _make_dock("da")
    db = _make_dock("db")
    source.addDockWidget(LeftDockWidgetArea, da)
    source.addDockWidget(RightDockWidgetArea, db)
    payload = json.loads(bytes(source.saveState()).decode())

    content_tree_payload = json.loads(json.dumps(payload))

    area_trees_payload = {
        "format_version": payload["format_version"],
        "state_version": payload["state_version"],
        "outer_splitter": payload["outer_splitter"],
        "inner_splitter": payload["inner_splitter"],
        "docks": payload["docks"],
        "current_tabs": payload["current_tabs"],
        "area_trees": {
            str(LeftDockWidgetArea.value): {"type": "dock", "id": "da"},
            str(RightDockWidgetArea.value): {"type": "dock", "id": "db"},
            str(TopDockWidgetArea.value): None,
            str(BottomDockWidgetArea.value): None,
        },
    }

    flat_payload = {
        "format_version": payload["format_version"],
        "state_version": payload["state_version"],
        "outer_splitter": payload["outer_splitter"],
        "inner_splitter": payload["inner_splitter"],
        "docks": payload["docks"],
        "current_tabs": payload["current_tabs"],
    }

    def restore_from(raw_payload: dict[str, object]) -> tuple[Qt.DockWidgetArea, Qt.DockWidgetArea]:
        win = LMainWindow()
        da_live = _make_dock("da")
        db_live = _make_dock("db")
        win.addDockWidget(BottomDockWidgetArea, da_live)
        win.addDockWidget(TopDockWidgetArea, db_live)
        assert win.restoreState(QByteArray(json.dumps(raw_payload).encode())) is True
        return win.dockWidgetArea(da_live), win.dockWidgetArea(db_live)

    expected = (LeftDockWidgetArea, RightDockWidgetArea)
    assert restore_from(content_tree_payload) == expected
    assert restore_from(area_trees_payload) == expected
    assert restore_from(flat_payload) == expected


def test_content_tree_leaf_state_tracks_docked_mutations(qapp):
    """Docked mutations update the in-memory content_tree leaf area state."""
    win = LMainWindow()
    da = _make_dock("da")
    db = _make_dock("db")
    win.addDockWidget(LeftDockWidgetArea, da)
    win.addDockWidget(LeftDockWidgetArea, db)
    win.tabifyDockWidget(da, db)

    leaf = win._leaf_for_key("left")

    assert leaf is not None
    assert leaf.area_state["type"] == "tabs"
    assert [child["id"] for child in leaf.area_state["children"]] == ["da", "db"]


def test_drop_and_direct_add_share_normalized_area_state(qapp):
    """Equivalent placements through addDockWidget and _drop_docks normalize the same way."""
    direct = LMainWindow()
    dropped = LMainWindow()
    for title in ("a", "b"):
        direct.addDockWidget(LeftDockWidgetArea, _make_dock(title))
        dropped.addDockWidget(LeftDockWidgetArea, _make_dock(title))

    direct.addDockWidget(LeftDockWidgetArea, _make_dock("c"))
    drop_c = _make_dock("c")
    dropped._drop_docks(LeftDockWidgetArea, [drop_c], mode="area")

    direct_leaf = direct._leaf_for_key("left")
    dropped_leaf = dropped._leaf_for_key("left")
    assert direct_leaf is not None
    assert dropped_leaf is not None
    assert direct_leaf.area_state == dropped_leaf.area_state


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
    source.tabifyDockWidget(first, second)
    state = source.saveState()

    win = LMainWindow()
    first_live = _make_dock("first")
    win.addDockWidget(RightDockWidgetArea, first_live)

    assert win.restoreState(state) is True
    second_live = _make_dock("second")
    assert win.restoreDockWidget(second_live) is True
    assert win.dockWidgetArea(second_live) == LeftDockWidgetArea
    assert second_live in win.tabifiedDockWidgets(first_live)


def test_restore_dock_widget_matches_direct_tab_insert_state(qapp):
    """Late restore into a saved tab group matches the direct docking state shape."""
    source = LMainWindow()
    first = _make_dock("first")
    second = _make_dock("second")
    source.addDockWidget(LeftDockWidgetArea, first)
    source.addDockWidget(LeftDockWidgetArea, second)
    source.tabifyDockWidget(first, second)
    state = source.saveState()

    restored = LMainWindow()
    restored_first = _make_dock("first")
    restored.addDockWidget(RightDockWidgetArea, restored_first)
    assert restored.restoreState(state) is True
    restored_second = _make_dock("second")
    assert restored.restoreDockWidget(restored_second) is True

    direct = LMainWindow()
    direct_first = _make_dock("first")
    direct_second = _make_dock("second")
    direct.addDockWidget(LeftDockWidgetArea, direct_first)
    direct.addDockWidget(LeftDockWidgetArea, direct_second)
    direct.tabifyDockWidget(direct_first, direct_second)

    restored_leaf = restored._leaf_for_key("left")
    direct_leaf = direct._leaf_for_key("left")
    assert restored_leaf is not None
    assert direct_leaf is not None
    assert restored_leaf.area_state == direct_leaf.area_state


def test_restore_dock_widget_uses_saved_nested_target_when_available(qapp):
    """Late restore uses the saved nested split target instead of top-level fallback."""
    source = LMainWindow()
    source.setDockOptions(source.dockOptions() | LMainWindow.AllowNestedDocks)
    anchor = _make_dock("anchor")
    sibling = _make_dock("sibling")
    nested = _make_dock("nested")
    source.addDockWidget(RightDockWidgetArea, anchor)
    source.addDockWidget(RightDockWidgetArea, sibling)
    source.tabifyDockWidget(anchor, sibling)
    source._drop_docks(
        RightDockWidgetArea,
        [nested],
        mode="side",
        target_id="anchor",
        side=BottomDockWidgetArea,
    )
    state = source.saveState()

    win = LMainWindow()
    win.setDockOptions(win.dockOptions() | LMainWindow.AllowNestedDocks)
    anchor_live = _make_dock("anchor")
    sibling_live = _make_dock("sibling")
    win.addDockWidget(LeftDockWidgetArea, anchor_live)
    win.addDockWidget(TopDockWidgetArea, sibling_live)
    win.tabifyDockWidget(anchor_live, sibling_live)

    assert win.restoreState(state) is True
    nested_live = _make_dock("nested")
    assert win.restoreDockWidget(nested_live) is True
    right_leaf = win._leaf_for_key("right")
    assert right_leaf is not None
    assert right_leaf.area_state["type"] == "split"
    tabs = right_leaf.area_state["children"][0]
    assert tabs["type"] == "tabs"
    assert [child["id"] for child in tabs["children"]] == ["anchor", "sibling"]
    assert right_leaf.area_state["children"][1]["id"] == "nested"


def test_restore_dock_widget_falls_back_when_saved_target_missing(qapp):
    """Late restore falls back to top-level area placement when the saved target is gone."""
    source = LMainWindow()
    source.setDockOptions(source.dockOptions() | LMainWindow.AllowNestedDocks)
    anchor = _make_dock("anchor")
    sibling = _make_dock("sibling")
    nested = _make_dock("nested")
    source.addDockWidget(RightDockWidgetArea, anchor)
    source.addDockWidget(RightDockWidgetArea, sibling)
    source._drop_docks(
        RightDockWidgetArea,
        [nested],
        mode="side",
        target_id="anchor",
        side=BottomDockWidgetArea,
    )
    state = source.saveState()

    win = LMainWindow()
    sibling_live = _make_dock("sibling")
    win.addDockWidget(LeftDockWidgetArea, sibling_live)

    assert win.restoreState(state) is True
    nested_live = _make_dock("nested")
    assert win.restoreDockWidget(nested_live) is True
    assert win.dockWidgetArea(nested_live) == RightDockWidgetArea


def test_restore_state_accepts_native_qt_save_state_for_docks(qapp):
    """restoreState accepts native Qt saveState blobs for dock layout."""
    native = _make_native_main_window()
    first = _make_native_dock("first")
    second = _make_native_dock("second")
    right = _make_native_dock("right")
    floating = _make_native_dock("floating")
    native.addDockWidget(LeftDockWidgetArea, first)
    native.addDockWidget(LeftDockWidgetArea, second)
    native.tabifyDockWidget(first, second)
    native.addDockWidget(RightDockWidgetArea, right)
    native.addDockWidget(BottomDockWidgetArea, floating)
    floating.setFloating(True)
    floating.setGeometry(120, 140, 260, 210)
    native.show()
    qapp.processEvents()

    state = native.saveState()

    win = LMainWindow()
    first_live = _make_dock("first")
    second_live = _make_dock("second")
    right_live = _make_dock("right")
    floating_live = _make_dock("floating")
    for dock in (first_live, second_live, right_live, floating_live):
        win.addDockWidget(TopDockWidgetArea, dock)

    assert win.restoreState(state) is True
    win.show()
    qapp.processEvents()
    assert win.dockWidgetArea(first_live) == LeftDockWidgetArea
    assert win.dockWidgetArea(second_live) == LeftDockWidgetArea
    assert second_live in win.tabifiedDockWidgets(first_live)
    assert first_live.isVisible()
    assert second_live.isVisible()
    assert win.dockWidgetArea(right_live) == RightDockWidgetArea
    assert floating_live.isFloating()
    geometry = floating_live.geometry()
    assert (geometry.x(), geometry.y(), geometry.width(), geometry.height()) == (120, 140, 260, 210)


def test_restore_state_accepts_native_qt_save_state_for_toolbar_shell(qapp):
    """restoreState imports toolbar areas, breaks, and corners from native Qt state."""
    native = _make_native_main_window()
    top = _make_toolbar("top")
    top2 = _make_toolbar("top2")
    left = _make_toolbar("left")
    right = _make_toolbar("right")
    bottom = _make_toolbar("bottom")
    native.addToolBar(Qt.ToolBarArea.TopToolBarArea, top)
    native.addToolBar(Qt.ToolBarArea.TopToolBarArea, top2)
    native.insertToolBarBreak(top2)
    native.addToolBar(Qt.ToolBarArea.LeftToolBarArea, left)
    native.addToolBar(Qt.ToolBarArea.RightToolBarArea, right)
    native.addToolBar(Qt.ToolBarArea.BottomToolBarArea, bottom)
    native.setCorner(Qt.Corner.TopLeftCorner, LeftDockWidgetArea)
    native.setCorner(Qt.Corner.BottomRightCorner, RightDockWidgetArea)
    native.show()
    qapp.processEvents()

    state = native.saveState()

    win = LMainWindow()
    top_live = _make_toolbar("top")
    top2_live = _make_toolbar("top2")
    left_live = _make_toolbar("left")
    right_live = _make_toolbar("right")
    bottom_live = _make_toolbar("bottom")
    for toolbar in (top_live, top2_live, left_live, right_live, bottom_live):
        win.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

    assert win.restoreState(state) is True
    assert win.toolBarArea(top_live) == Qt.ToolBarArea.TopToolBarArea
    assert win.toolBarArea(top2_live) == Qt.ToolBarArea.TopToolBarArea
    assert win.toolBarArea(left_live) == Qt.ToolBarArea.LeftToolBarArea
    assert win.toolBarArea(right_live) == Qt.ToolBarArea.RightToolBarArea
    assert win.toolBarArea(bottom_live) == Qt.ToolBarArea.BottomToolBarArea
    assert win.toolBarBreak(top2_live) is True
    assert win.toolBars()[:5] == [top_live, top2_live, left_live, right_live, bottom_live]
    assert win.corner(Qt.Corner.TopLeftCorner) == LeftDockWidgetArea
    assert win.corner(Qt.Corner.BottomRightCorner) == RightDockWidgetArea


def test_save_qt_state_restores_in_native_qt_for_supported_subset(qapp):
    """saveQtState exports a native Qt state blob for the supported subset."""
    win = LMainWindow()
    first = _make_dock("first")
    second = _make_dock("second")
    right = _make_dock("right")
    floating = _make_dock("floating")
    win.addDockWidget(LeftDockWidgetArea, first)
    win.addDockWidget(LeftDockWidgetArea, second)
    win.addDockWidget(RightDockWidgetArea, right)
    win.addDockWidget(BottomDockWidgetArea, floating)
    win.tabifyDockWidget(first, second)
    floating.setFloating(True)
    floating.setGeometry(90, 110, 240, 190)

    top = _make_toolbar("top")
    top2 = _make_toolbar("top2")
    left = _make_toolbar("left")
    right_tb = _make_toolbar("right_tb")
    bottom = _make_toolbar("bottom")
    win.addToolBar(Qt.ToolBarArea.TopToolBarArea, top)
    win.addToolBar(Qt.ToolBarArea.TopToolBarArea, top2)
    win.insertToolBarBreak(top2)
    win.addToolBar(Qt.ToolBarArea.LeftToolBarArea, left)
    win.addToolBar(Qt.ToolBarArea.RightToolBarArea, right_tb)
    win.addToolBar(Qt.ToolBarArea.BottomToolBarArea, bottom)
    win.setCorner(Qt.Corner.TopLeftCorner, LeftDockWidgetArea)
    win.setCorner(Qt.Corner.BottomRightCorner, RightDockWidgetArea)

    state = win.saveQtState()

    native = _make_native_main_window()
    first_native = _make_native_dock("first")
    second_native = _make_native_dock("second")
    right_native = _make_native_dock("right")
    floating_native = _make_native_dock("floating")
    for dock in (first_native, second_native, right_native, floating_native):
        native.addDockWidget(TopDockWidgetArea, dock)
    top_native = _make_toolbar("top")
    top2_native = _make_toolbar("top2")
    left_native = _make_toolbar("left")
    right_tb_native = _make_toolbar("right_tb")
    bottom_native = _make_toolbar("bottom")
    for toolbar in (top_native, top2_native, left_native, right_tb_native, bottom_native):
        native.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

    assert native.restoreState(state) is True
    native.show()
    qapp.processEvents()

    assert native.dockWidgetArea(first_native) == LeftDockWidgetArea
    assert native.dockWidgetArea(second_native) == LeftDockWidgetArea
    assert second_native in native.tabifiedDockWidgets(first_native)
    assert native.dockWidgetArea(right_native) == RightDockWidgetArea
    assert floating_native.isFloating()
    geometry = floating_native.geometry()
    assert (geometry.x(), geometry.y(), geometry.width(), geometry.height()) == (90, 110, 240, 190)
    assert native.toolBarArea(top_native) == Qt.ToolBarArea.TopToolBarArea
    assert native.toolBarArea(top2_native) == Qt.ToolBarArea.TopToolBarArea
    assert native.toolBarArea(left_native) == Qt.ToolBarArea.LeftToolBarArea
    assert native.toolBarArea(right_tb_native) == Qt.ToolBarArea.RightToolBarArea
    assert native.toolBarArea(bottom_native) == Qt.ToolBarArea.BottomToolBarArea
    assert native.toolBarBreak(top2_native) is True
    assert native.corner(Qt.Corner.TopLeftCorner) == LeftDockWidgetArea
    assert native.corner(Qt.Corner.BottomRightCorner) == RightDockWidgetArea


def test_restore_state_native_qt_skips_missing_live_dock_ids(qapp):
    """Native-state import restores known docks and ignores absent dock ids."""
    native = _make_native_main_window()
    first = _make_native_dock("first")
    missing = _make_native_dock("missing")
    native.addDockWidget(LeftDockWidgetArea, first)
    native.addDockWidget(RightDockWidgetArea, missing)
    state = native.saveState()

    win = LMainWindow()
    first_live = _make_dock("first")
    win.addDockWidget(TopDockWidgetArea, first_live)

    assert win.restoreState(state) is True
    assert win.dockWidgetArea(first_live) == LeftDockWidgetArea
    assert win._pending_dock_restore == {}


def test_restore_state_native_qt_skips_missing_live_toolbar_ids(qapp):
    """Native-state import restores known toolbars and ignores absent ids."""
    native = _make_native_main_window()
    top = _make_toolbar("top")
    missing = _make_toolbar("missing")
    native.addToolBar(Qt.ToolBarArea.TopToolBarArea, top)
    native.addToolBar(Qt.ToolBarArea.RightToolBarArea, missing)
    state = native.saveState()

    win = LMainWindow()
    top_live = _make_toolbar("top")
    win.addToolBar(Qt.ToolBarArea.BottomToolBarArea, top_live)

    assert win.restoreState(state) is True
    assert win.toolBarArea(top_live) == Qt.ToolBarArea.TopToolBarArea


def test_restore_state_native_qt_flattens_same_area_non_tab_groups(qapp):
    """Native same-area non-tab layouts degrade to ldocking's side-area split model."""
    native = _make_native_main_window()
    native.setDockOptions(NativeQMainWindow.DockOption.AnimatedDocks)
    docks = [_make_native_dock(name) for name in ("a", "b", "c")]
    for dock in docks:
        native.addDockWidget(LeftDockWidgetArea, dock)
    native.show()
    qapp.processEvents()
    state = native.saveState()

    win = LMainWindow()
    live_docks = [_make_dock(name) for name in ("a", "b", "c")]
    for dock in live_docks:
        win.addDockWidget(TopDockWidgetArea, dock)

    assert win.restoreState(state) is True
    assert [win.dockWidgetArea(dock) for dock in live_docks] == [LeftDockWidgetArea] * 3
    assert all(win.tabifiedDockWidgets(dock) == [] for dock in live_docks)
    left_leaf = win._leaf_for_key("left")
    assert left_leaf is not None
    assert left_leaf.area_state["type"] == "split"
NativeQDockWidget = monkey._ORIG["QDockWidget"]
NativeQMainWindow = monkey._ORIG["QMainWindow"]
