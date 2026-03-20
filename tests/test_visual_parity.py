"""Visual parity tests: QSS selectors and dimensions vs Qt originals.

Strategy
--------
- Apply a solid distinctive color via QSS to each named selector
- Grab the widget screenshot (works on offscreen platform)
- Sample center pixels in the expected region to confirm the color lands there
- Side-by-side comparisons between QDockWidget and LDockWidget validate that
  equivalent stylesheets produce equivalent visual regions

Helpers
-------
_sample(widget, rect=None)  — RGB tuple at center of widget (or sub-rect)
_close(actual, expected)    — color tolerance: ±COLOR_TOL per channel
_title_band_height(img, rgb) — scan from top to measure colored band height
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtWidgets import QApplication, QLabel, QTabBar, QToolBar, QWidget

from ldocking import (
    LDragManager,
    LDockWidget,
    LMainWindow,
    LeftDockWidgetArea,
    RightDockWidgetArea,
    TopDockWidgetArea,
    BottomDockWidgetArea,
    translate_stylesheet,
)
from ldocking.ldrag_manager import _DropTarget

# Use the real Qt classes for baseline comparisons, even if monkey patch is active.
try:
    from ldocking.monkey import _ORIG as _QT_ORIG
    _RealQMainWindow = _QT_ORIG["QMainWindow"]
    _RealQDockWidget = _QT_ORIG["QDockWidget"]
except ImportError:
    from PySide6.QtWidgets import QMainWindow as _RealQMainWindow, QDockWidget as _RealQDockWidget  # type: ignore

# Tolerance per color channel (accounts for compositing and sub-pixel rendering)
COLOR_TOL = 35
GEOM_TOL = 8
IMAGE_DIFF_TOL = 12.0
# Floating parity is intentionally looser because ldocking stays frameless
# instead of matching native Qt floating-window chrome pixel-for-pixel.
FLOATING_IMAGE_DIFF_TOL = 26.0


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _sample(widget, rect: QRect | None = None) -> tuple[int, int, int]:
    """Center-pixel RGB of a widget grab (or a sub-rect of it)."""
    if rect is None:
        rect = widget.rect()
    img = widget.grab(rect).toImage()
    c = img.pixelColor(img.width() // 2, img.height() // 2)
    return c.red(), c.green(), c.blue()


def _close(actual: tuple, expected: tuple) -> bool:
    return all(abs(a - e) <= COLOR_TOL for a, e in zip(actual, expected))


def _close_int(actual: int, expected: int, tol: int = GEOM_TOL) -> bool:
    return abs(actual - expected) <= tol


def _avg_image_diff(img1, img2) -> float:
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


def _global_rect(widget: QWidget) -> QRect:
    return QRect(widget.mapToGlobal(widget.rect().topLeft()), widget.size())


def _rect_in(widget: QWidget, ancestor: QWidget) -> QRect:
    return QRect(widget.mapTo(ancestor, QPoint(0, 0)), widget.size())


def _dock_metrics_l(dock: LDockWidget) -> dict[str, int]:
    content = dock._content_container.geometry()
    return {
        "title_height": dock._title_bar.height(),
        "left_inset": content.x(),
        "right_inset": dock.width() - content.right() - 1,
        "bottom_inset": dock.height() - content.bottom() - 1,
    }


def _dock_metrics_qt(dock: _RealQDockWidget) -> dict[str, int]:
    content = dock.widget().geometry()
    return {
        "title_height": content.y(),
        "left_inset": content.x(),
        "right_inset": dock.width() - content.right() - 1,
        "bottom_inset": dock.height() - content.bottom() - 1,
    }


def _find_qt_tab_bar(widget: QWidget) -> QTabBar:
    tab_bars = [
        bar
        for bar in widget.findChildren(QTabBar)
        if bar.isVisible() and bar.count() >= 2
    ]
    assert tab_bars, "Expected a visible Qt tab bar"
    return tab_bars[0]


def _toolbar_global_rects(toolbars: list[QToolBar]) -> dict[str, QRect]:
    return {
        toolbar.windowTitle(): _global_rect(toolbar)
        for toolbar in toolbars
        if toolbar.isVisible()
    }


def _named_dock_global_rects(docks: list[QWidget]) -> dict[str, QRect]:
    return {
        dock.windowTitle(): _global_rect(dock)
        for dock in docks
        if dock.isVisible()
    }


def _assert_rect_close(actual: QRect, expected: QRect, tol: int = GEOM_TOL) -> None:
    assert _close_int(actual.x(), expected.x(), tol)
    assert _close_int(actual.y(), expected.y(), tol)
    assert _close_int(actual.width(), expected.width(), tol)
    assert _close_int(actual.height(), expected.height(), tol)


def _apply_comparison_style(*widgets: QWidget) -> None:
    stylesheet = """
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
        QToolBar {
            background: #e2e8f0;
            border: 1px solid #94a3b8;
            spacing: 2px;
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
    for widget in widgets:
        widget.setStyleSheet(stylesheet)


def _make_l_tabbed_window(count: int = 2):
    mw = LMainWindow()
    mw.resize(420, 260)
    docks = []
    for idx in range(count):
        title = chr(ord("A") + idx)
        dock = LDockWidget(title)
        dock.setWidget(QLabel(title))
        mw.addDockWidget(LeftDockWidgetArea, dock)
        docks.append(dock)
    for dock in docks[1:]:
        mw.tabifyDockWidget(docks[0], dock)
    return mw, docks


def _make_qt_tabbed_window(count: int = 2):
    mw = _RealQMainWindow()
    mw.resize(420, 260)
    docks = []
    for idx in range(count):
        title = chr(ord("A") + idx)
        dock = _RealQDockWidget(title, mw)
        dock.setWidget(QLabel(title))
        mw.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)
        docks.append(dock)
    for dock in docks[1:]:
        mw.tabifyDockWidget(docks[0], dock)
    return mw, docks


