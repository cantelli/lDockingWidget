# lDockingWidget

Drop-in replacement for `QDockWidget` / `QMainWindow` using a splitter-based layout.

## Problem

Qt's `QMainWindow` internally creates a `QDockAreaLayout` (a private C++ class). When all dock widgets are simultaneously floating, this layout enters an invalid state and crashes. Since `QDockAreaLayout` is not exposed in the Python bindings, it cannot be subclassed or patched around.

## Solution

Replace `QMainWindow` and `QDockWidget` with pure-Python `QWidget` subclasses that never instantiate `QDockAreaLayout`. Layout is built entirely from `QSplitter` widgets.

## Compatibility Notes

`ldocking` aims to be a practical migration layer for common `QMainWindow` / `QDockWidget` usage, not a byte-for-byte reimplementation of every Qt docking behavior.

- `addDockWidget()` and drag/drop now honor `allowedAreas()`. If the requested area is disallowed, the dock falls back to the first allowed side; if no areas are allowed, the operation is ignored.
- Floating/re-docking preserves stable tab order within a dock area.
- `saveState()` / `restoreState()` now preserve the active tab within each tabbed dock area, plus toolbar areas/order/breaks and toolbar-corner ownership.
- `restoreState()` accepts both `ldocking`'s JSON state blobs and native Qt `QMainWindow.saveState()` blobs for the supported subset, restoring live docks/toolbars by `objectName()` or `windowTitle()`.
- `saveQtState()` exports a native Qt `QMainWindow.saveState()` blob for the same supported subset, while `saveState()` remains the default `ldocking` JSON format.
- Native Qt state import only restores docks/toolbars already present in the `LMainWindow`; missing ids are skipped and are not queued for later `restoreDockWidget()`.
- `toggleViewAction()` restores hidden docks without losing floating state, and re-selects a dock when it is shown inside a tab group.
- Drag/drop now distinguishes side-dock targets from center tab-drop targets within visible dock areas.
- `ForceTabbedDocks` is enforced for occupied sides: same-side additions and side drops tab into the existing group instead of creating side-by-side splits.
- `AllowNestedDocks` enables target-local nested splits only when tab forcing is off; when disabled, targeted side drops collapse to top-level side placement.
- `GroupedDragging` drags an entire tab group together, and grouped drops are rejected if any dock in the group disallows the target area.
- The top-level docked layout is now persisted as a root content tree around the central widget. `area_trees` are legacy restore-only compatibility for older saved states and are no longer written by current `saveState()` output.
- Toolbars now support all four Qt toolbar areas plus break rows, and `setCorner()` adjusts which area visually owns each toolbar corner.
- `saveState(version)` persists the caller-provided version number, and `restoreState(state, version)` requires the same version to succeed.
- `restoreDockWidget()` is supported for docks that are created after `restoreState()`.
- `setCorner()` now controls toolbar-corner ownership for the four-area toolbar shell.
- Docked chrome, tabs, toolbars, corners, and saved-state behavior are the primary parity targets; floating docks intentionally remain a frameless `Qt.Tool + FramelessWindowHint` presentation and are visually close to Qt rather than pixel-identical.
- Monkey patching now has a higher-level bootstrap path with runtime diagnostics for import-order leaks; native `QMainWindow` / `QDockWidget` bindings imported before patching are detected and reported.

## Installation

```bash
python -m pip install -e .   # editable from repo root
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

### Bootstrap + diagnostics

For app startup code, prefer the higher-level bootstrap helper:

```python
from ldocking.bootstrap import activate

report = activate(validate=True)
if not report.import_order_ok:
    print(report.format())
```

`activate()` patches Qt, confirms stylesheet translation is active, and reports any
module globals that still reference the original Qt docking classes because they were
imported too early.

If you want launcher-controlled fallback mode, `activate_from_env()` reads
`LDOCKING_PATCH`:

```python
from ldocking.bootstrap import activate_from_env

report = activate_from_env()  # "1"/"true"/"on" enables, "0"/"false"/"off" disables
```

This is useful for CI, staged rollouts, or a crash-only fallback mode without
rewriting the rest of the app bootstrap.

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
├── content_tree     (recursive split tree)
│   ├── dock side leaf / nested split
│   ├── central_widget
│   └── dock side leaf / nested split
└── StatusBar
```

The root content tree is the authoritative top-level docking layout. Compatibility `outer_splitter`, `inner_splitter`, and side `LDockArea` widgets are rebuilt from that tree so existing APIs, tests, and stylesheet selectors still work.

### Classes

| Class | Replaces | Notes |
|---|---|---|
| `LMainWindow` | `QMainWindow` | `QWidget` subclass, never creates `QDockAreaLayout` |
| `LDockWidget` | `QDockWidget` | `QWidget` subclass, floating stays frameless with `Qt.Tool + FramelessWindowHint` |
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
win.toolBarArea(toolbar) -> Qt.ToolBarArea   # Top, Bottom, Left, or Right
win.addToolBarBreak(...)   # supported in all toolbar areas
win.statusBar() -> QStatusBar
win.setStatusBar(status_bar)
win.setCorner(corner, area)   # controls toolbar-corner ownership
win.createPopupMenu() -> QMenu | None
win.saveState(version=0) -> QByteArray
win.saveQtState(version=0) -> QByteArray
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
python -m pytest -v

# Individual test modules
python -m pytest tests/test_api_compat.py -v   # 38 API surface assertions
python -m pytest tests/test_stability.py -v    # float-all-redock cycle
python -m pytest tests/test_state.py -v        # saveState / restoreState
python -m pytest tests/test_api_gaps.py -v     # isAreaAllowed, toolbar, createPopupMenu
python -m pytest tests/test_visual_parity.py -v
python -m pytest tests/test_screenshot_compare.py -v

# Legacy standalone scripts (not collected by pytest)
python tests/phase0_bug_demo.py     # reproduce the original Qt crash
python tests/phase2_docking.py      # float-all no-crash smoke test
python tests/demo_app.py            # full visual demo
python tests/visual_compare_demo.py # side-by-side Qt vs ldocking visual comparison
python tests/screenshot_compare.py  # writes Qt vs ldocking screenshot pairs
```

Current repo status at the time of this documentation update: `python -m pytest -q`
passes with `250` tests.

## Design Notes

- `LMainWindow` and `LDockWidget` intentionally do **not** inherit from their Qt counterparts. Inheriting `QMainWindow` or `QDockWidget` would trigger the C++ constructor that creates `QDockAreaLayout`.
- Enums are re-exported **by reference** (not copied), so `isinstance(x, QDockWidget.DockWidgetFeature)` returns `True` for values sourced from `ldocking`.
- `LDragManager` is a singleton; only one drag operation is active at a time.
- `setCorner` controls which toolbar area visually owns each window corner.
- `addToolBar` accepts either a `QToolBar` instance or a `str` title (matches both `QMainWindow` overloads). All four Qt toolbar areas are supported, and toolbar-break methods create additional lines within the selected area.
- Floating docks deliberately use a frameless top-level widget instead of native Qt floating-window chrome. The visual test suite treats floated docks as bounded-similarity parity rather than exact pixel equivalence.
- QSS background rules require `WA_StyledBackground = True`, which is set on `LMainWindow`, `LDockWidget`, and `LDockArea`. The drop indicator uses `QPalette.Highlight` for theme awareness.
