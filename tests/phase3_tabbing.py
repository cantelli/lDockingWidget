"""Phase 3 — Drag/drop, tabs, and tab tear-off test.

Tests:
  - Two docks in same area → tabbed
  - Tab tear-off → separate floating dock
  - Drag from title bar → drop indicator → re-dock
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
    LeftDockWidgetArea,
    LDockWidget,
    LMainWindow,
    RightDockWidgetArea,
    BottomDockWidgetArea,
)


class Phase3Window(LMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Phase 3 — Drag/Drop and Tabs")
        self.resize(1000, 700)

        central = QWidget()
        clayout = QVBoxLayout(central)
        clayout.addWidget(QLabel("Phase 3: Drag title bars to dock areas\n"
                                  "Drag tabs to tear off"))

        self.tab_btn = QPushButton("Add 2nd dock to Left (creates tabs)")
        self.tab_btn.clicked.connect(self.add_second_left_dock)
        clayout.addWidget(self.tab_btn)

        self.remove_btn = QPushButton("Remove tabbed dock (reduces to 1)")
        self.remove_btn.clicked.connect(self.remove_second_left_dock)
        clayout.addWidget(self.remove_btn)

        self.setCentralWidget(central)

        # Initial docks
        self.dock1 = LDockWidget("Left Dock 1")
        self.dock1.setWidget(QLabel("Left content 1"))
        self.dock1._main_window = self

        self.dock2 = LDockWidget("Left Dock 2")
        self.dock2.setWidget(QLabel("Left content 2 (added by button)"))
        self.dock2._main_window = self

        self.dock3 = LDockWidget("Right Dock")
        self.dock3.setWidget(QLabel("Right content"))
        self.dock3._main_window = self

        self.addDockWidget(LeftDockWidgetArea, self.dock1)
        self.addDockWidget(RightDockWidgetArea, self.dock3)

        self._second_added = False
        self.statusBar().showMessage("Drag title bars to drop zones")

    def add_second_left_dock(self):
        if not self._second_added:
            self.addDockWidget(LeftDockWidgetArea, self.dock2)
            self._second_added = True
            self.statusBar().showMessage("Left area now has tabs")
            print("Tabbing: Added second dock to Left area")

    def remove_second_left_dock(self):
        if self._second_added:
            self.removeDockWidget(self.dock2)
            self._second_added = False
            self.statusBar().showMessage("Left area back to single dock")
            print("Tabbing: Removed second dock from Left area")


def main():
    app = QApplication(sys.argv)
    win = Phase3Window()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
