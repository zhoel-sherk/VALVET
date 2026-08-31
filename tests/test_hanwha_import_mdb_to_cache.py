"""Live UPD.MDB → SQLite cache (mdbtools / ACE). Skip if the library is unreadable."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

import machine_library.hanwha_sqlite_cache as hanwha_cache
from mdb_paths import resolve_upd_mdb, skip_if_mdb_unreadable

_UPD_MDB = resolve_upd_mdb()


@pytest.fixture(scope="module")
def imported_cache(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    skip_if_mdb_unreadable(_UPD_MDB)
    src = tmp_path_factory.mktemp("mdb_src") / "UPD.MDB"
    shutil.copy2(_UPD_MDB, src)
    cache = tmp_path_factory.mktemp("hanwha_lib")
    hanwha_cache.import_mdb_to_cache(src, cache, force=True)
    return src, cache


@pytest.mark.slow
@pytest.mark.skipif(_UPD_MDB is None, reason="UPD.MDB not present")
def test_import_mdb_to_cache_writes_sqlite_and_meta(
    imported_cache: tuple[Path, Path],
) -> None:
    src, cache = imported_cache
    assert hanwha_cache.sqlite_path(cache).is_file()
    meta = json.loads(hanwha_cache.meta_path(cache).read_text(encoding="utf-8"))
    assert meta.get("source_size") == src.stat().st_size
    assert "source_mtime_ns" in meta
    assert hanwha_cache.cache_is_fresh(src, cache)


@pytest.mark.slow
@pytest.mark.skipif(_UPD_MDB is None, reason="UPD.MDB not present")
def test_import_mdb_to_cache_skips_when_fresh(
    imported_cache: tuple[Path, Path],
) -> None:
    src, cache = imported_cache
    meta = hanwha_cache.import_mdb_to_cache(src, cache, force=False)
    assert meta.get("source_size") == src.stat().st_size


@pytest.mark.slow
@pytest.mark.skipif(_UPD_MDB is None, reason="UPD.MDB not present")
def test_import_mdb_to_cache_stale_after_size_change(
    imported_cache: tuple[Path, Path],
) -> None:
    src, cache = imported_cache
    src.write_bytes(src.read_bytes() + b"\x00")
    assert not hanwha_cache.cache_is_fresh(src, cache)


@pytest.mark.slow
@pytest.mark.skipif(_UPD_MDB is None, reason="UPD.MDB not present")
def test_preview_and_outline_from_imported_cache(
    imported_cache: tuple[Path, Path],
) -> None:
    _src, cache = imported_cache
    df = hanwha_cache.load_preview_dataframe_from_sqlite(cache)
    assert len(df) >= 2
    assert "PARTNAME" in df.columns
    names = set(df["PARTNAME"].astype(str))
    profile = "_NewR0402" if "_NewR0402" in names else str(df.iloc[0]["PROFILENAME"])
    r = hanwha_cache.build_outline_from_sqlite(cache, profile)
    assert r.error == ""
    assert r.outline.source == "hanwha_upd"
    assert r.outline.lines or r.outline.pads or r.outline.circles
