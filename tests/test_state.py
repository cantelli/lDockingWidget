"""Tests for LMainWindow.saveState() / restoreState()."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtWidgets import QLabel

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

    wrong_version = QByteArray(json.dumps({"version": 99, "docks": []}).encode())
    assert win.restoreState(wrong_version) is False
