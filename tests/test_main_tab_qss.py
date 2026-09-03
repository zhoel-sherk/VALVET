"""Main tab strip QSS follows Settings colour tokens."""

from __future__ import annotations

from themes.stylesheet import compose_app_stylesheet


def test_main_tab_qss_scopes_selected_and_panel_bg() -> None:
    qss = compose_app_stylesheet({"panel_bg": "#112233"}, None)
    assert "QTabWidget#valvetMainTabs" in qss
    assert "QTabBar::tab:top:selected" in qss
    assert "QTabBar::tab:top:hover:!selected" in qss
    assert "#112233" in qss


def test_main_tab_qss_uses_tab_colour_tokens() -> None:
    qss = compose_app_stylesheet(
        None,
        None,
        {"selected_fg": "#AABBCC", "normal_fg": "#112233"},
        tab_min_height=30,
    )
    assert "#AABBCC" in qss
    assert "#112233" in qss
    assert "min-height: 30px" in qss


def test_main_tab_qss_selected_joins_pane() -> None:
    qss = compose_app_stylesheet(
        {"panel_bg": "#112233", "window_bg": "#010203"},
        None,
        {"selected_bg": "#AABBCC"},
    )
    assert "border-top: none" in qss
    assert "tab:top:selected" in qss
    assert "margin-bottom: -1px" in qss
    assert "qproperty-drawBase: 0" in qss
    marker = "QTabWidget#valvetMainTabs QTabBar::tab:top:selected"
    assert marker in qss
    sel = qss.split(marker, 1)[1].split("}", 1)[0]
    assert "#010203" in sel
    assert "#AABBCC" not in sel
    assert "#112233" not in sel
    pane = qss.split("QTabWidget#valvetMainTabs::pane", 1)[1].split("}", 1)[0]
    assert "#010203" in pane
    assert "top: -1px" in qss


def test_tab_icons_load_for_known_keys() -> None:
    from PySide6 import QtWidgets

    from themes.tab_icons import tab_icon

    app = QtWidgets.QApplication.instance()
    if app is None:
        QtWidgets.QApplication([])
    icon = tab_icon("project")
    assert not icon.isNull()
    assert tab_icon("unknown-tab").isNull()
