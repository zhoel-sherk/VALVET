"""Clean preview roles: neutral rows, PARTIAL/Alert markers, arbiter details.

The old Win%-driven green fill made every ordinary Cleaned cell look
emphasised, so normal cells now keep the view's own zebra striping. State is
carried by text (PARTIAL, ⚠) as well as colour.
"""

from __future__ import annotations

import re
from typing import Optional

import pandas as pd
import pytest

pytest.importorskip("PySide6")

from PySide6 import QtCore, QtGui, QtWidgets

from qt_models import CleanPreviewTableModel


def _qapp() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def _model(
    win_values: object,
    *,
    highlight: bool = True,
    columns: tuple = ("Cleaned", "Win%", "Alert"),
    alert: str = "",
) -> CleanPreviewTableModel:
    _qapp()
    data = {
        "Cleaned": [f"v{i}" for i in range(len(win_values))],
        "Win%": list(win_values),
        "Alert": [alert for _ in win_values],
    }
    df = pd.DataFrame(data)
    df = df[[c for c in columns if c in df.columns]]
    return CleanPreviewTableModel(df, arbiter_score_highlight=highlight)


def _roles(
    model: CleanPreviewTableModel, row: int, col_name: str
) -> tuple[Optional[QtGui.QBrush], Optional[QtGui.QBrush]]:
    col = list(model.get_dataframe().columns).index(col_name)
    idx = model.index(row, col)
    return (
        model.data(idx, QtCore.Qt.ItemDataRole.BackgroundRole),
        model.data(idx, QtCore.Qt.ItemDataRole.ForegroundRole),
    )


@pytest.mark.parametrize("pct", [0.0, 42.0, 90.0, 100.0, float("nan"), "n/a", ""])
def test_normal_cleaned_cell_has_no_model_fill(pct: object) -> None:
    """Every ordinary Cleaned cell stays neutral, whatever Win% says."""
    m = _model([pct, pct])
    for row in (0, 1):
        bg, fg = _roles(m, row, "Cleaned")
        assert bg is None
        assert fg is None


def test_other_columns_are_neutral_too() -> None:
    m = _model([100.0, 100.0])
    for col in ("Win%",):
        bg, fg = _roles(m, 0, col)
        assert bg is None
        assert fg is None


def test_source_partial_foreground_unchanged() -> None:
    """The pre-existing Source/PARTIAL colour must not move."""
    for value in ("PARTIAL", "partial", "MANUAL+PARTIAL"):
        m = _model([50.0, 50.0], columns=("Cleaned", "Win%", "Source"))
        m.get_dataframe().loc[0, "Source"] = value
        _, fg = _roles(m, 0, "Source")
        assert isinstance(fg, QtGui.QBrush)
        c = fg.color()
        assert (c.red(), c.green(), c.blue()) == (220, 85, 0)


def test_source_non_partial_foreground_unchanged() -> None:
    """Non-PARTIAL Source values still fall through to the theme (None)."""
    for value in ("MANUAL", "AUTO", ""):
        m = _model([50.0, 50.0], columns=("Cleaned", "Win%", "Source"))
        m.get_dataframe().loc[0, "Source"] = value
        _, fg = _roles(m, 0, "Source")
        assert fg is None


def test_alert_adds_text_marker_not_only_colour() -> None:
    m = _model(["x"], alert="missing=film;present=2/3")
    alert_col = list(m.get_dataframe().columns).index("Alert")
    text = m.data(m.index(0, alert_col), QtCore.Qt.ItemDataRole.DisplayRole)
    assert text.startswith("⚠ ")
    assert "missing=film" in text


def test_alert_tooltip_keeps_the_full_text() -> None:
    m = _model(["x"], alert="missing=film;present=2/3")
    alert_col = list(m.get_dataframe().columns).index("Alert")
    tip = m.data(m.index(0, alert_col), QtCore.Qt.ItemDataRole.ToolTipRole)
    assert tip == "missing=film;present=2/3"


def test_empty_alert_has_no_marker() -> None:
    m = _model(["x"], alert="")
    alert_col = list(m.get_dataframe().columns).index("Alert")
    assert m.data(m.index(0, alert_col), QtCore.Qt.ItemDataRole.DisplayRole) == ""
    assert m.data(m.index(0, alert_col), QtCore.Qt.ItemDataRole.ToolTipRole) == ""


