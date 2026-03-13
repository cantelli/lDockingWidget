"""Behavioral parity tests: signals, feature-flag enforcement, toggleViewAction,
resizeDocks, and other QDockWidget/QMainWindow contract items.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QLabel

from ldocking import (
    LDockWidget,
    LDragManager,
    LMainWindow,
    AllowNestedDocks,
    GroupedDragging,
    LeftDockWidgetArea,
    RightDockWidgetArea,
    TopDockWidgetArea,
    BottomDockWidgetArea,
    DockWidgetClosable,
    DockWidgetMovable,
    DockWidgetFloatable,
    NoDockWidgetFeatures,
    AllDockWidgetFeatures,
    ForceTabbedDocks,
)


def _dock(name: str) -> LDockWidget:
    d = LDockWidget(name)
    d.setObjectName(name)
    d.setWidget(QLabel(name))
    return d


def _tree_shape(node) -> tuple:
    if hasattr(node, "widget") and hasattr(node, "key"):
        return ("leaf", node.key)
    return (
        "split",
        int(node.orientation.value),
        tuple(_tree_shape(child) for child in node.children),
    )


# ------------------------------------------------------------------
# Signal: featuresChanged
# ------------------------------------------------------------------

def test_features_changed_fires(qapp):
    """featuresChanged emits when features actually change."""
    dock = _dock("d")
    received = []
    dock.featuresChanged.connect(lambda v: received.append(v))

    dock.setFeatures(DockWidgetClosable)
    assert len(received) == 1
    assert received[0] == DockWidgetClosable


def test_features_changed_no_fire_on_same_value(qapp):
    """featuresChanged does NOT emit when the same features are set again."""
    dock = _dock("d")
    dock.setFeatures(DockWidgetClosable)

    received = []
    dock.featuresChanged.connect(lambda v: received.append(v))
    dock.setFeatures(DockWidgetClosable)  # same value — no signal

    assert received == []


# ------------------------------------------------------------------
# Signal: allowedAreasChanged
# ------------------------------------------------------------------

def test_allowed_areas_changed_fires(qapp):
    """allowedAreasChanged emits when areas actually change."""
    dock = _dock("d")
    received = []
    dock.allowedAreasChanged.connect(lambda v: received.append(v))

    dock.setAllowedAreas(LeftDockWidgetArea)
    assert len(received) == 1


def test_allowed_areas_changed_no_fire_on_same_value(qapp):
    """allowedAreasChanged does NOT emit for a no-change setAllowedAreas."""
    dock = _dock("d")
    dock.setAllowedAreas(LeftDockWidgetArea)

    received = []
    dock.allowedAreasChanged.connect(lambda v: received.append(v))
    dock.setAllowedAreas(LeftDockWidgetArea)

    assert received == []


# ------------------------------------------------------------------
# Signal: visibilityChanged
# ------------------------------------------------------------------

def test_visibility_changed_on_hide_show(qapp):
    """visibilityChanged fires True on show and False on hide."""
    win = LMainWindow()
    dock = _dock("d")
    win.addDockWidget(LeftDockWidgetArea, dock)

    received = []
    dock.visibilityChanged.connect(lambda v: received.append(v))

    dock.hide()
    dock.show()

    assert False in received
    assert True in received


# ------------------------------------------------------------------
# Signal: dockLocationChanged
# ------------------------------------------------------------------

def test_dock_location_changed_fires(qapp):
    """dockLocationChanged emits the correct area when dock is added."""
    win = LMainWindow()
    dock = _dock("d")

    received = []
    dock.dockLocationChanged.connect(lambda a: received.append(a))

    win.addDockWidget(LeftDockWidgetArea, dock)
    assert received == [LeftDockWidgetArea]

    win.addDockWidget(RightDockWidgetArea, dock)
    assert received[-1] == RightDockWidgetArea


# ------------------------------------------------------------------
# Signal: topLevelChanged
# ------------------------------------------------------------------

def test_top_level_changed_on_float(qapp):
    """topLevelChanged(True) fires when dock floats, False when re-docked."""
    win = LMainWindow()
    win.resize(800, 600)
    dock = _dock("d")
    win.addDockWidget(LeftDockWidgetArea, dock)

    received = []
    dock.topLevelChanged.connect(lambda v: received.append(v))

    dock.setFloating(True)
    assert True in received

    dock.setFloating(False)
    assert False in received


# ------------------------------------------------------------------
# Feature flag enforcement: Floatable
# ------------------------------------------------------------------

def test_floatable_flag_controls_float_button(qapp):
    """Float button is hidden when DockWidgetFloatable is cleared."""
    dock = _dock("d")
    dock.setFeatures(DockWidgetClosable | DockWidgetMovable)  # no Floatable
    assert dock._title_bar._float_btn.isHidden()

    dock.setFeatures(AllDockWidgetFeatures)
    assert not dock._title_bar._float_btn.isHidden()


def test_floatable_flag_prevents_float(qapp):
    """Dock cannot float when DockWidgetFloatable is cleared."""
    win = LMainWindow()
    win.resize(800, 600)
    dock = _dock("d")
    win.addDockWidget(LeftDockWidgetArea, dock)
    dock.setFeatures(DockWidgetClosable | DockWidgetMovable)

    dock.setFloating(True)
    # setFloating should be a no-op because Floatable is off
    assert not dock.isFloating()


# ------------------------------------------------------------------
# Feature flag enforcement: Closable
# ------------------------------------------------------------------

def test_closable_flag_controls_close_button(qapp):
    """Close button is hidden when DockWidgetClosable is cleared."""
    dock = _dock("d")
    dock.setFeatures(DockWidgetMovable | DockWidgetFloatable)  # no Closable
    assert dock._title_bar._close_btn.isHidden()

    dock.setFeatures(AllDockWidgetFeatures)
    assert not dock._title_bar._close_btn.isHidden()


# ------------------------------------------------------------------
# toggleViewAction
# ------------------------------------------------------------------

def test_toggle_view_action_is_checkable(qapp):
    """toggleViewAction() returns a checkable QAction."""
    dock = _dock("d")
    action = dock.toggleViewAction()
    assert action.isCheckable()


def test_toggle_view_action_same_instance(qapp):
    """toggleViewAction() returns the same QAction on repeated calls."""
    dock = _dock("d")
    assert dock.toggleViewAction() is dock.toggleViewAction()


def test_toggle_view_action_text_matches_title(qapp):
    """Action text matches the dock's window title."""
    dock = _dock("MyTitle")
    assert dock.toggleViewAction().text() == "MyTitle"