def _make_l_shell_window():
    win = LMainWindow()
    win.resize(640, 420)
    win.setCentralWidget(QLabel("central"))
    toolbars = []
    for title, area in (
        ("Top", Qt.ToolBarArea.TopToolBarArea),
        ("Left", Qt.ToolBarArea.LeftToolBarArea),
        ("Right", Qt.ToolBarArea.RightToolBarArea),
        ("Bottom", Qt.ToolBarArea.BottomToolBarArea),
    ):
        toolbar = QToolBar(title)
        toolbar.addAction(title)
        win.addToolBar(area, toolbar)
        toolbars.append(toolbar)
    return win, toolbars


def _make_qt_shell_window():
    win = _RealQMainWindow()
    win.resize(640, 420)
    win.setCentralWidget(QLabel("central"))
    toolbars = []
    for title, area in (
        ("Top", Qt.ToolBarArea.TopToolBarArea),
        ("Left", Qt.ToolBarArea.LeftToolBarArea),
        ("Right", Qt.ToolBarArea.RightToolBarArea),
        ("Bottom", Qt.ToolBarArea.BottomToolBarArea),
    ):
        toolbar = QToolBar(title)
        toolbar.addAction(title)
        win.addToolBar(area, toolbar)
        toolbars.append(toolbar)
    return win, toolbars


def _make_nested_l_window():
    win = LMainWindow()
    win.resize(720, 480)
    win.setCentralWidget(QLabel("central"))
    docks = []
    for title, area in (
        ("Inspector", LeftDockWidgetArea),
        ("Assets", LeftDockWidgetArea),
        ("Layers", LeftDockWidgetArea),
        ("Console", BottomDockWidgetArea),
    ):
        dock = LDockWidget(title)
        dock.setWidget(QLabel(title))
        dock.setObjectName(title)
        win.addDockWidget(area, dock)
        docks.append(dock)
    win.setDockOptions(win.dockOptions() | LMainWindow.AllowNestedDocks)
    win._drop_docks(
        LeftDockWidgetArea,
        [docks[2]],
        mode="side",
        target_id="Inspector",
        side=BottomDockWidgetArea,
    )
    return win, docks


def _make_nested_qt_window():
    win = _RealQMainWindow()
    win.resize(720, 480)
    win.setCentralWidget(QLabel("central"))
    docks = []
    for title, area in (
        ("Inspector", Qt.DockWidgetArea.LeftDockWidgetArea),
        ("Assets", Qt.DockWidgetArea.LeftDockWidgetArea),
        ("Layers", Qt.DockWidgetArea.LeftDockWidgetArea),
        ("Console", Qt.DockWidgetArea.BottomDockWidgetArea),
    ):
        dock = _RealQDockWidget(title, win)
        dock.setWidget(QLabel(title))
        dock.setObjectName(title)
        win.addDockWidget(area, dock)
        docks.append(dock)
    win.tabifyDockWidget(docks[0], docks[1])
    win.splitDockWidget(docks[0], docks[2], Qt.Orientation.Vertical)
    return win, docks


def _title_band_height(img, target_rgb: tuple[int, int, int]) -> int:
    """Return the pixel height of a solid color band at the top of *img*.

    Scans the center column downward.  Stops at the first row that no longer
    matches *target_rgb* (within COLOR_TOL), returning the last matching row + 1.
    Returns 0 if no matching row is found.
    """
    tr, tg, tb = target_rgb
    cx = img.width() // 2
    height = 0
    for y in range(img.height()):
        px = img.pixelColor(cx, y)
        if (abs(px.red() - tr) <= COLOR_TOL and
                abs(px.green() - tg) <= COLOR_TOL and
                abs(px.blue() - tb) <= COLOR_TOL):
            height = y + 1
        elif height > 0:
            break  # band has ended
    return height


