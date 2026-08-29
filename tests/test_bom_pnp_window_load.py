"""Load BOM and PnP through MainWindow mixins without file dialogs."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6 import QtCore, QtWidgets

_ROOT = Path(__file__).resolve().parents[1]
_TABULAR = _ROOT / "tests" / "fixtures" / "clean_corpus" / "tabular_sample.csv"


def test_main_window_load_bom_and_pnp_by_path(tmp_path: Path) -> None:
    from app.window import MainWindow

    qapp = QtWidgets.QApplication.instance()
    if qapp is None:
        qapp = QtWidgets.QApplication([])

    pnp = tmp_path / "pnp.csv"
    pnp.write_text(
        "Designator,Mid X,Mid Y,Rotation,Layer,Footprint\n"
        "R1,1.0,2.0,0,Top,0402\n"
        "C1,3.0,4.0,90,Top,0402\n",
        encoding="utf-8",
    )
    settings = QtCore.QSettings(str(tmp_path / "t.ini"), QtCore.QSettings.Format.IniFormat)
    settings.setValue("experimental/enable_step_3d", False)
    win = MainWindow(settings=settings)
    try:
        win._load_bom(str(_TABULAR), force_original=True)
        qapp.processEvents()
        assert win._bom_df is not None
        assert len(win._bom_df) >= 2
        assert win.bom_model.rowCount() >= 2
        win._load_pnp(str(pnp), force_original=True)
        qapp.processEvents()
        assert win._pnp_df is not None
        assert len(win._pnp_df) >= 2
        assert win.bom_model.columnCount() >= 1
    finally:
        win.close()
