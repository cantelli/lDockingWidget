"""tests/parity_test.py — Headless scenario matrix: LDocking vs native QDockWidget.

Run with:
    python tests/parity_test.py
or explicitly headless:
    QT_QPA_PLATFORM=offscreen python tests/parity_test.py

Exit 0 = all scenarios pass.  Exit 1 = one or more mismatches.

To add a new scenario, append one dict to the SCENARIOS list.  No other
changes needed.
"""
import os
import sys

if "QT_QPA_PLATFORM" not in os.environ:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import ldocking.monkey as monkey
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QToolBar
from ldocking import LDockWidget, LMainWindow

NativeQMainWindow = monkey._ORIG["QMainWindow"]
NativeQDockWidget = monkey._ORIG["QDockWidget"]
NoTabs = NativeQMainWindow.DockOption.AnimatedDocks  # AllowTabbedDocks intentionally absent

# ── Area aliases ───────────────────────────────────────────────────────────────
Left   = Qt.DockWidgetArea.LeftDockWidgetArea
Right  = Qt.DockWidgetArea.RightDockWidgetArea
Top    = Qt.DockWidgetArea.TopDockWidgetArea
Bottom = Qt.DockWidgetArea.BottomDockWidgetArea
NoDock = Qt.DockWidgetArea.NoDockWidgetArea

TopTB = Qt.ToolBarArea.TopToolBarArea
LeftTB = Qt.ToolBarArea.LeftToolBarArea
RightTB = Qt.ToolBarArea.RightToolBarArea
BottomTB = Qt.ToolBarArea.BottomToolBarArea


# ── State snapshots ────────────────────────────────────────────────────────────

def qt_snap(win: NativeQMainWindow, docks: list) -> dict:
    """Snapshot state of a native QMainWindow + QDockWidget setup."""
    return {
        "docks": {
            d.windowTitle(): {
                "area":     win.dockWidgetArea(d),
                "floating": d.isFloating(),
                "visible":  d.isVisible(),
                "tabs":     sorted(t.windowTitle() for t in win.tabifiedDockWidgets(d)),
            }
            for d in docks
        }
    }


def _corner_snap(win) -> dict:
    return {
        "top_left": win.corner(Qt.Corner.TopLeftCorner),
        "top_right": win.corner(Qt.Corner.TopRightCorner),
        "bottom_left": win.corner(Qt.Corner.BottomLeftCorner),
        "bottom_right": win.corner(Qt.Corner.BottomRightCorner),
    }


def _toolbar_snap(win, toolbars: list) -> dict:
    return {
        "order": [toolbar.windowTitle() for toolbar in toolbars],
        "items": {
            toolbar.windowTitle(): {
                "area": win.toolBarArea(toolbar),
                "break": win.toolBarBreak(toolbar),
            }
            for toolbar in toolbars
        },
    }


def l_snap(win: LMainWindow, docks: list, toolbars: list | None = None) -> dict:
    """Snapshot state of an LMainWindow + LDockWidget setup.

    Returns NoDockWidgetArea for floating docks (matching Qt semantics),
    and computes tabbed peers from the dock area's internal list.
    """
    def tabbed_peers(d: LDockWidget) -> list:
        if d.isFloating():
            return []
        return sorted(t.windowTitle() for t in win.tabifiedDockWidgets(d))

    return {
        "docks": {
            d.windowTitle(): {
                "area":     NoDock if d.isFloating() else win.dockWidgetArea(d),
                "floating": d.isFloating(),
                "visible":  d.isVisible(),
                "tabs":     tabbed_peers(d),
            }
            for d in docks
        },
        "toolbars": _toolbar_snap(win, toolbars or []),
        "corners": _corner_snap(win),
    }