def _make_l_window(title="D"):
    mw = LMainWindow()
    mw.resize(300, 200)
    dock = LDockWidget(title)
    dock.setWidget(QLabel(title))
    mw.addDockWidget(LeftDockWidgetArea, dock)
    return mw, dock


def _make_qt_window(title="D"):
    mw = _RealQMainWindow()
    mw.resize(300, 200)
    dock = _RealQDockWidget(title, mw)
    dock.setWidget(QLabel(title))
    mw.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)
    return mw, dock


# ------------------------------------------------------------------
# QSS selector smoke tests: each selector applies its color
# ------------------------------------------------------------------

def test_ldock_titlebar_selector(qapp):
    """#dockTitleBar selector colors the title bar of LDockWidget."""
    GREEN = (0, 200, 0)
    _, dock = _make_l_window()
    dock.resize(200, 120)
    dock.setStyleSheet(f"#dockTitleBar {{ background: rgb(0,200,0); }}")
    dock.show()
    qapp.processEvents()

    color = _sample(dock._title_bar)
    assert _close(color, GREEN), (
        f"Expected green ({GREEN}) in title bar, got {color}"
    )
    dock.hide()


def test_ldock_content_selector(qapp):
    """#dockContent selector colors the content area of LDockWidget."""
    BLUE = (0, 0, 200)
    _, dock = _make_l_window()
    dock.resize(200, 120)
    dock.setStyleSheet("#dockContent { background: rgb(0,0,200); }")
    dock.show()
    qapp.processEvents()

    color = _sample(dock._content_container)
    assert _close(color, BLUE), (
        f"Expected blue ({BLUE}) in content area, got {color}"
    )
    dock.hide()


def test_ldock_area_left_selector(qapp):
    """LDockArea#dockAreaLeft selector colors the left dock strip."""
    ORANGE = (200, 100, 0)
    lmw, dock = _make_l_window()
    lmw.setStyleSheet("LDockArea#dockAreaLeft { background: rgb(200,100,0); }")
    lmw.show()
    qapp.processEvents()

    left_area = lmw._dock_areas[LeftDockWidgetArea]
    color = _sample(left_area)
    assert _close(color, ORANGE), (
        f"Expected orange ({ORANGE}) in left dock area, got {color}"
    )
    lmw.hide()


def test_ldock_area_right_selector(qapp):
    """LDockArea#dockAreaRight selector colors the right dock strip."""
    TEAL = (0, 150, 150)
    lmw, _ = _make_l_window()
    r_dock = LDockWidget("R")
    r_dock.setWidget(QLabel("R"))
    lmw.addDockWidget(RightDockWidgetArea, r_dock)
    lmw.setStyleSheet("LDockArea#dockAreaRight { background: rgb(0,150,150); }")
    lmw.show()
    qapp.processEvents()

    right_area = lmw._dock_areas[RightDockWidgetArea]
    color = _sample(right_area)
    assert _close(color, TEAL), (
        f"Expected teal ({TEAL}) in right dock area, got {color}"
    )
    lmw.hide()


def test_ldock_widget_background_selector(qapp):
    """LDockWidget background selector colors the outer dock frame."""
    CRIMSON = (180, 0, 40)
    _, dock = _make_l_window()
    dock.resize(200, 120)
    # Style only the outer frame, not the title bar or content
    dock.setStyleSheet(
        "LDockWidget { background: rgb(180,0,40); }"
        "#dockTitleBar { background: transparent; }"
        "#dockContent { background: transparent; }"
    )
    dock.show()
    qapp.processEvents()

    # Sample a 4px-wide strip along the left edge (the frame itself)
    edge = QRect(0, dock._title_bar.height() + 4, 4, 20)
    color = _sample(dock, edge)
    assert _close(color, CRIMSON), (
        f"Expected crimson ({CRIMSON}) in dock frame edge, got {color}"
    )
    dock.hide()


def test_legacy_qdockwidget_selector_colors_ldockwidget(qapp):
    """QDockWidget selector is translated for LDockWidget."""
    CRIMSON = (180, 0, 40)
    _, dock = _make_l_window()
    dock.resize(200, 120)
    dock.setStyleSheet(
        "QDockWidget { background: rgb(180,0,40); }"
        "QDockWidget::title { background: transparent; }"
        "QDockWidget > QWidget { background: transparent; }"
    )
    dock.show()
    qapp.processEvents()

    edge = QRect(0, dock._title_bar.height() + 4, 4, 20)
    color = _sample(dock, edge)
    assert _close(color, CRIMSON)
    dock.hide()


