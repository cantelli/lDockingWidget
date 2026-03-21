# CLAUDE.md — lDockingWidget

## Project Purpose

Drop-in replacement for `QDockWidget`/`QMainWindow` using splitter-based layout.
Eliminates `QDockAreaLayout` (private Qt C++ class) to fix a crash when all docks float simultaneously.

## Key Invariants — Never Break These

- `LMainWindow` must inherit `QWidget`, NOT `QMainWindow`. Inheriting `QMainWindow` triggers the C++ constructor that creates `QDockAreaLayout` and reintroduces the crash.
- `LDockWidget` must inherit `QWidget`, NOT `QDockWidget`. Qt's C++ `addDockWidget` performs a type check that would fail with a pure-Python subclass of `QDockWidget`.
- All enums in `enums.py` must be re-exported **by reference** from `QDockWidget`/`QMainWindow`, not redefined. This keeps `isinstance` checks working identically to stock Qt.

## Tech Stack

- Python 3.9+
- PySide6 (not PyQt5/PyQt6)

## Running Tests

```bash
pytest -v                            # full suite (primary)
pytest tests/test_api_compat.py -v  # API surface: 38 assertions
python tests/phase0_bug_demo.py     # reproduces the original Qt crash
python tests/demo_app.py            # full visual demo
```

Run `pytest -v` after any changes. All tests run headlessly via `QT_QPA_PLATFORM=offscreen` (set in `tests/conftest.py`).

## Parity Workflow

The primary development loop for this project is closing visual and behavioral gaps between
`LDockWidget`/`LMainWindow` and stock `QDockWidget`/`QMainWindow`. Follow this cycle:

### 1. Take screenshots

```bash
python tests/screenshot_compare.py   # renders all presets headlessly; writes tests/screenshots/
```

This writes paired PNGs: `tests/screenshots/<preset>_qt.png` (reference) and
`tests/screenshots/<preset>_l.png` (our implementation), plus a diff score summary.

### 2. Assess differences

**Always read the actual PNG files directly** using the Read tool — do not rely on diff scores alone.
Diff scores are summary statistics; the images reveal exact panel sizes, tab order, scrollbar presence,
and whitespace. Compare `*_qt.png` vs `*_l.png` for each preset, focusing on presets with
the highest diff scores (especially the `left` sub-score).

### 3. Fix

Identify the root cause in `ldocking/` source code and fix it. Run `pytest -v` after every change
to confirm no regressions (240 tests, all headless).

### 4. Verify and repeat

Re-run `screenshot_compare.py`, re-read the PNGs, confirm the gap is closed, then move to the
next discrepancy. Continue until ldocking looks identical to Qt for all presets.

### Key rule

Always fix ldocking behavior to match Qt — never adjust the test app or expected values to paper over
a difference.

### Manual side-by-side demo

```bash
python tests/visual_compare_demo.py  # live Qt vs ldocking side-by-side window
python tests/demo_app.py             # full ldocking demo app
```

## File Responsibilities

| File | Responsibility |
|---|---|
| `ldocking/__init__.py` | Public API exports only |
| `ldocking/enums.py` | Re-exports Qt enums by reference |
| `ldocking/lmain_window.py` | Top-level window; owns outer/inner splitters and dock areas |
| `ldocking/ldock_widget.py` | Individual dock; manages floating state, signals, resize grip |
| `ldocking/ldock_area.py` | One dock strip; transitions between empty/single/tab/split modes |
| `ldocking/ldock_tab_area.py` | `QTabBar + QStackedWidget` for 2+ docks in one area |
| `ldocking/ltitle_bar.py` | Custom title bar; emits drag/float/close signals |
| `ldocking/ldrag_manager.py` | Singleton event filter; drag→float→drop state machine |
| `ldocking/ldrop_indicator.py` | Semi-transparent overlay shown during drag |
| `ldocking/monkey.py` | Auto-replaces `PySide6.QtWidgets.QMainWindow/QDockWidget` with L* versions on import |

## Architecture Notes

### Layout tree

```
LMainWindow (QVBoxLayout)
├── MenuBar
├── ToolBars
├── outer_splitter (Horizontal): left_area | inner_splitter | right_area
│                                             inner_splitter (Vertical):
│                                               top_area | central | bottom_area
└── StatusBar
```

### LDockArea transitions

- 0 docks → hidden
- 1 dock → dock shown directly in area layout
- ≥2 docks + tabs allowed → `LDockTabArea`
- ≥2 docks + tabs off → `QSplitter`

### Drag lifecycle

1. `LTitleBar` fires `drag_started(global_pos)` after passing `startDragDistance`
2. `LDragManager.begin_drag()` installs a global event filter
3. `mouseMoveEvent` → float dock, compute drop target, show `LDropIndicator`
4. `mouseReleaseEvent` → `addDockWidget` on target, or leave floating
5. `Escape` → cancel, return to origin

## Intentional No-ops

| Method | Reason |
|---|---|
| `LMainWindow.setCorner()` | Corner ownership is implicit in the splitter geometry |
| `LMainWindow.addToolBarBreak()` | Single toolbar row — line breaks not supported |
| `LMainWindow.removeToolBarBreak()` | (same) |
| `LMainWindow.insertToolBarBreak()` | (same) |
| `LMainWindow.toolBarBreak()` | Always returns `False` |

## Conventions

- Type hints on all public methods.
- `TYPE_CHECKING` guards for circular imports between modules.
- Private helpers prefixed with `_`.
- No Qt signal connections in `__init__` of classes that are not yet fully constructed — connect signals after `super().__init__()` and full field setup.
- `setParent(None)` before `deleteLater()` when removing widgets from layouts.
- `WA_StyledBackground` must be set on any `QWidget` subclass that needs QSS `background-color` rules to work. Currently set on `LMainWindow`, `LDockWidget`, `LDockArea`, and `LTitleBar`.
- `ldocking/monkey.py` patches `PySide6.QtWidgets` module attributes at import time. `_ORIG` is captured at module load (not inside `patch()`), so calling `patch()` twice is safe. Tests that need real Qt classes must use `monkey._ORIG["QMainWindow"]` / `monkey._ORIG["QDockWidget"]` rather than importing from `PySide6.QtWidgets` directly (the patched names would return L* classes).
- **Import order for monkey patch**: `import ldocking.monkey` must appear before any other import that pulls in `QMainWindow` or `QDockWidget`. Place it as the very first import in `main.py`.