def compare(qt: dict, l: dict, checks: list) -> list:
    """Return list of (dock_name, field, qt_value, l_value) for any mismatch."""
    mismatches = []
    qt_docks = qt["docks"]
    l_docks = l["docks"]
    dock_checks = [field for field in checks if field in {"area", "floating", "visible", "tabs"}]
    shell_checks = [field for field in checks if field not in {"area", "floating", "visible", "tabs"}]

    for name in sorted(set(qt_docks) | set(l_docks)):
        if name not in qt_docks or name not in l_docks:
            mismatches.append((name, "existence", name in qt, name in l))
            continue
        for field in dock_checks:
            qv = qt_docks[name].get(field)
            lv = l_docks[name].get(field)
            if qv != lv:
                mismatches.append((name, field, qv, lv))

    if "toolbar_area" in shell_checks or "toolbar_break" in shell_checks:
        qt_toolbars = qt["toolbars"]["items"]
        l_toolbars = l["toolbars"]["items"]
        for name in sorted(set(qt_toolbars) | set(l_toolbars)):
            if name not in qt_toolbars or name not in l_toolbars:
                mismatches.append((name, "toolbar_existence", name in qt_toolbars, name in l_toolbars))
                continue
            if "toolbar_area" in shell_checks and qt_toolbars[name]["area"] != l_toolbars[name]["area"]:
                mismatches.append((name, "toolbar_area", qt_toolbars[name]["area"], l_toolbars[name]["area"]))
            if "toolbar_break" in shell_checks and qt_toolbars[name]["break"] != l_toolbars[name]["break"]:
                mismatches.append((name, "toolbar_break", qt_toolbars[name]["break"], l_toolbars[name]["break"]))

    if "toolbar_order" in shell_checks:
        if qt["toolbars"]["order"] != l["toolbars"]["order"]:
            mismatches.append(("__shell__", "toolbar_order", qt["toolbars"]["order"], l["toolbars"]["order"]))

    if "corners" in shell_checks:
        if qt["corners"] != l["corners"]:
            mismatches.append(("__shell__", "corners", qt["corners"], l["corners"]))
    return mismatches


# ── Action factories ───────────────────────────────────────────────────────────

def float_all(qt_win, qt_docks, l_win, l_docks, qt_toolbars=None, l_toolbars=None):
    """Float every dock on both sides."""
    for d in qt_docks:
        d.setFloating(True)
    for d in l_docks:
        d.setFloating(True)


def make_dock_all(setup: list):
    """Return action that re-docks all initially-placed docks to their original areas."""
    placements = [(i, a) for i, (_, a) in enumerate(setup) if a is not None]

    def action(qt_win, qt_docks, l_win, l_docks, qt_toolbars=None, l_toolbars=None):
        for i, a in placements:
            qt_docks[i].setFloating(False)        # un-float before re-registering area
            qt_win.addDockWidget(a, qt_docks[i])  # ensure correct area on Qt side
            l_win.addDockWidget(a, l_docks[i])    # L handles floating internally

    return action


def make_tabify_qt_only(idx_first: int, idx_second: int):
    """Call tabifyDockWidget on Qt side; L already tabs automatically."""
    def action(qt_win, qt_docks, l_win, l_docks, qt_toolbars=None, l_toolbars=None):
        qt_win.tabifyDockWidget(qt_docks[idx_first], qt_docks[idx_second])
    return action


def make_tabify_both(idx_first: int, idx_second: int):
    """Call tabifyDockWidget on both sides (moves second into first's area)."""
    def action(qt_win, qt_docks, l_win, l_docks, qt_toolbars=None, l_toolbars=None):
        qt_win.tabifyDockWidget(qt_docks[idx_first], qt_docks[idx_second])
        l_win.tabifyDockWidget(l_docks[idx_first], l_docks[idx_second])
    return action


def make_float_dock(idx: int):
    """Return action that floats dock[idx] on both sides."""
    def action(qt_win, qt_docks, l_win, l_docks, qt_toolbars=None, l_toolbars=None):
        qt_docks[idx].setFloating(True)
        l_docks[idx].setFloating(True)
    return action


