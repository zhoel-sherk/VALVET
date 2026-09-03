"""Headless Package tab: table + FootprintPreviewWidget."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6 import QtWidgets

from ui.machine_lib.footprint_preview import FootprintPreviewWidget
from ui.package_tab import PackageTab


@pytest.fixture
def qapp():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def test_package_tab_chip0402_canvas(qapp, tmp_path: Path) -> None:
    tab = PackageTab(db_path=tmp_path / "vspd.sqlite")
    try:
        assert isinstance(tab._fp_preview, FootprintPreviewWidget)
        model = tab._table.model()
        found = None
        for r in range(model.rowCount()):
            if str(model.index(r, 0).data()) == "CHIP-0402":
                found = r
                break
        assert found is not None
        tab._table.selectRow(found)
        tab._table.setCurrentIndex(model.index(found, 0))
        qapp.processEvents()
        tab._load_selected_outline()
        meta = tab._fp_preview._meta.text()
        assert meta
        assert "source=" in meta
        assert "vspd_heuristic" in meta
        assert tab._fp_preview._scene.items()
        sod = None
        for r in range(model.rowCount()):
            if str(model.index(r, 0).data()) == "SOD-523":
                sod = r
                break
        assert sod is not None
        tab._table.selectRow(sod)
        tab._table.setCurrentIndex(model.index(sod, 0))
        tab._load_selected_outline()
        assert "SOD-523" in tab._fp_preview._meta.text()
        from package_vspd.outline import build_result_for_package

        assert len(build_result_for_package("SOD-523").outline.pads) == 2
    finally:
        tab.close()
