"""SQLite cache lookups without Access/ODBC."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from machine_library.hanwha_sqlite_cache import (
    cache_is_fresh,
    load_preview_dataframe_from_sqlite,
    load_profile_snapshot_from_sqlite,
    build_outline_from_sqlite,
    meta_path,
    sqlite_path,
    _write_df_sqlite,
)


def _seed_vision_sqlite(cache: Path) -> None:
    cache.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(sqlite_path(cache)))
    try:
        _write_df_sqlite(
            conn,
            "PART_Det",
            pd.DataFrame(
                [
                    {
                        "PARTNAME": "AP2318GEN",
                        "PROFILENAME": "AP2318GEN",
                        "PARTDESC": "SOT23",
                    }
                ]
            ),
        )
        _write_df_sqlite(
            conn,
            "PROFILE_Det",
            pd.DataFrame(
                [
                    {
                        "PROFILENAME": "AP2318GEN",
                        "UPDPARTGROUPID": 7,
                        "FUNCTIONAL_TYPE_ID": 0,
                        "PARENTPROFILE": "",
                    }
                ]
            ),
        )
        _write_df_sqlite(
            conn,
            "PARTGROUP_Map",
            pd.DataFrame(
                [
                    {
                        "UPDPARTGROUPID": 7,
                        "UPDPARTGROUPNAME": "TR2",
                        "VISIONTYPE": 3,
                    }
                ]
            ),
        )
        _write_df_sqlite(
            conn,
            "PROFILECOMDATA_Det",
            pd.DataFrame(
                [
                    {
                        "PROFILENAME": "AP2318GEN",
                        "SIZEX": 2400,
                        "SIZEY": 2800,
                        "SIZEZ": 1000,
                        "PIN1XPOS": 0,
                        "PIN1YPOS": 0,
                    }
                ]
            ),
        )
        _write_df_sqlite(
            conn,
            "VISION_CHIP_WHOLE_Det",
            pd.DataFrame(
                [
                    {
                        "PROFILENAME": "AP2318GEN",
                        "TYPSIZEX": 2400,
                        "TYPSIZEY": 2800,
                    }
                ]
            ),
        )
        conn.commit()
    finally:
        conn.close()


def test_preview_and_outline_from_sqlite(tmp_path: Path) -> None:
    _seed_vision_sqlite(tmp_path)
    df = load_preview_dataframe_from_sqlite(tmp_path)
    assert len(df) == 1
    assert str(df.iloc[0]["PARTNAME"]) == "AP2318GEN"
    assert "UPDPARTGROUPNAME" in df.columns
    assert str(df.iloc[0]["UPDPARTGROUPNAME"]) == "TR2"

    snap = load_profile_snapshot_from_sqlite(tmp_path, "AP2318GEN")
    assert snap.vision_type == 3
    assert snap.partgroup_name == "TR2"
    assert snap.chip_whole is not None

    r = build_outline_from_sqlite(tmp_path, "AP2318GEN", partdesc="SOT23")
    assert r.error == ""
    assert len(r.outline.pads) == 3
    assert r.outline.source == "hanwha_upd"


def test_cache_is_fresh_mtime(tmp_path: Path) -> None:
    src = tmp_path / "lib.mdb"
    src.write_bytes(b"fake")
    cache = tmp_path / "hanwha_lib"
    cache.mkdir()
    (cache / "vision.sqlite").write_bytes(b"x")
    st = src.stat()
    meta_path(cache).write_text(
        json.dumps(
            {
                "source_path": str(src.resolve()),
                "source_mtime": st.st_mtime,
                "source_mtime_ns": st.st_mtime_ns,
                "source_size": st.st_size,
            }
        ),
        encoding="utf-8",
    )
    assert cache_is_fresh(src, cache)
    src.write_bytes(b"fake2")
    assert not cache_is_fresh(src, cache)
    src.write_bytes(b"fake")
    st = src.stat()
    meta_path(cache).write_text(
        json.dumps(
            {
                "source_path": str(src.resolve()),
                "source_mtime": st.st_mtime,
                "source_mtime_ns": st.st_mtime_ns,
                "source_size": st.st_size,
            }
        ),
        encoding="utf-8",
    )
    assert cache_is_fresh(src, cache)
    ns = src.stat().st_mtime_ns + 1_000_000
    os.utime(src, ns=(ns, ns))
    assert not cache_is_fresh(src, cache)


def test_empty_profile_name(tmp_path: Path) -> None:
    r = build_outline_from_sqlite(tmp_path, "")
    assert r.error == "empty profile name"


def test_import_mdb_to_cache_closes_odbc_on_mid_loop_failure(
    monkeypatch, mocker, tmp_path: Path
) -> None:
    from machine_library.hanwha_sqlite_cache import import_mdb_to_cache

    src = tmp_path / "lib.mdb"
    src.write_bytes(b"fake-mdb")
    cache = tmp_path / "cache"
    odbc_conn = mocker.Mock()
    write_calls = {"n": 0}

    def _write_df_sqlite(_conn, table, _df):
        write_calls["n"] += 1
        if write_calls["n"] == 2:
            raise RuntimeError("sqlite write failed")

    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setattr(
        "machine_library.access_odbc.connect_mdb",
        lambda *_a, **_k: odbc_conn,
    )
    monkeypatch.setattr(
        "machine_library.hanwha_sqlite_cache._read_mdb_table",
        lambda *_a, **_k: __import__("pandas").DataFrame(),
    )
    monkeypatch.setattr(
        "machine_library.hanwha_sqlite_cache._write_df_sqlite",
        _write_df_sqlite,
    )
    with pytest.raises(RuntimeError, match="sqlite write failed"):
        import_mdb_to_cache(src, cache, force=True)
    odbc_conn.close.assert_called_once()


def test_read_mdb_table_odbc_failure_falls_back_to_mdbtools(
    monkeypatch, mocker, tmp_path: Path
) -> None:
    from machine_library.access_odbc import AccessOdbcError
    from machine_library.hanwha_sqlite_cache import _read_mdb_table

    mdb = tmp_path / "lib.mdb"
    mdb.write_bytes(b"x")
    odbc_conn = mocker.Mock()
    monkeypatch.setattr(
        "machine_library.access_odbc.fetch_named_columns",
        lambda *_a, **_k: (_ for _ in ()).throw(AccessOdbcError("no table")),
    )
    monkeypatch.setattr(
        "machine_library.hanwha_sqlite_cache.export_table_csv",
        lambda *_a, **_k: "PARTNAME\nA\n",
    )
    warn_spy = mocker.spy(__import__("logger"), "warning")
    df = _read_mdb_table(
        mdb,
        "PART_Det",
        ("PARTNAME", "PROFILENAME"),
        odbc_conn,
    )
    assert list(df["PARTNAME"]) == ["A"]
    assert warn_spy.called
    blob = str(warn_spy.call_args.args[0]).lower()
    assert "mdbtools" in blob or "odbc" in blob
