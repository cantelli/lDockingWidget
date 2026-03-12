"""Visual side-by-side comparison between Qt docking and ldocking.

Run:
    python tests/visual_compare_demo.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDockWidget,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ldocking import LDockWidget, LMainWindow


Left = Qt.DockWidgetArea.LeftDockWidgetArea
Right = Qt.DockWidgetArea.RightDockWidgetArea
Top = Qt.DockWidgetArea.TopDockWidgetArea
Bottom = Qt.DockWidgetArea.BottomDockWidgetArea


LAYOUTS: dict[str, list[tuple[str, Qt.DockWidgetArea]]] = {
    "Single Left": [("Inspector", Left)],
    "Tabbed Left": [("Inspector", Left), ("Assets", Left)],
    "Balanced": [
        ("Inspector", Left),
        ("Assets", Left),
        ("Layers", Right),
        ("Console", Bottom),
    ],
    "Full Frame": [
        ("Inspector", Left),
        ("Assets", Left),
        ("Layers", Right),
        ("History", Right),
        ("Console", Bottom),
    ],
}


def make_panel(title: str) -> QWidget:
    panel = QFrame()
    panel.setObjectName("comparisonPanel")
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(10, 10, 10, 10)
    layout.setSpacing(8)

    heading = QLabel(title)
    heading.setObjectName("panelHeading")
    heading.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    layout.addWidget(heading)

    grid = QGridLayout()
    grid.setHorizontalSpacing(8)
    grid.setVerticalSpacing(6)
    rows = [
        ("Mode", "Docked"),
        ("Width", "320 px"),
        ("Visible", "Yes"),
        ("Focus", "Primary"),
    ]
    for row, (label, value) in enumerate(rows):
        grid.addWidget(QLabel(label), row, 0)
        value_label = QLabel(value)
        value_label.setObjectName("valueChip")
        grid.addWidget(value_label, row, 1)
    layout.addLayout(grid)

    body = QLabel(
        "This panel intentionally uses identical content on both sides so the "
        "comparison is about the dock chrome, spacing, title bars, and tab treatment."
    )
    body.setWordWrap(True)
    body.setObjectName("panelBody")
    layout.addWidget(body)
    layout.addStretch()
    return panel


def make_canvas(label: str) -> QWidget:
    frame = QFrame()
    frame.setObjectName("canvasFrame")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(18, 18, 18, 18)
    layout.setSpacing(12)

    title = QLabel(label)
    title.setObjectName("canvasTitle")
    layout.addWidget(title)

    subtitle = QLabel(
        "Use the preset selector above to compare a single dock, tabbed docks, "
        "and a more crowded frame."
    )
    subtitle.setWordWrap(True)
    subtitle.setObjectName("canvasSubtitle")
    layout.addWidget(subtitle)

    swatches = QWidget()
    swatch_layout = QHBoxLayout(swatches)
    swatch_layout.setContentsMargins(0, 8, 0, 0)
    swatch_layout.setSpacing(10)
    for color in ("#0f766e", "#d97706", "#1d4ed8", "#b91c1c"):
        chip = QFrame()
        chip.setFixedSize(72, 72)
        chip.setStyleSheet(
            f"background:{color}; border-radius:18px; border: 2px solid rgba(255,255,255,0.2);"
        )
        swatch_layout.addWidget(chip)
    swatch_layout.addStretch()
    layout.addWidget(swatches)
    layout.addStretch()
    return frame


class DockSceneMixin:
    _layout_name: str

    def _clear_docks(self) -> None:
        raise NotImplementedError

    def _create_dock(self, title: str):
        raise NotImplementedError

    def _add_dock(self, area: Qt.DockWidgetArea, dock) -> None:
        raise NotImplementedError

    def _float_dock(self, dock) -> None:
        raise NotImplementedError

    def apply_layout(self, layout_name: str) -> None:
        self._layout_name = layout_name
        self._clear_docks()
        self.docks = []
        for title, area in LAYOUTS[layout_name]:
            dock = self._create_dock(title)
            self._add_dock(area, dock)
            self.docks.append(dock)

    def float_first(self) -> None:
        if self.docks:
            self._float_dock(self.docks[0])


class QtComparisonPane(QFrame, DockSceneMixin):
    def __init__(self) -> None:
        super().__init__()
        self._layout_name = "Balanced"
        self.docks: list[QDockWidget] = []
        self.window = QMainWindow()
        self.window.setCentralWidget(make_canvas("Qt central widget"))
        self._build_ui("Native Qt", "#dcfce7")

    def _build_ui(self, label: str, color: str) -> None:
        self.setFrameShape(QFrame.Shape.StyledPanel)
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        header = QLabel(label)
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet(f"background:{color}; padding:6px; font-weight:700;")
        root.addWidget(header)
        root.addWidget(self.window, 1)

    def _clear_docks(self) -> None:
        for dock in self.docks:
            self.window.removeDockWidget(dock)
            dock.setParent(None)
            dock.deleteLater()

    def _create_dock(self, title: str) -> QDockWidget:
        dock = QDockWidget(title, self.window)
        dock.setWidget(make_panel(title))
        return dock

    def _add_dock(self, area: Qt.DockWidgetArea, dock: QDockWidget) -> None:
        self.window.addDockWidget(area, dock)

    def _float_dock(self, dock: QDockWidget) -> None:
        dock.setFloating(True)


class LDockingComparisonPane(QFrame, DockSceneMixin):
    def __init__(self) -> None:
        super().__init__()
        self._layout_name = "Balanced"
        self.docks: list[LDockWidget] = []
        self.window = LMainWindow()
        self.window.setCentralWidget(make_canvas("ldocking central widget"))
        self._build_ui("ldocking", "#dbeafe")

    def _build_ui(self, label: str, color: str) -> None:
        self.setFrameShape(QFrame.Shape.StyledPanel)
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        header = QLabel(label)
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet(f"background:{color}; padding:6px; font-weight:700;")
        root.addWidget(header)
        root.addWidget(self.window, 1)

    def _clear_docks(self) -> None:
        for dock in self.docks:
            if dock.isFloating():
                dock.hide()
            self.window.removeDockWidget(dock)
            dock.setParent(None)
            dock.deleteLater()

    def _create_dock(self, title: str) -> LDockWidget:
        dock = LDockWidget(title)
        dock.setWidget(make_panel(title))
        return dock

    def _add_dock(self, area: Qt.DockWidgetArea, dock: LDockWidget) -> None:
        self.window.addDockWidget(area, dock)

    def _float_dock(self, dock: LDockWidget) -> None:
        dock.setFloating(True)


class VisualCompareDemo(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Dock Visual Comparison: Qt vs ldocking")
        self.resize(1500, 920)

        self._qt = QtComparisonPane()
        self._ldocking = LDockingComparisonPane()

        self._build_ui()
        self._apply_layout("Balanced")

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(8)

        title = QLabel("Side-by-side visual comparison")
        title.setStyleSheet("font-size: 18px; font-weight: 700;")
        toolbar_layout.addWidget(title)
        toolbar_layout.addStretch()

        toolbar_layout.addWidget(QLabel("Preset:"))
        self._preset = QComboBox()
        self._preset.addItems(list(LAYOUTS))
        self._preset.currentTextChanged.connect(self._apply_layout)
        toolbar_layout.addWidget(self._preset)

        float_btn = QPushButton("Float First Dock")
        float_btn.clicked.connect(self._float_first)
        toolbar_layout.addWidget(float_btn)

        reset_btn = QPushButton("Reset")
        reset_btn.clicked.connect(lambda: self._apply_layout(self._preset.currentText()))
        toolbar_layout.addWidget(reset_btn)

        root.addWidget(toolbar)

        note = QLabel(
            "Both panes use the same content and Fusion styling. Focus on title bar height, "
            "tab treatment, padding, splitter geometry, and floating appearance."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#475569; padding: 0 2px 4px 2px;")
        root.addWidget(note)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._qt)
        splitter.addWidget(self._ldocking)
        splitter.setSizes([760, 760])
        root.addWidget(splitter, 1)

    def _apply_layout(self, layout_name: str) -> None:
        if layout_name not in LAYOUTS:
            return
        self._qt.apply_layout(layout_name)
        self._ldocking.apply_layout(layout_name)

    def _float_first(self) -> None:
        self._qt.float_first()
        self._ldocking.float_first()


def _apply_demo_style(app: QApplication) -> None:
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#f8fafc"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#0f172a"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#eff6ff"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#0f172a"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#e2e8f0"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#0f172a"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#2563eb"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)

    app.setStyleSheet(
        """
        QWidget {
            font-family: "Segoe UI";
            font-size: 10pt;
        }
        QMainWindow, LMainWindow {
            background: #f8fafc;
            border: 1px solid #cbd5e1;
        }
        QDockWidget, LDockWidget {
            background: #ffffff;
            border: 1px solid #94a3b8;
        }
        QDockWidget::title, #dockTitleBar {
            background: #e2e8f0;
            color: #0f172a;
            padding: 6px 8px;
            border-bottom: 1px solid #cbd5e1;
            font-weight: 600;
        }
        #dockContent, QDockWidget > QWidget {
            background: #ffffff;
        }
        #comparisonPanel {
            background: #ffffff;
        }
        #panelHeading {
            font-size: 11pt;
            font-weight: 700;
            color: #0f172a;
        }
        #panelBody {
            color: #334155;
            line-height: 1.3em;
        }
        #valueChip {
            background: #eff6ff;
            color: #1d4ed8;
            border: 1px solid #bfdbfe;
            padding: 3px 8px;
            border-radius: 10px;
        }
        #canvasFrame {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #ffffff, stop:1 #e2e8f0);
        }
        #canvasTitle {
            font-size: 18pt;
            font-weight: 700;
            color: #0f172a;
        }
        #canvasSubtitle {
            color: #475569;
            max-width: 480px;
        }
        """
    )


def main() -> None:
    app = QApplication(sys.argv)
    _apply_demo_style(app)

    demo = VisualCompareDemo()
    demo.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
