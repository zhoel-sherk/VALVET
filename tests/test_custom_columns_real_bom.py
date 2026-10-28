"""Custom column end-to-end on the production files the user actually ran.

BOM ``1235_1220.xlsx`` (sheet ``1235``) carries the 1C inventory code in column
``0``; ``GW16ALR100-XY-Pick and Place.txt`` is the placement file. Merge joins
them by REF, so every placement must carry the exact 1C code of its BOM row,
character for character, and Clean must not touch it.

The files live outside the repository, so the module skips when they are absent
(CI); the synthetic counterpart is ``test_custom_columns_merge.py``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "src")
)

from services.clean_apply import apply_clean_preview_to_bom  # noqa: E402
from services.column_mapping import (  # noqa: E402
    custom_columns_in_order,
    pn_columns_in_order,
    roles_after_clean_apply,
)
from services.processor_config import build_processor_config  # noqa: E402
from smt_processor import (  # noqa: E402
    normalize_designators,
    read_file,
    read_pnp_whitespace,
)

_OUT = Path(r"C:\Users\SMD\Documents\Production\Techbook_C\BOM_PNP_NEW")
_BOM_XLSX = _OUT / "1235_1220.xlsx"
_PNP_TXT = _OUT / "GW16ALR100-XY-Pick and Place.txt"

pytestmark = pytest.mark.skipif(
    not (_BOM_XLSX.is_file() and _PNP_TXT.is_file()),
    reason="production BOM/PnP files not present",
)

_BOM_ROLES = ["Custom", "Comment", "-", "REF", "-"]
_PNP_ROLES = ["REF", "X", "Y", "Rotation", "-", "Footprint"]


def _load() -> tuple[pd.DataFrame, pd.DataFrame]:
    bom = read_file(
        str(_BOM_XLSX),
        first_row=0,
        last_row=-1,
        separator="auto",
        sheet_name="1235",
        column_headers_from_file=False,
    )
    pnp = read_pnp_whitespace(str(_PNP_TXT))
    return bom, pnp


def _merge(bom: pd.DataFrame, pnp: pd.DataFrame) -> pd.DataFrame:
    proc = build_processor_config(
        bom,
        pnp,
        {"REF": "3", "Comment": "1"},
        {
            "REF": "0",
            "X": "1",
            "Y": "2",
            "Rotation": "3",
            "Footprint": "5",
        },
        bom_custom=custom_columns_in_order(bom.columns, _BOM_ROLES),
        pnp_custom=custom_columns_in_order(pnp.columns, _PNP_ROLES),
    )
    return proc.merge_bom_pnp()


def _oracle(bom: pd.DataFrame) -> dict[str, str]:
    """Independent REF -> 1C code map, built straight from the sheet."""
    out: dict[str, str] = {}
    for _, row in bom.iterrows():
        designators, _warnings = normalize_designators(str(row["3"]))
        for d in designators:
            out[d.strip().upper()] = str(row["0"])
    return out


def test_clean_never_reads_the_custom_column() -> None:
    bom, _pnp = _load()
    comment_cols = pn_columns_in_order(bom.columns, _BOM_ROLES)
    assert comment_cols == ["1"]
    custom = custom_columns_in_order(bom.columns, _BOM_ROLES)
    assert custom == [("Custom 1", "0")]


def test_clean_apply_leaves_the_custom_column_untouched() -> None:
    bom, _pnp = _load()
    out = apply_clean_preview_to_bom(
        bom,
        [
            (i + 1, str(o), f"CLEANED-{i}", "OTHER", "regex")
            for i, o in enumerate(bom["1"])
        ],
        list(range(len(bom))),
        "1",
    )
    pd.testing.assert_series_equal(out["0"], bom["0"])

    roles = roles_after_clean_apply(
        _BOM_ROLES, list(out.columns), comment_column="comment"
    )
    assert custom_columns_in_order(list(out.columns), roles) == [("Custom 1", "0")]


def test_every_placement_carries_its_exact_1c_code() -> None:
    bom, pnp = _load()
    merged = _merge(bom, pnp)
    oracle = _oracle(bom)

    assert len(oracle) == 1547
    assert len(merged) == len(pnp)

    matched = merged[merged["Ref"].str.strip().str.upper().isin(oracle)]
    assert len(matched) == len(oracle), "every BOM designator must appear in the PnP"
    for ref, code in zip(
        matched["Ref"].str.strip().str.upper(), matched["Custom 1"], strict=True
    ):
        assert code == oracle[ref], (ref, code, oracle[ref])

    # Nothing was dropped, trimmed, re-cased or reformatted.
    assert set(matched["Custom 1"]) == set(oracle.values())
    assert all(str(code).startswith("IN-") for code in matched["Custom 1"])


def test_spot_values_match_the_source_sheet() -> None:
    bom, pnp = _load()
    merged = _merge(bom, pnp).set_index("Ref")
    assert merged.at["BATT_CN2", "Custom 1"] == "IN-00004829"
    assert merged.at["SSD_CN1", "Custom 1"] == "IN-00004833"
    assert merged.at["U16", "Custom 1"] == "IN-00005020"


def test_multi_designator_rows_fan_out() -> None:
    bom, pnp = _load()
    merged = _merge(bom, pnp).set_index("Ref")
    # Sheet row 2: IN-00004551 / 0402_10K_1% -> RM7,RB13,RD14,PR1024,...
    row = bom[bom["0"] == "IN-00004551"].iloc[0]
    refs, _warnings = normalize_designators(str(row["3"]))
    assert len(refs) > 5
    for ref in refs:
        if ref in merged.index:
            assert merged.at[ref, "Custom 1"] == "IN-00004551"


def test_placements_absent_from_bom_get_an_empty_custom_value() -> None:
    bom, pnp = _load()
    merged = _merge(bom, pnp)
    oracle = _oracle(bom)
    extra = merged[~merged["Ref"].str.strip().str.upper().isin(oracle)]
    assert not extra.empty
    assert set(extra["Custom 1"]) == {""}


def test_csv_round_trip_preserves_custom_codes(tmp_path: Path) -> None:
    bom, pnp = _load()
    merged = _merge(bom, pnp)
    path = tmp_path / "merged.csv"
    merged.to_csv(path, index=False, encoding="utf-8")
    back = pd.read_csv(path, dtype=str, keep_default_na=False)
    assert back["Custom 1"].tolist() == [str(v) for v in merged["Custom 1"].tolist()]


def test_excel_round_trip_preserves_custom_codes(tmp_path: Path) -> None:
    bom, pnp = _load()
    merged = _merge(bom, pnp)
    path = tmp_path / "merged.xlsx"
    merged.to_excel(path, index=False)
    back = pd.read_excel(path, dtype=str, keep_default_na=False)
    assert back["Custom 1"].tolist() == [str(v) for v in merged["Custom 1"].tolist()]