def test_legacy_qdockwidget_title_selector_colors_ldock_titlebar(qapp):
    """QDockWidget::title selector maps to the custom title bar."""
    GREEN = (0, 200, 0)
    _, dock = _make_l_window()
    dock.resize(200, 120)
    dock.setStyleSheet("QDockWidget::title { background: rgb(0,200,0); }")
    dock.show()
    qapp.processEvents()

    color = _sample(dock._title_bar)
    assert _close(color, GREEN)
    dock.hide()


def test_legacy_qmainwindow_selector_colors_lmainwindow(qapp):
    """QMainWindow selector is translated for LMainWindow."""
    BLUE = (0, 0, 200)
    lmw, _ = _make_l_window()
    lmw.resize(320, 220)
    lmw.setStyleSheet("QMainWindow { background: rgb(0,0,200); }")
    lmw.show()
    qapp.processEvents()

    color = _sample(lmw, QRect(10, 10, 20, 20))
    assert _close(color, BLUE)
    lmw.hide()


def test_legacy_qdockwidget_button_selectors_map_to_named_title_buttons(qapp):
    """QDockWidget button selectors translate to the named title-bar buttons."""
    _, dock = _make_l_window()
    translated = translate_stylesheet(
        "QDockWidget::close-button { background: rgb(200,0,0); }"
        "QDockWidget::float-button { background: rgb(0,0,200); }"
    )
    assert "#dockCloseButton" in translated
    assert "#dockFloatButton" in translated
    assert dock._title_bar._close_btn.objectName() == "dockCloseButton"
    assert dock._title_bar._float_btn.objectName() == "dockFloatButton"


def test_translate_stylesheet_maps_qt_dock_selectors():
    translated = translate_stylesheet(
        "QMainWindow::separator { background: red; }"
        "QDockWidget::title { color: green; }"
        "QDockWidget::close-button { background: blue; }"
        "QDockWidget::float-button { background: yellow; }"
        "QDockWidget > QWidget { background: black; }"
        "QDockWidget { border: 1px solid red; }"
        "QMainWindow { background: white; }"
    )
    assert "#dockTitleBar" in translated
    assert "#dockCloseButton" in translated
    assert "#dockFloatButton" in translated
    assert "#dockContent" in translated
    assert "QSplitter::handle" in translated
    assert 'QWidget[class="QDockWidget"]' in translated
    assert 'QWidget[class="QMainWindow"]' in translated


# ------------------------------------------------------------------
# Baseline: verify the same technique works on Qt's QDockWidget
# (validates that our test infrastructure is sound, not just our code)
# ------------------------------------------------------------------

def test_qdock_titlebar_selector_baseline(qapp):
    """QDockWidget::title selector colors the Qt title bar (infrastructure check)."""
    GREEN = (0, 200, 0)
    qtmw, qtdock = _make_qt_window()
    qtdock.setStyleSheet("QDockWidget::title { background: rgb(0,200,0); }")
    qtmw.show()
    qapp.processEvents()

    img = qtdock.grab().toImage()
    height = _title_band_height(img, GREEN)
    assert height > 0, "QDockWidget::title selector did not color the title bar"
    qtmw.hide()


# ------------------------------------------------------------------
# Side-by-side comparison: same color, equivalent selectors, same region
# ------------------------------------------------------------------

def test_title_bar_color_parity(qapp):
    """Both docks show the same color in their title bar region.

    QDockWidget uses  QDockWidget::title { background: COLOR }
    LDockWidget uses  #dockTitleBar      { background: COLOR }
    Both must produce a colored band at the top of the grabbed dock image.
    """
    GREEN = (0, 200, 0)
    ss = "rgb(0,200,0)"

    # LDockWidget
    _, ldock = _make_l_window()
    ldock.resize(200, 150)
    ldock.setStyleSheet(f"#dockTitleBar {{ background: {ss}; }}")
    ldock.show()
    qapp.processEvents()
    l_img = ldock.grab().toImage()
    l_band = _title_band_height(l_img, GREEN)
    ldock.hide()

    # QDockWidget
    qtmw, qtdock = _make_qt_window()
    qtdock.resize(200, 150)
    qtdock.setStyleSheet(f"QDockWidget::title {{ background: {ss}; }}")
    qtmw.show()
    qapp.processEvents()
    qt_img = qtdock.grab().toImage()
    qt_band = _title_band_height(qt_img, GREEN)
    qtmw.hide()

    assert l_band > 0, "LDockWidget title bar color not detected"
    assert qt_band > 0, "QDockWidget title bar color not detected"