def make_dock_to_area(idx: int, area):
    """Return action that calls addDockWidget(area, dock[idx]) on both sides."""
    def action(qt_win, qt_docks, l_win, l_docks, qt_toolbars=None, l_toolbars=None):
        qt_win.addDockWidget(area, qt_docks[idx])
        l_win.addDockWidget(area, l_docks[idx])
    return action


def make_close_dock(idx: int):
    """Return action that closes dock[idx] on both sides."""
    def action(qt_win, qt_docks, l_win, l_docks, qt_toolbars=None, l_toolbars=None):
        qt_docks[idx].close()
        l_docks[idx].close()
    return action


def make_set_dock_options(options):
    """Set dock options on both sides."""
    def action(qt_win, qt_docks, l_win, l_docks, qt_toolbars=None, l_toolbars=None):
        qt_win.setDockOptions(options)
        l_win.setDockOptions(options)
    return action


def make_remove_dock(idx: int):
    """Call removeDockWidget on both sides."""
    def action(qt_win, qt_docks, l_win, l_docks, qt_toolbars=None, l_toolbars=None):
        qt_win.removeDockWidget(qt_docks[idx])
        l_win.removeDockWidget(l_docks[idx])
    return action


def make_save_restore_round_trip():
    """Save state on both sides, perturb layout, then restore it."""
    def action(qt_win, qt_docks, l_win, l_docks, qt_toolbars=None, l_toolbars=None):
        qt_state = qt_win.saveState()
        l_state = l_win.saveState()
        for dock in qt_docks:
            qt_win.addDockWidget(Right, dock)
        for dock in l_docks:
            l_win.addDockWidget(Right, dock)
        for toolbar in qt_toolbars or []:
            qt_win.addToolBar(TopTB, toolbar)
        for toolbar in l_toolbars or []:
            l_win.addToolBar(TopTB, toolbar)
        qt_win.setCorner(Qt.Corner.TopLeftCorner, Top)
        qt_win.setCorner(Qt.Corner.BottomRightCorner, Bottom)
        l_win.setCorner(Qt.Corner.TopLeftCorner, Top)
        l_win.setCorner(Qt.Corner.BottomRightCorner, Bottom)
        qt_win.restoreState(qt_state)
        l_win.restoreState(l_state)
    return action


def make_late_restore_dock(idx: int, area):
    """Restore one dock after restoreState() using restoreDockWidget on both sides."""
    def action(qt_win, qt_docks, l_win, l_docks, qt_toolbars=None, l_toolbars=None):
        qt_state = qt_win.saveState()
        l_state = l_win.saveState()

        qt_old = qt_docks[idx]
        l_old = l_docks[idx]
        title = qt_old.windowTitle()

        qt_win.removeDockWidget(qt_old)
        l_win.removeDockWidget(l_old)
        qt_old.setParent(None)
        l_old.setParent(None)

        qt_win.restoreState(qt_state)
        l_win.restoreState(l_state)

        qt_new = NativeQDockWidget(title)
        qt_new.setObjectName(title)
        qt_new.setWidget(QLabel(title))
        qt_docks[idx] = qt_new

        l_new = LDockWidget(title)
        l_new.setObjectName(title)
        l_new.setWidget(QLabel(title))
        l_docks[idx] = l_new

        if not qt_win.restoreDockWidget(qt_new):
            qt_win.addDockWidget(area, qt_new)
        if not l_win.restoreDockWidget(l_new):
            l_win.addDockWidget(area, l_new)
    return action


def make_insert_toolbar_break(idx: int):
    """Insert a toolbar break before toolbar[idx] on both sides."""
    def action(qt_win, qt_docks, l_win, l_docks, qt_toolbars=None, l_toolbars=None):
        qt_win.insertToolBarBreak(qt_toolbars[idx])
        l_win.insertToolBarBreak(l_toolbars[idx])
    return action


