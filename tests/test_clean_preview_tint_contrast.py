"""Clean preview arbiter-score tint: fill/foreground contrast and edge cases.

Regression cover for the dark-theme defect: the ``Cleaned`` fill is always a
light green, so the theme's own text colour (near-white in the dark theme) was
unreadable on it once the QSS bug stopped hiding the fill.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd
import pytest

pytest.importorskip("PySide6")

from PySide6 import QtCore, QtGui, QtWidgets

from qt_models import CleanPreviewTableModel

WCAG_AA = 4.5


def _qapp() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def _relative_luminance(color: QtGui.QColor) -> float:
    total = 0.0
    for value, weight in zip(
        (color.red(), color.green(), color.blue()),
        (0.2126, 0.7152, 0.0722),
    ):
        channel = value / 255.0
        if channel <= 0.03928:
            linear = channel / 12.92
        else:
            linear = ((channel + 0.055) / 1.055) ** 2.4
        total += weight * linear
    return total


def _contrast(a: QtGui.QColor, b: QtGui.QColor) -> float:
    la = _relative_luminance(a)
    lb = _relative_luminance(b)
    if la < lb:
        la, lb = lb, la
    return (la + 0.05) / (lb + 0.05)


def _model(
    win_values: object, *, highlight: bool = True, columns: tuple = ("Cleaned", "Win%")
) -> CleanPreviewTableModel:
    _qapp()
    data = {
        "Cleaned": [f"v{i}" for i in range(len(win_values))],
        "Win%": list(win_values),
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


def test_tint_foreground_contrast_meets_wcag_aa() -> None:
    """Every tint the model can produce must clear 4.5:1 (both row parities)."""
    worst = float("inf")
    worst_at: tuple[int, float] = (-1, -1.0)
    for pct in range(0, 101):
        for row in (0, 1):
            m = _model([pct, pct])
            bg, fg = _roles(m, row, "Cleaned")
            assert isinstance(bg, QtGui.QBrush)
            assert isinstance(fg, QtGui.QBrush)
            assert bg.color().alpha() == 255
            ratio = _contrast(fg.color(), bg.color())
            if ratio < worst:
                worst, worst_at = ratio, (row, pct)
    assert worst >= WCAG_AA, (
        f"contrast {worst:.2f} at row={worst_at[0]} Win%={worst_at[1]}"
    )
    # The dark theme's near-white text on a light fill was the defect; keep a
    # lower bound so a future tweak cannot quietly regress towards it.
    assert worst > 6.0


def test_tint_foreground_is_theme_independent() -> None:
    """Foreground must be one of the two fixed, high-contrast candidates."""
    for pct in (0.0, 42.0, 100.0):
        m = _model([pct, pct])
        _, fg = _roles(m, 0, "Cleaned")
        assert fg.color() in (QtGui.QColor(26, 26, 26), QtGui.QColor(255, 255, 255))


def test_alternating_rows_stay_distinct() -> None:
    m = _model([60.0, 60.0])
    even_bg, _ = _roles(m, 0, "Cleaned")
    odd_bg, _ = _roles(m, 1, "Cleaned")
    assert even_bg.color() != odd_bg.color()
    for brush in (even_bg, odd_bg):
        assert brush.color().alpha() == 255


@pytest.mark.parametrize(
    ("pct", "expected_bg"),
    [
        (0.0, (235, 218, 235)),
        (50.0, (235, 238, 235)),
        (100.0, (235, 255, 235)),
    ],
)
def test_tint_colours_even_rows(pct: float, expected_bg: tuple[int, int, int]) -> None:
    m = _model([pct, pct])
    bg, fg = _roles(m, 0, "Cleaned")
    assert (bg.color().red(), bg.color().green(), bg.color().blue()) == expected_bg
    assert fg.color() == QtGui.QColor(26, 26, 26)


@pytest.mark.parametrize(
    ("pct", "expected_bg"),
    [
        (0.0, (230, 210, 230)),
        (50.0, (212, 230, 212)),
        (100.0, (195, 250, 195)),
    ],
)
def test_tint_colours_odd_rows(pct: float, expected_bg: tuple[int, int, int]) -> None:
    m = _model([pct, pct])
    bg, fg = _roles(m, 1, "Cleaned")
    assert (bg.color().red(), bg.color().green(), bg.color().blue()) == expected_bg
    assert fg.color() == QtGui.QColor(26, 26, 26)


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


@pytest.mark.parametrize("bad", [float("nan"), None, "", "   ", "n/a", "abc", "50%"])
def test_unusable_win_percent_returns_base(bad: object) -> None:
    """NaN / empty / non-numeric: no tint, no foreground override, no raise."""
    m = _model([bad, bad])
    for row in (0, 1):
        bg, fg = _roles(m, row, "Cleaned")
        assert bg is None
        assert fg is None


@pytest.mark.parametrize(
    ("out_of_range", "reference"),
    [(-40.0, 0.0), (140.0, 100.0), (1e9, 100.0)],
)
def test_out_of_range_win_percent_is_clamped(
    out_of_range: float, reference: float
) -> None:
    """Out-of-range scores keep the existing clamp, not a new guard."""
    m = _model([out_of_range, out_of_range])
    ref = _model([reference, reference])
    for row in (0, 1):
        bg, fg = _roles(m, row, "Cleaned")
        ref_bg, ref_fg = _roles(ref, row, "Cleaned")
        assert bg.color() == ref_bg.color()
        assert fg.color() == ref_fg.color()
        assert bg.color().alpha() == 255


def test_highlight_off_leaves_cleaned_untinted() -> None:
    """arbiter_score_highlight=False: base (None) background and foreground."""
    m = _model([100.0, 100.0], highlight=False)
    for row in (0, 1):
        bg, fg = _roles(m, row, "Cleaned")
        assert bg is None
        assert fg is None


def test_highlight_off_keeps_partial_source_colour() -> None:
    m = _model([100.0, 100.0], highlight=False, columns=("Cleaned", "Win%", "Source"))
    m.get_dataframe().loc[0, "Source"] = "PARTIAL"
    _, fg = _roles(m, 0, "Source")
    c = fg.color()
    assert (c.red(), c.green(), c.blue()) == (220, 85, 0)


def test_toggle_emits_both_colour_roles() -> None:
    """Toggling the highlight must repaint the text, not only the fill."""
    m = _model([50.0, 50.0])
    seen: list[list[int]] = []
    m.dataChanged.connect(lambda _tl, _br, roles: seen.append(list(roles)))
    m.set_arbiter_score_highlight(False)
    m.set_arbiter_score_highlight(True)
    roles = QtCore.Qt.ItemDataRole
    for batch in seen:
        assert roles.BackgroundRole in batch
        assert roles.ForegroundRole in batch


def test_no_cleaned_column_leaves_other_columns_untinted() -> None:
    m = _model([50.0, 50.0], columns=("Win%",))
    bg, fg = _roles(m, 0, "Win%")
    assert bg is None
    assert fg is None


def test_out_of_range_index_does_not_raise() -> None:
    m = _model([50.0, 50.0])
    assert m._get_background(99, 0, "x") is None
    assert m._get_background(0, 99, "x") is None
    assert m._get_foreground(99, 0, "x") is None
    assert m._get_foreground(0, 99, "x") is None
