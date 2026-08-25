"""Unit tests for Windows Access ODBC helper (driver pick + UI strings)."""

from __future__ import annotations

from pathlib import Path

import pytest

from machine_library.access_odbc import (
    ACCESS_ENGINE_2016_REDIST_URL,
    PART_DET_SELECT_COLS,
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


def test_odbc_connection_string_readonly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from machine_library.access_odbc import format_access_odbc_connection_string

    mdb = tmp_path / "lib.mdb"
    mdb.write_bytes(b"x")
    monkeypatch.setattr(
        "machine_library.access_odbc.pick_access_odbc_driver",
        lambda **_k: "Microsoft Access Driver (*.mdb, *.accdb)",
    )
    rw = format_access_odbc_connection_string(mdb, read_only=False)
    assert "ReadOnly" not in rw
    ro = format_access_odbc_connection_string(mdb, read_only=True)
    assert "ReadOnly=1" in ro


def test_connect_mdb_does_not_set_odbc_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Jet/Access raises HYC00 if pyodbc sets SQL_ATTR_* timeout via SQLSetConnectAttr."""
    pytest.importorskip("pyodbc")
    import pyodbc

    from machine_library import access_odbc

    mdb = tmp_path / "lib.mdb"
    mdb.write_bytes(b"x")
    seen: list[dict] = []

    class _Conn:
        pass

    def fake_connect(conn_str: str, **kwargs: object) -> _Conn:
        seen.append({"conn_str": conn_str, **kwargs})
        return _Conn()

    monkeypatch.setattr(pyodbc, "connect", fake_connect)
    monkeypatch.setattr(access_odbc, "pick_access_odbc_driver", lambda **_k: "Microsoft Access Driver (*.mdb)")
    monkeypatch.setattr(access_odbc, "ensure_com_sta", lambda: None)
    monkeypatch.setattr(access_odbc, "_try_unlink_stale_lock", lambda _p: None)

    conn = access_odbc.connect_mdb(mdb, timeout=8)
    assert conn is not None
    assert seen
    for call in seen:
        assert "timeout" not in call


def test_part_det_select_is_narrow() -> None:
    assert "PARTNAME" in PART_DET_SELECT_COLS
    assert "VENDORID" in PART_DET_SELECT_COLS
    assert len(PART_DET_SELECT_COLS) == 6
