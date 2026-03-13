"""Run the official Qt for Python dockwidgets example in native or monkeypatched mode.

Writes JSON snapshots and PNG captures under tools/dock_benchmarks/artifacts/.

Usage:
    python tools/dock_benchmarks/benchmark_official_dockwidgets.py --mode native
    python tools/dock_benchmarks/benchmark_official_dockwidgets.py --mode monkey
    python tools/dock_benchmarks/benchmark_official_dockwidgets.py --mode monkey --scenario replay
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_DIR = ROOT / "third_party" / "dock_benchmarks" / "pyside-setup" / "examples" / "widgets" / "mainwindows" / "dockwidgets"
ARTIFACTS_DIR = ROOT / "tools" / "dock_benchmarks" / "artifacts"


def _load_window(mode: str):
    sys.path.insert(0, str(EXAMPLE_DIR))
    if mode == "monkey":
        import ldocking.monkey  # noqa: F401
    from PySide6.QtWidgets import QApplication, QDockWidget, QToolBar

    app = QApplication.instance() or QApplication([])
    spec = importlib.util.spec_from_file_location(f"dockwidgets_{mode}", EXAMPLE_DIR / "dockwidgets.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    window = module.MainWindow()
    window.show()
    app.processEvents()
    return app, window, QDockWidget, QToolBar


def _collect_docks(app, window, dock_type) -> list:
    docks_by_title = {}
    for top_level in app.topLevelWidgets():
        if isinstance(top_level, dock_type):
            docks_by_title[top_level.windowTitle()] = top_level
        for dock in top_level.findChildren(dock_type):
            docks_by_title[dock.windowTitle()] = dock
    for dock in window.findChildren(dock_type):
        docks_by_title[dock.windowTitle()] = dock
    return sorted(docks_by_title.values(), key=lambda dock: dock.windowTitle())


def _snapshot(app, window, dock_type, toolbar_type) -> dict[str, object]:
    docks = _collect_docks(app, window, dock_type)
    toolbars = sorted(window.findChildren(toolbar_type), key=lambda tb: tb.windowTitle())
    return {
        "window_title": window.windowTitle(),
        "docks": {
            dock.windowTitle(): {
                "area": int(window.dockWidgetArea(dock).value),
                "floating": dock.isFloating(),
                "visible": dock.isVisible(),
                "tabs": sorted(peer.windowTitle() for peer in window.tabifiedDockWidgets(dock)),
                "geometry": [dock.geometry().x(), dock.geometry().y(), dock.geometry().width(), dock.geometry().height()],
            }
            for dock in docks
        },
        "toolbars": [toolbar.windowTitle() for toolbar in toolbars],
        "menu_actions": [action.text() for action in window.menuBar().actions()],
    }


def _capture_step(mode: str, step: str, app, window, dock_type, toolbar_type) -> dict[str, object]:
    snapshot = _snapshot(app, window, dock_type, toolbar_type)
    image_path = ARTIFACTS_DIR / f"official_dockwidgets_{mode}_{step}.png"
    snapshot["image"] = str(image_path)
    window.grab().save(str(image_path))
    return snapshot


def _run_replay(mode: str, app, window, dock_type, toolbar_type) -> list[dict[str, object]]:
    docks = _collect_docks(app, window, dock_type)
    if len(docks) < 2:
        return [_capture_step(mode, "initial", app, window, dock_type, toolbar_type)]

    first, second = docks[0], docks[1]
    steps = [_capture_step(mode, "initial", app, window, dock_type, toolbar_type)]
    first.toggleViewAction().trigger()
    app.processEvents()
    steps.append(_capture_step(mode, "toggle_hide_first", app, window, dock_type, toolbar_type))
    first.toggleViewAction().trigger()
    app.processEvents()
    steps.append(_capture_step(mode, "toggle_show_first", app, window, dock_type, toolbar_type))
    window.tabifyDockWidget(first, second)
    app.processEvents()
    steps.append(_capture_step(mode, "tabify_first_second", app, window, dock_type, toolbar_type))
    second.setFloating(True)
    app.processEvents()
    steps.append(_capture_step(mode, "float_second", app, window, dock_type, toolbar_type))
    state = window.saveState()
    second.setFloating(False)
    app.processEvents()
    window.restoreState(state)
    app.processEvents()
    steps.append(_capture_step(mode, "restore_state", app, window, dock_type, toolbar_type))
    return steps


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("native", "monkey"), required=True)
    parser.add_argument("--scenario", choices=("baseline", "replay"), default="baseline")
    args = parser.parse_args()

    if not EXAMPLE_DIR.exists():
        raise SystemExit(f"Missing benchmark example at {EXAMPLE_DIR}")

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    app, window, dock_type, toolbar_type = _load_window(args.mode)
    if args.scenario == "baseline":
        payload: dict[str, object] = _capture_step(args.mode, "baseline", app, window, dock_type, toolbar_type)
    else:
        payload = {"steps": _run_replay(args.mode, app, window, dock_type, toolbar_type)}

    json_path = ARTIFACTS_DIR / f"official_dockwidgets_{args.mode}_{args.scenario}.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "payload": payload}, indent=2))
    app.processEvents()
    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
