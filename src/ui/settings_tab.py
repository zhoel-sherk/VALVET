"""Settings main tab: left rail + stacked pages."""

from __future__ import annotations

from PySide6 import QtWidgets

from ui.chrome import (
    CHROME_MARGIN,
    CHROME_SPACING,
    action_button,
    apply_equal_widths,
    left_rail_widget,
)
from ui.settings_pages import SettingsPages

SETTINGS_NAV_KEYS = (
    "settings.nav_snapshots",
    "settings.nav_cache",
    "settings.nav_session",
    "settings.nav_fonts",
    "settings.nav_colours",
    "settings.nav_tabs",
    "settings.nav_experimental",
)


class SettingsTabMixin:
    def _create_settings_tab(self) -> None:
        tab = QtWidgets.QWidget()
        self._register_main_tab("settings", tab)

        root = QtWidgets.QHBoxLayout(tab)
        root.setContentsMargins(
            CHROME_MARGIN, CHROME_MARGIN, CHROME_MARGIN, CHROME_MARGIN
        )
        root.setSpacing(CHROME_SPACING)

        left = left_rail_widget()
        left_l = QtWidgets.QVBoxLayout(left)
        left_l.setContentsMargins(0, 0, 8, 0)
        left_l.setSpacing(CHROME_SPACING)

        self._settings_pages = SettingsPages(self)
        self._settings_stack = QtWidgets.QStackedWidget()
        for page in self._settings_pages.pages:
            self._settings_stack.addWidget(page)

        nav_group = QtWidgets.QButtonGroup(tab)
        nav_group.setExclusive(True)
        self._settings_nav_buttons: list[QtWidgets.QPushButton] = []
        for i, key in enumerate(SETTINGS_NAV_KEYS):
            btn = action_button(self.ui_tr(key))
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
            nav_group.addButton(btn, i)
            btn.clicked.connect(
                lambda *_a, idx=i: self._settings_stack.setCurrentIndex(idx)
            )
            left_l.addWidget(btn)
            self._settings_nav_buttons.append(btn)
        apply_equal_widths(self._settings_nav_buttons)
        left_l.addStretch(1)
        self._settings_nav_buttons[0].setChecked(True)

        root.addWidget(left)
        root.addWidget(self._settings_stack, 1)

    def _refresh_settings_tab_static_texts(self) -> None:
        if not hasattr(self, "_settings_nav_buttons"):
            return
        for btn, key in zip(self._settings_nav_buttons, SETTINGS_NAV_KEYS, strict=True):
            btn.setText(self.ui_tr(key))
        apply_equal_widths(self._settings_nav_buttons)
        self._settings_pages.refresh_static_texts()
