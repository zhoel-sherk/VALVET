"""Clean preview model: Qt roles, neutral rows and header metadata."""

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


def test_normal_cleaned_cell_stays_neutral() -> None:
    _qapp()
    model = CleanPreviewTableModel(
        pd.DataFrame({"Cleaned": ["10k"], "Win%": [80.0]}),
        arbiter_score_highlight=True,
    )
    cleaned_col = list(model.get_dataframe().columns).index("Cleaned")
    idx = model.index(0, cleaned_col)
    assert model.data(idx, QtCore.Qt.ItemDataRole.BackgroundRole) is None
    assert model.data(idx, QtCore.Qt.ItemDataRole.ForegroundRole) is None


def test_header_tooltips_are_stored_per_column() -> None:
    _qapp()
    model = CleanPreviewTableModel(
        pd.DataFrame({"#": [1], "Cleaned": ["x"], "Type": ["RES"]})
    )
    model.set_column_header_metadata(
        {}, {"#": "row", "Cleaned": "clean", "Type": "type"}
    )
    for col, expected in enumerate(("row", "clean", "type")):
        tip = model.headerData(
            col,
            QtCore.Qt.Orientation.Horizontal,
            QtCore.Qt.ItemDataRole.ToolTipRole,
        )
        assert tip == expected


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
