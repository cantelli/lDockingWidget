"""Tests for ldocking.monkey — QMainWindow/QDockWidget auto-replacement."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import PySide6.QtWidgets as _qw
from PySide6.QtCore import Qt

import ldocking.monkey as monkey
from ldocking import LDockWidget, LMainWindow


@pytest.fixture(autouse=True)
def restore_patch():
    """Ensure each test starts and ends with the patch active."""
    monkey.patch()
    yield
    monkey.patch()  # re-apply in case a test called unpatch


# ------------------------------------------------------------------
# Patch state
# ------------------------------------------------------------------

def test_is_patched(qapp):
    assert monkey.is_patched() is True


def test_unpatch_then_repatch(qapp):
    monkey.unpatch()
    assert monkey.is_patched() is False
    monkey.patch()
    assert monkey.is_patched() is True


def test_double_patch_is_safe(qapp):
    """Calling patch() twice must not corrupt _ORIG with L* classes."""
    monkey.patch()  # second call while already patched
    assert monkey._ORIG["QMainWindow"] is not LMainWindow
    assert monkey._ORIG["QDockWidget"] is not LDockWidget


# ------------------------------------------------------------------
# Module attribute replacement
# ------------------------------------------------------------------

def test_patch_replaces_qmainwindow(qapp):
    assert _qw.QMainWindow is LMainWindow


def test_patch_replaces_qdockwidget(qapp):
    assert _qw.QDockWidget is LDockWidget


def test_unpatch_restores_qmainwindow(qapp):
    orig = monkey._ORIG["QMainWindow"]
    monkey.unpatch()
    assert _qw.QMainWindow is orig


def test_unpatch_restores_qdockwidget(qapp):
    orig = monkey._ORIG["QDockWidget"]
    monkey.unpatch()
    assert _qw.QDockWidget is orig


# ------------------------------------------------------------------
# from-import behaviour after patch
# ------------------------------------------------------------------

def test_from_import_after_patch(qapp):
    """`from PySide6.QtWidgets import QMainWindow` after patch yields LMainWindow."""
    from PySide6.QtWidgets import QMainWindow
    assert QMainWindow is LMainWindow


def test_from_import_qdockwidget_after_patch(qapp):
    from PySide6.QtWidgets import QDockWidget
    assert QDockWidget is LDockWidget


# ------------------------------------------------------------------
# Construction through patched names
# ------------------------------------------------------------------

def test_constructed_instance_is_lmainwindow(qapp):
    from PySide6.QtWidgets import QMainWindow
    win = QMainWindow()
    assert isinstance(win, LMainWindow)
    win.close()


def test_constructed_instance_is_ldockwidget(qapp):
    from PySide6.QtWidgets import QDockWidget
    dock = QDockWidget("Test")
    assert isinstance(dock, LDockWidget)


# ------------------------------------------------------------------
# isinstance after patch
# ------------------------------------------------------------------

def test_isinstance_lmainwindow_via_patched_name(qapp):
    """isinstance(LMainWindow(), QMainWindow) is True after patch."""
    from PySide6.QtWidgets import QMainWindow
    win = LMainWindow()
    assert isinstance(win, QMainWindow)
    win.close()


def test_isinstance_ldockwidget_via_patched_name(qapp):
    from PySide6.QtWidgets import QDockWidget
    dock = LDockWidget("T")
    assert isinstance(dock, QDockWidget)


def test_monkey_exposes_set_tab_position(qapp):
    """setTabPosition / tabPosition are accessible through the patched name."""
    from PySide6.QtWidgets import QMainWindow, QTabWidget
    win = QMainWindow()
    assert hasattr(win, "setTabPosition")
    assert hasattr(win, "tabPosition")
    win.setTabPosition(Qt.DockWidgetArea.RightDockWidgetArea, QTabWidget.TabPosition.East)
    assert win.tabPosition(Qt.DockWidgetArea.RightDockWidgetArea) == QTabWidget.TabPosition.East
    win.close()
