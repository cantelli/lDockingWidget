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

from pathlib import Path
from xml.etree import ElementTree as ET

import PySide6.QtWidgets as _qw
from PySide6.QtCore import Qt

from .ldock_widget import LDockWidget
from .lmain_window import LMainWindow
from .stylesheet_compat import translate_stylesheet

# Capture originals at module load time — never overwritten by patch/unpatch
_ORIG: dict[str, type] = {
    "QMainWindow": _qw.QMainWindow,
    "QDockWidget": _qw.QDockWidget,
    "QApplication.setStyleSheet": _qw.QApplication.setStyleSheet,
}
_QTpy_UIC_LOADUI_ORIG = None

_patched = False


def _compat_set_style_sheet(self, styleSheet: str) -> None:
    _ORIG["QApplication.setStyleSheet"](self, translate_stylesheet(styleSheet))


def _ui_top_level_props(filename: str) -> tuple[str | None, str | None]:
    try:
        root = ET.parse(Path(filename)).getroot()
    except (OSError, ET.ParseError, TypeError, ValueError):
        return None, None
    widget = root.find("widget")
    if widget is None:
        return None, None
    object_name = widget.get("name")
    title = None
    for prop in widget.findall("property"):
        if prop.get("name") == "windowTitle":
            title_node = prop.find("string")
            if title_node is not None and title_node.text is not None:
                title = title_node.text
            break
    return object_name, title


def _ui_toolbar_specs(
    filename: str,
) -> list[tuple[str, Qt.ToolBarArea, bool]]:
    try:
        root = ET.parse(Path(filename)).getroot()
    except (OSError, ET.ParseError, TypeError, ValueError):
        return []
    widget = root.find("widget")
    if widget is None or widget.get("class") != "QMainWindow":
        return []
    specs: list[tuple[str, Qt.ToolBarArea, bool]] = []
    for child in widget.findall("widget"):
        if child.get("class") != "QToolBar":
            continue
        name = child.get("name") or ""
        area = Qt.ToolBarArea.TopToolBarArea
        tool_bar_break = False
        for attr in child.findall("attribute"):
            attr_name = attr.get("name")
            if attr_name == "toolBarArea":
                enum_node = attr.find("enum")
                enum_name = (enum_node.text or "").rsplit("::", 1)[-1] if enum_node is not None else ""
                area = getattr(Qt.ToolBarArea, enum_name, Qt.ToolBarArea.TopToolBarArea)
            elif attr_name == "toolBarBreak":
                bool_node = attr.find("bool")
                tool_bar_break = bool_node is not None and (bool_node.text or "").strip().lower() == "true"
        specs.append((name, area, tool_bar_break))
    return specs


def _find_direct_child(parent, cls, object_name: str | None = None):
    for child in parent.findChildren(cls, options=Qt.FindDirectChildrenOnly):
        if object_name is None or child.objectName() == object_name:
            return child
    return None


def _adopt_loaded_main_window_children(filename: str, window: LMainWindow) -> None:
    central = _find_direct_child(window, _qw.QWidget, "centralwidget")
    if central is not None:
        window.setCentralWidget(central)

    menu_bar = _find_direct_child(window, _qw.QMenuBar, "menubar")
    if menu_bar is None:
        for candidate in window.findChildren(_qw.QMenuBar, options=Qt.FindDirectChildrenOnly):
            if candidate.actions():
                menu_bar = candidate
                break
    if menu_bar is not None:
        window.setMenuBar(menu_bar)

    status_bar = _find_direct_child(window, _qw.QStatusBar, "statusbar")
    if status_bar is None:
        status_bar = _find_direct_child(window, _qw.QStatusBar)
    if status_bar is not None:
        window.setStatusBar(status_bar)

    toolbars = {
        toolbar.objectName(): toolbar
        for toolbar in window.findChildren(_qw.QToolBar, options=Qt.FindDirectChildrenOnly)
    }
    added: set[_qw.QToolBar] = set()
    for toolbar_name, area, tool_bar_break in _ui_toolbar_specs(filename):
        toolbar = toolbars.get(toolbar_name)
        if toolbar is None:
            continue
        if tool_bar_break:
            window.addToolBarBreak(area)
        window.addToolBar(area, toolbar)
        added.add(toolbar)
    for toolbar in window.findChildren(_qw.QToolBar, options=Qt.FindDirectChildrenOnly):
        if toolbar in added:
            continue
        window.addToolBar(toolbar)


def _patch_qtpy_uic() -> None:
    global _QTpy_UIC_LOADUI_ORIG
    if _QTpy_UIC_LOADUI_ORIG is not None:
        return
    try:
        from qtpy import uic as qtpy_uic
    except ImportError:
        return

    original = getattr(qtpy_uic, "loadUi", None)
    if original is None:
        return

    def _compat_load_ui(uifile, baseinstance=None, *args, **kwargs):
        ui_file = str(uifile)
        existing_name = (
            baseinstance.objectName()
            if isinstance(baseinstance, (_qw.QDockWidget, _qw.QMainWindow))
            else ""
        )
        existing_title = (
            baseinstance.windowTitle()
            if isinstance(baseinstance, (_qw.QDockWidget, _qw.QMainWindow))
            else ""
        )
        result = original(uifile, baseinstance, *args, **kwargs)
        if isinstance(baseinstance, (_qw.QDockWidget, _qw.QMainWindow)):
            ui_name, ui_title = _ui_top_level_props(ui_file)
            current_name = baseinstance.objectName()
            if existing_name and current_name == ui_name and ui_name in {"DockWidget", "MainWindow"}:
                baseinstance.setObjectName(existing_name)
            if not baseinstance.windowTitle() and ui_title:
                baseinstance.setWindowTitle(ui_title)
            elif not baseinstance.windowTitle() and existing_title:
                baseinstance.setWindowTitle(existing_title)
        if isinstance(baseinstance, LMainWindow):
            _adopt_loaded_main_window_children(ui_file, baseinstance)
        return result

    qtpy_uic.loadUi = _compat_load_ui
    _QTpy_UIC_LOADUI_ORIG = original


def _unpatch_qtpy_uic() -> None:
    global _QTpy_UIC_LOADUI_ORIG
    if _QTpy_UIC_LOADUI_ORIG is None:
        return
    try:
        from qtpy import uic as qtpy_uic
    except ImportError:
        _QTpy_UIC_LOADUI_ORIG = None
        return
    qtpy_uic.loadUi = _QTpy_UIC_LOADUI_ORIG
    _QTpy_UIC_LOADUI_ORIG = None


def patch() -> None:
    """Replace QMainWindow and QDockWidget in PySide6.QtWidgets with L* versions."""
    global _patched
    _qw.QMainWindow = LMainWindow  # type: ignore[attr-defined]
    _qw.QDockWidget = LDockWidget  # type: ignore[attr-defined]
    _qw.QApplication.setStyleSheet = _compat_set_style_sheet  # type: ignore[assignment]
    _patch_qtpy_uic()
    _patched = True


def unpatch() -> None:
    """Restore the original PySide6 classes."""
    global _patched
    _qw.QMainWindow = _ORIG["QMainWindow"]  # type: ignore[attr-defined]
    _qw.QDockWidget = _ORIG["QDockWidget"]  # type: ignore[attr-defined]
    _qw.QApplication.setStyleSheet = _ORIG["QApplication.setStyleSheet"]  # type: ignore[assignment]
    _unpatch_qtpy_uic()
    _patched = False


def is_patched() -> bool:
    """Return True if the patch is currently active."""
    return _patched


# Apply automatically when this module is imported
patch()
