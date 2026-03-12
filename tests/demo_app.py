"""Demo app — LMainWindow with richly populated dockable panels.

Panels:
  LEFT   — File Browser (tree view)
  LEFT   — Color Palette (grid of color swatches)
  RIGHT  — Properties Inspector (form layout)
  RIGHT  — Layer Stack (list with visibility toggles)
  BOTTOM — Console / Log output
  TOP    — Toolbar (via addToolBar, not a dock)
  CENTER — Canvas (custom painted widget)

Run:
  python tests/demo_app.py
"""
import sys
import os
import random
import math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PySide6.QtCore import Qt, QTimer, QPointF, QRectF, Signal
from PySide6.QtGui import (
    QAction, QBrush, QColor, QFont, QFontMetrics, QPainter,
    QPainterPath, QPen, QPixmap,
)
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDoubleSpinBox,
    QFileSystemModel, QFormLayout, QFrame, QGridLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMenuBar, QPlainTextEdit, QPushButton,
    QScrollArea, QSizePolicy, QSlider, QSpinBox, QSplitter,
    QStatusBar, QToolBar, QTreeView, QVBoxLayout, QWidget,
)

from ldocking import (
    BottomDockWidgetArea, LeftDockWidgetArea,
    LDockWidget, LMainWindow, RightDockWidgetArea, TopDockWidgetArea,
)


# ──────────────────────────────────────────────────────────────────────────────
# Canvas — central painting area
# ──────────────────────────────────────────────────────────────────────────────