def test_toggle_view_action_text_updates_on_rename(qapp):
    """Renaming the dock updates the action text."""
    dock = _dock("OldName")
    dock.setWindowTitle("NewName")
    assert dock.toggleViewAction().text() == "NewName"


def test_toggle_view_action_hides_dock(qapp):
    """Triggering the action (unchecked) hides the dock."""
    win = LMainWindow()
    dock = _dock("d")
    win.addDockWidget(LeftDockWidgetArea, dock)
    dock.show()

    action = dock.toggleViewAction()
    action.setChecked(False)
    assert not dock.isVisible()


def test_toggle_view_action_shows_dock(qapp):
    """Triggering the action (checked) shows the dock."""
    win = LMainWindow()
    dock = _dock("d")
    win.addDockWidget(LeftDockWidgetArea, dock)
    dock.hide()

    action = dock.toggleViewAction()
    action.setChecked(True)
    assert not dock.isHidden()


def test_toggle_view_action_show_selects_tab(qapp):
    """Showing a hidden tabbed dock makes it the active tab again."""
    win = LMainWindow()
    da = _dock("da")
    db = _dock("db")
    win.addDockWidget(LeftDockWidgetArea, da)
    win.addDockWidget(LeftDockWidgetArea, db)

    area = win._dock_areas[LeftDockWidgetArea]
    area.set_current_tab_dock(da)
    db.hide()

    db.toggleViewAction().setChecked(True)

    assert area.current_tab_dock() is db


