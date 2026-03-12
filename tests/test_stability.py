"""Stability regression tests for dock float/dock cycles."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ldocking import (
    LDockWidget,
    LMainWindow,
    LeftDockWidgetArea,
    RightDockWidgetArea,
    BottomDockWidgetArea,
)


def test_float_dock_cycle(qapp):
    """Float all docks then re-dock: area map and tab order must be preserved."""
    win = LMainWindow()
    specs = [
        ("A", LeftDockWidgetArea),
        ("B", LeftDockWidgetArea),
        ("C", RightDockWidgetArea),
        ("D", RightDockWidgetArea),
        ("E", BottomDockWidgetArea),
    ]
    docks = []
    for name, area in specs:
        d = LDockWidget(name)
        win.addDockWidget(area, d)
        docks.append(d)

    def snapshot():
        return [(win.dockWidgetArea(d), d.windowTitle()) for d in docks]

    def area_order(area_side):
        return [d.windowTitle() for d in win._dock_areas[area_side]._docks]

    initial_map = snapshot()
    initial_left = area_order(LeftDockWidgetArea)
    initial_right = area_order(RightDockWidgetArea)

    # Float all
    for d in docks:
        d.setFloating(True)

    # Re-dock all in original areas
    for d, (_, area) in zip(docks, specs):
        win.addDockWidget(area, d)

    assert snapshot() == initial_map, "Area map changed after float/dock cycle"
    assert area_order(LeftDockWidgetArea) == initial_left, "Left tab order changed"
    assert area_order(RightDockWidgetArea) == initial_right, "Right tab order changed"