class CanvasWidget(QWidget):
    """Simple interactive canvas with animated shapes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 300)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAutoFillBackground(True)
        p = self.palette()
        p.setColor(self.backgroundRole(), QColor("#1e1e2e"))
        self.setPalette(p)

        # Animated blobs
        self._shapes = [
            {"cx": 200, "cy": 150, "r": 60,  "color": QColor("#cba6f7"), "vx": 1.2,  "vy": 0.7},
            {"cx": 400, "cy": 250, "r": 45,  "color": QColor("#89dceb"), "vx": -0.9, "vy": 1.1},
            {"cx": 300, "cy": 100, "r": 35,  "color": QColor("#a6e3a1"), "vx": 0.6,  "vy": -1.3},
            {"cx": 150, "cy": 300, "r": 50,  "color": QColor("#fab387"), "vx": -1.1, "vy": -0.5},
            {"cx": 500, "cy": 180, "r": 40,  "color": QColor("#f38ba8"), "vx": 0.8,  "vy": 0.9},
        ]

        self._show_grid = True
        self._show_labels = True
        self._tick = 0

        timer = QTimer(self)
        timer.timeout.connect(self._animate)
        timer.start(16)  # ~60 fps

    def set_show_grid(self, show: bool):
        self._show_grid = show
        self.update()

    def set_show_labels(self, show: bool):
        self._show_labels = show
        self.update()

    def _animate(self):
        self._tick += 1
        w, h = self.width(), self.height()
        for s in self._shapes:
            s["cx"] += s["vx"]
            s["cy"] += s["vy"]
            if s["cx"] - s["r"] < 0 or s["cx"] + s["r"] > w:
                s["vx"] *= -1
            if s["cy"] - s["r"] < 0 or s["cy"] + s["r"] > h:
                s["vy"] *= -1
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Grid
        if self._show_grid:
            p.setPen(QPen(QColor(255, 255, 255, 20), 1))
            step = 40
            for x in range(0, self.width(), step):
                p.drawLine(x, 0, x, self.height())
            for y in range(0, self.height(), step):
                p.drawLine(0, y, self.width(), y)

        # Blobs with glow
        for s in self._shapes:
            cx, cy, r = int(s["cx"]), int(s["cy"]), s["r"]
            col: QColor = s["color"]

            # Outer glow
            glow = QColor(col)
            glow.setAlpha(40)
            for i in range(3, 0, -1):
                p.setBrush(QBrush(glow))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(cx, cy), r + i * 8, r + i * 8)

            # Main circle
            p.setBrush(QBrush(col))
            p.setPen(QPen(col.lighter(150), 2))
            p.drawEllipse(QPointF(cx, cy), r, r)

        # Labels
        if self._show_labels:
            p.setPen(QColor(255, 255, 255, 180))
            font = QFont("Consolas", 9)
            p.setFont(font)
            for i, s in enumerate(self._shapes):
                p.drawText(
                    int(s["cx"]) - 20, int(s["cy"]) + 4,
                    f"shape{i+1}"
                )

        # FPS indicator
        p.setPen(QColor(255, 255, 255, 80))
        p.setFont(QFont("Consolas", 8))
        p.drawText(8, 16, f"tick {self._tick}")


# ──────────────────────────────────────────────────────────────────────────────
# File Browser panel
# ──────────────────────────────────────────────────────────────────────────────

def make_file_browser() -> QWidget:
    w = QWidget()
    layout = QVBoxLayout(w)
    layout.setContentsMargins(4, 4, 4, 4)
    layout.setSpacing(4)

    search = QLineEdit()
    search.setPlaceholderText("Search files…")
    layout.addWidget(search)

    tree = QTreeView()
    tree.setHeaderHidden(False)
    model = QFileSystemModel()
    root = os.path.expanduser("~")
    model.setRootPath(root)
    tree.setModel(model)
    tree.setRootIndex(model.index(root))
    tree.setColumnWidth(0, 160)
    tree.hideColumn(2)  # hide type column
    layout.addWidget(tree)
    return w


# ──────────────────────────────────────────────────────────────────────────────
# Color Palette panel
# ──────────────────────────────────────────────────────────────────────────────

PALETTE_COLORS = [
    # Catppuccin Mocha
    "#cba6f7", "#f38ba8", "#fab387", "#f9e2af",
    "#a6e3a1", "#94e2d5", "#89dceb", "#89b4fa",
    "#b4befe", "#cdd6f4", "#bac2de", "#a6adc8",
    "#585b70", "#45475a", "#313244", "#1e1e2e",
    # Extra saturated
    "#ff0055", "#ff6600", "#ffcc00", "#00cc44",
    "#0099ff", "#9933ff", "#ff33cc", "#33ffcc",
]

def make_color_palette() -> QWidget:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)

    container = QWidget()
    grid = QGridLayout(container)
    grid.setContentsMargins(6, 6, 6, 6)
    grid.setSpacing(4)

    cols = 4
    for i, hex_color in enumerate(PALETTE_COLORS):
        btn = QPushButton()
        btn.setFixedSize(36, 36)
        btn.setToolTip(hex_color)
        btn.setStyleSheet(
            f"background-color: {hex_color}; border: 1px solid #444; border-radius: 4px;"
            f"QPushButton:hover {{ border: 2px solid white; }}"
        )
        grid.addWidget(btn, i // cols, i % cols)

    scroll.setWidget(container)
    return scroll


# ──────────────────────────────────────────────────────────────────────────────
# Properties Inspector panel
# ──────────────────────────────────────────────────────────────────────────────

def make_properties() -> QWidget:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)

    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(8)

    # Transform group
    transform_box = QGroupBox("Transform")
    tf = QFormLayout(transform_box)
    tf.addRow("X:", QDoubleSpinBox())
    tf.addRow("Y:", QDoubleSpinBox())
    tf.addRow("Width:", QDoubleSpinBox())
    tf.addRow("Height:", QDoubleSpinBox())
    rot = QDoubleSpinBox()
    rot.setRange(-360, 360)
    tf.addRow("Rotation:", rot)
    layout.addWidget(transform_box)

    # Appearance group
    appear_box = QGroupBox("Appearance")
    af = QFormLayout(appear_box)
    opacity_slider = QSlider(Qt.Orientation.Horizontal)
    opacity_slider.setRange(0, 100)
    opacity_slider.setValue(100)
    af.addRow("Opacity:", opacity_slider)
    blend_combo = QComboBox()
    blend_combo.addItems(["Normal", "Multiply", "Screen", "Overlay", "Darken", "Lighten"])
    af.addRow("Blend:", blend_combo)
    af.addRow("Visible:", QCheckBox())
    af.addRow("Locked:", QCheckBox())
    layout.addWidget(appear_box)

    # Fill group
    fill_box = QGroupBox("Fill")
    ff = QFormLayout(fill_box)
    fill_color = QPushButton()
    fill_color.setFixedHeight(24)
    fill_color.setStyleSheet("background: #cba6f7; border: 1px solid #666;")
    ff.addRow("Color:", fill_color)
    fill_opacity = QSlider(Qt.Orientation.Horizontal)
    fill_opacity.setRange(0, 100)
    fill_opacity.setValue(100)
    ff.addRow("Fill opacity:", fill_opacity)
    layout.addWidget(fill_box)

    layout.addStretch()
    scroll.setWidget(container)
    return scroll


# ──────────────────────────────────────────────────────────────────────────────
# Layer Stack panel
# ──────────────────────────────────────────────────────────────────────────────

LAYER_NAMES = [
    ("shape5", "#f38ba8", True),
    ("shape4", "#fab387", True),
    ("shape3", "#a6e3a1", True),
    ("shape2", "#89dceb", False),
    ("shape1", "#cba6f7", True),
    ("background", "#1e1e2e", True),
]

def make_layers() -> QWidget:
    w = QWidget()
    layout = QVBoxLayout(w)
    layout.setContentsMargins(4, 4, 4, 4)
    layout.setSpacing(2)

    header = QHBoxLayout()
    header.addWidget(QLabel("Layers"))
    add_btn = QPushButton("+")
    add_btn.setFixedSize(22, 22)
    header.addStretch()
    header.addWidget(add_btn)
    layout.addLayout(header)

    list_widget = QListWidget()
    list_widget.setDragDropMode(QListWidget.DragDropMode.InternalMove)
    list_widget.setSpacing(1)

    for name, color, visible in LAYER_NAMES:
        item = QListWidgetItem()
        item_widget = QWidget()
        row = QHBoxLayout(item_widget)
        row.setContentsMargins(4, 2, 4, 2)
        row.setSpacing(6)

        swatch = QLabel()
        swatch.setFixedSize(14, 14)
        swatch.setStyleSheet(
            f"background: {color}; border-radius: 3px; border: 1px solid #555;"
        )
        vis_check = QCheckBox()
        vis_check.setChecked(visible)
        name_label = QLabel(name)
        name_label.setFont(QFont("Consolas", 9))

        row.addWidget(vis_check)
        row.addWidget(swatch)
        row.addWidget(name_label)
        row.addStretch()

        item.setSizeHint(item_widget.sizeHint())
        list_widget.addItem(item)
        list_widget.setItemWidget(item, item_widget)

    layout.addWidget(list_widget)
    return w


# ──────────────────────────────────────────────────────────────────────────────
# Console / Log panel
# ──────────────────────────────────────────────────────────────────────────────

class ConsoleWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self._output = QPlainTextEdit()
        self._output.setReadOnly(True)
        self._output.setFont(QFont("Consolas", 9))
        self._output.setStyleSheet(
            "QPlainTextEdit { background: #181825; color: #cdd6f4; border: none; }"
        )
        layout.addWidget(self._output)

        input_row = QHBoxLayout()
        self._input = QLineEdit()
        self._input.setFont(QFont("Consolas", 9))
        self._input.setPlaceholderText("Enter command…")
        self._input.returnPressed.connect(self._run_command)
        run_btn = QPushButton("Run")
        run_btn.setFixedWidth(48)
        run_btn.clicked.connect(self._run_command)
        clear_btn = QPushButton("Clear")
        clear_btn.setFixedWidth(48)
        clear_btn.clicked.connect(self._output.clear)
        input_row.addWidget(self._input)
        input_row.addWidget(run_btn)
        input_row.addWidget(clear_btn)
        layout.addLayout(input_row)

        # Seed with some fake log lines
        messages = [
            ("[INFO]  app started", "#a6e3a1"),
            ("[INFO]  canvas initialized — 5 shapes", "#a6e3a1"),
            ("[DEBUG] QSplitter sizes: [180, 640, 200]", "#89b4fa"),
            ("[INFO]  dock 'File Browser' docked LEFT", "#a6e3a1"),
            ("[INFO]  dock 'Properties' docked RIGHT", "#a6e3a1"),
            ("[WARN]  layer 'shape2' hidden", "#f9e2af"),
            ("[INFO]  ready", "#a6e3a1"),
        ]
        for msg, _ in messages:
            self._output.appendPlainText(msg)

    def log(self, text: str):
        self._output.appendPlainText(text)
        self._output.verticalScrollBar().setValue(
            self._output.verticalScrollBar().maximum()
        )

    def _run_command(self):
        cmd = self._input.text().strip()
        if not cmd:
            return
        self._output.appendPlainText(f">>> {cmd}")
        self._output.appendPlainText(f"    [exec] {cmd!r}")
        self._input.clear()


# ──────────────────────────────────────────────────────────────────────────────
# Main demo window
# ──────────────────────────────────────────────────────────────────────────────

class DemoWindow(LMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LDockingWidget Demo")
        self.resize(1400, 900)

        self._console: ConsoleWidget | None = None
        self._build_menu()
        self._build_toolbar()
        self._build_central()
        self._build_docks()
        self.statusBar().showMessage(
            "Drag title bars to reposition panels  •  Double-click title to float/dock"
        )

    # ── menu ──────────────────────────────────────────────────────────────────

    def _build_menu(self):
        mb = self.menuBar()

        file_menu = mb.addMenu("&File")
        file_menu.addAction(QAction("New", self))
        file_menu.addAction(QAction("Open…", self))
        file_menu.addSeparator()
        quit_action = QAction("&Quit", self)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        self._view_menu = mb.addMenu("&View")

        help_menu = mb.addMenu("&Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(
            lambda: self._console and self._console.log("[INFO]  LDockingWidget demo — no QDockAreaLayout!")
        )
        help_menu.addAction(about_action)

    # ── toolbar ───────────────────────────────────────────────────────────────

    def _build_toolbar(self):
        tb = QToolBar("Main")
        tb.setMovable(False)

        float_all = QAction("Float All", self)
        float_all.triggered.connect(self._float_all)
        tb.addAction(float_all)

        dock_all = QAction("Dock All", self)
        dock_all.triggered.connect(self._dock_all)
        tb.addAction(dock_all)

        tb.addSeparator()

        self._grid_action = QAction("Grid", self)
        self._grid_action.setCheckable(True)
        self._grid_action.setChecked(True)
        self._grid_action.toggled.connect(self._toggle_grid)
        tb.addAction(self._grid_action)

        self._labels_action = QAction("Labels", self)
        self._labels_action.setCheckable(True)
        self._labels_action.setChecked(True)
        self._labels_action.toggled.connect(self._toggle_labels)
        tb.addAction(self._labels_action)

        self.addToolBar(tb)

    # ── central widget ────────────────────────────────────────────────────────

    def _build_central(self):
        self._canvas = CanvasWidget()
        self.setCentralWidget(self._canvas)

    # ── dock panels ───────────────────────────────────────────────────────────

    def _build_docks(self):
        self._docks: list[LDockWidget] = []

        specs = [
            ("File Browser",  LeftDockWidgetArea,   make_file_browser),
            ("Color Palette", LeftDockWidgetArea,   make_color_palette),
            ("Properties",    RightDockWidgetArea,  make_properties),
            ("Layers",        RightDockWidgetArea,  make_layers),
            ("Console",       BottomDockWidgetArea, self._make_console),
        ]

        for title, area, factory in specs:
            dock = LDockWidget(title)
            dock._main_window = self
            dock.setWidget(factory())
            self.addDockWidget(area, dock)
            self._docks.append(dock)
            self._view_menu.addAction(dock.toggleViewAction())

        # Log startup info via console
        if self._console:
            self._console.log("[INFO]  all dock panels attached")

    def _make_console(self) -> ConsoleWidget:
        self._console = ConsoleWidget()
        return self._console

    # ── toolbar actions ───────────────────────────────────────────────────────

    def _float_all(self):
        for dock in self._docks:
            dock.setFloating(True)
        self.statusBar().showMessage("All panels floating")
        if self._console:
            self._console.log("[INFO]  all docks floated")

    _INITIAL_AREAS = [
        LeftDockWidgetArea,
        LeftDockWidgetArea,
        RightDockWidgetArea,
        RightDockWidgetArea,
        BottomDockWidgetArea,
    ]

    def _dock_all(self):
        for dock, area in zip(self._docks, self._INITIAL_AREAS):
            self.addDockWidget(area, dock)
        self.statusBar().showMessage("All panels docked")
        if self._console:
            self._console.log("[INFO]  all docks re-docked")

    def _toggle_grid(self, checked: bool):
        self._canvas.set_show_grid(checked)

    def _toggle_labels(self, checked: bool):
        self._canvas.set_show_labels(checked)


# ──────────────────────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Dark palette
    from PySide6.QtGui import QPalette
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#313244"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#cdd6f4"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#1e1e2e"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#181825"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#cdd6f4"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#313244"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#cdd6f4"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#cba6f7"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#1e1e2e"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#45475a"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#cdd6f4"))
    app.setPalette(palette)

    win = DemoWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
