"""Regression test: screenshot diff scores must stay within threshold.

Runs the full Qt-vs-ldocking screenshot capture on every pytest invocation so
stale PNGs can never silently exist alongside new code.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
# QT_QPA_PLATFORM is set by conftest.py for pytest runs (offscreen).
# Manual runs of screenshot_compare.py use the native platform for proper rendering.

import pytest
from PySide6.QtWidgets import QApplication

import screenshot_compare as sc

# In offscreen mode (CI/pytest) the comparison panes render without a real
# display, so scores are higher than on a desktop.  This threshold validates
# that the script runs and produces output; visual quality is assessed by
# running `python tests/screenshot_compare.py` on a native desktop.
THRESHOLD = 30.0


@pytest.fixture(scope="module")
def screenshot_results(tmp_path_factory):
    outdir = str(tmp_path_factory.mktemp("screenshots"))
    app = QApplication.instance() or QApplication(sys.argv)
    results = sc.capture_all(outdir, app)
    return results, outdir


def test_screenshot_scores(screenshot_results):
    results, _ = screenshot_results
    failures = [(n, s) for n, s in results if s > THRESHOLD]
    assert not failures, (
        "Screenshot diff scores exceed threshold ({}):\n".format(THRESHOLD)
        + "\n".join(f"  {n}: {s:.2f}" for n, s in failures)
    )


def test_screenshot_files_written(screenshot_results):
    _, outdir = screenshot_results
    for layout in sc.LAYOUTS:
        slug = layout.lower().replace(" ", "_")
        path = os.path.join(outdir, f"{slug}_side_by_side.png")
        assert os.path.isfile(path) and os.path.getsize(path) > 0, (
            f"Missing or empty screenshot: {path}"
        )
