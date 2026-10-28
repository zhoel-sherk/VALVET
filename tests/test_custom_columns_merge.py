"""Custom columns: exact pass-through through Merge, optional Cross-check.

A Custom column is not a part number: Clean BOM never reads it, and Merge must
copy it to every placement of the designators it belongs to without trimming,
case-folding or numeric coercion.
"""

from __future__ import annotations

import os
import sys

import pandas as pd
import pytest

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "src")
)

from services.processor_config import build_processor_config  # noqa: E402

BOM_COLUMNS = ["0", "1", "2", "3"]
PNP_COLUMNS = ["0", "1", "2", "3", "4", "5", "6", "7", "8"]


def _bom() -> pd.DataFrame:
    """[1C code, comment, refs, second custom code] — no header row."""
    return pd.DataFrame(
        [
            ["IN-00004817", "STP0603_R15M_T6DB1", "PL1,PL2,PL3", "A-1"],
            ["IN-00004818", "STP0402_10K", "LP812", "B-2"],
            ["  keep  ", "XTAL 25MHZ", "R1", "C-3"],
        ],
        columns=BOM_COLUMNS,
    )


def _pnp() -> pd.DataFrame:
    """[ref, X, Y, rot, blank gap, footprint, pnp custom 1, pnp custom 3, comment]."""
    return pd.DataFrame(
        [
            [
                "PL1",
                "10",
                "20",
                "0",
                "",
                "0402",
                "IN-00004817",
                "PNP3-PL1",
                "STP0603_R15M_T6DB1",
            ],
            [
                "PL2",
                "11",
                "21",
                "0",
                "",
                "0402",
                "DIFFERENT-CODE",
                "PNP3-PL2",
                "STP0603_R15M_T6DB1",
            ],
            [
                "LP812",
                "12",
                "22",
                "90",
                "",
                "0402",
                "IN-00004818",
                "PNP3-LP812",
                "STP0402_10K",
            ],
            ["R1", "13", "23", "180", "", "0603", "  keep  ", "PNP3-R1", "XTAL 25MHZ"],
            ["R9", "14", "24", "0", "", "0603", "PNP1-R9", "PNP3-R9", "PNP-ONLY"],
        ],
        columns=PNP_COLUMNS,
    )


def _processor(*, compare_custom: bool = False):
    return build_processor_config(
        _bom(),
        _pnp(),
        {"REF": "2", "Comment": "1"},
        {
            "REF": "0",
            "X": "1",
            "Y": "2",
            "Rotation": "3",
            "Footprint": "5",
            "Comment": "8",
        },
        bom_custom=[("Custom 1", "0"), ("Custom 2", "3")],
        pnp_custom=[("Custom 1", "6"), ("Custom 3", "7")],
        compare_custom=compare_custom,
    )


def test_merge_appends_custom_columns_after_the_standard_seven() -> None:
    merged = _processor().merge_bom_pnp()
    assert list(merged.columns) == [
        "Ref",
        "Value",
        "Footprint",
        "X",
        "Y",
        "Rotation",
        "Layer",
        "Custom 1",
        "Custom 2",
        "Custom 3",
    ]


def test_bom_custom_value_is_replicated_to_every_designator() -> None:
    merged = _processor().merge_bom_pnp().set_index("Ref")
    for ref in ("PL1", "PL2"):
        assert merged.at[ref, "Custom 1"] == "IN-00004817"
        assert merged.at[ref, "Custom 2"] == "A-1"
    assert merged.at["LP812", "Custom 1"] == "IN-00004818"
    assert merged.at["LP812", "Custom 2"] == "B-2"


def test_custom_value_is_passed_through_verbatim() -> None:
    """No strip / case fold / numeric coercion: what the BOM has is what ships."""
    merged = _processor().merge_bom_pnp().set_index("Ref")
    assert merged.at["R1", "Custom 1"] == "  keep  "
    assert merged.at["R1", "Custom 2"] == "C-3"


def test_bom_wins_over_pnp_for_the_same_custom_name() -> None:
    merged = _processor().merge_bom_pnp().set_index("Ref")
    assert merged.at["PL1", "Custom 1"] == "IN-00004817"
    # A placement whose designator is absent from the BOM falls back to PnP.
    assert merged.at["R9", "Custom 1"] == "PNP1-R9"
    assert merged.at["R9", "Custom 2"] == ""
    assert merged.at["R9", "Custom 3"] == "PNP3-R9"


