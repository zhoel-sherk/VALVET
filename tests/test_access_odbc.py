"""Unit tests for Windows Access ODBC helper (driver pick + UI strings)."""

from __future__ import annotations

import pytest

from machine_library.access_odbc import (
    ACCESS_ENGINE_2016_REDIST_URL,
    driver_status_message,
    pick_access_odbc_driver,
)


def test_driver_status_message_when_driver_found() -> None:
    msg = driver_status_message("Microsoft Access Driver (*.mdb, *.accdb)")
    assert "Found ODBC driver" in msg
    assert "Microsoft Access Driver" in msg


def test_driver_status_message_when_missing_lists_url() -> None:
    msg = driver_status_message(None)
    assert "No Microsoft Access ODBC driver" in msg
    assert ACCESS_ENGINE_2016_REDIST_URL in msg


def test_pick_prefers_first_preferred_driver(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("pyodbc")
    import pyodbc

    monkeypatch.setattr(
        pyodbc,
        "drivers",
        lambda: [
            "ODBC Driver 17 for SQL Server",
            "Microsoft Access Driver (*.mdb, *.accdb)",
            "Microsoft Access Driver (*.mdb)",
        ],
    )
    assert pick_access_odbc_driver() == "Microsoft Access Driver (*.mdb, *.accdb)"


def test_pick_second_preferred_when_first_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("pyodbc")
    import pyodbc

    monkeypatch.setattr(
        pyodbc,
        "drivers",
        lambda: ["Microsoft Access Driver (*.mdb)"],
    )
    assert pick_access_odbc_driver() == "Microsoft Access Driver (*.mdb)"


def test_pick_fuzzy_match_localized_access_driver(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("pyodbc")
    import pyodbc

    localized = "Microsoft Access-Treiber (*.mdb, *.accdb)"
    monkeypatch.setattr(pyodbc, "drivers", lambda: ["Other", localized])
    assert pick_access_odbc_driver() == localized


def test_pick_returns_none_without_access_driver(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("pyodbc")
    import pyodbc

    monkeypatch.setattr(pyodbc, "drivers", lambda: ["ODBC Driver 17 for SQL Server"])
    assert pick_access_odbc_driver() is None
