"""Dynamic scenario regression checks run in a subprocess for stability."""
from __future__ import annotations

import json
import os
import subprocess
import sys


def _run_scenario_probe(scenario_name: str) -> dict[str, object]:
    script = f"""
import json, os, sys
sys.path.insert(0, r"{os.path.join(os.getcwd(), 'tests')}")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication
from screenshot_compare import _dispose_panes, _equalize_pane_sizes
from visual_compare_demo import QtComparisonPane, LDockingComparisonPane, _apply_demo_style
from compare_scenarios import SCENARIOS

app = QApplication.instance() or QApplication([])
_apply_demo_style(app)
scenario = SCENARIOS[{scenario_name!r}]
qt_pane = QtComparisonPane()
l_pane = LDockingComparisonPane()
qt_pane.resize(760, 720)
l_pane.resize(760, 720)
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

metrics = {{}}
def rect_of(dock):
    top_left = dock.mapToGlobal(QPoint(0, 0))
    return [top_left.x(), top_left.y(), dock.width(), dock.height()]

def snap(label):
    metrics[label] = {{
        "qt": {{
            dock.windowTitle(): {{
                "floating": dock.isFloating(),
                "rect": rect_of(dock),
            }}
            for dock in qt_pane.docks
        }},
        "l": {{
            dock.windowTitle(): {{
                "floating": dock.isFloating(),
                "rect": rect_of(dock),
            }}
            for dock in l_pane.docks
        }},
    }}

snap("initial")
for action in scenario["steps"]:
    qt_pane.apply_action(action)
    l_pane.apply_action(action)
    for _ in range(8):
        app.processEvents()
    snap(str(action["label"]))

_dispose_panes(app, qt_pane, l_pane)
sys.stdout.write(json.dumps(metrics))
sys.stdout.flush()
os._exit(0)
"""
    proc = subprocess.run(
        [sys.executable, "-c", script],
        cwd=os.getcwd(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + "\nSTDERR:\n" + proc.stderr
    return json.loads(proc.stdout)


def test_dynamic_right_redock_preserves_bottom_geometry_like_qt():
    metrics = _run_scenario_probe("balanced_float_right_redock")
    initial_console_qt = metrics["initial"]["qt"]["Console"]["rect"][2]
    redock_console_qt = metrics["redock_layers"]["qt"]["Console"]["rect"][2]
    redock_console_l = metrics["redock_layers"]["l"]["Console"]["rect"][2]
    redock_layers_qt = metrics["redock_layers"]["qt"]["Layers"]["rect"][3]
    redock_layers_l = metrics["redock_layers"]["l"]["Layers"]["rect"][3]
    redock_console_top_qt = metrics["redock_layers"]["qt"]["Console"]["rect"][1]
    redock_console_top_l = metrics["redock_layers"]["l"]["Console"]["rect"][1]

    assert abs(redock_console_qt - initial_console_qt) <= 4
    assert abs(redock_console_l - redock_console_qt) <= 20
    assert abs(redock_layers_l - redock_layers_qt) <= 20
    assert redock_layers_l < redock_console_top_l
    assert redock_layers_qt < redock_console_top_qt


def test_dynamic_move_right_to_left_keeps_layers_docked():
    metrics = _run_scenario_probe("balanced_move_right_to_left")
    move = metrics["move_layers_left"]
    assert move["qt"]["Layers"]["floating"] is False
    assert move["l"]["Layers"]["floating"] is False
