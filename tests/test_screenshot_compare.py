"""Regression test: screenshot diff capture must run and write expected files."""
from __future__ import annotations

import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))

from compare_scenarios import SCENARIOS
import screenshot_compare as sc

THRESHOLD = 30.0
FLOATING_THRESHOLD = 60.0
STYLED_THRESHOLD = 35.0
_CAPTURE_RE = re.compile(r"Capturing:\s+(?P<name>.+?)\s+\.\.\.\s+diff=(?P<score>\d+\.\d+)")


def _parse_scores(stdout: str) -> dict[str, float]:
    scores: dict[str, float] = {}
    for line in stdout.splitlines():
        match = _CAPTURE_RE.search(line)
        if match:
            scores[match.group("name")] = float(match.group("score"))
    return scores


def _scenario_capture_names() -> list[str]:
    names: list[str] = []
    for scenario_name, scenario in SCENARIOS.items():
        names.append(f"{scenario_name}__00_initial")
        for index, step in enumerate(scenario["steps"], start=1):
            names.append(f"{scenario_name}__{index:02d}_{step['label']}")
    return names


def test_screenshot_compare_script_runs_and_writes_files():
    outdir = os.path.join(os.getcwd(), "tests", "screenshots", "_pytest_capture")
    os.makedirs(outdir, exist_ok=True)
    env = os.environ.copy()
    env.pop("QT_QPA_PLATFORM", None)
    proc = subprocess.run(
        [sys.executable, os.path.join("tests", "screenshot_compare.py"), "--outdir", outdir],
        cwd=os.getcwd(),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stdout + "\nSTDERR:\n" + proc.stderr
    scores = _parse_scores(proc.stdout)

    failures = []
    for name, score in scores.items():
        threshold = THRESHOLD
        if name.startswith("undock_all_") or name == "float_dock":
            threshold = FLOATING_THRESHOLD
        elif name.startswith("styled_"):
            threshold = STYLED_THRESHOLD
        if score > threshold:
            failures.append((name, score, threshold))
    assert not failures, (
        "Screenshot diff scores exceed threshold:\n"
        + "\n".join(f"  {n}: {s:.2f} > {t:.2f}" for n, s, t in failures)
    )

    for layout in sc.LAYOUTS:
        slug = layout.lower().replace(" ", "_")
        path = os.path.join(outdir, f"{slug}_side_by_side.png")
        assert os.path.isfile(path) and os.path.getsize(path) > 0, (
            f"Missing or empty screenshot: {path}"
        )

    for stem in (
        "float_main",
        "float_dock",
        "redock",
        "undock_all_main",
        "undock_all_scene",
        "undock_all_inspector",
        "undock_all_assets",
        "undock_all_layers",
        "undock_all_console",
    ):
        path = os.path.join(outdir, f"{stem}_side_by_side.png")
        assert os.path.isfile(path) and os.path.getsize(path) > 0, (
            f"Missing or empty screenshot: {path}"
        )

    for stem in _scenario_capture_names():
        path = os.path.join(outdir, f"{stem}_side_by_side.png")
        assert os.path.isfile(path) and os.path.getsize(path) > 0, (
            f"Missing or empty screenshot: {path}"
        )

    for stem in (
        "styled_direct_single_left",
        "styled_direct_balanced",
        "styled_direct_tabbed_left",
        "styled_direct_balanced__00_initial",
        "styled_direct_balanced__01_float_layers",
        "styled_direct_balanced__02_redock_layers",
        "styled_patched_balanced",
        "styled_patched_tabbed_left",
    ):
        path = os.path.join(outdir, f"{stem}_side_by_side.png")
        assert os.path.isfile(path) and os.path.getsize(path) > 0, (
            f"Missing or empty screenshot: {path}"
        )
