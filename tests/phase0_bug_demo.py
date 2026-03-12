"""Phase 0 — Demonstrates the QDockAreaLayout crash with QMainWindow.

Run this to see the bug:
  python tests/phase0_bug_demo.py

Steps to reproduce:
  1. Launch the window (3 dock widgets attached)
  2. Click "Float All" to undock all three docks
  3. Click "Dock All" to re-dock them
  4. Click "Float All" again — observe crash / geometry corruption
"""
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class BugDemoWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Phase 0 — QDockWidget Bug Demo")
        self.resize(800, 600)

        central = QWidget()
        layout = QVBoxLayout(central)

        self.float_btn = QPushButton("Float All")
        self.dock_btn = QPushButton("Dock All")
        self.float_btn.clicked.connect(self.float_all)
        self.dock_btn.clicked.connect(self.dock_all)

        layout.addWidget(QLabel("Click 'Float All', then 'Dock All', then 'Float All' again"))
        layout.addWidget(self.float_btn)
        layout.addWidget(self.dock_btn)
        self.setCentralWidget(central)

        # Create 3 dock widgets
        self.docks = []
        for i, area in enumerate([
            Qt.DockWidgetArea.LeftDockWidgetArea,
            Qt.DockWidgetArea.RightDockWidgetArea,
            Qt.DockWidgetArea.BottomDockWidgetArea,
        ]):
            dock = QDockWidget(f"Dock {i + 1}", self)
            dock.setWidget(QLabel(f"Content {i + 1}"))
            self.addDockWidget(area, dock)
            self.docks.append(dock)

    def float_all(self):
        for dock in self.docks:
            dock.setFloating(True)
        print("All docks floated")

    def dock_all(self):
        areas = [
            Qt.DockWidgetArea.LeftDockWidgetArea,
            Qt.DockWidgetArea.RightDockWidgetArea,
            Qt.DockWidgetArea.BottomDockWidgetArea,
        ]
        for dock, area in zip(self.docks, areas):
            self.addDockWidget(area, dock)
        print("All docks re-docked")


def main():
    app = QApplication(sys.argv)
    win = BugDemoWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
