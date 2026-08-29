"""PCB Preview tab: install one Gerber layer without QFileDialog."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6 import QtWidgets
from PySide6.QtCore import QSettings

_ART = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "gerber_example2"
    / "silk_top.art"
)


def _qapp():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def _wait_thread(thread, qapp, timeout_s: float = 60.0) -> None:
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
            pytest.fail("Gerber load timed out")
    qapp.processEvents()


def test_pcb_preview_tab_loads_gerber_layer(tmp_path: Path) -> None:
    if not _ART.is_file():
        pytest.skip("example Gerber not present")
    from pcb_preview_load_thread import GerberLoadThread
    from pcb_preview_tab import PcbPreviewTab

    qapp = _qapp()
    settings = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    tab = PcbPreviewTab(settings=settings)
    try:
        thread = GerberLoadThread(str(_ART), tab._px_per_mm, tab)
        thread.result_ready.connect(tab._on_gerber_loaded)
        thread.start()
        _wait_thread(thread, qapp)
        assert len(tab._layers) >= 1
        assert tab._scene.items()
    finally:
        tab.close()


def test_pcb_preview_gerber_unit_radio_rescales_layer(tmp_path: Path) -> None:
    if not _ART.is_file():
        pytest.skip("example Gerber not present")
    from pcb_preview_load_thread import GerberLoadThread
    from pcb_preview_tab import PcbPreviewTab

    qapp = _qapp()
    settings = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    tab = PcbPreviewTab(settings=settings)
    try:
        thread = GerberLoadThread(str(_ART), tab._px_per_mm, tab)
        thread.result_ready.connect(tab._on_gerber_loaded)
        thread.start()
        _wait_thread(thread, qapp)
        assert len(tab._layers) >= 1
        scale_auto = tab._layers[0].pixmap_item.scale()
        tab._rb_g_mils.setChecked(True)
        qapp.processEvents()
        scale_mils = tab._layers[0].pixmap_item.scale()
        assert scale_mils != scale_auto
        tab._rb_g_auto.setChecked(True)
        qapp.processEvents()
        assert tab._layers[0].pixmap_item.scale() == scale_auto
    finally:
        tab.close()


def test_pcb_preview_missing_gerber_logs_error(
    tmp_path: Path, mocker: pytest.MockFixture
) -> None:
    from pcb_preview_load_thread import GerberLoadThread
    from pcb_preview_tab import PcbPreviewTab
    import logger

    spy = mocker.spy(logger, "error")
    qapp = _qapp()
    settings = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    tab = PcbPreviewTab(settings=settings)
    missing = tmp_path / "missing.gbr"
    try:
        thread = GerberLoadThread(str(missing), tab._px_per_mm, tab)
        thread.result_ready.connect(tab._on_gerber_loaded)
        thread.finished.connect(tab._on_gerber_thread_finished)
        tab._gerber_thread = thread
        tab._btn_gerber.setEnabled(False)
        thread.start()
        _wait_thread(thread, qapp)
        assert len(tab._layers) == 0
        spy.assert_called()
        log_text = tab._log.toPlainText()
        assert "Gerber" in log_text or "Not a file" in log_text
    finally:
        tab.close()
