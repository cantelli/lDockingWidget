"""Shared dynamic action scenarios for Qt vs ldocking comparison tools."""
from __future__ import annotations

from PySide6.QtCore import Qt

Left = Qt.DockWidgetArea.LeftDockWidgetArea
Right = Qt.DockWidgetArea.RightDockWidgetArea
Bottom = Qt.DockWidgetArea.BottomDockWidgetArea


SCENARIOS: dict[str, dict[str, object]] = {
    "balanced_float_right_redock": {
        "layout": "Balanced",
        "steps": [
            {"label": "float_layers", "op": "float", "title": "Layers"},
            {"label": "redock_layers", "op": "redock", "title": "Layers"},
        ],
    },
    "balanced_float_bottom_redock": {
        "layout": "Balanced",
        "steps": [
            {"label": "float_console", "op": "float", "title": "Console"},
            {"label": "redock_console", "op": "redock", "title": "Console"},
        ],
    },
    "balanced_move_right_to_left": {
        "layout": "Balanced",
        "steps": [
            {"label": "move_layers_left", "op": "move", "title": "Layers", "area": Left},
        ],
    },
    "balanced_add_history_right": {
        "layout": "Balanced",
        "steps": [
            {"label": "add_history_right", "op": "add", "title": "History", "area": Right},
        ],
    },
}


def scenario_names() -> list[str]:
    return list(SCENARIOS)
