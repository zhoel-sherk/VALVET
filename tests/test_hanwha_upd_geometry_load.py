"""Live load_profile_snapshot / build_outline_from_mdb (one profile at a time)."""

from __future__ import annotations

from pathlib import Path

import pytest

from machine_library.upd_geometry_load import (
    build_outline_from_mdb,
    load_profile_snapshot,
    _load_tables,
)
from mdb_paths import resolve_upd_mdb, skip_if_mdb_unreadable

_UPD_MDB = resolve_upd_mdb()


def test_load_tables_logs_odbc_connect_fallback(
    monkeypatch, mocker, tmp_path: Path
) -> None:
    from machine_library.access_odbc import AccessOdbcError

    mdb = tmp_path / "lib.mdb"
    mdb.write_bytes(b"x")
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setattr(
        "machine_library.access_odbc.connect_mdb",
        lambda *_a, **_k: (_ for _ in ()).throw(AccessOdbcError("no driver")),
    )
    monkeypatch.setattr(
        "machine_library.upd_geometry_load.export_table_csv",
        lambda *_a, **_k: "PROFILENAME\nP1\n",
    )
    warn_spy = mocker.spy(__import__("logger"), "warning")
    tables = _load_tables(mdb, "P1")
    assert "PARTGROUP_Map" in tables
    assert warn_spy.called
    blob = " ".join(str(c.args[0]) for c in warn_spy.call_args_list).lower()
    assert "mdbtools" in blob or "odbc" in blob


def _require_mdb():
    skip_if_mdb_unreadable(_UPD_MDB)
    return _UPD_MDB


@pytest.mark.skipif(_UPD_MDB is None, reason="UPD.MDB not present")
def test_load_chip_r0402_from_mdb() -> None:
    mdb = _require_mdb()
    snap = load_profile_snapshot(mdb, "_NewR0402")
    assert snap.vision_type == 3
    assert snap.chip_whole is not None
    r = build_outline_from_mdb(mdb, "_NewR0402")
    assert r.error == ""
    assert len(r.outline.pads) == 2


@pytest.mark.skipif(_UPD_MDB is None, reason="UPD.MDB not present")
def test_load_sop_from_mdb() -> None:
    mdb = _require_mdb()
    name = "AT45DB161E-SSHF-T"
    snap = load_profile_snapshot(mdb, name)
    if snap.ll_whole is None and snap.vision_type != 1:
        pytest.skip(f"{name} not a leaded profile in this library")
    r = build_outline_from_mdb(mdb, name)
    assert r.error == ""
    assert len(r.outline.pads) >= 8


@pytest.mark.skipif(_UPD_MDB is None, reason="UPD.MDB not present")
def test_load_user_ic_from_mdb() -> None:
    mdb = _require_mdb()
    r = build_outline_from_mdb(mdb, "_NewUserIC")
    if r.error:
        pytest.skip(r.error)
    assert len(r.outline.pads) == 10
    assert any("rotated 90" in w for w in r.warnings)


@pytest.mark.skipif(_UPD_MDB is None, reason="UPD.MDB not present")
def test_load_bga_from_mdb() -> None:
    mdb = _require_mdb()
    r = build_outline_from_mdb(mdb, "_NewBGA")
    if r.error:
        pytest.skip(r.error)
    assert r.outline.lines
    assert r.outline.circles or any("BGA" in w for w in r.warnings)
