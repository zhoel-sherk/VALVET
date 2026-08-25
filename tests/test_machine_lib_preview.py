"""Machine lib preview columns and PARTGROUP Type join (no live .mdb)."""

from __future__ import annotations

import pandas as pd

from hanwha_mdb_edit.core.column_labels import label_and_tooltip_for_column
from machine_library.hanwha_preview import (
    MACHINE_LIB_PREVIEW_COLUMNS,
    attach_part_group_type,
    machine_lib_preview_frame,
)


def test_preview_frame_keeps_four_columns_in_order() -> None:
    df = pd.DataFrame(
        {
            "PARTNAME": ["FA05ZCT"],
            "PROFILENAME": ["p1"],
            "PARTDESC": ["tant"],
            "CONFIDENCE_LEVEL": [40],
            "USED_MACHINE_SET": [1],
            "VENDORID": [0],
            "UPDPARTGROUPNAME": ["Chip-Tantal"],
            "PARENTPROFILE": ["0406-001888"],
        }
    )
    view = machine_lib_preview_frame(df)
    assert list(view.columns) == list(MACHINE_LIB_PREVIEW_COLUMNS)
    assert view.iloc[0]["PARTNAME"] == "FA05ZCT"
    assert view.iloc[0]["UPDPARTGROUPNAME"] == "Chip-Tantal"
    assert "PARENTPROFILE" not in view.columns
    assert "PROFILENAME" not in view.columns


def test_preview_frame_adds_missing_type_column() -> None:
    df = pd.DataFrame(
        {
            "PARTNAME": ["a"],
            "PARTDESC": ["d"],
            "CONFIDENCE_LEVEL": [10],
        }
    )
    view = machine_lib_preview_frame(df)
    assert list(view.columns) == list(MACHINE_LIB_PREVIEW_COLUMNS)
    assert pd.isna(view.iloc[0]["UPDPARTGROUPNAME"])


def test_attach_part_group_type_via_profile() -> None:
    parts = pd.DataFrame(
        {
            "PARTNAME": ["FA05ZCT"],
            "PROFILENAME": ["profA"],
            "PARTDESC": ["x"],
            "CONFIDENCE_LEVEL": [40],
        }
    )
    profile = pd.DataFrame(
        {"PROFILENAME": ["profA"], "UPDPARTGROUPID": [27]},
    )
    gmap = pd.DataFrame(
        {
            "UPDPARTGROUPID": [27],
            "UPDPARTGROUPNAME": ["Chip-Tantal"],
        }
    )
    out = attach_part_group_type(parts, profile, gmap)
    assert out.iloc[0]["UPDPARTGROUPNAME"] == "Chip-Tantal"
    assert "CONFIDENCE_LEVEL" in out.columns


def test_machine_lib_header_labels() -> None:
    assert label_and_tooltip_for_column("PARTNAME")[0] == "Part name"
    assert label_and_tooltip_for_column("PARTDESC")[0] == "Description"
    assert label_and_tooltip_for_column("CONFIDENCE_LEVEL")[0] == "Level"
    label, tip = label_and_tooltip_for_column("UPDPARTGROUPNAME")
    assert label == "Type"
    assert "PARENTPROFILE" in tip
    assert "Chip-Tantal" in tip or "CHIP-Circle" in tip
