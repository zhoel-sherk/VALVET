"""Clean preview model: Qt roles (no QtCore.QtCore)."""

from __future__ import annotations

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


def test_set_arbiter_score_highlight_emits() -> None:
    _qapp()
    model = CleanPreviewTableModel(
        pd.DataFrame({"Cleaned": ["10k"], "Win%": [80.0]}),
        arbiter_score_highlight=True,
    )
    model.set_arbiter_score_highlight(True)
    idx = model.index(0, 0)
    bg = model.data(idx, QtCore.Qt.ItemDataRole.BackgroundRole)
    assert isinstance(bg, QtGui.QBrush)


def test_clean_preview_background_role_win_percent() -> None:
    _qapp()
    model = CleanPreviewTableModel(
        pd.DataFrame({"Cleaned": ["x"], "Win%": [80.0]}),
        arbiter_score_highlight=True,
    )
    cleaned_col = list(model.get_dataframe().columns).index("Cleaned")
    idx = model.index(0, cleaned_col)
    bg = model.data(idx, QtCore.Qt.ItemDataRole.BackgroundRole)
    assert isinstance(bg, QtGui.QBrush)


def test_clean_preview_partial_source_foreground() -> None:
    _qapp()
    model = CleanPreviewTableModel(
        pd.DataFrame({"Cleaned": ["x"], "Source": ["PARTIAL"], "Win%": [10.0]})
    )
    src_col = list(model.get_dataframe().columns).index("Source")
    idx = model.index(0, src_col)
    fg = model.data(idx, QtCore.Qt.ItemDataRole.ForegroundRole)
    assert isinstance(fg, QtGui.QBrush)
    assert fg.color().red() >= 200
