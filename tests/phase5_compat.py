"""Phase 5 — API compatibility assertions.

Checks that LDockWidget has the same public surface as QDockWidget.
Exit code 0 = all assertions passed.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PySide6.QtWidgets import QApplication, QDockWidget, QLabel

# Need a QApplication for widgets
app = QApplication.instance() or QApplication(sys.argv)

from ldocking import (
    AllDockWidgetAreas,
    AllDockWidgetFeatures,
    AllowTabbedDocks,
    AnimatedDocks,
    BottomDockWidgetArea,
    DockOption,
    DockWidgetArea,
    DockWidgetClosable,
    DockWidgetFeature,
    DockWidgetFloatable,
    DockWidgetMovable,
    DockWidgetVerticalTitleBar,
    ForceTabbedDocks,
    LeftDockWidgetArea,
    LDockWidget,
    LMainWindow,
    NoDockWidgetArea,
    NoDockWidgetFeatures,
    RightDockWidgetArea,
    TopDockWidgetArea,
    VerticalTabs,
)


def check(condition: bool, name: str) -> None:
    if condition:
        print(f"  PASS: {name}")
    else:
        print(f"  FAIL: {name}")
        sys.exit(1)


print("=== Phase 5: API Surface Compatibility ===\n")

# --- Method presence ---
print("--- Method presence ---")
dock = LDockWidget("Test")
required_methods = [
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
for method in required_methods:
    check(hasattr(dock, method), f"LDockWidget.{method}")

# --- Signal presence ---
print("\n--- Signals ---")
signals = [
    "featuresChanged",
    "allowedAreasChanged",
    "visibilityChanged",
    "topLevelChanged",
    "dockLocationChanged",
]
for sig in signals:
    check(hasattr(dock, sig), f"LDockWidget.{sig}")

# --- Enum identity (reuses Qt's exact types) ---
print("\n--- Enum identity ---")
from PySide6.QtWidgets import QDockWidget as _Q

check(
    DockWidgetFeature is _Q.DockWidgetFeature,
    "DockWidgetFeature is QDockWidget.DockWidgetFeature",
)
check(
    DockWidgetClosable is _Q.DockWidgetFeature.DockWidgetClosable,
    "DockWidgetClosable identity",
)
check(
    DockWidgetFloatable is _Q.DockWidgetFeature.DockWidgetFloatable,
    "DockWidgetFloatable identity",
)
check(
    DockWidgetMovable is _Q.DockWidgetFeature.DockWidgetMovable,
    "DockWidgetMovable identity",
)

# --- setFeatures with Qt enum must not raise ---
print("\n--- setFeatures with Qt enum types ---")
try:
    dock.setFeatures(_Q.DockWidgetFeature.DockWidgetClosable)
    check(True, "setFeatures(QDockWidget.DockWidgetClosable) does not raise")
except Exception as e:
    check(False, f"setFeatures raised: {e}")

try:
    dock.setFeatures(AllDockWidgetFeatures)
    check(True, "setFeatures(AllDockWidgetFeatures) does not raise")
except Exception as e:
    check(False, f"setFeatures raised: {e}")

try:
    dock.setFeatures(NoDockWidgetFeatures)
    check(True, "setFeatures(NoDockWidgetFeatures) does not raise")
except Exception as e:
    check(False, f"setFeatures raised: {e}")

# --- setWidget ---
print("\n--- setWidget ---")
label = QLabel("test")
dock.setWidget(label)
check(dock.widget() is label, "setWidget / widget round-trip")

# --- toggleViewAction ---
print("\n--- toggleViewAction ---")
action = dock.toggleViewAction()
check(action is not None, "toggleViewAction returns non-None")
check(action.isCheckable(), "toggleViewAction is checkable")
check(action.text() == "Test", "toggleViewAction text matches title")

# --- isFloating ---
print("\n--- isFloating ---")
check(not dock.isFloating(), "new dock is not floating")

# --- windowTitle ---
print("\n--- windowTitle ---")
dock.setWindowTitle("New Title")
check(dock.windowTitle() == "New Title", "setWindowTitle / windowTitle")

# --- Area enums ---
print("\n--- Area enum values ---")
from PySide6.QtCore import Qt
check(LeftDockWidgetArea == Qt.DockWidgetArea.LeftDockWidgetArea, "LeftDockWidgetArea")
check(RightDockWidgetArea == Qt.DockWidgetArea.RightDockWidgetArea, "RightDockWidgetArea")
check(TopDockWidgetArea == Qt.DockWidgetArea.TopDockWidgetArea, "TopDockWidgetArea")
check(BottomDockWidgetArea == Qt.DockWidgetArea.BottomDockWidgetArea, "BottomDockWidgetArea")

# --- LMainWindow.setDockOptions / dockOptions ---
print("\n--- LMainWindow dock options ---")
from PySide6.QtWidgets import QMainWindow as _QMW

win = LMainWindow()
check(hasattr(win, "setDockOptions"), "LMainWindow.setDockOptions")
check(hasattr(win, "dockOptions"), "LMainWindow.dockOptions")
check(hasattr(win, "setCorner"), "LMainWindow.setCorner")
check(hasattr(win, "tabifiedDockWidgets"), "LMainWindow.tabifiedDockWidgets")

default_opts = win.dockOptions()
check(
    bool(default_opts & _QMW.DockOption.AnimatedDocks),
    "default dockOptions includes AnimatedDocks",
)
check(
    bool(default_opts & _QMW.DockOption.AllowTabbedDocks),
    "default dockOptions includes AllowTabbedDocks",
)

try:
    win.setDockOptions(_QMW.DockOption.AnimatedDocks | _QMW.DockOption.AllowTabbedDocks)
    check(True, "setDockOptions does not raise")
except Exception as e:
    check(False, f"setDockOptions raised: {e}")

check(
    win.dockOptions() == _QMW.DockOption.AnimatedDocks | _QMW.DockOption.AllowTabbedDocks,
    "dockOptions round-trips set value",
)

# --- tabifiedDockWidgets functional check ---
print("\n--- tabifiedDockWidgets ---")
from PySide6.QtWidgets import QLabel as _QLabel
win2 = LMainWindow()
da = LDockWidget("DA"); da.setWidget(_QLabel("DA"))
db = LDockWidget("DB"); db.setWidget(_QLabel("DB"))
win2.addDockWidget(LeftDockWidgetArea, da)
win2.addDockWidget(LeftDockWidgetArea, db)
check(db in win2.tabifiedDockWidgets(da), "tabifiedDockWidgets(da) contains db")
check(da in win2.tabifiedDockWidgets(db), "tabifiedDockWidgets(db) contains da")
check(da not in win2.tabifiedDockWidgets(da), "tabifiedDockWidgets excludes self")

# --- DockOption enum identity ---
print("\n--- DockOption enum identity ---")
check(DockOption is _QMW.DockOption, "DockOption is QMainWindow.DockOption")
check(AnimatedDocks is _QMW.DockOption.AnimatedDocks, "AnimatedDocks identity")
check(AllowTabbedDocks is _QMW.DockOption.AllowTabbedDocks, "AllowTabbedDocks identity")
check(ForceTabbedDocks is _QMW.DockOption.ForceTabbedDocks, "ForceTabbedDocks identity")
check(VerticalTabs is _QMW.DockOption.VerticalTabs, "VerticalTabs identity")

print("\n=== All assertions PASSED ===")
sys.exit(0)
