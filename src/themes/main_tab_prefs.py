# SPDX-License-Identifier: MIT
"""QSettings + apply helpers for the main window tab strip."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6 import QtGui, QtWidgets

from themes.equal_tab_bar import (
    TAB_MIN_HEIGHT_DEFAULT,
    EqualWidthTabBar,
    clamp_tab_min_height,
    recompute_equal_tab_widths,
)
from themes.fonts_loader import apply_tab_bar_font
from themes.tab_icons import tab_icon

if TYPE_CHECKING:
    from app.window import MainWindow

TAB_ORDER_KEY = "ui/main_tab_order"
TAB_SHOW_ICONS_KEY = "ui/main_tab_show_icons"
TAB_MIN_HEIGHT_KEY = "ui/main_tab_min_height"


def _prefs_bool(val: object, default: bool = False) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return bool(val)
    if isinstance(val, str):
        v = val.strip().lower()
        if v in ("0", "false", "no", "off", ""):
            return False
        if v in ("1", "true", "yes", "on"):
            return True
    return default


DEFAULT_TAB_ORDER: tuple[str, ...] = (
    "project",
    "bom",
    "pnp",
    "package",
    "clean_bom",
    "merge",
    "pcb_preview",
    "step_3d",
    "machine_lib",
    "settings",
)


def default_order_for_available(available_keys: list[str]) -> list[str]:
    avail = set(available_keys)
    out = [k for k in DEFAULT_TAB_ORDER if k in avail]
    for k in available_keys:
        if k not in out:
            out.append(k)
    return out


def read_main_tab_order(settings: Any, available_keys: list[str]) -> list[str]:
    """Saved CSV order, skip unknown, append missing in default sequence."""
    avail = set(available_keys)
    raw = ""
    if settings is not None:
        raw = str(settings.value(TAB_ORDER_KEY, "") or "").strip()
    out: list[str] = []
    seen: set[str] = set()
    if raw:
        for part in raw.split(","):
            k = part.strip()
            if k in avail and k not in seen:
                out.append(k)
                seen.add(k)
    for k in default_order_for_available(list(available_keys)):
        if k not in seen:
            out.append(k)
            seen.add(k)
    return out


def write_main_tab_order(settings: Any, keys: list[str]) -> None:
    if settings is None:
        return
    settings.setValue(TAB_ORDER_KEY, ",".join(keys))


def read_show_tab_icons(settings: Any) -> bool:
    if settings is None:
        return True
    return _prefs_bool(settings.value(TAB_SHOW_ICONS_KEY, True), True)


def read_min_tab_height(settings: Any) -> int:
    if settings is None:
        return TAB_MIN_HEIGHT_DEFAULT
    v = settings.value(TAB_MIN_HEIGHT_KEY, TAB_MIN_HEIGHT_DEFAULT)
    try:
        return clamp_tab_min_height(int(v))
    except (TypeError, ValueError):
        return TAB_MIN_HEIGHT_DEFAULT


def apply_main_tab_order(main: MainWindow) -> None:
    tabs = main.tabs
    keys = list(getattr(main, "_tab_keys_in_order", []) or [])
    if not keys or tabs.count() != len(keys):
        return
    idx = tabs.currentIndex()
    current_key = keys[idx] if 0 <= idx < len(keys) else keys[0]
    widgets = {keys[i]: tabs.widget(i) for i in range(tabs.count())}
    texts = {keys[i]: tabs.tabText(i) for i in range(tabs.count())}
    icons = {keys[i]: tabs.tabIcon(i) for i in range(tabs.count())}
    order = read_main_tab_order(main._settings, keys)
    if order == keys:
        return
    tabs.blockSignals(True)
    while tabs.count():
        tabs.removeTab(0)
    new_keys: list[str] = []
    for k in order:
        w = widgets.get(k)
        if w is None:
            continue
        tabs.addTab(w, icons.get(k, QtGui.QIcon()), texts.get(k, k))
        new_keys.append(k)
    main._tab_keys_in_order = new_keys
    if current_key in new_keys:
        tabs.setCurrentIndex(new_keys.index(current_key))
    tabs.blockSignals(False)


def apply_main_tab_icons(main: MainWindow, show: bool) -> None:
    empty = QtGui.QIcon()
    for i, key in enumerate(main._tab_keys_in_order):
        main.tabs.setTabIcon(i, tab_icon(key) if show else empty)


def apply_main_tab_metrics(bar: QtWidgets.QTabBar, min_height: int) -> None:
    if isinstance(bar, EqualWidthTabBar):
        bar.set_min_tab_height(min_height)


def apply_all_main_tab_prefs(main: MainWindow) -> None:
    if not hasattr(main, "tabs"):
        return
    apply_main_tab_order(main)
    s = main._settings
    apply_main_tab_icons(main, read_show_tab_icons(s))
    apply_main_tab_metrics(main.tabs.tabBar(), read_min_tab_height(s))
    apply_tab_bar_font(main.tabs.tabBar(), s)
    recompute_equal_tab_widths(main.tabs)