def test_toggle_view_action_restores_hidden_floating_dock(qapp):
    """Showing a hidden floating dock keeps it floating."""
    win = LMainWindow()
    dock = _dock("d")
    win.addDockWidget(LeftDockWidgetArea, dock)
    dock.setFloating(True)
    dock.hide()

    dock.toggleViewAction().setChecked(True)

    assert dock.isVisible()
    assert dock.isFloating()


def test_force_tabbed_docks_tabs_same_area(qapp):
    """ForceTabbedDocks keeps same-area docks in a tab group."""
    win = LMainWindow()
    win.setDockOptions(ForceTabbedDocks)
    da = _dock("da")
    db = _dock("db")

    win.addDockWidget(LeftDockWidgetArea, da)
    win.addDockWidget(LeftDockWidgetArea, db)

    assert db in win.tabifiedDockWidgets(da)


def test_drag_manager_classifies_area_center_as_tab_target(qapp):
    """Dragging over the center of a visible dock area yields a tab target."""
    win = LMainWindow()
    win.resize(900, 700)
    win.show()
    dock = _dock("d")
    win.addDockWidget(LeftDockWidgetArea, dock)
    qapp.processEvents()

    dm = LDragManager.instance()
    area = win._dock_areas[LeftDockWidgetArea]
    center_global = area.mapToGlobal(area.rect().center())
    local = win.mapFromGlobal(center_global)

    dm._dock = dock
    target = dm._classify_drop_zone(win, local)

    assert target is not None
    assert target.area_side == LeftDockWidgetArea
    assert target.mode == "tab"
    assert target.target_id == "d"
    win.hide()


def test_drag_manager_classifies_window_edge_as_side_target(qapp):
    """Dragging near the main-window edge yields a side-dock target."""
    win = LMainWindow()
    win.resize(900, 700)
    win.show()
    dock = _dock("d")
    win.addDockWidget(LeftDockWidgetArea, dock)
    qapp.processEvents()

    dm = LDragManager.instance()
    dm._dock = dock
    target = dm._classify_drop_zone(win, win.rect().topLeft() + QPoint(5, 100))

    assert target is not None
    assert target.area_side == LeftDockWidgetArea
    assert target.mode == "side"
    win.hide()


def test_drag_manager_classifies_central_edge_as_area_target(qapp):
    """Dragging over a central-widget edge yields a root-tree area target."""
    win = LMainWindow()
    win.resize(900, 700)
    win.setCentralWidget(QLabel("central"))
    win.show()
    dock = _dock("d")
    qapp.processEvents()

    dm = LDragManager.instance()
    dm._dock = dock
    central = win.centralWidget()
    local = central.rect().center()
    local.setX(5)
    target = dm._classify_drop_zone(win, central.mapToGlobal(local), win.mapFromGlobal(central.mapToGlobal(local)))

    assert target is not None
    assert target.area_side == LeftDockWidgetArea
    assert target.mode == "area"
    assert target.target_key == "central"
    win.hide()


def test_allow_nested_docks_creates_nested_split(qapp):
    """AllowNestedDocks enables relative splits inside an occupied dock area."""
    win = LMainWindow()
    win.setDockOptions(AllowNestedDocks | ForceTabbedDocks)
    da = _dock("da")
    db = _dock("db")
    dc = _dock("dc")
    win.addDockWidget(LeftDockWidgetArea, da)
    win.addDockWidget(LeftDockWidgetArea, db)

    area = win._dock_areas[LeftDockWidgetArea]
    area.split_docks(da, [dc], RightDockWidgetArea)

    assert area._split_area is not None
    assert dc in area.all_docks()


def test_grouped_dragging_uses_full_tab_payload(qapp):
    """GroupedDragging tears off the whole tab group rather than one dock."""
    win = LMainWindow()
    win.setDockOptions(ForceTabbedDocks | GroupedDragging)
    da = _dock("da")
    db = _dock("db")
    win.addDockWidget(LeftDockWidgetArea, da)
    win.addDockWidget(LeftDockWidgetArea, db)

    payload = win._dock_areas[LeftDockWidgetArea].docks_for_group_drag(da)

    assert payload == [da, db]


