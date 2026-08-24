"""MappingHeaderView combo geometry stays locked to table columns."""

from __future__ import annotations

import pandas as pd
import pytest

pytest.importorskip("PySide6")

from PySide6 import QtCore, QtWidgets  # noqa: E402

from qt_models import SortableTableModel  # noqa: E402
from ui.mapping_header import MappingComboBox, MappingHeaderView  # noqa: E402


@pytest.fixture
def qapp():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def _visible_table(qapp) -> tuple[QtWidgets.QTableView, MappingHeaderView]:
    table = QtWidgets.QTableView()
    model = SortableTableModel(
        pd.DataFrame({f"c{i}": list(range(8)) for i in range(8)}),
        editable=False,
    )
    table.setModel(model)
    hh = MappingHeaderView(QtCore.Qt.Orientation.Horizontal, table)
    table.setHorizontalHeader(hh)
    hh.setMinimumSectionSize(48)
    hh.attach_table(table)
    widths = (80, 120, 60, 200, 90, 70, 150, 110)
    for i, w in enumerate(widths):
        table.setColumnWidth(i, w)
    combos = [MappingComboBox() for _ in widths]
    for i, combo in enumerate(combos):
        combo.addItem("-", "-")
        combo.setToolTip(f"Column {i}")
    hh.set_mapping_combos(combos)
    table.resize(400, 280)
    table.show()
    qapp.processEvents()
    hh.relayout_combos()
    qapp.processEvents()
    return table, hh


def _assert_combo_fits_section(hh: MappingHeaderView, i: int) -> None:
    combo = hh.combos()[i]
    x = hh.sectionViewportPosition(i)
    w = hh.sectionSize(i)
    handle = min(hh._handle_px, max(0, w - 16))
    assert combo.x() == x
    assert combo.width() == max(1, w - handle)
    assert combo.x() + combo.width() <= x + w


def test_combo_geometry_matches_section(qapp) -> None:
    table, hh = _visible_table(qapp)
    try:
        vp_w = hh.viewport().width()
        for i, combo in enumerate(hh.combos()):
            x = hh.sectionViewportPosition(i)
            w = hh.sectionSize(i)
            visible = w > 0 and (x + w) > 0 and x < vp_w
            assert combo.isVisible() is visible
            if visible:
                _assert_combo_fits_section(hh, i)
    finally:
        table.close()


def test_horizontal_scroll_keeps_combos_on_sections(qapp) -> None:
    table, hh = _visible_table(qapp)
    try:
        table.horizontalScrollBar().setValue(180)
        qapp.processEvents()
        hh.relayout_combos()
        qapp.processEvents()
        vp_w = hh.viewport().width()
        for i, combo in enumerate(hh.combos()):
            x = hh.sectionViewportPosition(i)
            w = hh.sectionSize(i)
            visible = w > 0 and (x + w) > 0 and x < vp_w
            assert combo.isVisible() is visible
            if visible:
                _assert_combo_fits_section(hh, i)
    finally:
        table.close()


def test_section_resize_updates_combo_width(qapp) -> None:
    table, hh = _visible_table(qapp)
    try:
        table.setColumnWidth(0, 160)
        qapp.processEvents()
        _assert_combo_fits_section(hh, 0)
        assert hh._handle_px >= 8
    finally:
        table.close()
