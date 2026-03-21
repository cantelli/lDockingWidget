"""Behavioral parity tests: size preservation, indicator geometry."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QDockWidget, QLabel, QMainWindow

import ldocking.monkey as monkey
_QMainWindow = monkey._ORIG["QMainWindow"]
_QDockWidget = monkey._ORIG["QDockWidget"]

from ldocking import LDockWidget, LMainWindow, LeftDockWidgetArea, BottomDockWidgetArea, RightDockWidgetArea

Left = Qt.DockWidgetArea.LeftDockWidgetArea
Bottom = Qt.DockWidgetArea.BottomDockWidgetArea
Right = Qt.DockWidgetArea.RightDockWidgetArea


def _process(qapp, n=5):
    for _ in range(n):
        qapp.processEvents()


def test_redock_preserves_bottom_panel_width(qapp):
    """Float a left panel and redock it; bottom panel width must not change."""
    # Qt side
    qt_mw = _QMainWindow()
    qt_mw.resize(800, 600)
    left_dock = _QDockWidget("Left", qt_mw)
    bot_dock = _QDockWidget("Bot", qt_mw)
    qt_mw.addDockWidget(Left, left_dock)
    qt_mw.addDockWidget(Bottom, bot_dock)
    qt_mw.show()
    _process(qapp)
    qt_bot_w_before = bot_dock.width()
    left_dock.setFloating(True)
    _process(qapp)
    left_dock.setFloating(False)
    _process(qapp)
    qt_bot_w_after = bot_dock.width()
    qt_mw.hide()

    # LDock side
    l_mw = LMainWindow()
    l_mw.resize(800, 600)
    l_left = LDockWidget("Left")
    l_left.setWidget(QLabel("L"))
    l_bot = LDockWidget("Bot")
    l_bot.setWidget(QLabel("B"))
    l_mw.addDockWidget(Left, l_left)
    l_mw.addDockWidget(Bottom, l_bot)
    l_mw.show()
    _process(qapp)
    l_bot_w_before = l_bot.width()
    l_left.setFloating(True)
    _process(qapp)
    l_left.setFloating(False)
    _process(qapp)
    l_bot_w_after = l_bot.width()
    l_mw.hide()

    # Qt baseline: bottom width unchanged
    assert abs(qt_bot_w_after - qt_bot_w_before) <= 4, (
        f"Qt baseline broken: bot width {qt_bot_w_before} -> {qt_bot_w_after}"
    )
    # LDock must match
    assert abs(l_bot_w_after - l_bot_w_before) <= 4, (
        f"LDock bot width changed: {l_bot_w_before} -> {l_bot_w_after}"
    )


def test_float_redock_left_preserves_right_and_bottom_widths(qapp):
    """Float left; redock it — right and bottom panel widths unchanged."""
    l_mw = LMainWindow()
    l_mw.resize(800, 600)
    l_left = LDockWidget("Left")
    l_left.setWidget(QLabel("L"))
    l_right = LDockWidget("Right")
    l_right.setWidget(QLabel("R"))
    l_bot = LDockWidget("Bot")
    l_bot.setWidget(QLabel("B"))
    l_mw.addDockWidget(Left, l_left)
    l_mw.addDockWidget(Right, l_right)
    l_mw.addDockWidget(Bottom, l_bot)
    l_mw.show()
    _process(qapp)

    right_w_before = l_right.width()
    bot_w_before = l_bot.width()

    l_left.setFloating(True)
    _process(qapp)
    l_left.setFloating(False)
    _process(qapp)

    right_w_after = l_right.width()
    bot_w_after = l_bot.width()
    l_mw.hide()

    assert abs(right_w_after - right_w_before) <= 4, (
        f"Right dock width changed: {right_w_before} -> {right_w_after}"
    )
    assert abs(bot_w_after - bot_w_before) <= 4, (
        f"Bottom dock width changed: {bot_w_before} -> {bot_w_after}"
    )


def test_initial_left_area_width_reasonable(qapp):
    """Left area initial width is a sensible fraction of the 800px window."""
    l_mw = LMainWindow()
    l_mw.resize(800, 600)
    ld = LDockWidget("Insp")
    ld.setWidget(QLabel("x"))
    l_mw.addDockWidget(Left, ld)
    l_mw.show()
    _process(qapp)
    l_w = ld.width()
    l_mw.hide()

    # Dock should be assigned roughly its sizeHint width — not 0 and not full window
    assert 30 <= l_w <= 400, f"Left dock initial width {l_w} is unreasonable for 800px window"


def test_tab_indicator_covers_full_target(qapp):
    """Tab-drop indicator rect should equal the full target rect minus margin."""
    from ldocking.ldrag_manager import LDragManager, _DropTarget, _INDICATOR_MARGIN

    mw = LMainWindow()
    mw.resize(800, 600)
    d1 = LDockWidget("A")
    d1.setWidget(QLabel("A"))
    mw.addDockWidget(Left, d1)
    mw.show()
    _process(qapp)

    mgr = LDragManager.instance()
    target_rect = QRect(mw.mapToGlobal(QPoint(0, 0)), QSize(200, 400))
    target = _DropTarget(mw, Left, "tab", target_dock=d1, target_rect=target_rect)
    rect = mgr._compute_indicator_rect(target)

    bounded = target_rect.adjusted(
        _INDICATOR_MARGIN, _INDICATOR_MARGIN,
        -_INDICATOR_MARGIN, -_INDICATOR_MARGIN,
    )
    assert rect == bounded, f"Tab indicator rect {rect} != bounded {bounded}"
    mw.hide()
