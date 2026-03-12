# lDockingWidget

Drop-in replacement for `QDockWidget` / `QMainWindow` using a splitter-based layout.

## Problem

Qt's `QMainWindow` internally creates a `QDockAreaLayout` (a private C++ class). When all dock widgets are simultaneously floating, this layout enters an invalid state and crashes. Since `QDockAreaLayout` is not exposed in the Python bindings, it cannot be subclassed or patched around.

## Solution

Replace `QMainWindow` and `QDockWidget` with pure-Python `QWidget` subclasses that never instantiate `QDockAreaLayout`. Layout is built entirely from `QSplitter` widgets.

## Installation

```bash
pip install pyside6
# copy the ldocking/ package into your project
```

## Quick Start

```python
from PySide6.QtWidgets import QApplication, QTextEdit
from ldocking import LMainWindow, LDockWidget, LeftDockWidgetArea, RightDockWidgetArea

app = QApplication([])

win = LMainWindow()
win.setCentralWidget(QTextEdit("Central"))

dock1 = LDockWidget("Tools")
dock1.setWidget(QTextEdit("Tools panel"))
win.addDockWidget(LeftDockWidgetArea, dock1)

dock2 = LDockWidget("Output")
dock2.setWidget(QTextEdit("Output panel"))
win.addDockWidget(RightDockWidgetArea, dock2)

win.show()
app.exec()
```

## Architecture

### Layout

```
LMainWindow (QVBoxLayout)
├── MenuBar          (optional)
├── ToolBars         (optional, stacked vertically)
├── outer_splitter   (Horizontal)
│   ├── left_area    (LDockArea)
│   ├── inner_splitter (Vertical)
│   │   ├── top_area      (LDockArea)
│   │   ├── central_widget
│   │   └── bottom_area   (LDockArea)
│   └── right_area   (LDockArea)
└── StatusBar
```

### Classes

| Class | Replaces | Notes |
|---|---|---|
| `LMainWindow` | `QMainWindow` | `QWidget` subclass, never creates `QDockAreaLayout` |
| `LDockWidget` | `QDockWidget` | `QWidget` subclass, floating uses `Qt.Tool + FramelessWindowHint` |
| `LDockArea` | internal | One dock strip; auto-collapses when empty |
| `LDockTabArea` | internal | `QTabBar + QStackedWidget`; appears when 2+ docks share an area |
| `LTitleBar` | internal | Drag handle with float/close buttons |
| `LDragManager` | internal | Singleton event filter; manages drag→float→drop state machine |
| `LDropIndicator` | internal | Semi-transparent overlay shown during drag |

### LDockArea State Machine

| Dock count | Mode |
|---|---|
| 0 | Hidden (splitter collapses) |
| 1 | Dock shown directly |
| ≥ 2, tabs allowed | `LDockTabArea` |
| ≥ 2, tabs off | `QSplitter` |

### Drag / Drop

1. `LTitleBar` detects drag beyond `startDragDistance` → emits `drag_started`
2. `LDragManager.begin_drag()` installs itself as a global event filter
3. `mouseMoveEvent`: moves floating dock + computes drop target + shows `LDropIndicator`
4. `mouseReleaseEvent`: calls `addDockWidget` on the target, or leaves dock floating
5. `Escape`: cancels drag, returns dock to origin area

## API Reference

### LMainWindow

Mirrors `QMainWindow`:

```python
win.setCentralWidget(widget)
win.centralWidget() -> QWidget | None
win.addDockWidget(area, dock)
win.removeDockWidget(dock)
win.dockWidgetArea(dock) -> Qt.DockWidgetArea
win.tabifyDockWidget(first, second)
win.tabifiedDockWidgets(dock) -> list[LDockWidget]
win.resizeDocks(docks, sizes, orientation)
win.setDockOptions(options)
win.dockOptions() -> QMainWindow.DockOption
win.setMenuBar(menu_bar)
win.menuBar() -> QMenuBar
win.addToolBar(toolbar)
win.statusBar() -> QStatusBar
win.setStatusBar(status_bar)
win.setCorner(corner, area)   # no-op; corners handled by splitter geometry
```

### LDockWidget

Mirrors `QDockWidget`:

```python
dock.setWidget(widget)
dock.widget() -> QWidget | None
dock.setWindowTitle(title)
dock.windowTitle() -> str
dock.setFloating(floating)
dock.isFloating() -> bool
dock.setFeatures(features)
dock.features() -> DockWidgetFeature
dock.setAllowedAreas(areas)
dock.allowedAreas() -> Qt.DockWidgetArea
dock.toggleViewAction() -> QAction
# Signals:
dock.featuresChanged(DockWidgetFeature)
dock.allowedAreasChanged(Qt.DockWidgetArea)
dock.visibilityChanged(bool)
dock.topLevelChanged(bool)
dock.dockLocationChanged(Qt.DockWidgetArea)
```

### Enums

All enums are re-exported by reference from `QDockWidget`/`QMainWindow`, so `isinstance` checks are identical to stock Qt:

```python
from ldocking import (
    LeftDockWidgetArea, RightDockWidgetArea,
    TopDockWidgetArea, BottomDockWidgetArea,
    DockWidgetClosable, DockWidgetMovable, DockWidgetFloatable,
    AllowTabbedDocks, AnimatedDocks, ...
)
```

## Tests

```bash
# Reproduce the original Qt crash (exits non-zero with stock Qt)
python tests/phase0_bug_demo.py

# Standalone floating LDockWidget
python tests/phase1_floating.py

# LMainWindow layout + float-all (no crash)
python tests/phase2_docking.py

# Drag-to-dock, drop zones, tab tear-off
python tests/phase3_tabbing.py

# Full window with menu/toolbar/statusbar
python tests/phase4_full.py

# API surface assertions (exit 0 = all 38 pass)
python tests/phase5_compat.py

# Visual demos
python tests/demo_app.py
python tests/parity_demo.py
python tests/tabified_visual.py
```

## Design Notes

- `LMainWindow` and `LDockWidget` intentionally do **not** inherit from their Qt counterparts. Inheriting `QMainWindow` or `QDockWidget` would trigger the C++ constructor that creates `QDockAreaLayout`.
- Enums are re-exported **by reference** (not copied), so `isinstance(x, QDockWidget.DockWidgetFeature)` returns `True` for values sourced from `ldocking`.
- `LDragManager` is a singleton; only one drag operation is active at a time.
- `setCorner` is a no-op because splitter geometry naturally handles corner ownership.
