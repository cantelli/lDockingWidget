"""Pytest configuration for lDockingWidget tests.

Sets QT_QPA_PLATFORM=offscreen so all tests run headlessly without a display server.
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Exclude legacy standalone scripts — they call sys.exit() at module level
# and are not pytest-compatible. Use the test_*.py equivalents instead.
collect_ignore = [
    "test_dock_stability.py",
    "parity_test.py",
]

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app
