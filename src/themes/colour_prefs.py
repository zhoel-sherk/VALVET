"""Profile-driven UI / table colour defaults and QSS fragment (after qdarkstyle)."""

from __future__ import annotations

import re
from typing import Any

_HEX = re.compile(r"^#[0-9a-fA-F]{3}$|^#[0-9a-fA-F]{6}$")


def _expand_hex(h: str) -> str | None:
    s = str(h).strip()
    if not s:
        return None
    if not _HEX.match(s):
        return None
    if len(s) == 4:
        return "#" + "".join(c * 2 for c in s[1:])
    return s


def sanitize_hex(h: Any, fallback: str) -> str:
    v = _expand_hex(str(h) if h is not None else "")
    return v if v else fallback


# Keys stored in profile JSON under ui["colours"] and top-level table_colours.
DEFAULT_UI_COLOURS: dict[str, str] = {
    "window_bg": "#19232D",
    "window_fg": "#DDE4EE",
    "panel_bg": "#1E2A35",
    "panel_fg": "#DDE4EE",
    "control_bg": "#2A3948",
    "control_fg": "#E8E8E8",
}

DEFAULT_TABLE_COLOURS: dict[str, str] = {
    "bg": "#1E2A35",
    "alt_bg": "#2A3540",
    "text": "#E8E8E8",
    "header_bg": "#283139",
    "header_fg": "#DAE5F0",
    "selection_bg": "#375A7F",
    "selection_fg": "#FFFFFF",
    "grid": "#3A4A5A",
}


def merge_ui_colours(overrides: dict[str, Any] | None) -> dict[str, str]:
    out = dict(DEFAULT_UI_COLOURS)
    if not isinstance(overrides, dict):
        return out
    for k in DEFAULT_UI_COLOURS:
        if k in overrides:
            out[k] = sanitize_hex(overrides[k], out[k])
    return out


def merge_table_colours(overrides: dict[str, Any] | None) -> dict[str, str]:
    out = dict(DEFAULT_TABLE_COLOURS)
    if not isinstance(overrides, dict):
        return out
    for k in DEFAULT_TABLE_COLOURS:
        if k in overrides:
            out[k] = sanitize_hex(overrides[k], out[k])
    return out


def _lighten_hex(h: str, amount: float = 0.18) -> str:
    """Blend ``h`` toward white; used for tab hover (not a picker key)."""
    s = sanitize_hex(h, DEFAULT_UI_COLOURS["control_bg"])
    r = int(s[1:3], 16)
    g = int(s[3:5], 16)
    b = int(s[5:7], 16)

    def _ch(c: int) -> int:
        return min(255, int(c + (255 - c) * amount))

    return f"#{_ch(r):02X}{_ch(g):02X}{_ch(b):02X}"


def profile_colour_qss(ui: dict[str, str], table: dict[str, str]) -> str:
    """QSS appended after qdarkstyle; fixes alternate row contrast for item views."""
    u = ui
    t = table
    bg, alt = t["bg"], t["alt_bg"]
    tx = t["text"]
    hb, hf = t["header_bg"], t["header_fg"]
    sb, sf = t["selection_bg"], t["selection_fg"]
    gr = t["grid"]
    hover = _lighten_hex(u["control_bg"])
    tab_border = u["control_bg"]
    return f"""
    QMainWindow, QDialog {{
        background-color: {u["window_bg"]};
        color: {u["window_fg"]};
    }}
    QTabWidget::pane {{
        border: 1px solid #32414B;
        background-color: {u["panel_bg"]};
    }}
    QTabBar::tab {{
        background-color: {u["control_bg"]};
        color: {u["panel_fg"]};
        padding: 10px 16px;
        min-height: 22px;
        font-weight: 700;
    }}
    QTabWidget#valvetMainTabs::pane {{
        border: 1px solid {tab_border};
        background-color: {u["panel_bg"]};
        top: -1px;
    }}
    QTabWidget#valvetMainTabs QTabBar {{
        background-color: {u["window_bg"]};
    }}
    QTabWidget#valvetMainTabs QTabBar::tab {{
        background-color: {u["control_bg"]};
        color: {u["panel_fg"]};
        padding: 8px 12px;
        min-height: 22px;
        font-weight: 700;
        border: 1px solid {tab_border};
        border-bottom: none;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        margin-right: 2px;
    }}
    QTabWidget#valvetMainTabs QTabBar::tab:selected {{
        background-color: {u["panel_bg"]};
        color: {u["panel_fg"]};
        border-color: {tab_border};
        border-bottom: 1px solid {u["panel_bg"]};
    }}
    QTabWidget#valvetMainTabs QTabBar::tab:hover:!selected {{
        background-color: {hover};
    }}
    QGroupBox {{
        color: {u["panel_fg"]};
        border: 1px solid #32414B;
        margin-top: 8px;
        background-color: {u["panel_bg"]};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 8px;
        padding: 0 4px;
    }}
    QLabel {{
        color: {u["window_fg"]};
    }}
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit, QPlainTextEdit {{
        background-color: {u["control_bg"]};
        color: {u["control_fg"]};
        border: 1px solid #32414B;
        padding: 2px 6px;
    }}
    QPushButton {{
        background-color: {u["control_bg"]};
        color: {u["control_fg"]};
        border: 1px solid #32414B;
        padding: 4px 12px;
    }}
    QPushButton:hover {{
        background-color: {u["panel_bg"]};
    }}
    QStatusBar {{
        background-color: {u["window_bg"]};
        color: {u["window_fg"]};
    }}

    QTableView, QTreeView, QTableWidget, QTreeWidget {{
        background-color: {bg};
        alternate-background-color: {alt};
        color: {tx};
        gridline-color: {gr};
        selection-background-color: {sb};
        selection-color: {sf};
    }}
    QTableView::item:!alternate:!selected, QTreeView::item:!alternate:!selected {{
        background-color: {bg};
        color: {tx};
    }}
    QTableView::item:alternate:!selected, QTreeView::item:alternate:!selected {{
        background-color: {alt};
        color: {tx};
    }}
    QTableView::item:selected, QTreeView::item:selected {{
        background-color: {sb};
        color: {sf};
    }}
    QHeaderView::section {{
        background-color: {hb};
        color: {hf};
        padding: 4px;
        border: 1px solid #32414B;
    }}
    QFrame#cleanRclRow {{
        border: 1px solid #32414B;
        border-radius: 3px;
        background-color: {u["panel_bg"]};
    }}
    /* qdarkstyle combo popups often reserve a wide left gutter (icon column) even with no icons */
    QComboBox QAbstractItemView {{
        margin: 0px;
        padding: 0px;
        outline: none;
    }}
    QComboBox QListView {{
        margin: 0px;
        padding: 0px;
    }}
    QComboBox QAbstractItemView::item {{
        padding: 2px 8px 2px 2px;
    }}
    /* Narrow Clean BOM template combos + BOM/PnP column mapping row (objectName set in app). */
    QComboBox#valvetCleanTemplateCombo,
    QComboBox#valvetMappingCombo {{
        padding: 2px 22px 2px 4px;
    }}
    QComboBox#valvetCleanTemplateCombo QAbstractItemView::item,
    QComboBox#valvetMappingCombo QAbstractItemView::item {{
        padding: 2px 8px 2px 2px;
    }}
    """
