"""Shared realistic dock panel factories for comparison tools.

Public API:
    make_panel(title: str) -> QWidget
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTextEdit,
    QTreeView,
    QVBoxLayout,
    QWidget,
)


def _make_inspector() -> QWidget:
    """Property inspector with form fields."""
    panel = QFrame()
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(6, 6, 6, 6)
    layout.setSpacing(4)
    form = QFormLayout()
    form.setContentsMargins(0, 0, 0, 0)
    form.setSpacing(4)
    form.addRow("Name:", QLineEdit("MainObject"))
    spin = QSpinBox()
    spin.setValue(42)
    form.addRow("Width:", spin)
    dspin = QDoubleSpinBox()
    dspin.setValue(1.0)
    form.addRow("Opacity:", dspin)
    combo = QComboBox()
    combo.addItems(["Solid", "Dashed", "Dotted"])
    form.addRow("Style:", combo)
    form.addRow("Visible:", QCheckBox())
    layout.addLayout(form)
    slider = QSlider(Qt.Orientation.Horizontal)
    slider.setValue(60)
    layout.addWidget(QLabel("Blend:"))
    layout.addWidget(slider)
    layout.addStretch()
    return panel


def _make_assets() -> QWidget:
    """Asset browser with a list."""
    panel = QFrame()
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(4, 4, 4, 4)
    layout.setSpacing(4)
    search = QLineEdit()
    search.setPlaceholderText("Search assets…")
    layout.addWidget(search)
    lst = QListWidget()
    lst.addItems(["texture_albedo.png", "mesh_hero.fbx", "anim_run.anim",
                  "material_metal.mat", "shader_pbr.glsl", "audio_footstep.wav"])
    layout.addWidget(lst, 1)
    row = QHBoxLayout()
    row.addWidget(QPushButton("Import"))
    row.addWidget(QPushButton("Refresh"))
    layout.addLayout(row)
    return panel


def _make_layers() -> QWidget:
    """Layer list with checkboxes via a tree view."""
    panel = QFrame()
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(4, 4, 4, 4)
    layout.setSpacing(4)
    model = QStandardItemModel(0, 2)
    model.setHorizontalHeaderLabels(["Layer", "Lock"])
    for name, locked in [("Background", False), ("Terrain", False),
                          ("Props", True), ("Characters", False), ("FX", False)]:
        item = QStandardItem(name)
        item.setCheckable(True)
        item.setCheckState(Qt.CheckState.Checked)
        lock = QStandardItem("🔒" if locked else "")
        model.appendRow([item, lock])
    tree = QTreeView()
    tree.setModel(model)
    tree.setColumnWidth(0, 100)
    tree.header().setStretchLastSection(True)
    layout.addWidget(tree, 1)
    return panel


def _make_console() -> QWidget:
    """Output console with log lines."""
    panel = QFrame()
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(4, 4, 4, 4)
    layout.setSpacing(4)
    log = QTextEdit()
    log.setReadOnly(True)
    log.setPlainText(
        "[INFO]  Scene loaded in 0.42 s\n"
        "[INFO]  Compiling shaders (12/12)\n"
        "[WARN]  Missing LOD for mesh_hero\n"
        "[INFO]  Physics world initialized\n"
        "[ERROR] audio_footstep.wav not found\n"
    )
    log.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
    layout.addWidget(log, 1)
    row = QHBoxLayout()
    row.addWidget(QLineEdit(), 1)
    row.addWidget(QPushButton("Run"))
    layout.addLayout(row)
    return panel


def _make_history() -> QWidget:
    """Undo/redo history list."""
    panel = QFrame()
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(4, 4, 4, 4)
    layout.setSpacing(4)
    lst = QListWidget()
    actions = ["Move object", "Scale mesh", "Add material",
                "Delete vertex", "UV unwrap", "Bake lighting"]
    for i, act in enumerate(actions):
        lst.addItem(f"{i + 1}. {act}")
    lst.setCurrentRow(3)
    layout.addWidget(lst, 1)
    row = QHBoxLayout()
    row.addWidget(QPushButton("Undo"))
    row.addWidget(QPushButton("Redo"))
    layout.addLayout(row)
    return panel


def _make_outline() -> QWidget:
    """Scene outliner tree."""
    panel = QFrame()
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(4, 4, 4, 4)
    layout.setSpacing(4)
    model = QStandardItemModel()
    model.setHorizontalHeaderLabels(["Scene"])
    root = QStandardItem("Scene Root")
    for child_name, grandchildren in [
        ("Environment", ["Sky", "Terrain", "Water"]),
        ("Characters", ["Hero", "NPC_01"]),
        ("Props", ["Crate_A", "Barrel_B"]),
    ]:
        child = QStandardItem(child_name)
        for gc in grandchildren:
            child.appendRow(QStandardItem(gc))
        root.appendRow(child)
    model.appendRow(root)
    tree = QTreeView()
    tree.setModel(model)
    tree.expandAll()
    tree.setHeaderHidden(True)
    layout.addWidget(tree, 1)
    return panel


def _fallback_panel(title: str) -> QWidget:
    panel = QFrame()
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.addWidget(QLabel(title))
    layout.addStretch()
    return panel


_PANEL_FACTORIES = {
    "Inspector": _make_inspector,
    "Assets":    _make_assets,
    "Layers":    _make_layers,
    "Console":   _make_console,
    "History":   _make_history,
    "Outline":   _make_outline,
}


def make_panel(title: str) -> QWidget:
    """Return the realistic content widget for a named dock panel.

    Wraps the inner widget in a QScrollArea so every dock reports the same
    compact sizeHint regardless of content, preventing QSplitter from
    skewing size distribution due to large preferred sizes.
    """
    factory = _PANEL_FACTORIES.get(title)
    inner = factory() if factory is not None else _fallback_panel(title)
    scroll = QScrollArea()
    scroll.setWidget(inner)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    return scroll
