"""Headless regression test: Float All → Dock All preserves areas and tab order."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PySide6.QtWidgets import QApplication
from ldocking import (
    LDockWidget, LMainWindow,
    LeftDockWidgetArea, RightDockWidgetArea, BottomDockWidgetArea,
)

app = QApplication.instance() or QApplication(sys.argv)

win = LMainWindow()
docks = []
specs = [
    ("A", LeftDockWidgetArea),
    ("B", LeftDockWidgetArea),
    ("C", RightDockWidgetArea),
    ("D", RightDockWidgetArea),
    ("E", BottomDockWidgetArea),
]
for name, area in specs:
    d = LDockWidget(name)
    win.addDockWidget(area, d)
    docks.append(d)


def snapshot():
    return [(win.dockWidgetArea(d), d.windowTitle()) for d in docks]


def area_order(area_side):
    return [d.windowTitle() for d in win._dock_areas[area_side]._docks]


initial_map   = snapshot()
initial_left  = area_order(LeftDockWidgetArea)
initial_right = area_order(RightDockWidgetArea)

print(f"Initial map:   {initial_map}")
print(f"Initial left:  {initial_left}")
print(f"Initial right: {initial_right}")

# Float all
for d in docks:
    d.setFloating(True)

# Dock all
for d, (_, area) in zip(docks, specs):
    win.addDockWidget(area, d)

after_map   = snapshot()
after_left  = area_order(LeftDockWidgetArea)
after_right = area_order(RightDockWidgetArea)

print(f"After map:     {after_map}")
print(f"After left:    {after_left}")
print(f"After right:   {after_right}")

failures = []
if after_map != initial_map:
    failures.append(f"Area map changed:\n  got: {after_map}\n  exp: {initial_map}")
if after_left != initial_left:
    failures.append(f"Left tab order wrong:\n  got: {after_left}\n  exp: {initial_left}")
if after_right != initial_right:
    failures.append(f"Right tab order wrong:\n  got: {after_right}\n  exp: {initial_right}")

if failures:
    for f in failures:
        print(f"FAIL: {f}")
    sys.exit(1)

print("PASS: dock areas and tab order preserved after Float All -> Dock All")
sys.exit(0)
