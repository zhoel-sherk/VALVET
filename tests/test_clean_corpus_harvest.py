"""Harvest extractors for clean corpus."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

tests_dir = Path(__file__).resolve().parent
_repo_root = tests_dir.parent
sys.path.insert(0, str(_repo_root / "tools"))

from clean_corpus_lib import (  # noqa: E402
    harvest_curated_xlsx,
    harvest_from_allegro_html,
    harvest_from_cmp_report,
    harvest_from_tabular,
    is_procurement_or_internal_code,
    is_reference_designator_text,
    sample_records_stratified_by_file,
    should_harvest_original,
)


def test_sample_stratified_by_file_round_robin() -> None:
    records = []
    for fi in range(3):
        for j in range(20):
            records.append(
                {
                    "id": f"f{fi}_{j}",
                    "source_file": f"file_{fi}.xlsx",
                    "source_kind": "tabular",
                    "original": f"PART_{fi}_{j}",
                }
            )
    picked, counts = sample_records_stratified_by_file(
        records, limit=30, seed=0, min_per_file=5, max_per_file=12
    )
    assert len(picked) == 30
    assert len(counts) == 3
    for c in counts.values():
        assert 5 <= c <= 12


def test_harvest_allegro_html_device_type() -> None:
    htm = _repo_root / "user_temp" / "WXH510M1RG6-BOT(1).htm"
    if not htm.is_file():
        pytest.skip("user_temp HTM not present")
    rows = list(harvest_from_allegro_html(htm, "user_temp/WXH510M1RG6-BOT(1).htm"))
    assert len(rows) > 100
    assert any("CAP_SMC" in r["original"] or "0.1" in r["original"] for r in rows)


@pytest.mark.parametrize(
    "text,is_ref",
    [
        ("RP1054", True),
        ("SATA_1,SATA_2,SATA_3,SATA_4", True),
        ("RP140,RP143,RP146,RP1003,RP1044,RP1178", True),
        ("RES 0402 10 OHM +/-1% LEAD-FREE - Y01", False),
        ("01.1.01.0010001-Y01", False),
        ("STM32F103CBT6", False),
        ("U20,U9518", True),
    ],
)
def test_is_reference_designator_text(text: str, is_ref: bool) -> None:
    assert is_reference_designator_text(text) is is_ref


@pytest.mark.parametrize(
    "text,drop",
    [
        ("02.1.01.4742331-Y01", True),
        ("E.R.T.0000666", True),
        ("E.O.M.0000328", True),
        ("富腾茂(FTM)", True),
        ("RES 0402 10 OHM +/-1% LEAD-FREE - Y01", False),
        ("Battery Warning Label UN3481", True),
        ("(Z3)Russia NewTradingEnglishManual", True),
    ],
)
def test_should_harvest_original_filters(text: str, drop: bool) -> None:
    assert should_harvest_original(text) is (not drop)


def test_is_procurement_or_internal_code() -> None:
    assert is_procurement_or_internal_code("01.1.01.0453001-Y01")
    assert not is_procurement_or_internal_code("RES 0402 10 OHM")


def test_harvest_tabular_comment_columns() -> None:
    csv = tests_dir / "fixtures" / "clean_corpus" / "tabular_sample.csv"
    rows = list(
        harvest_from_tabular(csv, "tests/fixtures/clean_corpus/tabular_sample.csv")
    )
    originals = {r["original"] for r in rows}
    assert "RES 10K 1% 0402" in originals
    assert "CAP CER 0.1uF 16V 0402" in originals
    assert all(r["source_kind"] == "tabular" for r in rows)


def test_harvest_bom_check_skips_part_reference() -> None:
    xlsx = _repo_root / "user_temp" / "BOM check.xlsx"
    if not xlsx.is_file():
        pytest.skip("BOM check.xlsx not present")
    rows = list(harvest_from_tabular(xlsx, "user_temp/BOM check.xlsx"))
    originals = {r["original"] for r in rows}
    assert "RP1054" not in originals
    assert "SATA_1,SATA_2,SATA_3,SATA_4" not in originals
    assert any("RES 0402" in o and "OHM" in o for o in originals)


def test_harvest_curated_component_test_xlsx() -> None:
    xlsx = _repo_root / "user_temp" / "component_test.xlsx"
    if not xlsx.is_file():
        pytest.skip("component_test.xlsx not present")
    rows, stats = harvest_curated_xlsx(xlsx, join_mode=True, join_columns=3)
    assert stats["raw_rows"] >= 1600
    assert len(rows) >= 900
    assert rows[0]["source_kind"] == "curated"
    assert "RES 0402" in rows[0]["original"] or "OHM" in rows[0]["original"]
    joined = [r for r in rows if " | " in r["original"]]
    assert len(joined) >= 500


def test_harvest_curated_single_column_mode() -> None:
    from parsers.bom_text_utils import merge_clean_comment_cell_parts

    assert (
        merge_clean_comment_cell_parts(
            ["FERRITE BEAD(0805)30 OHM/6A", "SPORTON/LCB2012K-300T60", None],
            " | ",
        )
        == "FERRITE BEAD(0805)30 OHM/6A | SPORTON/LCB2012K-300T60"
    )


def test_harvest_cmp_report_example6() -> None:
    cmp = _repo_root / "examples" / "example6" / "cmp.txt"
    if not cmp.is_file():
        pytest.skip("example6 cmp.txt missing")
    rows = list(harvest_from_cmp_report(cmp, "examples/example6/cmp.txt"))
    assert len(rows) > 50
    assert any("C_C0402" in r["original"] for r in rows)
