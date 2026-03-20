"""Headless screenshot capture + diff tool for Qt vs ldocking visual parity.

Usage:
    python tests/screenshot_compare.py [--outdir tests/screenshots]

For each demo mode (Single Left, Tabbed Left, Grouped Tabs, Balanced,
Nested Split, Full Frame) this script:
  - Creates Qt QMainWindow + docks and LMainWindow + LDockWidgets
  - Applies an identical stylesheet using ONLY legacy Qt selectors
    (exercises translate_stylesheet() end-to-end for ldocking)
  - Grabs screenshots of both windows
  - Saves <mode>_qt.png, <mode>_l.png, <mode>_side_by_side.png
  - Prints a ranked diff score table

Run after making visual changes to quickly spot regressions/improvements.
"""
from __future__ import annotations

import os
import sys
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap, QStandardItemModel, QStandardItem
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QSizePolicy,
    QTextEdit,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from ldocking import LDockWidget, LMainWindow
from ldocking.stylesheet_compat import translate_stylesheet

try:
    from ldocking.monkey import _ORIG as _QT_ORIG
    _QtMainWindow = _QT_ORIG["QMainWindow"]
    _QtDockWidget = _QT_ORIG["QDockWidget"]
except ImportError:
    from PySide6.QtWidgets import QMainWindow as _QtMainWindow, QDockWidget as _QtDockWidget  # type: ignore
    _QtDockWidget = _QtDockWidget  # noqa: F811

Left = Qt.DockWidgetArea.LeftDockWidgetArea
Right = Qt.DockWidgetArea.RightDockWidgetArea
Top = Qt.DockWidgetArea.TopDockWidgetArea
Bottom = Qt.DockWidgetArea.BottomDockWidgetArea

WINDOW_SIZE = QSize(640, 420)

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

# Pure Qt-selector stylesheet — ldocking receives this via translate_stylesheet()
# Qt receives it verbatim.  No ldocking-specific selectors allowed here.
PURE_QT_QSS = """
    QMainWindow {
        background: #f8fafc;
    }
    QMainWindow::separator {
        background: #94a3b8;
        width: 4px;
        height: 4px;
    }
    QDockWidget {
        background: #ffffff;
        border: 1px solid #94a3b8;
    }
    QDockWidget::title {
        background: #e2e8f0;
        color: #0f172a;
        padding: 4px 8px;
        font-weight: 600;
        border-bottom: 1px solid #cbd5e1;
    }
    QDockWidget > QWidget {
        background: #f8fafc;
    }
    QDockWidget::close-button {
        background: transparent;
    }
    QDockWidget::float-button {
        background: transparent;
    }
    QTabBar::tab {
        background: #dbeafe;
        border: 1px solid #94a3b8;
        padding: 4px 10px;
    }
    QTabBar::tab:selected {
        background: #ffffff;
    }
"""


def _make_inspector() -> QWidget:
    """Property inspector with form fields."""
    panel = QFrame()
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(6, 6, 6, 6)
    layout.setSpacing(4)
    form = QFormLayout()
    form.setContentsMargins(0, 0, 0, 0)
    form.setSpacing(4)
    form.addRow("Name:", QLineEdit("MainObject"))
    spin = QSpinBox()
    spin.setValue(42)
    form.addRow("Width:", spin)
    dspin = QDoubleSpinBox()
    dspin.setValue(1.0)
    form.addRow("Opacity:", dspin)
    combo = QComboBox()
    combo.addItems(["Solid", "Dashed", "Dotted"])
    form.addRow("Style:", combo)
    form.addRow("Visible:", QCheckBox())
    layout.addLayout(form)
    slider = QSlider(Qt.Orientation.Horizontal)
    slider.setValue(60)
    layout.addWidget(QLabel("Blend:"))
    layout.addWidget(slider)
    layout.addStretch()
    return panel


