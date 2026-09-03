# SPDX-License-Identifier: MIT
"""Main tab order, icons, and colour merge."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6 import QtCore, QtWidgets

from themes.colour_prefs import DEFAULT_TAB_COLOURS, merge_tab_colours
from themes.main_tab_prefs import (
    TAB_ORDER_KEY,
    TAB_SHOW_ICONS_KEY,
    apply_all_main_tab_prefs,
    read_main_tab_order,
    write_main_tab_order,
)


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


@pytest.fixture
def import_parsers():
    import parsers  # noqa: F401


def _ini_settings(tmp_path: Path) -> QtCore.QSettings:
    ini = tmp_path / "valvet.ini"
    return QtCore.QSettings(str(ini), QtCore.QSettings.Format.IniFormat)


def test_read_main_tab_order_skips_unknown_appends_missing() -> None:
    class _S:
        def value(self, key, default=""):
            if key == TAB_ORDER_KEY:
                return "settings,bogus,project"
            return default

    available = ["project", "bom", "settings"]
    order = read_main_tab_order(_S(), available)
    assert order[0] == "settings"
    assert order[1] == "project"
    assert "bogus" not in order
    assert "bom" in order
    assert set(order) == set(available)


def test_merge_tab_colours_defaults_and_override() -> None:
    merged = merge_tab_colours(None)
    assert merged == DEFAULT_TAB_COLOURS
    over = merge_tab_colours({"selected_bg": "#ff0000", "nope": "#000"})
    assert over["selected_bg"].lower() == "#ff0000"
    assert "nope" not in over
    assert over["bar_bg"] == DEFAULT_TAB_COLOURS["bar_bg"]


def test_apply_main_tab_order_and_icons(import_parsers, qapp, tmp_path) -> None:
    from app.window import MainWindow

    settings = _ini_settings(tmp_path)
    settings.setValue("experimental/enable_step_3d", False)
    write_main_tab_order(settings, ["settings", "project"])
    win = MainWindow(settings=settings)
    try:
        keys = win._tab_keys_in_order
        assert keys[0] == "settings"
        assert keys[1] == "project"
        assert win.tabs.widget(0) is win.tabs.widget(win._tab_index("settings"))
        assert not win.tabs.tabIcon(win._tab_index("project")).isNull()
        settings.setValue(TAB_SHOW_ICONS_KEY, False)
        apply_all_main_tab_prefs(win)
        assert win.tabs.tabIcon(win._tab_index("project")).isNull()
        settings.setValue(TAB_SHOW_ICONS_KEY, True)
        apply_all_main_tab_prefs(win)
        assert not win.tabs.tabIcon(win._tab_index("project")).isNull()
    finally:
        win.close()


def test_settings_tabs_page_present(import_parsers, qapp, tmp_path) -> None:
    from app.window import MainWindow

    settings = _ini_settings(tmp_path)
    settings.setValue("experimental/enable_step_3d", False)
    win = MainWindow(settings=settings)
    try:
        pages = win._settings_pages
        assert pages.page_tabs is not None
        assert pages._tabs_order_list.count() == win.tabs.count()
        pages._chk_tab_icons.setChecked(False)
        pages._spin_tab_height.setValue(36)
        pages._on_tabs_apply_clicked()
        assert win.tabs.tabIcon(win._tab_index("project")).isNull()
        from themes.equal_tab_bar import EqualWidthTabBar

        bar = win.tabs.tabBar()
        assert isinstance(bar, EqualWidthTabBar)
        assert bar.tabSizeHint(0).height() >= 36
    finally:
        win.close()
