"""Qt stylesheet compatibility helpers for ldocking widgets."""
from __future__ import annotations

import re

_MARKER = "/* ldocking-qt-compat */"

_PLACEHOLDERS = {
    "__LDOCK_TITLE__": "#dockTitleBar",
    "__LDOCK_CLOSE__": "#dockCloseButton",
    "__LDOCK_FLOAT__": "#dockFloatButton",
    "__LDOCK_CONTENT__": "#dockContent",
    "__LMAIN_SEPARATOR__": "QSplitter::handle",
    "__LDOCK_TABBAR__": "#dockTabBar",
}


def translate_stylesheet(qss: str) -> str:
    """Translate common QMainWindow/QDockWidget selectors to ldocking widgets."""
    if not qss:
        return qss
    if _MARKER in qss:
        return qss

    translated = qss

    # Pseudo-element sub-controls (order matters: more specific before bare)
    translated = re.sub(r"QDockWidget\s*::\s*title", "__LDOCK_TITLE__", translated)
    translated = re.sub(
        r"QDockWidget\s*::\s*close-button", "__LDOCK_CLOSE__", translated
    )
    translated = re.sub(
        r"QDockWidget\s*::\s*float-button", "__LDOCK_FLOAT__", translated
    )
    translated = re.sub(
        r"QDockWidget\s*>\s*QWidget", "__LDOCK_CONTENT__", translated
    )
    translated = re.sub(
        r"QMainWindow\s*::\s*separator", "__LMAIN_SEPARATOR__", translated
    )

    # Tab bar selector inside a dock widget
    translated = re.sub(
        r"QDockWidget\s+QTabBar", "__LDOCK_TABBAR__", translated
    )

    # Bare class names (replace after sub-controls to avoid double-substitution)
    translated = re.sub(
        r"(?<![\w-])QDockWidget(?![\w:-])",
        'LDockWidget, QWidget[class="QDockWidget"]',
        translated,
    )
    translated = re.sub(
        r"(?<![\w-])QMainWindow(?![\w:-])",
        'LMainWindow, QWidget[class="QMainWindow"]',
        translated,
    )

    for placeholder, replacement in _PLACEHOLDERS.items():
        translated = translated.replace(placeholder, replacement)
    return f"{_MARKER}\n{translated}"