def test_grouped_dragging_drop_preserves_current_tab(qapp):
    """Dropping a grouped tab payload keeps the selected tab in the moved group."""
    win = LMainWindow()
    win.setDockOptions(ForceTabbedDocks | GroupedDragging)
    da = _dock("da")
    db = _dock("db")
    target = _dock("target")
    win.addDockWidget(LeftDockWidgetArea, da)
    win.addDockWidget(LeftDockWidgetArea, db)
    win.addDockWidget(RightDockWidgetArea, target)

    source_area = win._dock_areas[LeftDockWidgetArea]
    source_area.set_current_tab_dock(db)
    payload = source_area.docks_for_group_drag(db)

    win._drop_docks(RightDockWidgetArea, payload, mode="side", target_dock=target, side=BottomDockWidgetArea)

    right_area = win._dock_areas[RightDockWidgetArea]
    assert [dock.windowTitle() for dock in right_area.all_docks()] == ["target", "da", "db"]
    assert right_area.current_tab_dock() is db


def test_drop_docks_accepts_target_id_without_target_widget(qapp):
    """Tree-driven drop accepts a stable target id without a live target widget object."""
    win = LMainWindow()
    win.setDockOptions(AllowNestedDocks | ForceTabbedDocks)
    anchor = _dock("anchor")
    moved = _dock("moved")
    win.addDockWidget(RightDockWidgetArea, anchor)

    win._drop_docks(
        RightDockWidgetArea,
        [moved],
        mode="side",
        target_id="anchor",
        side=BottomDockWidgetArea,
    )

    right_leaf = win._leaf_for_key("right")
    assert right_leaf is not None
    assert right_leaf.area_state["type"] == "split"
    assert [dock.windowTitle() for dock in win._dock_areas[RightDockWidgetArea].all_docks()] == ["anchor", "moved"]


def test_root_tree_grows_around_central_widget(qapp):
    """Top-level content tree inserts area leaves relative to the central leaf."""
    win = LMainWindow()
    left = _dock("left")
    top = _dock("top")
    right = _dock("right")

    win.addDockWidget(LeftDockWidgetArea, left)
    win.addDockWidget(TopDockWidgetArea, top)
    win.addDockWidget(RightDockWidgetArea, right)

    assert _tree_shape(win._content_tree) == (
        "split",
        int(Qt.Orientation.Horizontal.value),
        (
            ("leaf", "left"),
            (
                "split",
                int(Qt.Orientation.Vertical.value),
                (
                    ("leaf", "top"),
                    ("leaf", "central"),
                ),
            ),
            ("leaf", "right"),
        ),
    )


def test_root_tree_prunes_empty_area_leaves(qapp):
    """Removing the last dock from a side collapses that area out of the root tree."""
    win = LMainWindow()
    left = _dock("left")
    top = _dock("top")

    win.addDockWidget(LeftDockWidgetArea, left)
    win.addDockWidget(TopDockWidgetArea, top)
    win.removeDockWidget(left)

    assert win._leaf_for_key("left") is None
    assert _tree_shape(win._content_tree) == (
        "split",
        int(Qt.Orientation.Vertical.value),
        (
            ("leaf", "top"),
            ("leaf", "central"),
        ),
    )


# ------------------------------------------------------------------
# resizeDocks
# ------------------------------------------------------------------

def test_resize_docks_horizontal(qapp):
    """resizeDocks changes the outer splitter size for a left dock."""
    win = LMainWindow()
    win.resize(800, 600)
    win.show()

    dock = _dock("d")
    win.addDockWidget(LeftDockWidgetArea, dock)

    win.resizeDocks([dock], [200], Qt.Orientation.Horizontal)
    sizes = win._outer_splitter.sizes()
    left_idx = win._outer_splitter.indexOf(win._dock_areas[LeftDockWidgetArea])
    assert sizes[left_idx] == 200

    win.hide()


def test_resize_docks_vertical(qapp):
    """resizeDocks changes the inner splitter size for a top dock."""
    win = LMainWindow()
    win.resize(800, 600)
    win.show()

    dock = _dock("d")
    win.addDockWidget(TopDockWidgetArea, dock)

    win.resizeDocks([dock], [150], Qt.Orientation.Vertical)
    sizes = win._inner_splitter.sizes()
    top_idx = win._inner_splitter.indexOf(win._dock_areas[TopDockWidgetArea])
    assert sizes[top_idx] == 150

    win.hide()


