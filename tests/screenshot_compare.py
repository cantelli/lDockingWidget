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

from PySide6.QtCore import QPoint, Qt, QSize
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
from compare_scenarios import SCENARIOS

# Pane size: each comparison pane is shown at this size so docks have enough
# room to render real widget content visibly.
PANE_SIZE = QSize(760, 720)

# All screenshots are scaled to this common size before diffing and saving.
WINDOW_SIZE = QSize(760, 720)
UNDOCK_ALL_DOCKS = ("Inspector", "Assets", "Layers", "Console")


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


def _save_side_by_side(outdir: str, stem: str, img_qt: QImage, img_l: QImage) -> float:
    """Save paired Qt/ldocking images plus a diff composite. Returns avg diff."""
    diff = _make_diff_image(img_qt, img_l)
    composite = _make_side_by_side(img_qt, img_l, diff, stem)
    QPixmap.fromImage(img_qt).save(os.path.join(outdir, f"{stem}_qt.png"))
    QPixmap.fromImage(img_l).save(os.path.join(outdir, f"{stem}_l.png"))
    QPixmap.fromImage(composite).save(os.path.join(outdir, f"{stem}_side_by_side.png"))
    return _avg_image_diff(img_qt, img_l)


def _dock_by_title(docks, title: str):
    for dock in docks:
        if dock.windowTitle() == title:
            return dock
    raise KeyError(f"Missing dock {title!r}")


def _scene_image(docks) -> QImage:
    visible_docks = [dock for dock in docks if dock.isVisible()]
    if not visible_docks:
        img = QImage(32, 32, QImage.Format.Format_RGB32)
        img.fill(QColor("#f1f5f9"))
        return img

    rects = [dock.geometry() for dock in visible_docks]
    min_x = min(rect.x() for rect in rects)
    min_y = min(rect.y() for rect in rects)
    max_x = max(rect.right() for rect in rects)
    max_y = max(rect.bottom() for rect in rects)
    pad = 20
    canvas = QImage(
        max_x - min_x + 1 + pad * 2,
        max_y - min_y + 1 + pad * 2,
        QImage.Format.Format_RGB32,
    )
    canvas.fill(QColor("#f1f5f9"))

    painter = QPainter(canvas)
    for dock in visible_docks:
        offset = QPoint(
            dock.geometry().x() - min_x + pad,
            dock.geometry().y() - min_y + pad,
        )
        painter.drawImage(offset, dock.grab().toImage())
    painter.end()
    return canvas


def _dispose_panes(app: QApplication, *panes) -> None:
    for pane in panes:
        window = getattr(pane, "window", None)
        for dock in getattr(pane, "docks", []):
            dock.hide()
            dock.setParent(None)
            dock.deleteLater()
        if window is not None:
            window.hide()
            window.setParent(None)
            window.deleteLater()
        pane.hide()
        pane.setParent(None)
        pane.deleteLater()
    for _ in range(4):
        app.processEvents()


def _dock_metrics(pane) -> dict[str, dict[str, object]]:
    metrics: dict[str, dict[str, object]] = {}
    for dock in pane.docks:
        rect = dock.geometry()
        metrics[dock.windowTitle()] = {
            "floating": dock.isFloating(),
            "visible": dock.isVisible(),
            "rect": (rect.x(), rect.y(), rect.width(), rect.height()),
        }
    return metrics


# ---------------------------------------------------------------------------
# Size equalization helper
# ---------------------------------------------------------------------------

def _equalize_pane_sizes(qt_pane, l_pane, layout_name: str, app: QApplication) -> None:
    """Apply Qt's natural dock sizes to the ldocking pane for fair comparison."""
    from visual_compare_demo import LAYOUTS

    qt_win = qt_pane.window
    l_win  = l_pane.window

    qt_docks_by_title = {d.windowTitle(): d for d in qt_pane.docks}
    l_docks_by_title  = {d.windowTitle(): d for d in l_pane.docks}

    Left   = Qt.DockWidgetArea.LeftDockWidgetArea
    Right  = Qt.DockWidgetArea.RightDockWidgetArea
    Bottom = Qt.DockWidgetArea.BottomDockWidgetArea

    areas_seen: set = set()
    for title, area in LAYOUTS[layout_name]:
        if area in areas_seen:
            continue
        areas_seen.add(area)
        qt_d = qt_docks_by_title.get(title)
        l_d  = l_docks_by_title.get(title)
        if qt_d is None or l_d is None:
            continue
        if area in (Left, Right):
            w = qt_d.width()
            qt_win.resizeDocks([qt_d], [w], Qt.Orientation.Horizontal)
            l_win.resizeDocks([l_d],  [w], Qt.Orientation.Horizontal)
        if area == Bottom:
            h = qt_d.height()
            qt_win.resizeDocks([qt_d], [h], Qt.Orientation.Vertical)
            l_win.resizeDocks([l_d],  [h], Qt.Orientation.Vertical)
    for _ in range(4):
        app.processEvents()


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

        _equalize_pane_sizes(qt_pane, l_pane, layout_name, app)

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

        _dispose_panes(app, qt_pane, l_pane)

    # Restore global app state
    if saved_style:
        app.setStyle(saved_style)
    app.setPalette(saved_palette)
    app.setStyleSheet(saved_stylesheet)

    return results


