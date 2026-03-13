"""Local fixture mirroring labelme's four right-side dock layout."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QDockWidget, QMainWindow, QMenuBar, QWidget

QMAINWINDOW_CLASS = QMainWindow
QDOCKWIDGET_CLASS = QDockWidget

DOCK_TITLES = ("Flags", "Annotation List", "Label List", "File List")


def build_window():
    window = QMainWindow()
    window.setObjectName("labelme_shape_fixture")
    window.setWindowTitle("labelme-shape fixture")
    window.setMenuBar(QMenuBar())
    view_menu = window.menuBar().addMenu("&View")
    window.setCentralWidget(QWidget())

    for title in DOCK_TITLES:
        dock = QDockWidget(title)
        dock.setObjectName(title)
        dock.setWidget(QLabel(title))
        window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        view_menu.addAction(dock.toggleViewAction())
    return window
