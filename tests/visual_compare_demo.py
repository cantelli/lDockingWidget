"""Visual side-by-side comparison between Qt docking and ldocking.

Run:
    python tests/visual_compare_demo.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDockWidget,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ldocking import LDockWidget, LMainWindow
from dock_panels import make_panel
from compare_scenarios import SCENARIOS, scenario_names

# Use the real Qt classes even when ldocking.monkey has patched PySide6.QtWidgets.
try:
    from ldocking.monkey import _ORIG as _QT_ORIG
    _QMainWindow = _QT_ORIG["QMainWindow"]
    _QDockWidget = _QT_ORIG["QDockWidget"]
except (ImportError, KeyError):
    _QMainWindow = QMainWindow  # type: ignore[assignment]
    _QDockWidget = QDockWidget  # type: ignore[assignment]


Left = Qt.DockWidgetArea.LeftDockWidgetArea
Right = Qt.DockWidgetArea.RightDockWidgetArea
Top = Qt.DockWidgetArea.TopDockWidgetArea
Bottom = Qt.DockWidgetArea.BottomDockWidgetArea


LAYOUTS: dict[str, list[tuple[str, Qt.DockWidgetArea]]] = {
    "Single Left": [("Inspector", Left)],
    "Tabbed Left": [("Inspector", Left), ("Assets", Left)],
    "Grouped Tabs": [("Inspector", Left), ("Assets", Left), ("Outline", Left)],
    "Balanced": [
        ("Inspector", Left),
        ("Assets", Left),
        ("Layers", Right),
        ("Console", Bottom),
    ],
    "Nested Split": [
        ("Inspector", Left),
        ("Assets", Left),
        ("Layers", Left),
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

    def _redock_dock(self, dock) -> None:
        raise NotImplementedError

    def _move_dock_to_area(self, dock, area: Qt.DockWidgetArea) -> None:
        raise NotImplementedError

    def _tabify_docks(self, first, second) -> None:
        raise NotImplementedError

    def _post_layout(self, layout_name: str) -> None:
        pass

    def apply_layout(self, layout_name: str) -> None:
        self._layout_name = layout_name
        self._clear_docks()
        self.docks = []
        for title, area in LAYOUTS[layout_name]:
            dock = self._create_dock(title)
            self._add_dock(area, dock)
            self.docks.append(dock)
        self._post_layout(layout_name)

    def float_first(self) -> None:
        if self.docks:
            self._float_dock(self.docks[0])

    def dock_by_title(self, title: str):
        for dock in self.docks:
            if dock.windowTitle() == title:
                return dock
        raise KeyError(f"Missing dock {title!r}")

    def ensure_dock(self, title: str, area: Qt.DockWidgetArea):
        try:
            return self.dock_by_title(title)
        except KeyError:
            dock = self._create_dock(title)
            self._add_dock(area, dock)
            self.docks.append(dock)
            return dock

    def apply_action(self, action: dict[str, object]) -> None:
        op = action["op"]
        if op == "float":
            self._float_dock(self.dock_by_title(str(action["title"])))
        elif op == "redock":
            self._redock_dock(self.dock_by_title(str(action["title"])))
        elif op == "move":
            self._move_dock_to_area(
                self.dock_by_title(str(action["title"])),
                action["area"],
            )
        elif op == "add":
            self._move_dock_to_area(
                self.ensure_dock(str(action["title"]), action["area"]),
                action["area"],
            )
        elif op == "tabify":
            self._tabify_docks(
                self.dock_by_title(str(action["first"])),
                self.dock_by_title(str(action["second"])),
            )
        else:
            raise ValueError(f"Unsupported action op: {op!r}")


class QtComparisonPane(QFrame, DockSceneMixin):
    def __init__(self) -> None:
        super().__init__()
        self._layout_name = "Balanced"
        self.docks: list[QDockWidget] = []
        self.window = _QMainWindow()
        self.window.setCentralWidget(make_canvas("Central"))
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
        self.window.setDockOptions(_QMainWindow.DockOption.AnimatedDocks | _QMainWindow.DockOption.AllowTabbedDocks)

    def _create_dock(self, title: str) -> QDockWidget:
        dock = _QDockWidget(title, self.window)
        dock.setWidget(make_panel(title))
        return dock

    def _add_dock(self, area: Qt.DockWidgetArea, dock: QDockWidget) -> None:
        self.window.addDockWidget(area, dock)

    def _float_dock(self, dock: QDockWidget) -> None:
        dock.setFloating(True)

    def _redock_dock(self, dock: QDockWidget) -> None:
        dock.setFloating(False)

    def _move_dock_to_area(self, dock: QDockWidget, area: Qt.DockWidgetArea) -> None:
        if dock.isFloating():
            dock.setFloating(False)
        self.window.addDockWidget(area, dock)

    def _tabify_docks(self, first: QDockWidget, second: QDockWidget) -> None:
        self.window.tabifyDockWidget(first, second)

    def _post_layout(self, layout_name: str) -> None:
        if layout_name == "Nested Split" and len(self.docks) >= 3:
            self.window.tabifyDockWidget(self.docks[0], self.docks[1])
            self.window.splitDockWidget(self.docks[0], self.docks[2], Qt.Orientation.Vertical)
        elif layout_name == "Grouped Tabs" and len(self.docks) >= 3:
            self.window.tabifyDockWidget(self.docks[0], self.docks[1])
            self.window.tabifyDockWidget(self.docks[0], self.docks[2])


class LDockingComparisonPane(QFrame, DockSceneMixin):
    def __init__(self) -> None:
        super().__init__()
        self._layout_name = "Balanced"
        self.docks: list[LDockWidget] = []
        self.window = LMainWindow()
        self.window.setCentralWidget(make_canvas("Central"))
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
        self.window.setDockOptions(LMainWindow.AnimatedDocks | LMainWindow.AllowTabbedDocks)

    def _create_dock(self, title: str) -> LDockWidget:
        dock = LDockWidget(title)
        dock.setWidget(make_panel(title))
        return dock

    def _add_dock(self, area: Qt.DockWidgetArea, dock: LDockWidget) -> None:
        self.window.addDockWidget(area, dock)

    def _float_dock(self, dock: LDockWidget) -> None:
        dock.setFloating(True)

    def _redock_dock(self, dock: LDockWidget) -> None:
        dock.setFloating(False)

    def _move_dock_to_area(self, dock: LDockWidget, area: Qt.DockWidgetArea) -> None:
        self.window.addDockWidget(area, dock)

    def _tabify_docks(self, first: LDockWidget, second: LDockWidget) -> None:
        self.window.tabifyDockWidget(first, second)

    def _post_layout(self, layout_name: str) -> None:
        if layout_name == "Nested Split" and len(self.docks) >= 3:
            # Qt's splitDockWidget inserts docks[2] immediately after docks[0].
            # tabifyDockWidget appends at end, so tabify docks[2] first so it
            # lands at position 1, then docks[1] appends at the end — matching Qt.
            self.window.tabifyDockWidget(self.docks[0], self.docks[2])
            self.window.tabifyDockWidget(self.docks[0], self.docks[1])
        elif layout_name == "Grouped Tabs" and len(self.docks) >= 3:
            self.window.tabifyDockWidget(self.docks[0], self.docks[1])
            self.window.tabifyDockWidget(self.docks[0], self.docks[2])


class VisualCompareDemo(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Dock Visual Comparison: Qt vs ldocking")
        self.resize(1500, 920)

        self._qt = QtComparisonPane()
        self._ldocking = LDockingComparisonPane()
        self._scenario_steps: list[dict[str, object]] = []
        self._scenario_index = 0

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

        toolbar_layout.addWidget(QLabel("Scenario:"))
        self._scenario = QComboBox()
        self._scenario.addItem("None")
        self._scenario.addItems(scenario_names())
        self._scenario.currentTextChanged.connect(self._select_scenario)
        toolbar_layout.addWidget(self._scenario)

        step_btn = QPushButton("Run Step")
        step_btn.clicked.connect(self._run_next_step)
        toolbar_layout.addWidget(step_btn)

        float_btn = QPushButton("Float First Dock")
        float_btn.clicked.connect(self._float_first)
        toolbar_layout.addWidget(float_btn)

        reset_btn = QPushButton("Reset")
        reset_btn.clicked.connect(lambda: self._apply_layout(self._preset.currentText()))
        toolbar_layout.addWidget(reset_btn)

        root.addWidget(toolbar)

        note = QLabel(
            "Both panes use the same content and Fusion styling. Use scenarios to compare dynamic transitions "
            "like float, redock, and move steps, not just static end states."
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
        self._scenario_steps = []
        self._scenario_index = 0
        self._qt.apply_layout(layout_name)
        self._ldocking.apply_layout(layout_name)

    def _float_first(self) -> None:
        self._qt.float_first()
        self._ldocking.float_first()

    def _select_scenario(self, scenario_name: str) -> None:
        if scenario_name == "None":
            self._scenario_steps = []
            self._scenario_index = 0
            self._apply_layout(self._preset.currentText())
            return
        scenario = SCENARIOS[scenario_name]
        layout_name = str(scenario["layout"])
        self._preset.setCurrentText(layout_name)
        self._scenario_steps = list(scenario["steps"])
        self._scenario_index = 0

    def _run_next_step(self) -> None:
        if self._scenario.currentText() == "None" or self._scenario_index >= len(self._scenario_steps):
            return
        action = self._scenario_steps[self._scenario_index]
        self._qt.apply_action(action)
        self._ldocking.apply_action(action)
        self._scenario_index += 1


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