def capture_float_redock_states(outdir: str, app: QApplication) -> list[tuple[str, float]]:
    """Capture float and redock states. Returns [(name, score), ...]."""
    from visual_compare_demo import QtComparisonPane, LDockingComparisonPane

    results: list[tuple[str, float]] = []
    os.makedirs(outdir, exist_ok=True)
    saved_palette = app.palette()
    saved_stylesheet = app.styleSheet()
    saved_style = app.style().objectName() if app.style() else None
    _apply_demo_style(app)

    layout_name = "Balanced"

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

    _equalize_pane_sizes(qt_pane, l_pane, layout_name, app)

    # --- State 1: After floating Inspector ---
    print("  Capturing: float_main ...", end=" ", flush=True)
    qt_pane.float_first()
    l_pane.float_first()
    for _ in range(6):
        app.processEvents()

    img_qt_main = qt_pane.window.grab().toImage().scaled(
        WINDOW_SIZE,
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    img_l_main = l_pane.window.grab().toImage().scaled(
        WINDOW_SIZE,
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    score_main = _save_side_by_side(outdir, "float_main", img_qt_main, img_l_main)
    results.append(("float_main", score_main))
    print(f"diff={score_main:.2f}")

    # Grab the floating dock itself
    print("  Capturing: float_dock ...", end=" ", flush=True)
    qt_dock_img = qt_pane.docks[0].grab().toImage().scaled(
        WINDOW_SIZE,
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    l_dock_img = l_pane.docks[0].grab().toImage().scaled(
        WINDOW_SIZE,
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    score_dock = _save_side_by_side(outdir, "float_dock", qt_dock_img, l_dock_img)
    results.append(("float_dock", score_dock))
    print(f"diff={score_dock:.2f}  (expected: large — different chrome by design)")

    # --- State 2: After redocking Inspector ---
    print("  Capturing: redock ...", end=" ", flush=True)
    qt_pane.docks[0].setFloating(False)
    l_pane.docks[0].setFloating(False)
    for _ in range(8):
        app.processEvents()

    img_qt_redock = qt_pane.window.grab().toImage().scaled(
        WINDOW_SIZE,
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    img_l_redock = l_pane.window.grab().toImage().scaled(
        WINDOW_SIZE,
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    score_redock = _save_side_by_side(outdir, "redock", img_qt_redock, img_l_redock)
    results.append(("redock", score_redock))
    print(f"diff={score_redock:.2f}")

    _dispose_panes(app, qt_pane, l_pane)
    if saved_style:
        app.setStyle(saved_style)
    app.setPalette(saved_palette)
    app.setStyleSheet(saved_stylesheet)

    return results


def capture_undock_all_state(outdir: str, app: QApplication) -> list[tuple[str, float]]:
    """Capture the all-docks-floating shell, scene, and per-dock windows."""
    results: list[tuple[str, float]] = []
    os.makedirs(outdir, exist_ok=True)
    saved_palette = app.palette()
    saved_stylesheet = app.styleSheet()
    saved_style = app.style().objectName() if app.style() else None
    _apply_demo_style(app)

    qt_pane = QtComparisonPane()
    l_pane = LDockingComparisonPane()
    qt_pane.resize(PANE_SIZE)
    l_pane.resize(PANE_SIZE)
    qt_pane.show()
    l_pane.show()
    for _ in range(6):
        app.processEvents()

    layout_name = "Balanced"
    qt_pane.apply_layout(layout_name)
    l_pane.apply_layout(layout_name)
    for _ in range(6):
        app.processEvents()

    _equalize_pane_sizes(qt_pane, l_pane, layout_name, app)

    print("  Capturing: undock_all_main ...", end=" ", flush=True)
    for dock in qt_pane.docks:
        dock.setFloating(True)
    for dock in l_pane.docks:
        dock.setFloating(True)
    for _ in range(10):
        app.processEvents()

    img_qt_main = qt_pane.window.grab().toImage().scaled(
        WINDOW_SIZE,
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    img_l_main = l_pane.window.grab().toImage().scaled(
        WINDOW_SIZE,
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    score_main = _save_side_by_side(outdir, "undock_all_main", img_qt_main, img_l_main)
    results.append(("undock_all_main", score_main))
    print(f"diff={score_main:.2f}")

    print("  Capturing: undock_all_scene ...", end=" ", flush=True)
    score_scene = _save_side_by_side(
        outdir,
        "undock_all_scene",
        _scene_image(qt_pane.docks),
        _scene_image(l_pane.docks),
    )
    results.append(("undock_all_scene", score_scene))
    print(f"diff={score_scene:.2f}")

    for title in UNDOCK_ALL_DOCKS:
        stem = f"undock_all_{title.lower()}"
        print(f"  Capturing: {stem} ...", end=" ", flush=True)
        score_dock = _save_side_by_side(
            outdir,
            stem,
            _dock_by_title(qt_pane.docks, title).grab().toImage(),
            _dock_by_title(l_pane.docks, title).grab().toImage(),
        )
        results.append((stem, score_dock))
        print(f"diff={score_dock:.2f}")

    _dispose_panes(app, qt_pane, l_pane)
    if saved_style:
        app.setStyle(saved_style)
    app.setPalette(saved_palette)
    app.setStyleSheet(saved_stylesheet)

    return results


def capture_dynamic_scenarios(
    outdir: str,
    app: QApplication,
) -> tuple[list[tuple[str, float]], dict[str, dict[str, dict[str, dict[str, object]]]]]:
    """Capture step-by-step action scenarios and return scores plus geometry metrics."""
    results: list[tuple[str, float]] = []
    metrics: dict[str, dict[str, dict[str, dict[str, object]]]] = {}
    os.makedirs(outdir, exist_ok=True)
    saved_palette = app.palette()
    saved_stylesheet = app.styleSheet()
    saved_style = app.style().objectName() if app.style() else None
    _apply_demo_style(app)

    for scenario_name, scenario in SCENARIOS.items():
        qt_pane = QtComparisonPane()
        l_pane = LDockingComparisonPane()
        qt_pane.resize(PANE_SIZE)
        l_pane.resize(PANE_SIZE)
        qt_pane.show()
        l_pane.show()
        for _ in range(6):
            app.processEvents()

        layout_name = str(scenario["layout"])
        qt_pane.apply_layout(layout_name)
        l_pane.apply_layout(layout_name)
        for _ in range(6):
            app.processEvents()
        _equalize_pane_sizes(qt_pane, l_pane, layout_name, app)

        scenario_metrics: dict[str, dict[str, dict[str, object]]] = {}

        def _capture_step(step_index: int, label: str) -> None:
            stem = f"{scenario_name}__{step_index:02d}_{label}"
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
            score = _save_side_by_side(outdir, stem, img_qt, img_l)
            results.append((stem, score))
            scenario_metrics[label] = {
                "qt": _dock_metrics(qt_pane),
                "l": _dock_metrics(l_pane),
            }
            print(f"  Capturing: {stem} ... diff={score:.2f}")

        _capture_step(0, "initial")

        for index, action in enumerate(scenario["steps"], start=1):
            qt_pane.apply_action(action)
            l_pane.apply_action(action)
            for _ in range(8):
                app.processEvents()
            _capture_step(index, str(action["label"]))

        metrics[scenario_name] = scenario_metrics
        _dispose_panes(app, qt_pane, l_pane)

    if saved_style:
        app.setStyle(saved_style)
    app.setPalette(saved_palette)
    app.setStyleSheet(saved_stylesheet)
    return results, metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", default=os.path.join(os.path.dirname(__file__), "screenshots"))
    args = parser.parse_args()

    app = QApplication.instance() or QApplication(sys.argv)

    results = capture_all(args.outdir, app)
    results += capture_float_redock_states(args.outdir, app)
    results += capture_undock_all_state(args.outdir, app)
    dynamic_results, _ = capture_dynamic_scenarios(args.outdir, app)
    results += dynamic_results

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