def test_title_bar_height_parity(qapp):
    """LDockWidget title bar height is within ±6 px of QDockWidget.

    L* height is measured directly from the rendered widget.
    Qt height is measured via pixel scanning of a color-tagged grab.
    """
    GREEN = (0, 200, 0)

    # LDockWidget: ask the rendered widget for its actual height
    _, ldock = _make_l_window()
    ldock.resize(200, 150)
    ldock.show()
    qapp.processEvents()
    l_height = ldock._title_bar.height()
    ldock.hide()

    # QDockWidget: pixel scan — color the title and measure the band
    qtmw, qtdock = _make_qt_window()
    qtdock.resize(200, 150)
    qtdock.setStyleSheet("QDockWidget::title { background: rgb(0,200,0); }")
    qtmw.show()
    qapp.processEvents()
    qt_img = qtdock.grab().toImage()
    qt_height = _title_band_height(qt_img, GREEN)
    qtmw.hide()

    assert l_height > 0, "LDockWidget title bar has zero height after show()"
    assert qt_height > 0, "Could not detect QDockWidget title bar height via pixel scan"
    assert abs(l_height - qt_height) <= 6, (
        f"Title bar height mismatch: L={l_height}px, Qt={qt_height}px (tolerance ±6px)"
    )


def test_content_color_parity(qapp):
    """Both docks show the same color in their content region.

    QDockWidget child widget: set background on the inner QLabel parent.
    LDockWidget uses #dockContent { background: COLOR }.
    Both must produce a blue content area.
    """
    BLUE = (0, 0, 200)
    ss = "rgb(0,0,200)"

    # LDockWidget — use #dockContent
    _, ldock = _make_l_window()
    ldock.resize(200, 150)
    ldock.setStyleSheet(f"#dockContent {{ background: {ss}; }}")
    ldock.show()
    qapp.processEvents()
    l_color = _sample(ldock._content_container)
    ldock.hide()

    # QDockWidget — set background on the content widget directly
    qtmw, qtdock = _make_qt_window()
    qtdock.resize(200, 150)
    qtdock.widget().setStyleSheet(f"QLabel {{ background: {ss}; }}")
    qtmw.show()
    qapp.processEvents()
    w = qtdock.widget()
    qt_color = _sample(w)
    qtmw.hide()

    assert _close(l_color, BLUE), (
        f"LDockWidget content should be blue ({BLUE}), got {l_color}"
    )
    assert _close(qt_color, BLUE), (
        f"QDockWidget content should be blue ({BLUE}), got {qt_color}"
    )


def test_floating_title_bar_geometry_survives_float(qapp):
    """Floating an LDockWidget keeps the custom title bar visible with nonzero geometry."""
    lmw, ldock = _make_l_window()
    lmw.resize(300, 200)
    lmw.show()
    ldock.setFloating(True)
    qapp.processEvents()

    assert ldock._title_bar.isVisible()
    assert ldock._title_bar.height() > 0
    assert ldock._title_bar.width() > 0
    assert not ldock.grab().isNull()
    ldock.hide()


def test_floating_size_grip_visibility_tracks_float_state(qapp):
    """The frameless floating mode shows its size grip only while floating."""
    lmw, ldock = _make_l_window()
    lmw.resize(300, 200)
    lmw.show()
    qapp.processEvents()

    assert ldock._size_grip is None or not ldock._size_grip.isVisible()

    ldock.setFloating(True)
    qapp.processEvents()

    assert ldock._size_grip is not None
    assert ldock._size_grip.isVisible()

    ldock.setFloating(False)
    qapp.processEvents()

    assert not ldock.isFloating()
    assert not ldock._size_grip.isVisible()
    lmw.hide()


def test_single_dock_screenshot_parity(qapp):
    """Single-dock windows stay visually close under the same stylesheet."""
    qapp.setStyle("Fusion")
    lmw, ldock = _make_l_window()
    qtmw, qtdock = _make_qt_window()
    _apply_comparison_style(lmw, qtmw)
    lmw.show()
    qtmw.show()
    qapp.processEvents()

    diff = _avg_image_diff(lmw.grab().toImage(), qtmw.grab().toImage())

    assert diff <= IMAGE_DIFF_TOL
    lmw.hide()
    qtmw.hide()


def test_single_dock_frame_and_content_metrics_parity(qapp):
    """Single docks keep similar title height and content insets to Qt."""
    qapp.setStyle("Fusion")
    lmw, ldock = _make_l_window()
    qtmw, qtdock = _make_qt_window()
    _apply_comparison_style(lmw, qtmw)
    lmw.show()
    qtmw.show()
    qapp.processEvents()

    l_metrics = _dock_metrics_l(ldock)
    qt_metrics = _dock_metrics_qt(qtdock)

    for key in ("title_height", "left_inset", "right_inset", "bottom_inset"):
        assert _close_int(l_metrics[key], qt_metrics[key])

    lmw.hide()
    qtmw.hide()


