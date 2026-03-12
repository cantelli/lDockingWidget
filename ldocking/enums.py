"""Re-exports QDockWidget flags, Qt.DockWidgetArea, and QMainWindow.DockOption by reference.

No new enum types are declared. Callers' isinstance checks and flag
operations work identically to the Qt originals.
"""
from PySide6.QtWidgets import QDockWidget as _Q, QMainWindow as _QMW
from PySide6.QtCore import Qt as _Qt

# --- DockWidgetFeature flags ---
DockWidgetFeature = _Q.DockWidgetFeature
DockWidgetClosable = _Q.DockWidgetFeature.DockWidgetClosable
DockWidgetMovable = _Q.DockWidgetFeature.DockWidgetMovable
DockWidgetFloatable = _Q.DockWidgetFeature.DockWidgetFloatable
DockWidgetVerticalTitleBar = _Q.DockWidgetFeature.DockWidgetVerticalTitleBar
NoDockWidgetFeatures = _Q.DockWidgetFeature.NoDockWidgetFeatures
AllDockWidgetFeatures = (
    _Q.DockWidgetFeature.DockWidgetClosable
    | _Q.DockWidgetFeature.DockWidgetMovable
    | _Q.DockWidgetFeature.DockWidgetFloatable
)

# --- DockOption flags (QMainWindow) ---
DockOption = _QMW.DockOption
AnimatedDocks = _QMW.DockOption.AnimatedDocks
AllowNestedDocks = _QMW.DockOption.AllowNestedDocks
AllowTabbedDocks = _QMW.DockOption.AllowTabbedDocks
ForceTabbedDocks = _QMW.DockOption.ForceTabbedDocks
VerticalTabs = _QMW.DockOption.VerticalTabs
GroupedDragging = _QMW.DockOption.GroupedDragging

# --- DockWidgetArea flags ---
DockWidgetArea = _Qt.DockWidgetArea
LeftDockWidgetArea = _Qt.DockWidgetArea.LeftDockWidgetArea
RightDockWidgetArea = _Qt.DockWidgetArea.RightDockWidgetArea
TopDockWidgetArea = _Qt.DockWidgetArea.TopDockWidgetArea
BottomDockWidgetArea = _Qt.DockWidgetArea.BottomDockWidgetArea
AllDockWidgetAreas = _Qt.DockWidgetArea.AllDockWidgetAreas
NoDockWidgetArea = _Qt.DockWidgetArea.NoDockWidgetArea