def make_set_corner(corner, area):
    """Set corner ownership on both sides."""
    def action(qt_win, qt_docks, l_win, l_docks, qt_toolbars=None, l_toolbars=None):
        qt_win.setCorner(corner, area)
        l_win.setCorner(corner, area)
    return action


# ── Scenario table ─────────────────────────────────────────────────────────────
#
# Each scenario dict:
#   name    – unique identifier printed in output
#   setup   – list of (title, area_or_None) tuples
#               area=None → dock created but NOT placed initially
#   actions – list of callables(qt_win, qt_docks, l_win, l_docks)
#   check   – subset of ['area', 'floating', 'visible', 'tabs'] to compare
#
# To add a new scenario: append one dict here.  No other changes needed.

SCENARIOS = [
    # 1 ── two docks on Left, float all, dock all back ────────────────────────
    {
        "name": "float_all_dock_all_2L",
        "setup": [("A", Left), ("B", Left)],
        "actions": [
            float_all,
            make_dock_all([("A", Left), ("B", Left)]),
        ],
        "check": ["area", "floating"],
    },

    # 2 ── full layout, float all, dock all back ──────────────────────────────
    {
        "name": "float_all_dock_all_full",
        "setup": [
            ("A", Left), ("B", Left),
            ("C", Right), ("D", Right),
            ("E", Bottom),
        ],
        "actions": [
            float_all,
            make_dock_all([
                ("A", Left), ("B", Left),
                ("C", Right), ("D", Right),
                ("E", Bottom),
            ]),
        ],
        "check": ["area", "floating"],
    },

    # 3 ── float one dock, then dock all ──────────────────────────────────────
    {
        "name": "float_one_dock_all",
        "setup": [("A", Left), ("B", Left), ("C", Right), ("D", Right)],
        "actions": [
            make_float_dock(1),   # float B
            make_dock_all([("A", Left), ("B", Left), ("C", Right), ("D", Right)]),
        ],
        "check": ["area", "floating"],
    },

    # 4 ── float A, re-dock A, float B, re-dock B ─────────────────────────────
    {
        "name": "float_each_dock_each",
        "setup": [("A", Left), ("B", Left)],
        "actions": [
            make_float_dock(0),
            make_dock_to_area(0, Left),
            make_float_dock(1),
            make_dock_to_area(1, Left),
        ],
        "check": ["area"],
    },

    # 5 ── move A from Left to Right ──────────────────────────────────────────
    {
        "name": "move_dock_to_new_area",
        "setup": [("A", Left), ("B", Left)],
        "actions": [make_dock_to_area(0, Right)],
        "check": ["area"],
    },

    # 6 ── add a second dock to an already-occupied area ──────────────────────
    #       B starts unplaced (None), then is added to Left where A lives
    {
        "name": "add_dock_to_occupied_area",
        "setup": [("A", Left), ("B", None)],
        "actions": [make_dock_to_area(1, Left)],
        "check": ["area"],
    },

    # 7 ── close one dock in a tabbed pair ────────────────────────────────────
    {
        "name": "close_dock",
        "setup": [("A", Left), ("B", Left)],
        "actions": [make_close_dock(0)],
        "check": ["visible"],
    },

    # 8 ── float all, then re-dock in reverse order ───────────────────────────
    {
        "name": "float_all_dock_out_of_order",
        "setup": [("A", Left), ("B", Left), ("C", Right)],
        "actions": [
            float_all,
            make_dock_to_area(2, Right),  # C first
            make_dock_to_area(1, Left),   # B second
            make_dock_to_area(0, Left),   # A last
        ],
        "check": ["area"],
    },

    # 9 ── explicit tabify: both sides should agree on tab peers ──────────────
    {
        "name": "tabify_explicit",
        "setup": [("A", Left), ("B", Left)],
        "actions": [
            make_tabify_qt_only(0, 1),  # Qt: explicitly tabify A and B; L already tabs
        ],
        "check": ["tabs"],
    },

    # 10 ── three docks tabified on Left ──────────────────────────────────────
    {
        "name": "tabify_three_explicit",
        "setup": [("A", Left), ("B", Left), ("C", Left)],
        "actions": [
            make_tabify_qt_only(0, 1),
            make_tabify_qt_only(0, 2),
        ],
        "check": ["tabs"],
    },

    # 11 ── tabify two, then float one ─────────────────────────────────────────
    {
        "name": "tabify_then_float_one",
        "setup": [("A", Left), ("B", Left)],
        "actions": [
            make_tabify_qt_only(0, 1),
            make_float_dock(1),
        ],
        "check": ["tabs", "floating"],
    },

    # 12 ── remove one dock ────────────────────────────────────────────────────
    {
        "name": "remove_dock",
        "setup": [("A", Left), ("B", Left)],
        "actions": [make_remove_dock(0)],
        "check": ["area"],
    },

    # 14 ── AllowTabbedDocks=False: second dock in same area must not tab ──────
    {
        "name": "dock_options_no_tabs",
        "setup": [("A", Left), ("B", None)],
        "actions": [
            make_set_dock_options(NoTabs),   # disable AllowTabbedDocks
            make_dock_to_area(1, Left),      # B added to Left after option set
        ],
        "check": ["tabs"],
    },

    # 13 ── float then dock to a different area ────────────────────────────────
    #        Only checks area: Qt does not reliably un-float via addDockWidget
    #        alone (see make_dock_all which calls setFloating(False) first).
    {
        "name": "float_then_dock_to_new_area",
        "setup": [("A", Left), ("B", Left)],
        "actions": [
            make_float_dock(0),
            make_dock_to_area(0, Right),
        ],
        "check": ["area"],
    },

    # 15 ── all four areas simultaneously ─────────────────────────────────────
    {
        "name": "all_four_areas",
        "setup": [("A", Left), ("B", Right), ("C", Top), ("D", Bottom)],
        "actions": [],
        "check": ["area"],
    },

    # 16 ── three explicitly tabbed, remove middle, A and C still peers ─────────
    #        Without the explicit tabify calls Qt would split (not tab) the three
    #        docks, so tabs would be empty on both sides after removal — that is
    #        not what we're testing here.
    {
        "name": "tabify_then_remove_middle",
        "setup": [("A", Left), ("B", Left), ("C", Left)],
        "actions": [
            make_tabify_qt_only(0, 1),  # Qt: tabify A+B; L already tabs
            make_tabify_qt_only(0, 2),  # Qt: tabify A+C; L already has all three
            make_remove_dock(1),        # remove B — A and C should still be peers
        ],
        "check": ["tabs"],
    },

    # 17 ── tabifyDockWidget across areas: moves dock to target's area ─────────
    {
        "name": "cross_area_tabify",
        "setup": [("A", Left), ("B", Right)],
        "actions": [make_tabify_both(0, 1)],   # B moves to Left, tabs with A
        "check": ["area", "tabs"],
    },

    # 18 ── float all four docks, re-dock each to the opposite area ────────────
    {
        "name": "float_all_four_dock_swapped",
        "setup": [("A", Left), ("B", Right), ("C", Top), ("D", Bottom)],
        "actions": [
            float_all,
            make_dock_all([("A", Right), ("B", Left), ("C", Bottom), ("D", Top)]),
        ],
        "check": ["area"],
    },

    # 19 -- save/restore round-trip should preserve externally visible state
    {
        "name": "save_restore_round_trip",
        "setup": [("A", Left), ("B", Left), ("C", Right)],
        "actions": [
            make_tabify_qt_only(0, 1),
            make_save_restore_round_trip(),
        ],
        "check": ["area", "floating", "tabs"],
    },

    # 20 -- late-created dock restored after restoreState
    {
        "name": "restore_dock_widget_late",
        "setup": [("A", Left), ("B", Right)],
        "actions": [make_late_restore_dock(1, Right)],
        "check": ["area", "floating", "tabs"],
    },

    {
        "name": "toolbar_shell_restore",
        "setup": [("A", Left)],
        "toolbars": [
            ("Top A", TopTB),
            ("Top B", TopTB),
            ("Left", LeftTB),
            ("Right", RightTB),
            ("Bottom", BottomTB),
        ],
        "actions": [
            make_insert_toolbar_break(1),
            make_set_corner(Qt.Corner.TopLeftCorner, Left),
            make_set_corner(Qt.Corner.BottomRightCorner, Right),
            make_save_restore_round_trip(),
        ],
        "check": ["area", "toolbar_area", "toolbar_break", "toolbar_order", "corners"],
    },
]