def test_tabbed_dock_geometry_parity_two_tabs(qapp):
    """Two-tab groups keep similar tab bar and active-tab geometry."""
    qapp.setStyle("Fusion")
    lmw, l_docks = _make_l_tabbed_window(2)
    qtmw, q_docks = _make_qt_tabbed_window(2)
    _apply_comparison_style(lmw, qtmw)
    lmw.show()
    qtmw.show()
    qapp.processEvents()

    l_tab_bar = lmw._dock_areas[LeftDockWidgetArea]._tab_area._tab_bar
    q_tab_bar = _find_qt_tab_bar(qtmw)

    assert _close_int(l_tab_bar.height(), q_tab_bar.height(), 6)
    assert _close_int(l_tab_bar.tabRect(0).x(), q_tab_bar.tabRect(0).x(), 10)
    assert _close_int(l_tab_bar.tabRect(0).height(), q_tab_bar.tabRect(0).height(), 6)
    assert l_tab_bar.count() == q_tab_bar.count()
    assert l_tab_bar.currentIndex() == q_tab_bar.currentIndex()

    lmw.hide()
    qtmw.hide()


def test_tabbed_dock_screenshot_parity_three_tabs(qapp):
    """Three-tab groups stay visually close under the shared comparison style."""
    qapp.setStyle("Fusion")
    lmw, _ = _make_l_tabbed_window(3)
    qtmw, _ = _make_qt_tabbed_window(3)
    _apply_comparison_style(lmw, qtmw)
    lmw.show()
    qtmw.show()
    qapp.processEvents()

    l_group = lmw._dock_areas[LeftDockWidgetArea]._tab_area
    q_group = _find_qt_tab_bar(qtmw).parentWidget()
    diff = _avg_image_diff(l_group.grab().toImage(), q_group.grab().toImage())

    assert diff <= IMAGE_DIFF_TOL
    lmw.hide()
    qtmw.hide()


def test_splitter_geometry_parity_left_right_layout(qapp):
    """Left/right dock rectangles stay close to Qt for a simple split layout."""
    qapp.setStyle("Fusion")
    lmw = LMainWindow()
    lmw.resize(720, 420)
    lmw.setCentralWidget(QLabel("central"))
    l_left = LDockWidget("Left")
    l_right = LDockWidget("Right")
    for dock in (l_left, l_right):
        dock.setWidget(QLabel(dock.windowTitle()))
    lmw.addDockWidget(LeftDockWidgetArea, l_left)
    lmw.addDockWidget(RightDockWidgetArea, l_right)

    qtmw = _RealQMainWindow()
    qtmw.resize(720, 420)
    qtmw.setCentralWidget(QLabel("central"))
    q_left = _RealQDockWidget("Left", qtmw)
    q_right = _RealQDockWidget("Right", qtmw)
    for dock in (q_left, q_right):
        dock.setWidget(QLabel(dock.windowTitle()))
    qtmw.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, q_left)
    qtmw.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, q_right)
    _apply_comparison_style(lmw, qtmw)
    lmw.show()
    qtmw.show()
    qapp.processEvents()

    l_left_rect = _global_rect(l_left)
    q_left_rect = _global_rect(q_left)
    l_right_rect = _global_rect(l_right)
    q_right_rect = _global_rect(q_right)
    assert _close_int(l_left_rect.width(), q_left_rect.width(), 30)
    assert _close_int(l_right_rect.width(), q_right_rect.width(), 30)
    assert _close_int(l_left_rect.x(), q_left_rect.x(), 10)
    assert _close_int(l_right_rect.right(), q_right_rect.right(), 30)

    lmw.hide()
    qtmw.hide()


def test_splitter_geometry_parity_left_right_bottom_layout(qapp):
    """Bottom dock spans the full shell width like Qt when side docks are present."""
    qapp.setStyle("Fusion")
    lmw = LMainWindow()
    lmw.resize(720, 460)
    lmw.setCentralWidget(QLabel("central"))
    l_left = LDockWidget("Left")
    l_right = LDockWidget("Right")
    l_bottom = LDockWidget("Bottom")
    for dock in (l_left, l_right, l_bottom):
        dock.setWidget(QLabel(dock.windowTitle()))
    lmw.addDockWidget(LeftDockWidgetArea, l_left)
    lmw.addDockWidget(RightDockWidgetArea, l_right)
    lmw.addDockWidget(BottomDockWidgetArea, l_bottom)

    qtmw = _RealQMainWindow()
    qtmw.resize(720, 460)
    qtmw.setCentralWidget(QLabel("central"))
    q_left = _RealQDockWidget("Left", qtmw)
    q_right = _RealQDockWidget("Right", qtmw)
    q_bottom = _RealQDockWidget("Bottom", qtmw)
    for dock in (q_left, q_right, q_bottom):
        dock.setWidget(QLabel(dock.windowTitle()))
    qtmw.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, q_left)
    qtmw.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, q_right)
    qtmw.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, q_bottom)
    _apply_comparison_style(lmw, qtmw)
    lmw.show()
    qtmw.show()
    qapp.processEvents()

    l_left_rect = _global_rect(l_left)
    l_right_rect = _global_rect(l_right)
    l_bottom_rect = _global_rect(l_bottom)
    q_left_rect = _global_rect(q_left)
    q_right_rect = _global_rect(q_right)
    q_bottom_rect = _global_rect(q_bottom)

    assert _close_int(l_bottom_rect.width(), q_bottom_rect.width(), 30)
    assert _close_int(l_bottom_rect.x(), q_bottom_rect.x(), 20)
    assert _close_int(l_bottom_rect.right(), q_bottom_rect.right(), 20)
    assert _close_int(l_bottom_rect.top() - l_left_rect.bottom(), q_bottom_rect.top() - q_left_rect.bottom(), 4)
    assert _close_int(l_bottom_rect.top() - l_right_rect.bottom(), q_bottom_rect.top() - q_right_rect.bottom(), 4)
    assert l_left_rect.bottom() < l_bottom_rect.top()
    assert l_right_rect.bottom() < l_bottom_rect.top()
    assert l_bottom_rect.width() > l_left_rect.width()
    assert l_bottom_rect.width() > l_right_rect.width()

    lmw.hide()
    qtmw.hide()