def test_pnp_only_custom_column_is_appended() -> None:
    merged = _processor().merge_bom_pnp().set_index("Ref")
    assert merged.at["PL1", "Custom 3"] == "PNP3-PL1"
    assert list(merged.columns).count("Custom 1") == 1


def test_pnp_custom_without_bom_custom_still_passes_through() -> None:
    proc = build_processor_config(
        _bom(),
        _pnp(),
        {"REF": "2", "Comment": "1"},
        {"REF": "0", "Comment": "8"},
        pnp_custom=[("Custom 1", "6")],
    )
    merged = proc.merge_bom_pnp().set_index("Ref")
    assert merged.at["PL1", "Custom 1"] == "IN-00004817"
    assert merged.at["R9", "Custom 1"] == "PNP1-R9"


def test_custom_columns_do_not_change_value_or_coordinates() -> None:
    merged = _processor().merge_bom_pnp().set_index("Ref")
    assert merged.at["PL1", "Value"] == "STP0603_R15M_T6DB1"
    assert merged.at["R9", "Value"] == "PNP-ONLY"
    assert float(merged.at["PL1", "X"]) == 10.0
    assert merged.at["PL1", "Layer"] == "Top"


def test_merge_without_custom_columns_is_unchanged() -> None:
    proc = build_processor_config(
        _bom(),
        _pnp(),
        {"REF": "2", "Comment": "1"},
        {"REF": "0", "X": "1", "Y": "2", "Rotation": "3", "Footprint": "5"},
    )
    assert list(proc.merge_bom_pnp().columns) == [
        "Ref",
        "Value",
        "Footprint",
        "X",
        "Y",
        "Rotation",
        "Layer",
    ]


def test_mmd_export_ignores_custom_columns() -> None:
    """MMD has a fixed field list; Custom codes must not leak into it."""
    from mmd_export import merge_dataframe_to_mmd_mercury

    merged = _processor().merge_bom_pnp()
    text = merge_dataframe_to_mmd_mercury(merged)
    assert "PL1" in text
    assert "IN-00004817" not in text
    assert "A-1" not in text


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("IN-00004817", "IN-00004817"),
        ("  005  ", "  005  "),
        ("+7", "+7"),
        ("A=1", "A=1"),
        (1000001, "1000001"),
        (1000001.0, "1000001"),
        ("", ""),
        (None, ""),
    ],
)
def test_custom_cell_text_keeps_text_and_cleans_numbers(
    value: object, expected: str
) -> None:
    from smt_processor import custom_cell_text

    assert custom_cell_text(value) == expected


def test_cross_check_ignores_custom_columns_by_default() -> None:
    result = _processor(compare_custom=False).cross_check()
    assert "custom_mismatch" not in set(result["IssueType"].tolist())


def test_cross_check_compares_same_named_custom_columns_when_enabled() -> None:
    result = _processor(compare_custom=True).cross_check()
    custom = result[result["IssueType"] == "custom_mismatch"]
    # Every placement matches except PL2, whose BOM code differs from PnP.
    assert len(custom) == 1
    assert custom["Designator"].tolist() == ["PL2"]
    assert custom.iloc[0]["BOM_Value"] == "IN-00004817"
    assert custom.iloc[0]["PnP_Value"] == "DIFFERENT-CODE"
    assert custom.iloc[0]["Severity"] == "warning"


def test_cross_check_identical_custom_values_raise_nothing() -> None:
    bom = _bom()
    pnp = _pnp()
    pnp["6"] = ["IN-00004817", "IN-00004817", "IN-00004818", "  keep  ", "x"]
    proc = build_processor_config(
        bom,
        pnp,
        {"REF": "2", "Comment": "1"},
        {"REF": "0", "Comment": "8"},
        bom_custom=[("Custom 1", "0")],
        pnp_custom=[("Custom 1", "6")],
        compare_custom=True,
    )
    result = proc.cross_check()
    assert "custom_mismatch" not in set(result["IssueType"].tolist())