def test_cleaned_tooltip_shows_arbiter_detail_only_when_enabled() -> None:
    df = pd.DataFrame(
        {
            "Cleaned": ["10K_0402_5%"],
            "Arbiter": ["regex"],
            "Win%": ["87"],
            "Alert": [""],
        }
    )
    on = CleanPreviewTableModel(df, arbiter_score_highlight=True)
    off = CleanPreviewTableModel(df, arbiter_score_highlight=False)
    col = list(df.columns).index("Cleaned")
    on_tip = on.data(on.index(0, col), QtCore.Qt.ItemDataRole.ToolTipRole)
    off_tip = off.data(off.index(0, col), QtCore.Qt.ItemDataRole.ToolTipRole)
    assert "Arbiter: regex" in on_tip
    assert "Win%: 87" in on_tip
    assert "Arbiter" not in off_tip


def test_row_number_is_right_aligned() -> None:
    _qapp()
    m = CleanPreviewTableModel(pd.DataFrame({"#": [1], "Cleaned": ["x"]}))
    align = m.data(m.index(0, 0), QtCore.Qt.ItemDataRole.TextAlignmentRole)
    assert align & QtCore.Qt.AlignmentFlag.AlignRight


def test_highlight_toggle_no_longer_repaints_colours() -> None:
    m = _model([50.0, 50.0])
    seen: list[list[int]] = []
    m.dataChanged.connect(lambda _tl, _br, roles: seen.append(list(roles)))
    m.set_arbiter_score_highlight(False)
    m.set_arbiter_score_highlight(True)
    assert seen == []


def test_out_of_range_index_does_not_raise() -> None:
    m = _model([50.0, 50.0])
    assert m._get_background(99, 0, "x") is None
    assert m._get_background(0, 99, "x") is None
    assert m._get_foreground(99, 0, "x") is None
    assert m._get_foreground(0, 99, "x") is None


#: Selector states that legitimately paint the cell themselves. ``:selected``
#: owns both colours, while ``:hover`` / ``:pressed`` always pair their own
#: background with a matching text colour, so neither can leave a model tint
#: wearing the theme's text colour.
_STATE_SELECTORS = (":selected", ":hover", ":pressed")


def test_profile_item_rules_do_not_shadow_model_colours() -> None:
    """The profile overlay must not colour a non-selected item by default.

    Qt's stylesheet style paints an item itself as soon as a rule declares
    ``color`` or ``background-color``, and then ignores the model's
    ``ForegroundRole`` and ``BackgroundRole``. That made the PARTIAL source
    marker vanish. Text colour belongs on the view rule, per-cell colour in the
    model.
    """
    from themes.colour_prefs import (
        merge_table_colours,
        merge_ui_colours,
        profile_colour_qss,
    )

    qss = profile_colour_qss(merge_ui_colours(None), merge_table_colours(None))
    item_rules = re.findall(r"([^{}]*::item[^{}]*)\{([^}]*)\}", qss)
    assert item_rules, "profile overlay no longer styles item views at all"

    offenders = [
        selector.strip()
        for selector, body in item_rules
        if not any(state in selector for state in _STATE_SELECTORS)
        and re.search(r"(?<![-\w])(?:color|background-color)\s*:", body)
    ]
    assert not offenders, f"profile item rules shadow model colours: {offenders}"
    assert re.search(r"QTableView::item:selected", qss), "selection rule disappeared"


def test_composed_item_rules_only_paint_stateful_cells() -> None:
    """qdarkstyle may colour ``:hover`` / ``:pressed`` / ``:selected`` only."""
    from themes.stylesheet import compose_app_stylesheet

    qss = compose_app_stylesheet(None, None)
    item_rules = re.findall(r"([^{}]*QTableView::item[^{}]*)\{([^}]*)\}", qss)
    assert item_rules, "item-view rules disappeared from the composed stylesheet"

    offenders = [
        selector.strip()
        for selector, body in item_rules
        if not any(state in selector for state in _STATE_SELECTORS)
        and re.search(r"(?<![-\w])(?:color|background-color)\s*:", body)
    ]
    assert not offenders, f"item rules shadow model colours: {offenders}"


def test_view_rule_still_sets_the_theme_text_colour() -> None:
    """Removing the item colour rules must keep the theme text on the view."""
    from themes.stylesheet import compose_app_stylesheet

    qss = compose_app_stylesheet(None, {"text": "#123456"})
    view_rule = qss.split("QTableView, QTreeView, QTableWidget, QTreeWidget {", 1)[
        1
    ].split("}", 1)[0]
    assert "color: #123456;" in view_rule
