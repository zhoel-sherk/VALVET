"""Main tab strip QSS follows Settings colour tokens."""

from __future__ import annotations

from themes.stylesheet import compose_app_stylesheet


def test_main_tab_qss_scopes_selected_and_panel_bg() -> None:
    qss = compose_app_stylesheet({"panel_bg": "#112233"}, None)
    assert "QTabWidget#valvetMainTabs" in qss
    assert "QTabBar::tab:selected" in qss
    assert "QTabBar::tab:hover:!selected" in qss
    assert "#112233" in qss


def test_tab_icons_load_for_known_keys() -> None:
    from PySide6 import QtWidgets

    from themes.tab_icons import tab_icon

    app = QtWidgets.QApplication.instance()
    if app is None:
        QtWidgets.QApplication([])
    icon = tab_icon("project")
    assert not icon.isNull()
    assert tab_icon("unknown-tab").isNull()
