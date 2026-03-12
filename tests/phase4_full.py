"""Phase 4 — Full LMainWindow with menu, toolbar, statusbar."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMenuBar,
    QStatusBar,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ldocking import (
    AllDockWidgetFeatures,
    BottomDockWidgetArea,
    DockWidgetClosable,
    DockWidgetFloatable,
    DockWidgetMovable,
    LeftDockWidgetArea,
    LDockWidget,
    LMainWindow,
    NoDockWidgetFeatures,
    RightDockWidgetArea,
    TopDockWidgetArea,
)


class Phase4Window(LMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Phase 4 — Full LMainWindow")
        self.resize(1200, 800)

        # Menu bar
        menubar = self.menuBar()
        view_menu = menubar.addMenu("&View")
        file_menu = menubar.addMenu("&File")
        exit_action = QAction("E&xit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Toolbar
        toolbar = QToolBar("Main Toolbar")
        toolbar.addAction(QAction("New", self))
        toolbar.addAction(QAction("Open", self))
        toolbar.addSeparator()
        float_all_action = QAction("Float All", self)
        float_all_action.triggered.connect(self.float_all)
        toolbar.addAction(float_all_action)
        dock_all_action = QAction("Dock All", self)
        dock_all_action.triggered.connect(self.dock_all)
        toolbar.addAction(dock_all_action)
        self.addToolBar(toolbar)

        # Central widget
        editor = QTextEdit()
        editor.setPlainText("Central editor area\n\nThis is the main content.")
        self.setCentralWidget(editor)

        # Dock widgets
        self.docks: list[LDockWidget] = []
        configs = [
            ("File Browser", LeftDockWidgetArea, "Files go here"),
            ("Properties", RightDockWidgetArea, "Properties panel"),
            ("Console", BottomDockWidgetArea, "Console output"),
            ("Outline", LeftDockWidgetArea, "Document outline"),
        ]

        for title, area, content in configs:
            dock = LDockWidget(title)
            dock.setWidget(QLabel(content))
            dock._main_window = self
            self.addDockWidget(area, dock)
            self.docks.append(dock)
            view_menu.addAction(dock.toggleViewAction())

        # Status bar
        self.statusBar().showMessage("Phase 4 Ready")

    def float_all(self):
        for dock in self.docks:
            dock.setFloating(True)
        self.statusBar().showMessage("All docks floating")

    def dock_all(self):
        configs = [
            LeftDockWidgetArea,
            RightDockWidgetArea,
            BottomDockWidgetArea,
            LeftDockWidgetArea,
        ]
        for dock, area in zip(self.docks, configs):
            self.addDockWidget(area, dock)
        self.statusBar().showMessage("All docks docked")


def main():
    app = QApplication(sys.argv)
    win = Phase4Window()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
