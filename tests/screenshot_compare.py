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
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
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


def _make_panel(title: str) -> QWidget:
    panel = QFrame()
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(6)
    heading = QLabel(title)
    heading.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    layout.addWidget(heading)
    grid = QGridLayout()
    for row, (k, v) in enumerate([("Mode", "Docked"), ("Visible", "Yes")]):
        grid.addWidget(QLabel(k), row, 0)
        grid.addWidget(QLabel(v), row, 1)
    layout.addLayout(grid)
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
        win.setDockOptions(win.dockOptions() | LMainWindow.AllowNestedDocks)
        win._drop_docks(
            Left,
            [docks[2]],
            mode="side",
            target_id=docks[0].windowTitle(),
            side=Bottom,
        )
    elif layout_name == "Grouped Tabs" and len(docks) >= 3:
        win.setDockOptions(
            win.dockOptions() | LMainWindow.ForceTabbedDocks | LMainWindow.GroupedDragging
        )

    win.setStyleSheet(translate_stylesheet(PURE_QT_QSS))
    return win


# ---------------------------------------------------------------------------
# Image diff helpers
# ---------------------------------------------------------------------------

def _avg_image_diff(img1: QImage, img2: QImage) -> float:
    width = min(img1.width(), img2.width())
    height = min(img1.height(), img2.height())
    if width <= 0 or height <= 0:
        return 255.0
    total = 0
    for y in range(height):
        for x in range(width):
            c1 = img1.pixelColor(x, y)
            c2 = img2.pixelColor(x, y)
            total += (
                abs(c1.red() - c2.red())
                + abs(c1.green() - c2.green())
                + abs(c1.blue() - c2.blue())
            )
    return total / (width * height * 3)


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

        qt_win.show()
        l_win.show()
        app.processEvents()
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
        results.append((layout_name, score))
        print(f"diff={score:.2f}")

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
