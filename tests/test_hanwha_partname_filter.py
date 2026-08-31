"""Hanwha PARTNAME junk filter and confidence export."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

tests_dir = Path(__file__).resolve().parent
_repo_root = tests_dir.parent
sys.path.insert(0, str(_repo_root / "src"))

from machine_library.hanwha_mdbtools import part_det_rows_to_dataframe  # noqa: E402
from machine_library.hanwha_partnames import (  # noqa: E402
    filter_by_confidence_levels,
    is_junk_hanwha_partname,
    is_passive_rc_hanwha_partname,
    load_partnames_snapshot,
    partnames_for_clean,
    resolve_upd_mdb_path,
)

_FIXTURE = _repo_root / "tests" / "fixtures" / "hanwha_PART_Det_sample.csv"


def _sample_df():

    from machine_library.hanwha_mdbtools import parse_part_det_csv

    text = _FIXTURE.read_text(encoding="utf-8")
    return part_det_rows_to_dataframe(parse_part_det_csv(text))


@pytest.mark.parametrize(
    "pn,desc,junk",
    [
        ("0603", None, True),
        ("0402", None, True),
        ("0402__", None, True),
        ("0603_", None, True),
        ("_NewC0201", None, True),
        ("__BGA_FOO", "[STDVER.1]", True),
        ("Y01", None, True),
        ("0402_4.7K", None, False),
        ("JW7115S-2SOTA#TRPBF", None, False),
        ("STPI0412-1R0M-T2", None, False),
    ],
)
def test_is_junk_hanwha_partname(pn: str, desc: str | None, junk: bool) -> None:
    assert is_junk_hanwha_partname(pn, desc) is junk


@pytest.mark.parametrize(
    "pn,desc,passive",
    [
        ("0402_4.7K_1%", "R0402", True),
        ("0201_0.1uF_16V_X5R_10%", "C0201", True),
        ("C0402_10uF_25V_X7R", None, True),
        ("0402ESDA_05_5.5V", "0402", False),
        ("AST2500A2-GP", "BGA_456P_31_748X748", False),
        ("FH82H610", "BGA CHIPSET", False),
        ("NCP15WF104F03RC", "THERMISTOR0402", False),
        ("LQG15HS68NJ02D", "L0402", False),
    ],
)
def test_is_passive_rc_hanwha_partname(pn: str, desc: str | None, passive: bool) -> None:
    assert is_passive_rc_hanwha_partname(pn, desc) is passive


def test_filter_confidence_40_only() -> None:
    df = _sample_df()
    f40 = filter_by_confidence_levels(df, {40})
    f10 = filter_by_confidence_levels(df, {10})
    assert len(f10) >= 2
    assert len(f40) < len(df)
    assert all(_confidence_level(v) == 40 for v in f40["CONFIDENCE_LEVEL"])


def _confidence_level(raw: object) -> int:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def test_partnames_for_clean_excludes_templates() -> None:
    df = _sample_df()
    names = partnames_for_clean(df, enabled_confidence_levels={10, 20, 40, 0})
    assert "_NewC0201" not in names
    assert "A005007P0001C_shield" in names


def test_partnames_for_clean_excludes_passive_rc_by_default() -> None:
    import pandas as pd

    df = pd.DataFrame(
        [
            {"PARTNAME": "0402_10K_1%", "PARTDESC": "R0402", "CONFIDENCE_LEVEL": 40},
            {"PARTNAME": "AST2500A2-GP", "PARTDESC": "BGA", "CONFIDENCE_LEVEL": 40},
        ]
    )
    names = partnames_for_clean(df, exclude_passive_rc=True)
    assert "0402_10K_1%" not in names
    assert "AST2500A2-GP" in names
    all_names = partnames_for_clean(df, exclude_passive_rc=False)
    assert "0402_10K_1%" in all_names


@pytest.mark.skipif(
    not (_repo_root / "examples" / "UPD.MDB").is_file()
    and not (_repo_root.parent / "UPD.MDB").is_file(),
    reason="UPD.MDB not present",
)
def test_resolve_upd_mdb_path() -> None:
    p = resolve_upd_mdb_path(boomer_root=_repo_root)
    assert p.is_file()


@pytest.mark.skipif(
    not (_repo_root / "tests" / "fixtures" / "clean_corpus" / "hanwha_partnames_cl40.json").is_file(),
    reason="hanwha_partnames_cl40.json not generated yet",
)
def test_load_partnames_snapshot() -> None:
    path = _repo_root / "tests" / "fixtures" / "clean_corpus" / "hanwha_partnames_cl40.json"
    names = load_partnames_snapshot(path)
    assert len(names) > 0
    assert "0603" not in names
    assert "0201_0.1uF_16V_X5R_10%" not in names
    assert "0402_4.7K" not in names
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "meta" in data and "partnames" in data
    assert data["meta"].get("exclude_passive_rc") is True
