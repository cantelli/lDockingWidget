"""Screenshot capture + diff tool for Qt vs ldocking visual parity.

Usage:
    python tests/screenshot_compare.py [--outdir tests/screenshots]

For each layout preset this script:
  - Creates Qt and ldocking comparison panes (identical to visual_compare_demo.py)
  - Grabs screenshots of each embedded window
  - Saves <mode>_qt.png, <mode>_l.png, <mode>_side_by_side.png
  - Prints a ranked diff score table

Run on a desktop (not headless) to get screenshots that look exactly like the
visual compare app with real widget content.  pytest runs this in offscreen mode
(QT_QPA_PLATFORM=offscreen set by conftest.py) for CI validation of scores.
"""
from __future__ import annotations

import os
import sys
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))  # so visual_compare_demo is importable

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

# Reuse the exact same comparison pane classes and layout definitions used in
# the interactive demo so screenshots look identical to what the user sees.
from visual_compare_demo import (
    LAYOUTS,
    QtComparisonPane,
    LDockingComparisonPane,
    _apply_demo_style,
)

# Pane size: each comparison pane is shown at this size so docks have enough
# room to render real widget content visibly.
PANE_SIZE = QSize(760, 720)

# All screenshots are scaled to this common size before diffing and saving.
WINDOW_SIZE = QSize(760, 720)


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
# Main capture loop (also called by test_screenshot_compare.py)
# ---------------------------------------------------------------------------

def capture_all(outdir: str, app: QApplication) -> list[tuple[str, float]]:
    """Capture all layouts, save PNGs to *outdir*, return [(name, score), ...]."""
    # Save global app state so we can restore it after capture — prevents
    # _apply_demo_style()'s palette/stylesheet changes from leaking into
    # subsequent pytest tests that check specific colors.
    saved_palette = app.palette()
    saved_stylesheet = app.styleSheet()
    saved_style = app.style().objectName() if app.style() else None

    _apply_demo_style(app)
    os.makedirs(outdir, exist_ok=True)
    results: list[tuple[str, float]] = []

    for layout_name in LAYOUTS:
        slug = layout_name.lower().replace(" ", "_")
        print(f"  Capturing: {layout_name} ...", end=" ", flush=True)

        qt_pane = QtComparisonPane()
        l_pane = LDockingComparisonPane()

        qt_pane.resize(PANE_SIZE)
        l_pane.resize(PANE_SIZE)
        qt_pane.show()
        l_pane.show()
        for _ in range(6):
            app.processEvents()

        qt_pane.apply_layout(layout_name)
        l_pane.apply_layout(layout_name)
        for _ in range(6):
            app.processEvents()

        # Grab the embedded QMainWindow / LMainWindow — identical to the pane
        # the user sees in visual_compare_demo.py.
        img_qt = qt_pane.window.grab().toImage().scaled(
            WINDOW_SIZE,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        img_l = l_pane.window.grab().toImage().scaled(
            WINDOW_SIZE,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        diff_img = _make_diff_image(img_qt, img_l)
        composite = _make_side_by_side(img_qt, img_l, diff_img, layout_name)

        QPixmap.fromImage(img_qt).save(os.path.join(outdir, f"{slug}_qt.png"))
        QPixmap.fromImage(img_l).save(os.path.join(outdir, f"{slug}_l.png"))
        QPixmap.fromImage(composite).save(os.path.join(outdir, f"{slug}_side_by_side.png"))

        score = _avg_image_diff(img_qt, img_l)
        regions = _region_scores(img_qt, img_l)
        region_str = "  ".join(f"{k}={v:.1f}" for k, v in regions.items())
        results.append((layout_name, score))
        print(f"diff={score:.2f}  [{region_str}]")

        qt_pane.hide()
        l_pane.hide()
        qt_pane.deleteLater()
        l_pane.deleteLater()
        app.processEvents()

    # Restore global app state
    if saved_style:
        app.setStyle(saved_style)
    app.setPalette(saved_palette)
    app.setStyleSheet(saved_stylesheet)

    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", default=os.path.join(os.path.dirname(__file__), "screenshots"))
    args = parser.parse_args()

    app = QApplication.instance() or QApplication(sys.argv)

    results = capture_all(args.outdir, app)

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
