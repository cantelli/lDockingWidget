"""tests/parity_demo.py — Visual side-by-side parity demo.

Shows Native Qt (QMainWindow + QDockWidget) on the left and LDocking
(LMainWindow + LDockWidget) on the right, kept in sync by toolbar actions.
The status bar reports any detected state mismatches after every action.

Run with:
    python tests/parity_demo.py
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDockWidget,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ldocking import LDockWidget, LMainWindow

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

# ── Layout presets ─────────────────────────────────────────────────────────────
LAYOUTS: dict[str, list[tuple[str, Qt.DockWidgetArea]]] = {
    "2L": [
        ("Panel A", Left),
        ("Panel B", Left),
    ],
    "Grouped": [
        ("Panel A", Left),
        ("Panel B", Left),
        ("Panel C", Left),
    ],
    "Nested": [
        ("Panel A", Left),
        ("Panel B", Left),
        ("Panel C", Left),
        ("Panel D", Right),
    ],
    "2L+2R": [
        ("Panel A", Left),
        ("Panel B", Left),
        ("Panel C", Right),
        ("Panel D", Right),
    ],
    "Full": [
        ("Panel A", Left),
        ("Panel B", Left),
        ("Panel C", Right),
        ("Panel D", Right),
        ("Panel E", Bottom),
    ],
}


# ── Snapshot helpers ───────────────────────────────────────────────────────────

def qt_snap(win: QMainWindow, docks: list) -> dict:
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


def _corner_snap(win) -> dict:
    return {
        "top_left": win.corner(Qt.Corner.TopLeftCorner),
        "top_right": win.corner(Qt.Corner.TopRightCorner),
        "bottom_left": win.corner(Qt.Corner.BottomLeftCorner),
        "bottom_right": win.corner(Qt.Corner.BottomRightCorner),
    }


def l_snap(win: LMainWindow, docks: list, toolbars: list) -> dict:
    def tabbed_peers(d: LDockWidget) -> list:
        if d.isFloating():
            return []
        area = win.dockWidgetArea(d)
        if area == NoDock:
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
        "toolbars": _toolbar_snap(win, toolbars),
        "corners": _corner_snap(win),
    }


def compare_snaps(qt: dict, l: dict) -> list:
    """Return list of (dock_name, field, qt_value, l_value) for all mismatches."""
    checks = ["area", "floating", "visible", "tabs"]
    mismatches = []
    for name in sorted(set(qt["docks"]) | set(l["docks"])):
        if name not in qt["docks"] or name not in l["docks"]:
            mismatches.append((name, "existence", name in qt["docks"], name in l["docks"]))
            continue
        for field in checks:
            qv = qt["docks"][name].get(field)
            lv = l["docks"][name].get(field)
            if qv != lv:
                mismatches.append((name, field, qv, lv))
    if qt["toolbars"]["order"] != l["toolbars"]["order"]:
        mismatches.append(("__shell__", "toolbar_order", qt["toolbars"]["order"], l["toolbars"]["order"]))
    for name in sorted(set(qt["toolbars"]["items"]) | set(l["toolbars"]["items"])):
        if name not in qt["toolbars"]["items"] or name not in l["toolbars"]["items"]:
            mismatches.append(
                (name, "toolbar_existence", name in qt["toolbars"]["items"], name in l["toolbars"]["items"])
            )
            continue
        for field in ("area", "break"):
            qv = qt["toolbars"]["items"][name][field]
            lv = l["toolbars"]["items"][name][field]
            if qv != lv:
                mismatches.append((name, f"toolbar_{field}", qv, lv))
    if qt["corners"] != l["corners"]:
        mismatches.append(("__shell__", "corners", qt["corners"], l["corners"]))
    return mismatches


# ── Native-Qt panel ────────────────────────────────────────────────────────────

class NativePanel(QFrame):
    """Left half: embedded QMainWindow with native QDockWidgets."""

    def __init__(self) -> None:
        super().__init__()
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._layout_name = ""
        self.qt_win = QMainWindow()
        self.docks: list[QDockWidget] = []
        self.toolbars: list[QToolBar] = []
        self._saved_state = None

        root = QVBoxLayout(self)
        root.setContentsMargins(2, 2, 2, 2)
        root.setSpacing(2)

        header = QLabel("Native Qt")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet("font-weight: bold; padding: 4px; background: #e8f4e8;")
        root.addWidget(header)
        root.addWidget(self.qt_win, 1)

        central = QTextEdit()
        central.setPlainText("Native Qt central area")
        self.qt_win.setCentralWidget(central)
        self._build_shell()

    def _build_shell(self) -> None:
        specs = [
            ("Top A", TopTB),
            ("Top B", TopTB),
            ("Left", LeftTB),
            ("Right", RightTB),
            ("Bottom", BottomTB),
        ]
        for title, area in specs:
            toolbar = QToolBar(title)
            toolbar.setObjectName(title)
            toolbar.addAction(title)
            self.qt_win.addToolBar(area, toolbar)
            self.toolbars.append(toolbar)
        self.qt_win.insertToolBarBreak(self.toolbars[1])

    def apply_layout(self, name: str) -> None:
        self._layout_name = name
        self.qt_win.setDockOptions(QMainWindow.DockOption.AnimatedDocks | QMainWindow.DockOption.AllowTabbedDocks)
        for d in self.docks:
            self.qt_win.removeDockWidget(d)
            d.setParent(None)
            d.deleteLater()
        self.docks = []
        for title, area in LAYOUTS[name]:
            d = QDockWidget(title)
            d.setWidget(QLabel(title))
            self.qt_win.addDockWidget(area, d)
            self.docks.append(d)
        if name == "Grouped" and len(self.docks) >= 3:
            self.qt_win.tabifyDockWidget(self.docks[0], self.docks[1])
            self.qt_win.tabifyDockWidget(self.docks[0], self.docks[2])
        elif name == "Nested" and len(self.docks) >= 3:
            self.qt_win.tabifyDockWidget(self.docks[0], self.docks[1])
            self.qt_win.splitDockWidget(self.docks[0], self.docks[2], Qt.Orientation.Vertical)

    def float_all(self) -> None:
        for d in self.docks:
            d.setFloating(True)

    def dock_all(self) -> None:
        for d, (_, area) in zip(self.docks, LAYOUTS[self._layout_name]):
            self.qt_win.addDockWidget(area, d)

    def float_one(self, idx: int = 0) -> None:
        if self.docks and idx < len(self.docks):
            self.docks[idx].setFloating(True)

    def dock_one(self, idx: int = 0) -> None:
        if self.docks and self._layout_name and idx < len(self.docks):
            area = LAYOUTS[self._layout_name][idx][1]
            self.qt_win.addDockWidget(area, self.docks[idx])

    def snap(self) -> dict:
        snap = qt_snap(self.qt_win, self.docks)
        snap["toolbars"] = _toolbar_snap(self.qt_win, self.toolbars)
        snap["corners"] = _corner_snap(self.qt_win)
        return snap

    def save_restore(self) -> None:
        state = self.qt_win.saveState()
        for dock in self.docks:
            self.qt_win.addDockWidget(Right, dock)
        for toolbar in self.toolbars:
            self.qt_win.addToolBar(TopTB, toolbar)
        self.qt_win.restoreState(state)

    def flip_corners(self) -> None:
        self.qt_win.setCorner(Qt.Corner.TopLeftCorner, Left)
        self.qt_win.setCorner(Qt.Corner.BottomRightCorner, Right)


# ── LDocking panel ─────────────────────────────────────────────────────────────

class LDockingPanel(QFrame):
    """Right half: LMainWindow with LDockWidgets."""

    def __init__(self) -> None:
        super().__init__()
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._layout_name = ""
        self.l_win = LMainWindow()
        self.docks: list[LDockWidget] = []
        self.toolbars: list[QToolBar] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(2, 2, 2, 2)
        root.setSpacing(2)

        header = QLabel("LDocking")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet("font-weight: bold; padding: 4px; background: #e8e8f4;")
        root.addWidget(header)
        root.addWidget(self.l_win, 1)

        central = QTextEdit()
        central.setPlainText("LDocking central area")
        self.l_win.setCentralWidget(central)
        self._build_shell()

    def _build_shell(self) -> None:
        specs = [
            ("Top A", TopTB),
            ("Top B", TopTB),
            ("Left", LeftTB),
            ("Right", RightTB),
            ("Bottom", BottomTB),
        ]
        for title, area in specs:
            toolbar = QToolBar(title)
            toolbar.setObjectName(title)
            toolbar.addAction(title)
            self.l_win.addToolBar(area, toolbar)
            self.toolbars.append(toolbar)
        self.l_win.insertToolBarBreak(self.toolbars[1])

    def apply_layout(self, name: str) -> None:
        self._layout_name = name
        self.l_win.setDockOptions(LMainWindow.AnimatedDocks | LMainWindow.AllowTabbedDocks)
        for d in self.docks:
            if d.isFloating():
                d.hide()
            self.l_win.removeDockWidget(d)
            d.setParent(None)
            d.deleteLater()
        self.docks = []
        for title, area in LAYOUTS[name]:
            d = LDockWidget(title)
            d.setWidget(QLabel(title))
            self.l_win.addDockWidget(area, d)
            self.docks.append(d)
        if name == "Grouped" and len(self.docks) >= 3:
            self.l_win.setDockOptions(
                self.l_win.dockOptions() | LMainWindow.ForceTabbedDocks | LMainWindow.GroupedDragging
            )
        elif name == "Nested" and len(self.docks) >= 3:
            self.l_win.setDockOptions(self.l_win.dockOptions() | LMainWindow.AllowNestedDocks)
            self.l_win._drop_docks(
                Left,
                [self.docks[2]],
                mode="side",
                target_id=self.docks[0].objectName() or self.docks[0].windowTitle(),
                side=Bottom,
            )

    def float_all(self) -> None:
        for d in self.docks:
            d.setFloating(True)

    def dock_all(self) -> None:
        for d, (_, area) in zip(self.docks, LAYOUTS[self._layout_name]):
            self.l_win.addDockWidget(area, d)

    def float_one(self, idx: int = 0) -> None:
        if self.docks and idx < len(self.docks):
            self.docks[idx].setFloating(True)

    def dock_one(self, idx: int = 0) -> None:
        if self.docks and self._layout_name and idx < len(self.docks):
            area = LAYOUTS[self._layout_name][idx][1]
            self.l_win.addDockWidget(area, self.docks[idx])

    def snap(self) -> dict:
        return l_snap(self.l_win, self.docks, self.toolbars)

    def save_restore(self) -> None:
        state = self.l_win.saveState()
        for dock in self.docks:
            self.l_win.addDockWidget(Right, dock)
        for toolbar in self.toolbars:
            self.l_win.addToolBar(TopTB, toolbar)
        self.l_win.restoreState(state)

    def flip_corners(self) -> None:
        self.l_win.setCorner(Qt.Corner.TopLeftCorner, Left)
        self.l_win.setCorner(Qt.Corner.BottomRightCorner, Right)


# ── Main container window ──────────────────────────────────────────────────────

class ParityDemo(QWidget):
    """Top-level window containing both panels and a synchronized toolbar."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("LDocking Parity Demo — Native Qt  |  LDocking")
        self._current_layout = "2L"
        self._native   = NativePanel()
        self._ldocking = LDockingPanel()

        self._build_ui()
        self._apply_layout("2L")

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        # ── Toolbar ────────────────────────────────────────────────────────────
        tb = QWidget()
        tb_layout = QHBoxLayout(tb)
        tb_layout.setContentsMargins(0, 0, 0, 0)
        tb_layout.setSpacing(6)

        def btn(label: str, slot) -> QPushButton:
            b = QPushButton(label)
            b.clicked.connect(slot)
            tb_layout.addWidget(b)
            return b

        btn("Float All",    self._do_float_all)
        btn("Dock All",     self._do_dock_all)
        btn("Float One",    self._do_float_one)
        btn("Dock One",     self._do_dock_one)
        btn("Save/Restore", self._do_save_restore)
        btn("Flip Corners", self._do_flip_corners)
        btn("Reset Layout", self._do_reset)

        tb_layout.addStretch()
        tb_layout.addWidget(QLabel("Layout:"))

        self._layout_combo = QComboBox()
        self._layout_combo.addItems(list(LAYOUTS))
        self._layout_combo.currentTextChanged.connect(self._apply_layout)
        tb_layout.addWidget(self._layout_combo)

        root.addWidget(tb)

        # ── Side-by-side splitter ──────────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._native)
        splitter.addWidget(self._ldocking)
        splitter.setSizes([600, 600])
        root.addWidget(splitter, 1)

        # ── Status bar ─────────────────────────────────────────────────────────
        self._status = QStatusBar()
        root.addWidget(self._status)

    # ── Layout management ──────────────────────────────────────────────────────

    def _apply_layout(self, name: str) -> None:
        if name not in LAYOUTS:
            return
        self._current_layout = name
        self._native.apply_layout(name)
        self._ldocking.apply_layout(name)
        self._compare_and_update("reset")

    # ── Toolbar actions ────────────────────────────────────────────────────────

    def _do_float_all(self) -> None:
        self._native.float_all()
        self._ldocking.float_all()
        self._compare_and_update("float_all")

    def _do_dock_all(self) -> None:
        self._native.dock_all()
        self._ldocking.dock_all()
        self._compare_and_update("dock_all")

    def _do_float_one(self) -> None:
        self._native.float_one()
        self._ldocking.float_one()
        self._compare_and_update("float_one(0)")

    def _do_dock_one(self) -> None:
        self._native.dock_one()
        self._ldocking.dock_one()
        self._compare_and_update("dock_one(0)")

    def _do_reset(self) -> None:
        self._apply_layout(self._current_layout)

    def _do_save_restore(self) -> None:
        self._native.save_restore()
        self._ldocking.save_restore()
        self._compare_and_update("save_restore")

    def _do_flip_corners(self) -> None:
        self._native.flip_corners()
        self._ldocking.flip_corners()
        self._compare_and_update("flip_corners")

    # ── State comparison ───────────────────────────────────────────────────────

    def _compare_and_update(self, action: str) -> None:
        mismatches = compare_snaps(self._native.snap(), self._ldocking.snap())
        if not mismatches:
            self._status.showMessage(f"[{action}]  ✓ In sync")
            self._status.setStyleSheet("")
        else:
            parts = [
                f"{name}.{field}: qt={qv!r} l={lv!r}"
                for name, field, qv, lv in mismatches
            ]
            msg = f"[{action}]  ✗ {len(mismatches)} mismatch(es): " + ";  ".join(parts)
            self._status.showMessage(msg)
            self._status.setStyleSheet("color: red;")


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    app = QApplication(sys.argv)
    win = ParityDemo()
    win.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