def _make_assets() -> QWidget:
    """Asset browser with a list."""
    panel = QFrame()
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(4, 4, 4, 4)
    layout.setSpacing(4)
    search = QLineEdit()
    search.setPlaceholderText("Search assets…")
    layout.addWidget(search)
    lst = QListWidget()
    lst.addItems(["texture_albedo.png", "mesh_hero.fbx", "anim_run.anim",
                  "material_metal.mat", "shader_pbr.glsl", "audio_footstep.wav"])
    layout.addWidget(lst, 1)
    row = QHBoxLayout()
    row.addWidget(QPushButton("Import"))
    row.addWidget(QPushButton("Refresh"))
    layout.addLayout(row)
    return panel


def _make_layers() -> QWidget:
    """Layer list with checkboxes via a tree view."""
    panel = QFrame()
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(4, 4, 4, 4)
    layout.setSpacing(4)
    model = QStandardItemModel(0, 2)
    model.setHorizontalHeaderLabels(["Layer", "Lock"])
    for name, locked in [("Background", False), ("Terrain", False),
                          ("Props", True), ("Characters", False), ("FX", False)]:
        item = QStandardItem(name)
        item.setCheckable(True)
        item.setCheckState(Qt.CheckState.Checked)
        lock = QStandardItem("🔒" if locked else "")
        model.appendRow([item, lock])
    tree = QTreeView()
    tree.setModel(model)
    tree.setColumnWidth(0, 100)
    tree.header().setStretchLastSection(True)
    layout.addWidget(tree, 1)
    return panel


def _make_console() -> QWidget:
    """Output console with log lines."""
    panel = QFrame()
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(4, 4, 4, 4)
    layout.setSpacing(4)
    log = QTextEdit()
    log.setReadOnly(True)
    log.setPlainText(
        "[INFO]  Scene loaded in 0.42 s\n"
        "[INFO]  Compiling shaders (12/12)\n"
        "[WARN]  Missing LOD for mesh_hero\n"
        "[INFO]  Physics world initialized\n"
        "[ERROR] audio_footstep.wav not found\n"
    )
    log.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
    layout.addWidget(log, 1)
    row = QHBoxLayout()
    row.addWidget(QLineEdit(), 1)
    row.addWidget(QPushButton("Run"))
    layout.addLayout(row)
    return panel


def _make_history() -> QWidget:
    """Undo/redo history list."""
    panel = QFrame()
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(4, 4, 4, 4)
    layout.setSpacing(4)
    lst = QListWidget()
    actions = ["Move object", "Scale mesh", "Add material",
                "Delete vertex", "UV unwrap", "Bake lighting"]
    for i, act in enumerate(actions):
        lst.addItem(f"{i + 1}. {act}")
    lst.setCurrentRow(3)
    layout.addWidget(lst, 1)
    row = QHBoxLayout()
    row.addWidget(QPushButton("Undo"))
    row.addWidget(QPushButton("Redo"))
    layout.addLayout(row)
    return panel


def _make_outline() -> QWidget:
    """Scene outliner tree."""
    panel = QFrame()
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(4, 4, 4, 4)
    layout.setSpacing(4)
    model = QStandardItemModel()
    model.setHorizontalHeaderLabels(["Scene"])
    root = QStandardItem("Scene Root")
    for child_name, grandchildren in [
        ("Environment", ["Sky", "Terrain", "Water"]),
        ("Characters", ["Hero", "NPC_01"]),
        ("Props", ["Crate_A", "Barrel_B"]),
    ]:
        child = QStandardItem(child_name)
        for gc in grandchildren:
            child.appendRow(QStandardItem(gc))
        root.appendRow(child)
    model.appendRow(root)
    tree = QTreeView()
    tree.setModel(model)
    tree.expandAll()
    tree.setHeaderHidden(True)
    layout.addWidget(tree, 1)
    return panel


_PANEL_FACTORIES = {
    "Inspector": _make_inspector,
    "Assets":    _make_assets,
    "Layers":    _make_layers,
    "Console":   _make_console,
    "History":   _make_history,
    "Outline":   _make_outline,
}


