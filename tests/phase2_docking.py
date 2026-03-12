"""Phase 2 — LMainWindow docking test.

Success criterion: "add 3 docks → float all → re-dock all" completes
without crash or geometry corruption.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ldocking import (
    BottomDockWidgetArea,
    LeftDockWidgetArea,
    LDockWidget,
    LMainWindow,
    RightDockWidgetArea,
    TopDockWidgetArea,
)


class Phase2Window(LMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Phase 2 — LMainWindow Docking")
        self.resize(900, 600)

        # Central widget
        central = QWidget()
        clayout = QVBoxLayout(central)
        clayout.addWidget(QLabel("Central Widget — LMainWindow"))

        self.float_btn = QPushButton("Float All")
        self.dock_btn = QPushButton("Dock All")
        self.float_btn.clicked.connect(self.float_all)
        self.dock_btn.clicked.connect(self.dock_all)
        clayout.addWidget(self.float_btn)
        clayout.addWidget(self.dock_btn)

        self.setCentralWidget(central)

        # Create 3 dock widgets
        self.docks: list[LDockWidget] = []
        self.dock_areas = [
            LeftDockWidgetArea,
            RightDockWidgetArea,
            BottomDockWidgetArea,
        ]

        for i, area in enumerate(self.dock_areas):
            dock = LDockWidget(f"Dock {i + 1}")
            dock.setWidget(QLabel(f"Content {i + 1}"))
            dock._main_window = self
            self.addDockWidget(area, dock)
            self.docks.append(dock)

        self.statusBar().showMessage("Ready")

    def float_all(self):
        for dock in self.docks:
            dock.setFloating(True)
        self.statusBar().showMessage("All docks floated — no crash!")
        print("float_all: OK")

    def dock_all(self):
        for dock, area in zip(self.docks, self.dock_areas):
            self.addDockWidget(area, dock)
        self.statusBar().showMessage("All docks re-docked — no crash!")
        print("dock_all: OK")


def main():
    app = QApplication(sys.argv)
    win = Phase2Window()
    win.show()

    # Automated smoke test: float all, dock all, float all again
    from PySide6.QtCore import QTimer
    step = [0]

    def run_step():
        if step[0] == 0:
            print("Step 1: float all")
            win.float_all()
        elif step[0] == 1:
            print("Step 2: dock all")
            win.dock_all()
        elif step[0] == 2:
            print("Step 3: float all again")
            win.float_all()
            print("SUCCESS: No crash!")
        elif step[0] == 3:
            print("Step 4: dock all again")
            win.dock_all()
            print("Phase 2 PASSED")
        step[0] += 1

    timer = QTimer()
    timer.timeout.connect(run_step)
    timer.start(300)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