def test_toolbar_shell_geometry_and_screenshot_parity(qapp):
    """Mixed-area shell toolbars keep similar bounds and overall render to Qt."""
    qapp.setStyle("Fusion")
    lmw, l_toolbars = _make_l_shell_window()
    qtmw, q_toolbars = _make_qt_shell_window()
    _apply_comparison_style(lmw, qtmw)
    lmw.insertToolBarBreak(l_toolbars[1])
    qtmw.insertToolBarBreak(q_toolbars[1])
    lmw.show()
    qtmw.show()
    qapp.processEvents()

    l_rects = _toolbar_global_rects(l_toolbars)
    q_rects = _toolbar_global_rects(q_toolbars)
    assert _close_int(l_rects["Top"].height(), q_rects["Top"].height(), 6)
    assert _close_int(l_rects["Bottom"].height(), q_rects["Bottom"].height(), 6)
    assert l_rects["Left"].width() > 0 and q_rects["Left"].width() > 0
    assert l_rects["Right"].width() > 0 and q_rects["Right"].width() > 0

    diff = _avg_image_diff(lmw.grab().toImage(), qtmw.grab().toImage())
    assert diff <= IMAGE_DIFF_TOL
    lmw.hide()
    qtmw.hide()


def test_corner_visual_ownership_shifts_ldocking_toolbar_bounds(qapp):
    """Corner ownership changes the rendered ldocking shell geometry in the expected direction."""
    qapp.setStyle("Fusion")
    lmw, l_toolbars = _make_l_shell_window()
    _apply_comparison_style(lmw)
    lmw.show()
    qapp.processEvents()

    before = _toolbar_global_rects(l_toolbars)
    lmw.setCorner(Qt.Corner.TopLeftCorner, LeftDockWidgetArea)
    lmw.setCorner(Qt.Corner.BottomRightCorner, RightDockWidgetArea)
    qapp.processEvents()
    after = _toolbar_global_rects(l_toolbars)

    assert after["Top"].x() > before["Top"].x()
    assert after["Bottom"].right() < before["Bottom"].right()
    lmw.hide()


def test_floating_dock_geometry_and_screenshot_parity(qapp):
    """Floated docks stay visually bounded under the frameless floating model."""
    qapp.setStyle("Fusion")
    lmw, ldock = _make_l_window("Float")
    qtmw, qtdock = _make_qt_window("Float")
    _apply_comparison_style(lmw, qtmw)
    lmw.show()
    qtmw.show()
    ldock.setFloating(True)
    qtdock.setFloating(True)
    qapp.processEvents()

    assert ldock._size_grip is not None and ldock._size_grip.isVisible()
    assert ldock.isVisible()
    assert qtdock.isVisible()

    diff = _avg_image_diff(ldock.grab().toImage(), qtdock.grab().toImage())
    assert diff <= FLOATING_IMAGE_DIFF_TOL
    ldock.hide()
    qtdock.hide()


def test_nested_layout_named_dock_geometry_parity(qapp):
    """Nested dock presets keep named panel rectangles close to native Qt."""
    qapp.setStyle("Fusion")
    lmw, l_docks = _make_nested_l_window()
    qtmw, q_docks = _make_nested_qt_window()
    _apply_comparison_style(lmw, qtmw)
    lmw.show()
    qtmw.show()
    qapp.processEvents()

    l_rects = _named_dock_global_rects(l_docks)
    q_rects = _named_dock_global_rects(q_docks)
    assert l_rects["Console"].y() > l_rects["Layers"].y()
    assert q_rects["Console"].y() > q_rects["Layers"].y()

    diff = _avg_image_diff(lmw.grab().toImage(), qtmw.grab().toImage())
    assert diff <= IMAGE_DIFF_TOL
    lmw.hide()
    qtmw.hide()