def _make_panel(title: str) -> QWidget:
    factory = _PANEL_FACTORIES.get(title)
    inner = factory() if factory is not None else _fallback_panel(title)
    # Wrap in a scroll area so every dock reports the same compact sizeHint
    # regardless of content.  Without this, QTextEdit / QListWidget produce
    # large sizeHints that skew the QSplitter size distribution differently
    # than Qt's QMainWindow algorithm, making the comparison unfair.
    scroll = QScrollArea()
    scroll.setWidget(inner)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    return scroll


def _fallback_panel(title: str) -> QWidget:
    panel = QFrame()
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.addWidget(QLabel(title))
    layout.addStretch()
    return panel


def _make_central() -> QWidget:
    w = QLabel("Central")
    w.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return w


# ---------------------------------------------------------------------------
# Qt window builder
# ---------------------------------------------------------------------------

def _build_qt_window(layout_name: str) -> _QtMainWindow:
    win = _QtMainWindow()
    win.resize(WINDOW_SIZE)
    win.setCentralWidget(_make_central())
    docks = []
    for title, area in LAYOUTS[layout_name]:
        dock = _QtDockWidget(title, win)
        dock.setWidget(_make_panel(title))
        win.addDockWidget(area, dock)
        docks.append(dock)

    if layout_name == "Nested Split" and len(docks) >= 3:
        win.tabifyDockWidget(docks[0], docks[1])
        win.splitDockWidget(docks[0], docks[2], Qt.Orientation.Vertical)
    elif layout_name == "Grouped Tabs" and len(docks) >= 3:
        win.tabifyDockWidget(docks[0], docks[1])
        win.tabifyDockWidget(docks[0], docks[2])

    win.setStyleSheet(PURE_QT_QSS)
    return win


# ---------------------------------------------------------------------------
# ldocking window builder
# ---------------------------------------------------------------------------

def _build_l_window(layout_name: str) -> LMainWindow:
    win = LMainWindow()
    win.resize(WINDOW_SIZE)
    win.setCentralWidget(_make_central())
    docks = []
    for title, area in LAYOUTS[layout_name]:
        dock = LDockWidget(title)
        dock.setWidget(_make_panel(title))
        win.addDockWidget(area, dock)
        docks.append(dock)

    if layout_name == "Nested Split" and len(docks) >= 3:
        # Qt's splitDockWidget on a tabified dock actually tabs all three together.
        # Mirror that behavior so layouts match.
        win.tabifyDockWidget(docks[0], docks[1])
        win.tabifyDockWidget(docks[0], docks[2])
    elif layout_name == "Grouped Tabs" and len(docks) >= 3:
        win.tabifyDockWidget(docks[0], docks[1])
        win.tabifyDockWidget(docks[0], docks[2])

    win.setStyleSheet(translate_stylesheet(PURE_QT_QSS))
    return win


# Target dock sizes for the 640×420 window — identical for Qt and ldocking.
_DOCK_W_LEFT   = 180
_DOCK_W_RIGHT  = 170
_DOCK_H_BOTTOM = 100


