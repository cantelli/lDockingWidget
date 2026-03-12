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

# ── Layout presets ─────────────────────────────────────────────────────────────
LAYOUTS: dict[str, list[tuple[str, Qt.DockWidgetArea]]] = {
    "2L": [
        ("Panel A", Left),
        ("Panel B", Left),
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
        d.windowTitle(): {
            "area":     win.dockWidgetArea(d),
            "floating": d.isFloating(),
            "visible":  d.isVisible(),
            "tabs":     sorted(t.windowTitle() for t in win.tabifiedDockWidgets(d)),
        }
        for d in docks
    }


def l_snap(win: LMainWindow, docks: list) -> dict:
    def tabbed_peers(d: LDockWidget) -> list:
        if d.isFloating():
            return []
        area = win.dockWidgetArea(d)
        if area == NoDock:
            return []
        return sorted(
            t.windowTitle()
            for t in win._dock_areas[area].all_docks()
            if t is not d
        )

    return {
        d.windowTitle(): {
            "area":     NoDock if d.isFloating() else win.dockWidgetArea(d),
            "floating": d.isFloating(),
            "visible":  d.isVisible(),
            "tabs":     tabbed_peers(d),
        }
        for d in docks
    }


def compare_snaps(qt: dict, l: dict) -> list:
    """Return list of (dock_name, field, qt_value, l_value) for all mismatches."""
    checks = ["area", "floating", "visible", "tabs"]
    mismatches = []
    for name in sorted(set(qt) | set(l)):
        if name not in qt or name not in l:
            mismatches.append((name, "existence", name in qt, name in l))
            continue
        for field in checks:
            qv = qt[name].get(field)
            lv = l[name].get(field)
            if qv != lv:
                mismatches.append((name, field, qv, lv))
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

    def apply_layout(self, name: str) -> None:
        self._layout_name = name
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
        return qt_snap(self.qt_win, self.docks)


# ── LDocking panel ─────────────────────────────────────────────────────────────

class LDockingPanel(QFrame):
    """Right half: LMainWindow with LDockWidgets."""

    def __init__(self) -> None:
        super().__init__()
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._layout_name = ""
        self.l_win = LMainWindow()
        self.docks: list[LDockWidget] = []

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

    def apply_layout(self, name: str) -> None:
        self._layout_name = name
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
        return l_snap(self.l_win, self.docks)


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
