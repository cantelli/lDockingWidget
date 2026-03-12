# CLAUDE.md — lDockingWidget

## Project Purpose

Drop-in replacement for `QDockWidget`/`QMainWindow` using splitter-based layout.
Eliminates `QDockAreaLayout` (private Qt C++ class) to fix a crash when all docks float simultaneously.

## Key Invariants — Never Break These

- `LMainWindow` must inherit `QWidget`, NOT `QMainWindow`. Inheriting `QMainWindow` triggers the C++ constructor that creates `QDockAreaLayout` and reintroduces the crash.
- `LDockWidget` must inherit `QWidget`, NOT `QDockWidget`. Qt's C++ `addDockWidget` performs a type check that would fail with a pure-Python subclass of `QDockWidget`.
- All enums in `enums.py` must be re-exported **by reference** from `QDockWidget`/`QMainWindow`, not redefined. This keeps `isinstance` checks working identically to stock Qt.

## Tech Stack

- Python 3.10+
- PySide6 (not PyQt5/PyQt6)

## Running Tests

```bash
python tests/phase5_compat.py   # API surface: 38 assertions, exit 0 = pass
python tests/phase2_docking.py  # Float-all smoke test (the original crash scenario)
python tests/phase0_bug_demo.py # Reproduces the original Qt crash for reference
python tests/demo_app.py        # Full visual demo
```

Always run `phase5_compat.py` after any API changes to verify the public surface is intact.

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

## Conventions

- Type hints on all public methods.
- `TYPE_CHECKING` guards for circular imports between modules.
- Private helpers prefixed with `_`.
- No Qt signal connections in `__init__` of classes that are not yet fully constructed — connect signals after `super().__init__()` and full field setup.
- `setParent(None)` before `deleteLater()` when removing widgets from layouts.
