"""ldocking — drop-in replacement for QDockWidget / QMainWindow.

Public API
----------
LDockWidget   — replaces QDockWidget
LMainWindow   — replaces QMainWindow (no QDockAreaLayout)
LDockArea     — one dock strip (internal, but public for power users)
LDockTabArea  — tabbed dock container
LDragManager  — singleton drag/drop state machine
LDropIndicator — semi-transparent drop hint overlay

Enum re-exports (identical to Qt originals):
  DockWidgetFeature, DockWidgetClosable, DockWidgetMovable,
  DockWidgetFloatable, DockWidgetVerticalTitleBar,
  NoDockWidgetFeatures, AllDockWidgetFeatures,
  DockWidgetArea, LeftDockWidgetArea, RightDockWidgetArea,
  TopDockWidgetArea, BottomDockWidgetArea,
  AllDockWidgetAreas, NoDockWidgetArea,
  DockOption, AnimatedDocks, AllowNestedDocks, AllowTabbedDocks,
  ForceTabbedDocks, VerticalTabs, GroupedDragging
"""

from .enums import (
    AllDockWidgetAreas,
    AllDockWidgetFeatures,
    AllowNestedDocks,
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
    GroupedDragging,
    LeftDockWidgetArea,
    NoDockWidgetArea,
    NoDockWidgetFeatures,
    RightDockWidgetArea,
    TopDockWidgetArea,
    VerticalTabs,
)
from .ldock_area import LDockArea
from .ldock_tab_area import LDockTabArea
from .ldock_widget import LDockWidget
from .ldrag_manager import LDragManager
from .ldrop_indicator import LDropIndicator
from .lmain_window import LMainWindow
from .ltitle_bar import LTitleBar

__all__ = [
    "LDockWidget",
    "LMainWindow",
    "LDockArea",
    "LDockTabArea",
    "LDragManager",
    "LDropIndicator",
    "LTitleBar",
    # DockWidgetFeature enums
    "DockWidgetFeature",
    "DockWidgetClosable",
    "DockWidgetMovable",
    "DockWidgetFloatable",
    "DockWidgetVerticalTitleBar",
    "NoDockWidgetFeatures",
    "AllDockWidgetFeatures",
    # DockWidgetArea enums
    "DockWidgetArea",
    "LeftDockWidgetArea",
    "RightDockWidgetArea",
    "TopDockWidgetArea",
    "BottomDockWidgetArea",
    "AllDockWidgetAreas",
    "NoDockWidgetArea",
    # DockOption enums
    "DockOption",
    "AnimatedDocks",
    "AllowNestedDocks",
    "AllowTabbedDocks",
    "ForceTabbedDocks",
    "VerticalTabs",
    "GroupedDragging",
]