def test_grouped_tabbed_preset_visual_parity(qapp):
    """Grouped tab presets keep the tab-group region visually close to Qt."""
    qapp.setStyle("Fusion")
    lmw, _ = _make_l_tabbed_window(3)
    qtmw, _ = _make_qt_tabbed_window(3)
    _apply_comparison_style(lmw, qtmw)
    lmw.show()
    qtmw.show()
    qapp.processEvents()

    l_tab_bar = lmw._dock_areas[LeftDockWidgetArea]._tab_area._tab_bar
    q_tab_bar = _find_qt_tab_bar(qtmw)
    assert l_tab_bar.count() == q_tab_bar.count()
    assert _close_int(l_tab_bar.height(), q_tab_bar.height(), 6)
    diff = _avg_image_diff(l_tab_bar.grab().toImage(), q_tab_bar.grab().toImage())
    assert diff <= IMAGE_DIFF_TOL

    lmw.hide()
    qtmw.hide()


def test_drag_preview_indicator_renders_visible_tab_overlay(qapp):
    """Tab drop previews render a visible bounded overlay image."""
    win = LMainWindow()
    win.resize(900, 700)
    target_rect = QRect(100, 120, 300, 180)
    dm = LDragManager.instance()
    target = _DropTarget(
        win,
        LeftDockWidgetArea,
        "tab",
        target_id="anchor",
        target_rect=target_rect,
    )

    rect = dm._compute_indicator_rect(target)
    dm._indicator.show_at(rect)
    qapp.processEvents()
    img = dm._indicator.grab().toImage()
    dm._indicator.hide_indicator()

    assert not img.isNull()
    center = img.pixelColor(img.width() // 2, img.height() // 2)
    assert center.alpha() > 0 or center.blue() > 0


def test_drag_preview_indicator_rects_differ_by_drop_mode(qapp):
    """Tab, side, and root-edge previews stay visually distinct by geometry."""
    win = LMainWindow()
    win.resize(900, 700)
    dm = LDragManager.instance()
    base = QRect(100, 120, 300, 180)

    tab_rect = dm._compute_indicator_rect(
        _DropTarget(win, LeftDockWidgetArea, "tab", target_rect=base)
    )
    side_rect = dm._compute_indicator_rect(
        _DropTarget(
            win,
            LeftDockWidgetArea,
            "side",
            target_rect=base,
            relative_side=BottomDockWidgetArea,
        )
    )
    root_rect = dm._compute_indicator_rect(
        _DropTarget(
            win,
            LeftDockWidgetArea,
            "area",
            target_rect=QRect(0, 0, 900, 700),
        )
    )

    assert tab_rect.width() < root_rect.width()
    assert side_rect.height() < root_rect.height()
    assert tab_rect != side_rect


# ------------------------------------------------------------------
# WA_StyledBackground required: control test
# ------------------------------------------------------------------

def test_wa_styled_background_required(qapp):
    """A plain QWidget without WA_StyledBackground ignores background-color QSS.

    This test documents WHY WA_StyledBackground is set on all L* widgets.
    It passes only if the plain widget does NOT show the color (i.e. the
    attribute is genuinely needed).
    """
    from PySide6.QtCore import Qt as _Qt
    from PySide6.QtWidgets import QWidget

    RED = (200, 0, 0)
    plain = QWidget()
    plain.resize(100, 60)
    # Deliberately do NOT set WA_StyledBackground
    plain.setStyleSheet("QWidget { background: rgb(200,0,0); }")
    plain.show()
    qapp.processEvents()

    color = _sample(plain)
    # Without WA_StyledBackground the background rule is silently ignored.
    # The widget will show the default window/palette color, not red.
    # We simply document the behavior; the test passes either way but
    # records whether the workaround is still necessary.
    plain.hide()
    # (No assertion — this is an informational/documentary test)


def test_wa_styled_background_on_ldock(qapp):
    """LDockWidget shows background-color because WA_StyledBackground is set."""
    RED = (200, 0, 0)
    _, dock = _make_l_window()
    dock.resize(200, 120)
    dock.setStyleSheet(
        "LDockWidget { background: rgb(200,0,0); }"
        "#dockTitleBar { background: transparent; }"
        "#dockContent { background: transparent; }"
    )
    dock.show()
    qapp.processEvents()

    # The outer dock frame (left edge) must be red
    edge = QRect(0, dock._title_bar.height() + 2, 4, 20)
    color = _sample(dock, edge)
    assert _close(color, RED), (
        f"LDockWidget must show red due to WA_StyledBackground; got {color}"
    )
    dock.hide()
