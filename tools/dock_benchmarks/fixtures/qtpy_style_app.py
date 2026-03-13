"""Local qtpy-style fixture app for monkeypatch comparison tests."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget

from .qt_abstraction import QDockWidget, QMainWindow

QMAINWINDOW_CLASS = QMainWindow
QDOCKWIDGET_CLASS = QDockWidget


def build_window():
    window = QMainWindow()
    window.setObjectName("qtpy_style_fixture")
    window.setWindowTitle("qtpy-style fixture")
    if hasattr(window, "setCentralWidget"):
        window.setCentralWidget(QWidget())
    for title, area in (
        ("Layers", Qt.DockWidgetArea.LeftDockWidgetArea),
        ("Console", Qt.DockWidgetArea.RightDockWidgetArea),
    ):
        dock = QDockWidget(title)
        dock.setObjectName(title)
        dock.setWidget(QLabel(title))
        window.addDockWidget(area, dock)
    return window
