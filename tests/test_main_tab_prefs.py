# SPDX-License-Identifier: MIT
"""Main tab order, icons, and colour merge."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6 import QtCore

from themes.colour_prefs import DEFAULT_TAB_COLOURS, merge_tab_colours
from themes.main_tab_prefs import (
    TAB_ORDER_KEY,
    TAB_SHOW_ICONS_KEY,
    apply_all_main_tab_prefs,
    read_main_tab_order,
    write_main_tab_order,
)


def _ini_settings(tmp_path: Path) -> QtCore.QSettings:
    ini = tmp_path / "valvet.ini"
    return QtCore.QSettings(str(ini), QtCore.QSettings.Format.IniFormat)


@pytest.fixture
def main_window(qapp, tmp_path):
    """Function-scoped MainWindow for tests that modify window state."""
    from app.window import MainWindow

    settings = _ini_settings(tmp_path)
    settings.setValue("experimental/enable_step_3d", False)
    win = MainWindow(settings=settings)
    yield win
    win.close()


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


def test_apply_main_tab_order_and_icons(import_parsers, main_window) -> None:

    from themes.main_tab_prefs import (
        TAB_ORDER_KEY,
    )

    settings = main_window._settings
    write_main_tab_order(settings, ["settings", "project"])
    # Apply the new tab order
    apply_all_main_tab_prefs(main_window)
    keys = main_window._tab_keys_in_order
    assert keys[0] == "settings"
    assert keys[1] == "project"
    assert main_window.tabs.widget(0) is main_window.tabs.widget(
        main_window._tab_index("settings")
    )
    assert not main_window.tabs.tabIcon(main_window._tab_index("project")).isNull()
    # The hidden Scan page survives a tab reorder and stays out of the bar.
    scan_idx = main_window.tabs.indexOf(main_window._scan_tab)
    assert scan_idx >= 0
    assert not main_window.tabs.isTabVisible(scan_idx)
    assert main_window.tabs.count() == len(keys) + 1
    settings.setValue(TAB_SHOW_ICONS_KEY, False)
    apply_all_main_tab_prefs(main_window)
    assert main_window.tabs.tabIcon(main_window._tab_index("project")).isNull()
    settings.setValue(TAB_SHOW_ICONS_KEY, True)
    apply_all_main_tab_prefs(main_window)
    assert not main_window.tabs.tabIcon(main_window._tab_index("project")).isNull()
    # Clean up
    settings.remove(TAB_ORDER_KEY)
    settings.remove(TAB_SHOW_ICONS_KEY)


def test_settings_tabs_page_present(import_parsers, main_window) -> None:

    from themes.equal_tab_bar import EqualWidthTabBar

    pages = main_window._settings_pages
    assert pages.page_tabs is not None
    assert pages._tabs_order_list.count() == len(main_window._tab_keys_in_order)
    pages._chk_tab_icons.setChecked(False)
    pages._spin_tab_height.setValue(36)
    pages._on_tabs_apply_clicked()
    assert main_window.tabs.tabIcon(main_window._tab_index("project")).isNull()
    bar = main_window.tabs.tabBar()
    assert isinstance(bar, EqualWidthTabBar)
    assert bar.tabSizeHint(0).height() >= 36
