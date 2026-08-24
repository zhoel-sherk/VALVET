"""Tests for Hanwha UPD .mdb reading (mdbtools on Linux; ODBC on Windows when pyodbc + ACE are available).

Fixture ``fixtures/hanwha_PART_Det_sample.csv`` is a 20-row excerpt from ``PART_Det``
(``mdb-export`` on ``UPD.MDB``): template rows ``_NewC0201`` / ``_NewR0201``, mixed
``CONFIDENCE_LEVEL`` / ``VENDORID``, and typical ``PARTDESC`` text. Regenerate when
the production library schema changes (requires mdbtools + ``UPD.MDB`` beside ``boomer/``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from machine_library.hanwha_mdbtools import (
    HanwhaMdbToolsError,
    export_table_csv,
    list_mdb_tables,
    load_part_det_from_mdb,
    parse_part_det_csv,
    part_det_rows_to_dataframe,
)

_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
_SAMPLE_CSV = _FIXTURE_DIR / "hanwha_PART_Det_sample.csv"
_BOOMER_ROOT = Path(__file__).resolve().parents[1]


def _resolve_upd_mdb_for_tests() -> Path | None:
    for cand in (
        _BOOMER_ROOT / "examples" / "UPD.MDB",
        _BOOMER_ROOT.parent / "UPD.MDB",
    ):
        if cand.is_file():
            return cand
    return None


_UPD_MDB = _resolve_upd_mdb_for_tests()


def test_parse_part_det_fixture() -> None:
    text = _SAMPLE_CSV.read_text(encoding="utf-8")
    rows = parse_part_det_csv(text)
    assert len(rows) == 20
    assert rows[0].partname == "_NewC0201"
    assert rows[0].profilename == "_NewC0201"
    assert rows[0].confidence_level == 10
    assert rows[1].partname == "_NewR0201"
    assert rows[2].partname == "A005007P0001C_shield"
    assert rows[2].partdesc == "DDR5"
    assert rows[2].vendor_id == 21
    assert rows[10].partname == "_NewBGA"


def test_part_det_rows_to_dataframe() -> None:
    text = _SAMPLE_CSV.read_text(encoding="utf-8")
    df = part_det_rows_to_dataframe(parse_part_det_csv(text))
    assert list(df.columns) == [
        "PARTNAME",
        "PROFILENAME",
        "PARTDESC",
        "CONFIDENCE_LEVEL",
        "USED_MACHINE_SET",
        "VENDORID",
    ]
    assert len(df) == 20


@pytest.mark.skipif(_UPD_MDB is None, reason="UPD.MDB not present")
def test_list_tables_on_sample_upd_mdb() -> None:
    names = list_mdb_tables(_UPD_MDB)
    assert "PART_Det" in names
    assert "PARTGROUP_Map" in names
    assert "FEEDERTYPE_Map" in names


@pytest.mark.skipif(_UPD_MDB is None, reason="UPD.MDB not present")
def test_load_part_det_from_sample_upd_mdb() -> None:
    rows = load_part_det_from_mdb(_UPD_MDB)
    assert len(rows) >= 2
    names = {r.partname for r in rows}
    assert "_NewC0201" in names
    assert "_NewR0201" in names


@pytest.mark.skipif(_UPD_MDB is None, reason="UPD.MDB not present")
def test_export_table_rejects_bad_name() -> None:
    with pytest.raises(HanwhaMdbToolsError, match="unsafe"):
        export_table_csv(_UPD_MDB, "PART_Det;DROP")


def test_mdb_export_matches_fixture_snapshot() -> None:
    from machine_library.hanwha_partnames import export_partnames_snapshot, load_partnames_snapshot

    fixture = _BOOMER_ROOT / "tests" / "fixtures" / "clean_corpus" / "hanwha_partnames_cl40.json"
    if _UPD_MDB is None or not fixture.is_file():
        pytest.skip("UPD.MDB or hanwha_partnames_cl40.json missing")
    import json
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "out.json"
        export_partnames_snapshot(_UPD_MDB, tmp, confidence_levels=frozenset({40}))
        a = load_partnames_snapshot(fixture)
        b = load_partnames_snapshot(tmp)
    if a != b:
        only_a = sorted(a - b)[:5]
        only_b = sorted(b - a)[:5]
        meta = json.loads(fixture.read_text(encoding="utf-8")).get("meta", {})
        pytest.fail(
            f"snapshot drift vs {fixture.name}: "
            f"fixture={len(a)} fresh={len(b)} "
            f"only_fixture_sample={only_a!r} only_fresh_sample={only_b!r} "
            f"fixture_meta={meta!r}"
        )
