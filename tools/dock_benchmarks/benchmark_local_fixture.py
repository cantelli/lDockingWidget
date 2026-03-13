"""Run a local fixture app natively or with the monkeypatch for comparison."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = ROOT / "tools" / "dock_benchmarks" / "artifacts"
FIXTURE_PREFIX = "tools.dock_benchmarks.fixtures"


def _clear_fixture_modules() -> None:
    for name in list(sys.modules):
        if name == FIXTURE_PREFIX or name.startswith(f"{FIXTURE_PREFIX}."):
            sys.modules.pop(name, None)


def _load_window(mode: str, fixture: str):
    _clear_fixture_modules()
    if mode == "monkey":
        import ldocking.monkey as monkey

        monkey.patch()
    else:
        import ldocking.monkey as monkey

        monkey.unpatch()
    module = importlib.import_module(f"{FIXTURE_PREFIX}.{fixture}")
    from PySide6.QtWidgets import QApplication, QToolBar

    app = QApplication.instance() or QApplication([])
    window = module.build_window()
    window.show()
    app.processEvents()
    return app, window, module, module.QDOCKWIDGET_CLASS, QToolBar


def _collect_docks(app, window, dock_type, expected_titles) -> list:
    docks_by_title = {}
    for top_level in app.topLevelWidgets():
        if isinstance(top_level, dock_type):
            docks_by_title[top_level.windowTitle()] = top_level
        for dock in top_level.findChildren(dock_type):
            docks_by_title[dock.windowTitle()] = dock
    for dock in window.findChildren(dock_type):
        docks_by_title[dock.windowTitle()] = dock
    if expected_titles is not None:
        return [docks_by_title[title] for title in expected_titles if title in docks_by_title]
    return sorted(docks_by_title.values(), key=lambda dock: dock.windowTitle())


def _snapshot(app, window, module, dock_type, toolbar_type) -> dict[str, object]:
    docks = _collect_docks(app, window, dock_type, getattr(module, "DOCK_TITLES", None))
    toolbars = sorted(window.findChildren(toolbar_type), key=lambda tb: tb.windowTitle())
    return {
        "window_title": window.windowTitle(),
        "docks": {
            dock.windowTitle(): {
                "area": int(window.dockWidgetArea(dock).value),
                "floating": dock.isFloating(),
                "visible": dock.isVisible(),
                "tabs": sorted(peer.windowTitle() for peer in window.tabifiedDockWidgets(dock)),
            }
            for dock in docks
        },
        "toolbars": [toolbar.windowTitle() for toolbar in toolbars],
        "menu_actions": [action.text() for action in window.menuBar().actions()] if window.menuBar() is not None else [],
    }


def _capture_step(fixture: str, mode: str, step: str, app, window, module, dock_type, toolbar_type) -> dict[str, object]:
    snapshot = _snapshot(app, window, module, dock_type, toolbar_type)
    image_path = ARTIFACTS_DIR / f"{fixture}_{mode}_{step}.png"
    snapshot["image"] = str(image_path)
    window.grab().save(str(image_path))
    return snapshot


def _run_replay(fixture: str, mode: str, app, window, module, dock_type, toolbar_type) -> list[dict[str, object]]:
    docks = _collect_docks(app, window, dock_type, getattr(module, "DOCK_TITLES", None))
    steps = [_capture_step(fixture, mode, "initial", app, window, module, dock_type, toolbar_type)]
    if not docks:
        return steps

    docks[0].toggleViewAction().trigger()
    app.processEvents()
    steps.append(_capture_step(fixture, mode, "toggle_hide_first", app, window, module, dock_type, toolbar_type))
    docks[0].toggleViewAction().trigger()
    app.processEvents()
    steps.append(_capture_step(fixture, mode, "toggle_show_first", app, window, module, dock_type, toolbar_type))

    if len(docks) > 1:
        window.tabifyDockWidget(docks[0], docks[1])
        app.processEvents()
        steps.append(_capture_step(fixture, mode, "tabify_first_second", app, window, module, dock_type, toolbar_type))

    state = window.saveState()
    if len(docks) > 1:
        docks[1].setFloating(True)
        app.processEvents()
        steps.append(_capture_step(fixture, mode, "float_second", app, window, module, dock_type, toolbar_type))
    window.restoreState(state)
    app.processEvents()
    steps.append(_capture_step(fixture, mode, "restore_state", app, window, module, dock_type, toolbar_type))
    return steps


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", choices=("labelme_shape_app", "qtpy_style_app"), required=True)
    parser.add_argument("--mode", choices=("native", "monkey"), required=True)
    parser.add_argument("--scenario", choices=("baseline", "replay"), default="baseline")
    args = parser.parse_args()

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    app, window, module, dock_type, toolbar_type = _load_window(args.mode, args.fixture)
    if args.scenario == "baseline":
        payload: dict[str, object] = _capture_step(args.fixture, args.mode, "baseline", app, window, module, dock_type, toolbar_type)
    else:
        payload = {"steps": _run_replay(args.fixture, args.mode, app, window, module, dock_type, toolbar_type)}

    json_path = ARTIFACTS_DIR / f"{args.fixture}_{args.mode}_{args.scenario}.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "payload": payload}, indent=2))
    window.close()
    app.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
