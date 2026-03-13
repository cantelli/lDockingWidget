"""Comparative monkeypatch tests against local fixture apps."""

import importlib
import sys
from pathlib import Path
import importlib.util

from PySide6.QtWidgets import QToolBar
from PySide6.QtCore import Qt

import ldocking.monkey as monkey
from ldocking import LDockWidget
from parity_test import _corner_snap, _toolbar_snap, compare, l_snap, qt_snap

FIXTURE_PREFIX = "tools.dock_benchmarks.fixtures"
NativeQDockWidget = monkey._ORIG["QDockWidget"]
EXAMPLE_DIR = (
    Path(__file__).resolve().parents[1]
    / "third_party"
    / "dock_benchmarks"
    / "pyside-setup"
    / "examples"
    / "widgets"
    / "mainwindows"
    / "dockwidgets"
)


def _clear_fixture_modules():
    for name in list(sys.modules):
        if name == FIXTURE_PREFIX or name.startswith(f"{FIXTURE_PREFIX}."):
            sys.modules.pop(name, None)


def _load_fixture(module_name: str, *, patched: bool):
    if patched:
        monkey.patch()
    else:
        monkey.unpatch()
    _clear_fixture_modules()
    return importlib.import_module(f"{FIXTURE_PREFIX}.{module_name}")


def _snapshot_pair(native_win, monkey_win):
    native_docks = sorted(native_win.findChildren(NativeQDockWidget), key=lambda dock: dock.windowTitle())
    monkey_docks = sorted(monkey_win.findChildren(LDockWidget), key=lambda dock: dock.windowTitle())
    native_toolbars = sorted(native_win.findChildren(QToolBar), key=lambda toolbar: toolbar.windowTitle())
    monkey_toolbars = sorted(monkey_win.findChildren(QToolBar), key=lambda toolbar: toolbar.windowTitle())

    native_state = qt_snap(native_win, native_docks)
    native_state["toolbars"] = _toolbar_snap(native_win, native_toolbars)
    native_state["corners"] = _corner_snap(native_win)
    monkey_state = l_snap(monkey_win, monkey_docks, monkey_toolbars)
    return native_state, monkey_state


def _dock_by_title(window, dock_type, title: str):
    for dock in window.findChildren(dock_type):
        if dock.windowTitle() == title:
            return dock
    raise AssertionError(f"missing dock {title!r}")


def _build_fixture_pair(qapp, module_name: str):
    native_module = _load_fixture(module_name, patched=False)
    native_win = native_module.build_window()
    monkey_module = _load_fixture(module_name, patched=True)
    monkey_win = monkey_module.build_window()
    native_win.show()
    monkey_win.show()
    qapp.processEvents()
    return native_win, monkey_win


def _load_official_example(qapp, mode: str):
    if mode == "monkey":
        monkey.patch()
    else:
        monkey.unpatch()
    sys.path.insert(0, str(EXAMPLE_DIR))
    spec = importlib.util.spec_from_file_location(f"dockwidgets_test_{mode}", EXAMPLE_DIR / "dockwidgets.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    window = module.MainWindow()
    window.show()
    qapp.processEvents()
    return window


def test_qtpy_style_fixture_native_vs_monkey_layout(qapp):
    native_win, monkey_win = _build_fixture_pair(qapp, "qtpy_style_app")
    native_state, monkey_state = _snapshot_pair(native_win, monkey_win)
    assert compare(native_state, monkey_state, ["area", "floating", "visible", "tabs"]) == []
    native_win.close()
    monkey_win.close()


def test_labelme_shape_fixture_native_vs_monkey_layout(qapp):
    native_win, monkey_win = _build_fixture_pair(qapp, "labelme_shape_app")
    native_state, monkey_state = _snapshot_pair(native_win, monkey_win)
    assert compare(native_state, monkey_state, ["area", "floating", "visible", "tabs"]) == []
    native_win.close()
    monkey_win.close()


def test_labelme_shape_toggle_and_restore_parity(qapp):
    native_win, monkey_win = _build_fixture_pair(qapp, "labelme_shape_app")

    _dock_by_title(native_win, NativeQDockWidget, "Label List").toggleViewAction().trigger()
    _dock_by_title(monkey_win, LDockWidget, "Label List").toggleViewAction().trigger()
    qapp.processEvents()

    native_state, monkey_state = _snapshot_pair(native_win, monkey_win)
    assert compare(native_state, monkey_state, ["visible", "tabs"]) == []

    native_win.tabifyDockWidget(
        _dock_by_title(native_win, NativeQDockWidget, "Flags"),
        _dock_by_title(native_win, NativeQDockWidget, "Annotation List"),
    )
    monkey_win.tabifyDockWidget(
        _dock_by_title(monkey_win, LDockWidget, "Flags"),
        _dock_by_title(monkey_win, LDockWidget, "Annotation List"),
    )
    qapp.processEvents()

    native_saved = native_win.saveState()
    monkey_saved = monkey_win.saveState()
    _dock_by_title(native_win, NativeQDockWidget, "File List").setFloating(True)
    _dock_by_title(monkey_win, LDockWidget, "File List").setFloating(True)
    qapp.processEvents()
    assert native_win.restoreState(native_saved) is True
    assert monkey_win.restoreState(monkey_saved) is True
    qapp.processEvents()

    native_state, monkey_state = _snapshot_pair(native_win, monkey_win)
    assert compare(native_state, monkey_state, ["area", "floating", "visible", "tabs"]) == []

    native_win.close()
    monkey_win.close()


def test_official_example_tab_float_restore_parity(qapp):
    if not EXAMPLE_DIR.exists():
        import pytest

        pytest.skip("official Qt dockwidgets example is not present locally")

    native_win = _load_official_example(qapp, "native")
    monkey_win = _load_official_example(qapp, "monkey")

    native_docks = sorted(native_win.findChildren(NativeQDockWidget), key=lambda dock: dock.windowTitle())
    monkey_docks = sorted(monkey_win.findChildren(LDockWidget), key=lambda dock: dock.windowTitle())
    native_first, native_second = native_docks
    monkey_first, monkey_second = monkey_docks

    native_win.tabifyDockWidget(native_first, native_second)
    monkey_win.tabifyDockWidget(monkey_first, monkey_second)
    qapp.processEvents()

    native_second.setFloating(True)
    monkey_second.setFloating(True)
    qapp.processEvents()

    native_saved = native_win.saveState()
    monkey_saved = monkey_win.saveState()
    native_second.setFloating(False)
    monkey_second.setFloating(False)
    qapp.processEvents()

    assert native_win.restoreState(native_saved) is True
    assert monkey_win.restoreState(monkey_saved) is True
    qapp.processEvents()

    native_state = qt_snap(native_win, native_docks)
    native_state["toolbars"] = _toolbar_snap(native_win, sorted(native_win.findChildren(QToolBar), key=lambda tb: tb.windowTitle()))
    native_state["corners"] = _corner_snap(native_win)
    monkey_state = l_snap(monkey_win, monkey_docks, sorted(monkey_win.findChildren(QToolBar), key=lambda tb: tb.windowTitle()))
    assert compare(native_state, monkey_state, ["area", "floating", "visible", "tabs"]) == []

    native_win.close()
    monkey_win.close()
