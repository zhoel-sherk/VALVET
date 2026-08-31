"""Headless Machine Lib: import thread + footprint thread without QFileDialog."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6 import QtCore, QtWidgets

from mdb_paths import resolve_upd_mdb, skip_if_mdb_unreadable

_UPD_MDB = resolve_upd_mdb()


def _qapp():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def _wait_thread(thread, qapp, timeout_s: float = 180.0) -> None:
    t0 = time.monotonic()
    while thread is not None:
        try:
            running = thread.isRunning()
        except RuntimeError:
            break
        if not running:
            break
        qapp.processEvents()
        thread.wait(50)
        if time.monotonic() - t0 > timeout_s:
            pytest.fail("QThread timed out")
    qapp.processEvents()


@pytest.mark.slow
@pytest.mark.skipif(_UPD_MDB is None, reason="UPD.MDB not present")
def test_machine_lib_start_mdb_load_and_footprint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    skip_if_mdb_unreadable(_UPD_MDB)
    qapp = _qapp()
    from app.window import MainWindow

    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(QtWidgets.QMessageBox, "information", lambda *a, **k: None)

    cache = tmp_path / "hanwha_lib"
    cache.mkdir()
    monkeypatch.setattr(
        "app_paths.hanwha_lib_cache_dir",
        lambda _pid="default": cache,
    )

    src = tmp_path / "UPD.MDB"
    shutil.copy2(_UPD_MDB, src)
    ini = QtCore.QSettings(str(tmp_path / "t.ini"), QtCore.QSettings.Format.IniFormat)
    ini.setValue("experimental/enable_step_3d", False)
    win = MainWindow(settings=ini)
    tab = win._machine_library_tab
    try:
        tab._mdb_path = str(src)
        tab._start_mdb_load(force=True)
        _wait_thread(tab._mdb_load_thread, qapp)
        qapp.processEvents()
        assert tab._hanwha_df is not None
        assert len(tab._hanwha_df) >= 2
        assert (cache / "vision.sqlite").is_file()

        tab._start_mdb_load(force=True)
        _wait_thread(tab._mdb_load_thread, qapp)
        qapp.processEvents()
        assert len(tab._hanwha_df) >= 2

        tab._fp_gen += 1
        tab._start_footprint_thread("_NewR0402", "", tab._fp_gen)
        _wait_thread(tab._fp_thread, qapp)
        qapp.processEvents()
        meta = tab._fp_preview._meta.text()
        assert "Error:" not in meta
        assert "VISIONTYPE" in meta
    finally:
        if tab._mdb_busy:
            QtWidgets.QApplication.restoreOverrideCursor()
            tab._mdb_busy = False
        win.close()