# ------------------------------------------------------------------
# tabifiedDockWidgets
# ------------------------------------------------------------------

def test_tabified_dock_widgets(qapp):
    """tabifiedDockWidgets returns peers excluding the queried dock."""
    win = LMainWindow()
    da = _dock("da")
    db = _dock("db")
    dc = _dock("dc")
    win.addDockWidget(LeftDockWidgetArea, da)
    win.addDockWidget(LeftDockWidgetArea, db)
    win.addDockWidget(LeftDockWidgetArea, dc)

    peers_of_da = win.tabifiedDockWidgets(da)
    assert db in peers_of_da
    assert dc in peers_of_da
    assert da not in peers_of_da


def test_tabified_dock_widgets_empty_when_alone(qapp):
    """tabifiedDockWidgets returns [] for a dock that is the only one in its area."""
    win = LMainWindow()
    da = _dock("da")
    win.addDockWidget(LeftDockWidgetArea, da)
    assert win.tabifiedDockWidgets(da) == []


# ------------------------------------------------------------------
# dockWidgetArea
# ------------------------------------------------------------------

def test_dock_widget_area_tracks_moves(qapp):
    """dockWidgetArea returns the correct area after moving a dock."""
    win = LMainWindow()
    dock = _dock("d")
    win.addDockWidget(LeftDockWidgetArea, dock)
    assert win.dockWidgetArea(dock) == LeftDockWidgetArea

    win.addDockWidget(RightDockWidgetArea, dock)
    assert win.dockWidgetArea(dock) == RightDockWidgetArea


def test_dock_widget_area_unknown_returns_none(qapp):
    """dockWidgetArea returns NoDockWidgetArea for unregistered docks."""
    win = LMainWindow()
    dock = _dock("d")
    assert win.dockWidgetArea(dock) == Qt.DockWidgetArea.NoDockWidgetArea


def test_dock_widget_area_derives_from_live_layout_not_cache(qapp):
    """dockWidgetArea follows the live area contents even if the cache is stale."""
    win = LMainWindow()
    dock = _dock("d")
    win.addDockWidget(LeftDockWidgetArea, dock)

    win._dock_map[dock] = RightDockWidgetArea

    assert win.dockWidgetArea(dock) == LeftDockWidgetArea


def test_add_dock_widget_falls_back_to_first_allowed_area(qapp):
    """addDockWidget docks into the first allowed area when preferred area is invalid."""
    win = LMainWindow()
    dock = _dock("d")
    dock.setAllowedAreas(RightDockWidgetArea | BottomDockWidgetArea)

    win.addDockWidget(LeftDockWidgetArea, dock)

    assert win.dockWidgetArea(dock) == RightDockWidgetArea


def test_add_dock_widget_noops_when_no_areas_allowed(qapp):
    """addDockWidget leaves the dock untouched when no dock areas are allowed."""
    win = LMainWindow()
    dock = _dock("d")
    dock.setAllowedAreas(Qt.DockWidgetArea.NoDockWidgetArea)

    win.addDockWidget(LeftDockWidgetArea, dock)

    assert win.dockWidgetArea(dock) == Qt.DockWidgetArea.NoDockWidgetArea


# ------------------------------------------------------------------
# removeDockWidget
# ------------------------------------------------------------------

def test_remove_dock_widget(qapp):
    """removeDockWidget unregisters the dock from the window."""
    win = LMainWindow()
    dock = _dock("d")
    win.addDockWidget(LeftDockWidgetArea, dock)
    win.removeDockWidget(dock)
    assert win.dockWidgetArea(dock) == Qt.DockWidgetArea.NoDockWidgetArea


def test_remove_dock_widget_noop_unknown(qapp):
    """removeDockWidget on an unknown dock does not raise."""
    win = LMainWindow()
    dock = _dock("d")
    win.removeDockWidget(dock)  # should not raise
