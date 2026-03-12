"""Tabified dock widgets — side-by-side visual comparison.

Native QMainWindow on the left, LMainWindow on the right.
Every button action runs on both sides and prints tabifiedDockWidgets()
output so you can confirm parity at a glance.

Run:
    python tests/tabified_visual.py
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ldocking import (
    BottomDockWidgetArea,
    LeftDockWidgetArea,
    LDockWidget,
    LMainWindow,
    RightDockWidgetArea,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def make_qt_dock(title: str) -> QDockWidget:
    d = QDockWidget(title)
    d.setWidget(QLabel(f"  {title}  "))
    return d


def make_l_dock(title: str) -> LDockWidget:
    d = LDockWidget(title)
    d.setWidget(QLabel(f"  {title}  "))
    return d


def qt_tabified(win: QMainWindow, docks: list[QDockWidget]) -> dict[str, list[str]]:
    return {d.windowTitle(): [t.windowTitle() for t in win.tabifiedDockWidgets(d)]
            for d in docks}


def l_tabified(win: LMainWindow, docks: list[LDockWidget]) -> dict[str, list[str]]:
    return {d.windowTitle(): [t.windowTitle() for t in win.tabifiedDockWidgets(d)]
            for d in docks}


def fmt(result: dict) -> str:
    lines = []
    for name, peers in sorted(result.items()):
        peer_str = ", ".join(peers) if peers else "—"
        lines.append(f"  {name}: [{peer_str}]")
    return "\n".join(lines)


# ── native QMainWindow window ─────────────────────────────────────────────────

class QtSide(QMainWindow):
    def __init__(self, log):
        super().__init__()
        self._log = log
        self.setWindowTitle("Native QMainWindow")
        self.resize(500, 500)

        self.dA = make_qt_dock("Alpha")
        self.dB = make_qt_dock("Beta")
        self.dC = make_qt_dock("Gamma")
        self.dD = make_qt_dock("Delta")

        self.addDockWidget(LeftDockWidgetArea, self.dA)
        self.addDockWidget(LeftDockWidgetArea, self.dB)   # tabs with A
        self.addDockWidget(RightDockWidgetArea, self.dC)
        self.addDockWidget(BottomDockWidgetArea, self.dD)

        self.setCentralWidget(QLabel("Native central"))
        self.statusBar().showMessage("ready")

    def all_docks(self):
        return [self.dA, self.dB, self.dC, self.dD]

    def snapshot(self, label: str):
        result = qt_tabified(self, self.all_docks())
        self._log(f"[Qt] {label}\n{fmt(result)}\n")
        self.statusBar().showMessage(label)

    def tabify_gamma(self):
        self.tabifyDockWidget(self.dA, self.dC)
        self.snapshot("tabifyDockWidget(Alpha, Gamma)")

    def float_beta(self):
        self.dB.setFloating(True)
        self.snapshot("Beta → floating")

    def dock_beta_right(self):
        self.dB.setFloating(False)
        self.addDockWidget(RightDockWidgetArea, self.dB)
        self.snapshot("Beta → Right area")

    def reset(self):
        for d in self.all_docks():
            d.setFloating(False)
        self.addDockWidget(LeftDockWidgetArea, self.dA)
        self.addDockWidget(LeftDockWidgetArea, self.dB)
        self.tabifyDockWidget(self.dA, self.dB)
        self.addDockWidget(RightDockWidgetArea, self.dC)
        self.addDockWidget(BottomDockWidgetArea, self.dD)
        self.snapshot("reset")


# ── LMainWindow window ────────────────────────────────────────────────────────

class LSide(LMainWindow):
    def __init__(self, log):
        super().__init__()
        self._log = log
        self.setWindowTitle("LMainWindow")
        self.resize(500, 500)

        self.dA = make_l_dock("Alpha")
        self.dB = make_l_dock("Beta")
        self.dC = make_l_dock("Gamma")
        self.dD = make_l_dock("Delta")

        self.addDockWidget(LeftDockWidgetArea, self.dA)
        self.addDockWidget(LeftDockWidgetArea, self.dB)
        self.addDockWidget(RightDockWidgetArea, self.dC)
        self.addDockWidget(BottomDockWidgetArea, self.dD)

        self.setCentralWidget(QLabel("L central"))
        self.statusBar().showMessage("ready")

    def all_docks(self):
        return [self.dA, self.dB, self.dC, self.dD]

    def snapshot(self, label: str):
        result = l_tabified(self, self.all_docks())
        self._log(f"[L]  {label}\n{fmt(result)}\n")
        self.statusBar().showMessage(label)

    def tabify_gamma(self):
        self.tabifyDockWidget(self.dA, self.dC)
        self.snapshot("tabifyDockWidget(Alpha, Gamma)")

    def float_beta(self):
        self.dB.setFloating(True)
        self.snapshot("Beta → floating")

    def dock_beta_right(self):
        self.addDockWidget(RightDockWidgetArea, self.dB)
        self.snapshot("Beta → Right area")

    def reset(self):
        for d in self.all_docks():
            d.setFloating(False)
        self.addDockWidget(LeftDockWidgetArea, self.dA)
        self.addDockWidget(LeftDockWidgetArea, self.dB)
        self.addDockWidget(RightDockWidgetArea, self.dC)
        self.addDockWidget(BottomDockWidgetArea, self.dD)
        self.snapshot("reset")


# ── Control panel ─────────────────────────────────────────────────────────────

class ControlPanel(QWidget):
    def __init__(self, qt_side: QtSide, l_side: LSide):
        super().__init__()
        self._qt = qt_side
        self._l = l_side
        self.setWindowTitle("Controls + Log")
        self.resize(500, 600)

        self._log_box = QTextEdit()
        self._log_box.setReadOnly(True)
        self._log_box.setFontFamily("Courier New")

        layout = QVBoxLayout(self)

        def btn(label: str, slot):
            b = QPushButton(label)
            b.clicked.connect(slot)
            layout.addWidget(b)
            return b

        btn("Initial snapshot", self.initial_snapshot)
        btn("tabifyDockWidget(Alpha, Gamma)  →  3-way tab group", self.tabify_gamma)
        btn("Beta → floating", self.float_beta)
        btn("Beta → Right area", self.dock_beta_right)
        btn("Reset", self.reset)

        layout.addWidget(QLabel("─" * 60))
        layout.addWidget(QLabel("tabifiedDockWidgets() output (Qt vs L):"))
        layout.addWidget(self._log_box, 1)

        self.initial_snapshot()

    def _log(self, text: str):
        self._log_box.append(text)

    def initial_snapshot(self):
        self._log("=== initial state ===")
        self._qt.snapshot("initial")
        self._l.snapshot("initial")

    def tabify_gamma(self):
        self._log("=== tabify Gamma into Left group ===")
        self._qt.tabify_gamma()
        self._l.tabify_gamma()

    def float_beta(self):
        self._log("=== float Beta ===")
        self._qt.float_beta()
        self._l.float_beta()

    def dock_beta_right(self):
        self._log("=== dock Beta to Right ===")
        self._qt.dock_beta_right()
        self._l.dock_beta_right()

    def reset(self):
        self._log("=== reset ===")
        self._qt.reset()
        self._l.reset()


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)

    log_lines = []

    qt_side = QtSide(log_lines.append)
    l_side = LSide(log_lines.append)
    panel = ControlPanel(qt_side, l_side)

    # Arrange windows: Qt left, L middle, controls right
    qt_side.move(50, 100)
    qt_side.show()

    l_side.move(580, 100)
    l_side.show()

    panel.move(1110, 100)
    panel.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
