"""ldocking.monkey — automatic drop-in replacement for QMainWindow / QDockWidget.

Import this module once, as early as possible in your application (before any
code that imports QMainWindow or QDockWidget from PySide6.QtWidgets):

    import ldocking.monkey          # top of main.py; must precede PySide6 imports

After this, any code that does:

    from PySide6.QtWidgets import QMainWindow, QDockWidget

will receive LMainWindow and LDockWidget instead.  Existing code requires no
other changes.  isinstance checks work correctly because the name ``QMainWindow``
in the caller's namespace now refers to ``LMainWindow``.

API
---
patch()      — apply the replacements (called automatically on import)
unpatch()    — restore the originals (useful in tests or conditional rollback)
is_patched() -> bool
"""
from __future__ import annotations

import PySide6.QtWidgets as _qw

from .ldock_widget import LDockWidget
from .lmain_window import LMainWindow

# Capture originals at module load time — never overwritten by patch/unpatch
_ORIG: dict[str, type] = {
    "QMainWindow": _qw.QMainWindow,
    "QDockWidget": _qw.QDockWidget,
}

_patched = False


def patch() -> None:
    """Replace QMainWindow and QDockWidget in PySide6.QtWidgets with L* versions."""
    global _patched
    _qw.QMainWindow = LMainWindow  # type: ignore[attr-defined]
    _qw.QDockWidget = LDockWidget  # type: ignore[attr-defined]
    _patched = True


def unpatch() -> None:
    """Restore the original PySide6 classes."""
    global _patched
    _qw.QMainWindow = _ORIG["QMainWindow"]  # type: ignore[attr-defined]
    _qw.QDockWidget = _ORIG["QDockWidget"]  # type: ignore[attr-defined]
    _patched = False


def is_patched() -> bool:
    """Return True if the patch is currently active."""
    return _patched


# Apply automatically when this module is imported
patch()
