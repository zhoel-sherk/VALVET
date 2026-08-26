"""Shared UPD.MDB paths for Hanwha integration tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from machine_library.hanwha_mdbtools import HanwhaMdbToolsError, list_mdb_tables

_REPO_ROOT = Path(__file__).resolve().parents[1]


def resolve_upd_mdb() -> Path | None:
    for cand in (
        _REPO_ROOT / "examples" / "UPD.MDB",
        _REPO_ROOT.parent / "UPD.MDB",
    ):
        if cand.is_file():
            return cand
    return None


def skip_if_mdb_unreadable(mdb: Path | None) -> None:
    if mdb is None:
        pytest.skip("UPD.MDB not present")
    try:
        list_mdb_tables(mdb)
    except HanwhaMdbToolsError as exc:
        pytest.skip(f"cannot read UPD.MDB: {exc}")
