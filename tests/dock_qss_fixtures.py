"""Qt-authored stylesheet fixtures used for dock parity tests."""
from __future__ import annotations


DOCK_CHROME_QSS = """
QMainWindow {
    background: #f3f4f6;
}
QMainWindow::separator {
    background: #ef4444;
    width: 6px;
    height: 6px;
}
QDockWidget {
    background: #ffffff;
    border: 2px solid #0f172a;
    color: #0f172a;
}
QDockWidget::title {
    background: #f59e0b;
    color: #111827;
    padding: 6px 10px;
    border-bottom: 2px solid #b45309;
    font-weight: 700;
}
QDockWidget > QWidget {
    background: #dbeafe;
    color: #1e3a8a;
}
QDockWidget::close-button {
    background: #dc2626;
    border: 1px solid #7f1d1d;
}
QDockWidget::float-button {
    background: #2563eb;
    border: 1px solid #1e3a8a;
}
"""


TABBED_DOCK_QSS = DOCK_CHROME_QSS + """
QDockWidget QTabBar {
    background: #e5e7eb;
}
QDockWidget QTabBar::tab {
    background: #cbd5e1;
    color: #0f172a;
    padding: 5px 10px;
    border: 1px solid #64748b;
}
QDockWidget QTabBar::tab:selected {
    background: #14b8a6;
    color: #042f2e;
}
"""
