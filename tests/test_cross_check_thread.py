"""CrossCheckThread emits DataFrame or error without touching widgets."""

from __future__ import annotations

import time

import pandas as pd
import pytest

pytest.importorskip("PySide6")

from PySide6 import QtWidgets

from app.workers import CrossCheckThread
from smt_processor import ColumnConfig, SMTDataProcessor


def _qapp() -> QtWidgets.QApplication:
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


def test_cross_check_thread_emits_dataframe() -> None:
    qapp = _qapp()
    bom_df = pd.DataFrame({"Designator": ["R1"], "Value": ["100R"]})
    pnp_df = pd.DataFrame({"Designator": ["R1"], "Comment": ["100R"]})
    proc = SMTDataProcessor().set_dataframes(
        bom_df,
        pnp_df,
        ColumnConfig(designator="Designator", comment="Value"),
        ColumnConfig(designator="Designator", comment="Comment"),
    )
    results: list[tuple[object, str]] = []
    thread = CrossCheckThread(proc)
    thread.result_ready.connect(lambda df, err: results.append((df, err)))
    thread.start()
    _wait_thread(thread, qapp)
    assert len(results) == 1
    df, err = results[0]
    assert err == ""
    assert isinstance(df, pd.DataFrame)
    thread.wait(1000)
    thread.deleteLater()


def test_cross_check_thread_emits_error_when_pnp_missing() -> None:
    qapp = _qapp()
    proc = SMTDataProcessor()
    proc._bom_df = pd.DataFrame({"Designator": ["R1"]})
    proc._bom_config = ColumnConfig(designator="Designator", comment="Value")
    results: list[tuple[object, str]] = []
    thread = CrossCheckThread(proc)
    thread.result_ready.connect(lambda df, err: results.append((df, err)))
    thread.start()
    _wait_thread(thread, qapp)
    assert len(results) == 1
    df, err = results[0]
    assert df is None
    assert "PnP" in err
    thread.wait(1000)
    thread.deleteLater()
