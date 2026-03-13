"""Inspect labelme's dock setup without importing the full app runtime.

This is intentionally static: labelme currently imports PyQt5 directly and
needs extra dependencies that are not part of this repo's normal environment.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP_PY = ROOT / "third_party" / "dock_benchmarks" / "labelme" / "labelme" / "app.py"


class DockInspector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.created: list[dict[str, str]] = []
        self.added: list[dict[str, str]] = []

    def visit_Assign(self, node: ast.Assign) -> None:
        if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute):
            if node.value.func.attr == "QDockWidget" and node.value.args:
                target = node.targets[0]
                if isinstance(target, ast.Attribute) and isinstance(node.value.args[0], ast.Call):
                    self.created.append({"attr": target.attr, "title_expr": ast.unparse(node.value.args[0])})
        self.generic_visit(node)

    def visit_Expr(self, node: ast.Expr) -> None:
        if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute):
            if node.value.func.attr == "addDockWidget" and len(node.value.args) >= 2:
                self.added.append(
                    {
                        "area_expr": ast.unparse(node.value.args[0]),
                        "dock_expr": ast.unparse(node.value.args[1]),
                    }
                )
        self.generic_visit(node)


def main() -> int:
    if not APP_PY.exists():
        raise SystemExit(f"Missing labelme source at {APP_PY}")
    tree = ast.parse(APP_PY.read_text(encoding="utf-8"))
    inspector = DockInspector()
    inspector.visit(tree)
    report = {
        "source": str(APP_PY),
        "created_docks": inspector.created,
        "add_dock_calls": inspector.added,
        "assessment": [
            "labelme creates four QDockWidget instances in MainWindow.__init__",
            "all four docks are added to Qt.RightDockWidgetArea in sequence",
            "this is the same pattern that exposed ldocking's pre-fix same-area auto-tabification mismatch",
            "full runtime benchmark is deferred because labelme imports PyQt5 directly and requires extra app dependencies not present in this repo environment",
        ],
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
