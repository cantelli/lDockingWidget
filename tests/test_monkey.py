"""Tests for ldocking.monkey — QMainWindow/QDockWidget auto-replacement."""
import importlib
import sys
import os
from types import ModuleType
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import PySide6.QtWidgets as _qw
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

import ldocking.monkey as monkey
import ldocking.bootstrap as bootstrap
from ldocking import LDockWidget, LMainWindow

FIXTURE_PREFIX = "tools.dock_benchmarks.fixtures"
_TEST_LEAK_EXCLUDES = (
    "test_",
    "parity_test",
    "visual_compare_demo",
)


def _clear_fixture_modules():
    for name in list(sys.modules):
        if name == FIXTURE_PREFIX or name.startswith(f"{FIXTURE_PREFIX}."):
            sys.modules.pop(name, None)


def _load_fixture(module_name: str):
    _clear_fixture_modules()
    return importlib.import_module(f"{FIXTURE_PREFIX}.{module_name}")


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


def test_unpatch_restores_qapplication_setstylesheet(qapp):
    orig = monkey._ORIG["QApplication.setStyleSheet"]
    monkey.unpatch()
    assert _qw.QApplication.setStyleSheet is orig


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


def test_imported_alias_before_patch_stays_native(qapp):
    monkey.unpatch()
    from PySide6.QtWidgets import QMainWindow as NativeImportedMainWindow

    monkey.patch()
    win = NativeImportedMainWindow()
    assert type(win) is monkey._ORIG["QMainWindow"]
    win.close()


def test_qtpy_style_fixture_uses_native_classes_without_patch(qapp):
    monkey.unpatch()
    module = _load_fixture("qtpy_style_app")
    assert module.QMAINWINDOW_CLASS is monkey._ORIG["QMainWindow"]
    assert module.QDOCKWIDGET_CLASS is monkey._ORIG["QDockWidget"]
    win = module.build_window()
    assert type(win) is monkey._ORIG["QMainWindow"]
    win.close()


def test_qtpy_style_fixture_uses_ldocking_classes_when_patched(qapp):
    monkey.patch()
    module = _load_fixture("qtpy_style_app")
    assert module.QMAINWINDOW_CLASS is LMainWindow
    assert module.QDOCKWIDGET_CLASS is LDockWidget
    win = module.build_window()
    assert isinstance(win, LMainWindow)
    win.close()


def test_fixture_imported_before_patch_keeps_native_bindings(qapp):
    monkey.unpatch()
    module = _load_fixture("labelme_shape_app")
    monkey.patch()
    win = module.build_window()
    assert type(win) is monkey._ORIG["QMainWindow"]
    assert all(type(dock) is monkey._ORIG["QDockWidget"] for dock in win.findChildren(monkey._ORIG["QDockWidget"]))
    win.close()


def test_qapplication_stylesheet_translates_qdockwidget_selector_when_patched(qapp):
    qapp.setStyleSheet(
        "QDockWidget { background: rgb(180,0,40); }"
        "QDockWidget::title { background: transparent; }"
        "QDockWidget > QWidget { background: transparent; }"
    )
    try:
        from PySide6.QtWidgets import QMainWindow, QDockWidget

        win = QMainWindow()
        dock = QDockWidget("Dock")
        dock.setWidget(QLabel("Dock"))
        win.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)
        win.show()
        qapp.processEvents()

        edge = dock.grab(dock.rect()).toImage().pixelColor(2, dock.height() // 2)
        assert edge.red() > 150 and edge.green() < 80 and edge.blue() < 80
        win.close()
    finally:
        qapp.setStyleSheet("")


def test_qapplication_stylesheet_translation_disabled_after_unpatch(qapp):
    monkey.unpatch()
    qapp.setStyleSheet("QDockWidget::title { background: rgb(1,2,3); }")
    try:
        win = LMainWindow()
        dock = LDockWidget("Dock")
        dock.setWidget(QLabel("Dock"))
        win.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)
        win.show()
        qapp.processEvents()

        color = dock._title_bar.palette().window().color()
        assert (color.red(), color.green(), color.blue()) != (1, 2, 3)
        win.close()
    finally:
        qapp.setStyleSheet("")
        monkey.patch()


def test_bootstrap_activate_reports_clean_runtime(qapp):
    _clear_fixture_modules()
    leak_module = ModuleType("fake_clean_runtime")
    sys.modules[leak_module.__name__] = leak_module
    try:
        report = bootstrap.activate(exclude_prefixes=_TEST_LEAK_EXCLUDES)
        assert report.patched is True
        assert report.requested is True
        assert report.stylesheet_translation_active is True
        assert report.import_order_ok is True
        assert report.leaks == ()
    finally:
        sys.modules.pop(leak_module.__name__, None)


def test_bootstrap_detects_late_import_binding_leak(qapp):
    leak_module = ModuleType("fake_late_import")
    leak_module.QMainWindow = monkey._ORIG["QMainWindow"]
    leak_module.QDockWidget = monkey._ORIG["QDockWidget"]
    sys.modules[leak_module.__name__] = leak_module
    try:
        monkey.patch()
        report = bootstrap.describe_runtime(exclude_prefixes=_TEST_LEAK_EXCLUDES)
        assert report.import_order_ok is False
        assert any(leak.module == "fake_late_import" and leak.attr == "QMainWindow" for leak in report.leaks)
        assert any(leak.module == "fake_late_import" and leak.attr == "QDockWidget" for leak in report.leaks)
    finally:
        sys.modules.pop(leak_module.__name__, None)


def test_bootstrap_strict_mode_raises_on_late_import_leak(qapp):
    leak_module = ModuleType("fake_strict_late_import")
    leak_module.QMainWindow = monkey._ORIG["QMainWindow"]
    sys.modules[leak_module.__name__] = leak_module
    try:
        with pytest.raises(RuntimeError, match="fake_strict_late_import"):
            bootstrap.activate(strict=True, exclude_prefixes=_TEST_LEAK_EXCLUDES)
    finally:
        sys.modules.pop(leak_module.__name__, None)


def test_bootstrap_activate_from_env_can_disable_patch(qapp, monkeypatch):
    monkeypatch.setenv("LDOCKING_PATCH", "0")
    report = bootstrap.activate_from_env(exclude_prefixes=_TEST_LEAK_EXCLUDES)
    assert report.requested is False
    assert report.patched is False
    assert report.stylesheet_translation_active is False
    monkey.patch()


def test_bootstrap_activate_from_env_can_enable_patch(qapp, monkeypatch):
    monkey.unpatch()
    monkeypatch.setenv("LDOCKING_PATCH", "1")
    report = bootstrap.activate_from_env(exclude_prefixes=_TEST_LEAK_EXCLUDES)
    assert report.requested is True
    assert report.patched is True
    assert report.stylesheet_translation_active is True