# ── Scenario runner ────────────────────────────────────────────────────────────

def run_scenario(scenario: dict, app: QApplication) -> list:
    """Set up both sides, execute actions, compare and return mismatches."""
    setup = scenario["setup"]

    # Native Qt side
    qt_win = NativeQMainWindow()
    qt_win.setCentralWidget(QLabel("central"))
    qt_docks: list[NativeQDockWidget] = []
    qt_toolbars: list[QToolBar] = []
    for title, _ in setup:
        d = NativeQDockWidget(title)
        d.setObjectName(title)
        d.setWidget(QLabel(title))
        qt_docks.append(d)
    for d, (_, area) in zip(qt_docks, setup):
        if area is not None:
            qt_win.addDockWidget(area, d)
    for title, area in scenario.get("toolbars", []):
        toolbar = QToolBar(title)
        toolbar.setObjectName(title)
        toolbar.addAction(title)
        qt_win.addToolBar(area, toolbar)
        qt_toolbars.append(toolbar)

    # LDocking side
    l_win = LMainWindow()
    l_docks: list[LDockWidget] = []
    l_toolbars: list[QToolBar] = []
    for title, _ in setup:
        d = LDockWidget(title)
        d.setObjectName(title)
        d.setWidget(QLabel(title))
        l_docks.append(d)
    for d, (_, area) in zip(l_docks, setup):
        if area is not None:
            l_win.addDockWidget(area, d)
    for title, area in scenario.get("toolbars", []):
        toolbar = QToolBar(title)
        toolbar.setObjectName(title)
        toolbar.addAction(title)
        l_win.addToolBar(area, toolbar)
        l_toolbars.append(toolbar)

    qt_win.show()
    l_win.show()
    app.processEvents()

    for action in scenario["actions"]:
        action(qt_win, qt_docks, l_win, l_docks, qt_toolbars, l_toolbars)
        app.processEvents()

    qt_s = qt_snap(qt_win, qt_docks)
    qt_s["toolbars"] = _toolbar_snap(qt_win, qt_toolbars)
    qt_s["corners"] = _corner_snap(qt_win)
    l_s  = l_snap(l_win, l_docks, l_toolbars)
    mismatches = compare(qt_s, l_s, scenario["check"])

    qt_win.close()
    l_win.close()
    app.processEvents()

    return mismatches


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    app = QApplication.instance() or QApplication(sys.argv)

    total    = len(SCENARIOS)
    failures = 0

    print("=" * 60)
    print("Parity test: LDocking vs native QDockWidget")
    print("=" * 60)

    for scenario in SCENARIOS:
        name = scenario["name"]
        mismatches = run_scenario(scenario, app)
        if mismatches:
            failures += 1
            print(f"FAIL  {name}")
            for dock, field, qt_val, l_val in mismatches:
                print(f"      dock={dock!r:4}  field={field!r:10}  "
                      f"qt={str(qt_val)!r:40}  l={str(l_val)!r}")
        else:
            print(f"PASS  {name}")

    print("-" * 60)
    passed = total - failures
    print(f"{passed}/{total} passed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