def _equalize_sizes(
    qt_win: _QtMainWindow,
    l_win: LMainWindow,
    layout_name: str,
    qt_docks: list,
    l_docks: list,
) -> None:
    """Force identical dock sizes on both windows so the pixel comparison
    measures rendering fidelity rather than initial size-distribution policy."""
    pairs = list(LAYOUTS[layout_name])

    qt_by_area: dict[Qt.DockWidgetArea, list] = {}
    l_by_area:  dict[Qt.DockWidgetArea, list] = {}
    for (_, area), qd, ld in zip(pairs, qt_docks, l_docks):
        qt_by_area.setdefault(area, []).append(qd)
        l_by_area.setdefault(area, []).append(ld)

    has_bottom = Bottom in qt_by_area
    h_main = WINDOW_SIZE.height() - (_DOCK_H_BOTTOM + 4 if has_bottom else 0)

    # ---- horizontal widths (Left / Right area) ----
    if Left in qt_by_area:
        qt_win.resizeDocks(qt_by_area[Left][:1], [_DOCK_W_LEFT],  Qt.Orientation.Horizontal)
        l_win.resizeDocks( l_by_area [Left][:1], [_DOCK_W_LEFT],  Qt.Orientation.Horizontal)
    if Right in qt_by_area:
        qt_win.resizeDocks(qt_by_area[Right][:1], [_DOCK_W_RIGHT], Qt.Orientation.Horizontal)
        l_win.resizeDocks( l_by_area [Right][:1], [_DOCK_W_RIGHT], Qt.Orientation.Horizontal)

    # ---- Bottom dock height ----
    if has_bottom:
        qt_win.resizeDocks(qt_by_area[Bottom][:1], [_DOCK_H_BOTTOM], Qt.Orientation.Vertical)
        l_win.resizeDocks( l_by_area [Bottom][:1], [_DOCK_H_BOTTOM], Qt.Orientation.Vertical)

    # ---- Stacked docks within a single area (Qt supports resizeDocks for these;
    #      ldocking's resizeDocks only handles area-level, so poke the internal
    #      QSplitter directly). ----
    for area, qt_ds in qt_by_area.items():
        if len(qt_ds) < 2 or area == Bottom:
            continue
        n = len(qt_ds)
        sep = 4
        h_each = max(40, (h_main - sep * (n - 1)) // n)
        qt_win.resizeDocks(qt_ds, [h_each] * n, Qt.Orientation.Vertical)
        l_ds = l_by_area.get(area, [])
        l_area_widget = l_win._dock_areas.get(area)
        if l_area_widget is not None and getattr(l_area_widget, "_split_area", None) is not None:
            l_area_widget._split_area.setSizes([h_each] * n)


# ---------------------------------------------------------------------------
# Image diff helpers
# ---------------------------------------------------------------------------

def _avg_image_diff(img1: QImage, img2: QImage,
                    x0: int = 0, y0: int = 0,
                    x1: int | None = None, y1: int | None = None) -> float:
    """Average per-channel pixel difference over an optional sub-region."""
    width = min(img1.width(), img2.width())
    height = min(img1.height(), img2.height())
    if x1 is None:
        x1 = width
    if y1 is None:
        y1 = height
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(x1, width), min(y1, height)
    if x1 <= x0 or y1 <= y0:
        return 255.0
    total = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            c1 = img1.pixelColor(x, y)
            c2 = img2.pixelColor(x, y)
            total += (
                abs(c1.red() - c2.red())
                + abs(c1.green() - c2.green())
                + abs(c1.blue() - c2.blue())
            )
    return total / ((x1 - x0) * (y1 - y0) * 3)


def _region_scores(img_qt: QImage, img_l: QImage) -> dict[str, float]:
    """Per-region diff scores to pinpoint where differences are."""
    w, h = min(img_qt.width(), img_l.width()), min(img_qt.height(), img_l.height())
    regions = {
        "left ": (0,       0,       w // 4,     h),
        "right": (3*w//4,  0,       w,          h),
        "top  ": (0,       0,       w,          h // 5),
        "bot  ": (0,       4*h//5,  w,          h),
        "centr": (w // 4,  h // 5,  3*w // 4,   4*h // 5),
    }
    return {
        name: _avg_image_diff(img_qt, img_l, x0, y0, x1, y1)
        for name, (x0, y0, x1, y1) in regions.items()
    }


def _make_diff_image(img1: QImage, img2: QImage, scale: int = 5) -> QImage:
    """Amplified per-pixel difference image (differences scaled for visibility)."""
    width = min(img1.width(), img2.width())
    height = min(img1.height(), img2.height())
    out = QImage(width, height, QImage.Format.Format_RGB32)
    out.fill(QColor(0, 0, 0))
    for y in range(height):
        for x in range(width):
            c1 = img1.pixelColor(x, y)
            c2 = img2.pixelColor(x, y)
            dr = min(255, abs(c1.red() - c2.red()) * scale)
            dg = min(255, abs(c1.green() - c2.green()) * scale)
            db = min(255, abs(c1.blue() - c2.blue()) * scale)
            out.setPixelColor(x, y, QColor(dr, dg, db))
    return out


def _make_side_by_side(img_qt: QImage, img_l: QImage, diff: QImage, label: str) -> QImage:
    """Composite: [Qt label | ldocking label | diff label] + images below."""
    gap = 6
    bar_h = 20
    w = img_qt.width()
    h = img_qt.height()
    total_w = w * 3 + gap * 2
    total_h = h + bar_h
    out = QImage(total_w, total_h, QImage.Format.Format_RGB32)
    out.fill(QColor(40, 40, 40))

    painter = QPainter(out)

    def _label_band(x: int, text: str, color: QColor) -> None:
        painter.fillRect(x, 0, w, bar_h, color)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(x, 0, w, bar_h, Qt.AlignmentFlag.AlignCenter, text)

    _label_band(0, f"Qt  ({label})", QColor(30, 100, 30))
    _label_band(w + gap, f"ldocking  ({label})", QColor(20, 60, 120))
    _label_band(w * 2 + gap * 2, "diff ×5", QColor(100, 40, 40))

    painter.drawImage(0, bar_h, img_qt)
    painter.drawImage(w + gap, bar_h, img_l)
    painter.drawImage(w * 2 + gap * 2, bar_h, diff)
    painter.end()
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", default=os.path.join(os.path.dirname(__file__), "screenshots"))
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")

    results: list[tuple[str, float]] = []

    for layout_name in LAYOUTS:
        slug = layout_name.lower().replace(" ", "_")
        print(f"  Capturing: {layout_name} ...", end=" ", flush=True)

        qt_win = _build_qt_window(layout_name)
        l_win = _build_l_window(layout_name)

        qt_docks = [d for d in qt_win.findChildren(_QtDockWidget)]
        # Preserve creation order by matching titles
        ordered_titles = [t for t, _ in LAYOUTS[layout_name]]
        qt_docks_ordered = sorted(qt_docks, key=lambda d: ordered_titles.index(d.windowTitle()) if d.windowTitle() in ordered_titles else 99)
        l_docks_ordered = []  # built in order inside _build_l_window
        for title, _ in LAYOUTS[layout_name]:
            for d in l_win.findChildren(LDockWidget):
                if d.windowTitle() == title and d not in l_docks_ordered:
                    l_docks_ordered.append(d)
                    break

        qt_win.show()
        l_win.show()
        for _ in range(6):
            app.processEvents()

        _equalize_sizes(qt_win, l_win, layout_name, qt_docks_ordered, l_docks_ordered)
        for _ in range(4):
            app.processEvents()

        img_qt = qt_win.grab().toImage().scaled(
            WINDOW_SIZE, Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        img_l = l_win.grab().toImage().scaled(
            WINDOW_SIZE, Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        diff_img = _make_diff_image(img_qt, img_l)
        composite = _make_side_by_side(img_qt, img_l, diff_img, layout_name)

        QPixmap.fromImage(img_qt).save(os.path.join(args.outdir, f"{slug}_qt.png"))
        QPixmap.fromImage(img_l).save(os.path.join(args.outdir, f"{slug}_l.png"))
        QPixmap.fromImage(composite).save(os.path.join(args.outdir, f"{slug}_side_by_side.png"))

        score = _avg_image_diff(img_qt, img_l)
        regions = _region_scores(img_qt, img_l)
        region_str = "  ".join(f"{k}={v:.1f}" for k, v in regions.items())
        results.append((layout_name, score))
        print(f"diff={score:.2f}  [{region_str}]")

        qt_win.hide()
        l_win.hide()
        qt_win.deleteLater()
        l_win.deleteLater()
        app.processEvents()

    print()
    print("=" * 48)
    print(f"{'Mode':<20}  {'Avg diff':>8}  {'Status'}")
    print("-" * 48)
    for name, score in sorted(results, key=lambda x: -x[1]):
        status = "OK" if score <= 12.0 else ("WARN" if score <= 20.0 else "FAIL")
        print(f"{name:<20}  {score:>8.2f}  {status}")
    print("=" * 48)
    print(f"Screenshots saved to: {args.outdir}")


if __name__ == "__main__":
    main()
