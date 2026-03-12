# lDockingWidget

Drop-in replacement for `QDockWidget` / `QMainWindow` using a splitter-based layout.

## Problem

Qt's `QMainWindow` internally creates a `QDockAreaLayout` (a private C++ class). When all dock widgets are simultaneously floating, this layout enters an invalid state and crashes. Since `QDockAreaLayout` is not exposed in the Python bindings, it cannot be subclassed or patched around.

## Solution

Replace `QMainWindow` and `QDockWidget` with pure-Python `QWidget` subclasses that never instantiate `QDockAreaLayout`. Layout is built entirely from `QSplitter` widgets.

## Installation

```bash
pip install -e .   # editable from repo root
# or copy the ldocking/ directory into your project
```

## Monkey Patch (zero-code migration)

If you have an existing PySide6 app and want to swap in `LMainWindow`/`LDockWidget` without touching any import lines, add one import at the very top of `main.py` — before any other PySide6 imports:

```python
import ldocking.monkey   # must be the first import in main.py

# All subsequent imports now get the L* versions automatically:
from PySide6.QtWidgets import QMainWindow, QDockWidget   # → LMainWindow, LDockWidget
```

After that, every `QMainWindow()` and `QDockWidget()` call in your app creates the L* replacement. No other code changes are needed.

### Monkey patch API

```python
import ldocking.monkey as monkey

monkey.patch()        # apply replacements (called automatically on import)
monkey.unpatch()      # restore original Qt classes
monkey.is_patched()   # → bool
```

> **Import order matters.** Any `from PySide6.QtWidgets import QMainWindow` that runs *before* `import ldocking.monkey` will get the original Qt class. Place the monkey-patch import first.

---

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
win.addToolBar(toolbar_or_title)   # QToolBar or str
win.removeToolBar(toolbar)
win.insertToolBar(before, toolbar)
win.toolBars() -> list[QToolBar]
win.toolBarArea(toolbar) -> Qt.ToolBarArea   # always TopToolBarArea
win.addToolBarBreak(...)   # no-op (single toolbar row)
win.statusBar() -> QStatusBar
win.setStatusBar(status_bar)
win.setCorner(corner, area)   # no-op; splitter geometry handles corners
win.createPopupMenu() -> QMenu | None
win.saveState(version=0) -> QByteArray
win.restoreState(state, version=0) -> bool
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
dock.isAreaAllowed(area) -> bool
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

## Stylesheets

All widgets use `WA_StyledBackground` and carry QSS-addressable `objectName` selectors:

| Selector | Widget |
|---|---|
| `LDockWidget` | The outer dock frame |
| `LDockWidget > #dockTitleBar` | Title bar strip |
| `LDockWidget > #dockContent` | Content area |
| `LDockArea#dockAreaLeft` | Left dock strip |
| `LDockArea#dockAreaRight` | Right dock strip |
| `LDockArea#dockAreaTop` | Top dock strip |
| `LDockArea#dockAreaBottom` | Bottom dock strip |

Example dark theme:

```css
LDockWidget {
    background: #2b2b2b;
    border: 1px solid #3c3f41;
}
LDockWidget > #dockTitleBar {
    background: #3c3f41;
    color: #bbbbbb;
}
LDockWidget > #dockContent {
    background: #2b2b2b;
}
```

## Tests

```bash
# pytest suite (headless, uses offscreen QPA)
pytest -v

# Individual test modules
pytest tests/test_api_compat.py -v   # 38 API surface assertions
pytest tests/test_stability.py -v   # float-all-redock cycle
pytest tests/test_state.py -v       # saveState / restoreState
pytest tests/test_api_gaps.py -v    # isAreaAllowed, toolbar, createPopupMenu

# Legacy standalone scripts (not collected by pytest)
python tests/phase0_bug_demo.py     # reproduce the original Qt crash
python tests/phase2_docking.py      # float-all no-crash smoke test
python tests/demo_app.py            # full visual demo
```

## Design Notes

- `LMainWindow` and `LDockWidget` intentionally do **not** inherit from their Qt counterparts. Inheriting `QMainWindow` or `QDockWidget` would trigger the C++ constructor that creates `QDockAreaLayout`.
- Enums are re-exported **by reference** (not copied), so `isinstance(x, QDockWidget.DockWidgetFeature)` returns `True` for values sourced from `ldocking`.
- `LDragManager` is a singleton; only one drag operation is active at a time.
- `setCorner` is a no-op because splitter geometry naturally handles corner ownership.
- `addToolBar` accepts either a `QToolBar` instance or a `str` title (matches both `QMainWindow` overloads). All toolbars live at the top; `toolBarArea` always returns `TopToolBarArea` and toolbar-break methods are no-ops.
- QSS background rules require `WA_StyledBackground = True`, which is set on `LMainWindow`, `LDockWidget`, and `LDockArea`. The drop indicator uses `QPalette.Highlight` for theme awareness.
