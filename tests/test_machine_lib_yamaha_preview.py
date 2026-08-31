"""Headless Machine Lib Yamaha: load example .Tou and show footprint (no dialogs)."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6 import QtCore, QtWidgets

from yamaha_paths import YAMAHA_TOU_TOP


def _qapp():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def test_machine_lib_yamaha_tou_preview(tmp_path: Path) -> None:
    qapp = _qapp()
    from app.window import MainWindow

    ini = QtCore.QSettings(str(tmp_path / "t.ini"), QtCore.QSettings.Format.IniFormat)
    ini.setValue("experimental/enable_step_3d", False)
    win = MainWindow(settings=ini)
    tab = win._machine_library_tab
    try:
        tab._vendor_combo.setCurrentIndex(1)
        qapp.processEvents()
        tab._yam_tou_path = str(YAMAHA_TOU_TOP)
        tab._yam_tou_is_dir = False
        tab._reload_yamaha_preview()
        qapp.processEvents()
        assert len(tab._yamaha_partnames) >= 29
        model = tab._table_model
        hit = -1
        for r in range(model.rowCount()):
            name = str(model.get_row_values(r).get("PARTNAME") or "")
            if "1206" in name.upper():
                hit = r
                break
        assert hit >= 0
        tab._table.selectRow(hit)
        qapp.processEvents()
        tab._load_yamaha_footprint()
        qapp.processEvents()
        meta = tab._fp_preview._meta.text()
        assert "N/A for Yamaha" not in meta
        assert "yamaha_tou" in meta
        assert "3.200" in meta or "3.2" in meta
    finally:
        win.close()
