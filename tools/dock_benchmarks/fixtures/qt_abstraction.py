"""Minimal Qt indirection layer for monkeypatch import-boundary tests."""

from PySide6.QtWidgets import QDockWidget, QMainWindow

QMAINWINDOW_CLASS = QMainWindow
QDOCKWIDGET_CLASS = QDockWidget
