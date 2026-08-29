"""Headless QThread contracts for app.workers and pcb_preview_load_thread."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6 import QtWidgets


def _qapp():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def _wait_thread(thread, qapp, timeout_s: float = 30.0) -> None:
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


def test_hanwha_sqlite_import_thread_missing_mdb(
    tmp_path: Path, mocker: pytest.MockFixture
) -> None:
    import logger
    from app.workers import HanwhaSqliteImportThread

    spy = mocker.spy(logger, "error")
    qapp = _qapp()
    cache = tmp_path / "cache"
    cache.mkdir()
    missing = tmp_path / "missing.mdb"
    results: list[tuple[object, str]] = []

    thread = HanwhaSqliteImportThread(str(missing), str(cache))
    thread.result_ready.connect(
        lambda df, err: results.append((df, err)),
    )
    thread.start()
    _wait_thread(thread, qapp)

    assert len(results) == 1
    df, err = results[0]
    assert df is None
    assert "Not a file" in err
    spy.assert_called()
    thread.wait(1000)
    thread.deleteLater()


def test_gerber_load_thread_missing_file(
    tmp_path: Path, mocker: pytest.MockFixture
) -> None:
    import logger
    from pcb_preview.types import GerberSvgPayload
    from pcb_preview_load_thread import GerberLoadThread

    spy = mocker.spy(logger, "error")
    qapp = _qapp()
    missing = tmp_path / "nope.gbr"
    packed_results: list[object] = []

    thread = GerberLoadThread(str(missing))
    thread.result_ready.connect(packed_results.append)
    thread.start()
    _wait_thread(thread, qapp)

    assert len(packed_results) == 1
    packed = packed_results[0]
    assert isinstance(packed, tuple)
    assert len(packed) == 3
    payload, image, vb = packed
    assert isinstance(payload, GerberSvgPayload)
    assert image is None
    assert payload.errors
    assert "Not a file" in payload.errors[0]
    spy.assert_called()
    thread.wait(1000)
    thread.deleteLater()
