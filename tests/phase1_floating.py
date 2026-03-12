"""Phase 1 — LDockWidget floating-only test.

Tests:
  - Title bar displays title
  - Float button shows/hides correctly
  - Close button works
  - Drag threshold signal fires
  - setFeatures / features round-trip
  - toggleViewAction
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
    AllDockWidgetFeatures,
    DockWidgetClosable,
    DockWidgetFloatable,
    DockWidgetMovable,
    LDockWidget,
    NoDockWidgetFeatures,
)


class Phase1Window(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Phase 1 — LDockWidget Floating")
        self.resize(400, 300)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("LDockWidget floating-only demo"))

        # Create a floating dock widget
        self.dock = LDockWidget("Test Dock")
        self.dock.setWidget(QLabel("Hello from LDockWidget!"))
        self.dock.setFloating(True)
        self.dock.move(200, 200)
        self.dock.resize(300, 200)

        # Buttons for testing
        btn_toggle = QPushButton("Toggle Features (all / none)")
        btn_toggle.clicked.connect(self.toggle_features)
        layout.addWidget(btn_toggle)

        btn_show = QPushButton("Show Dock")
        btn_show.clicked.connect(self.dock.show)
        layout.addWidget(btn_show)

        btn_view_action = QPushButton("Print toggleViewAction state")
        btn_view_action.clicked.connect(self.print_view_action)
        layout.addWidget(btn_view_action)

        self._features_state = True

        # Connect signals
        self.dock.featuresChanged.connect(
            lambda f: print(f"featuresChanged: {f}")
        )
        self.dock.visibilityChanged.connect(
            lambda v: print(f"visibilityChanged: {v}")
        )
        self.dock.topLevelChanged.connect(
            lambda tl: print(f"topLevelChanged: {tl}")
        )

        self.dock.show()

    def toggle_features(self):
        if self._features_state:
            self.dock.setFeatures(NoDockWidgetFeatures)
        else:
            self.dock.setFeatures(AllDockWidgetFeatures)
        self._features_state = not self._features_state

    def print_view_action(self):
        action = self.dock.toggleViewAction()
        print(f"toggleViewAction checked: {action.isChecked()}, text: {action.text()}")


def main():
    app = QApplication(sys.argv)
    win = Phase1Window()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
