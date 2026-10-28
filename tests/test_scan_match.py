"""Scan resolution: Custom code -> component -> T-OLP feeder slots."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "src")
)

from parsers.tolp_export import TolpExport, TolpFeeder  # noqa: E402
from services.scan_match import (  # noqa: E402
    STATE_OK,
    STATE_PART_MISSING,
    STATE_UNKNOWN_CODE,
    build_code_index,
    resolve_scan,
)

ROWS = [
    {
        "Ref": "R1,R2",
        "Value": "0201_10K_1%",
        "Comment": "0201_10K_1%",
        "Custom 1": "IN-00004594",
    },
    {
        "Ref": "U16",
        "Value": "i5_13500HX",
        "Comment": "i5_13500HX",
        "Custom 1": "IN-00005020",
    },
    {
        "Ref": "R9",
        "Value": "0201_10K_1%",
        "Comment": "0201_10K_1%",
        "Custom 1": "IN-00004594",
    },
    {"Ref": "D1", "Value": "", "Comment": "DSS36", "Custom 1": "IN-00004778"},
]


def _export() -> TolpExport:
    return TolpExport(
        folder=Path("."),
        feeders=(
            TolpFeeder("M1", "DECANS2", "Rear", 18, "0201_10K_1%"),
            TolpFeeder("M3", "DECANL2", "Front", 44, "0201_10K_1%"),
            TolpFeeder("M4", "SM485P", "Front", 1, "i5_13500HX"),
        ),
        machines={"M1": "DECANS2", "M3": "DECANL2", "M4": "SM485P"},
    )


def test_index_groups_refs_per_code_and_part() -> None:
    index = build_code_index(ROWS, "Custom 1", ("Value", "Comment"))
    entry = index["IN-00004594"][0]
    assert entry.part == "0201_10K_1%"
    assert entry.refs == ("R1,R2", "R9")


def test_index_falls_back_to_the_second_part_key() -> None:
    index = build_code_index(ROWS, "Custom 1", ("Value", "Comment"))
    assert [e.part for e in index["IN-00004778"]] == ["DSS36"]


def test_resolve_returns_every_slot_sorted() -> None:
    index = build_code_index(ROWS, "Custom 1", ("Value", "Comment"))
    result = resolve_scan("IN-00004594", index, _export())
    assert result.state == STATE_OK
    assert [(f.machine, f.side, f.slot) for f in result.feeders] == [
        ("M1", "Rear", 18),
        ("M3", "Front", 44),
    ]


def test_scan_input_is_trimmed() -> None:
    index = build_code_index(ROWS, "Custom 1", ("Value", "Comment"))
    result = resolve_scan("  IN-00004594 \r\n", index, _export())
    assert result.state == STATE_OK


def test_unknown_code_is_reported() -> None:
    index = build_code_index(ROWS, "Custom 1", ("Value", "Comment"))
    result = resolve_scan("IN-99999999", index, _export())
    assert result.state == STATE_UNKNOWN_CODE
    assert result.entries == ()
    assert result.feeders == ()


def test_known_code_without_feeder_is_reported_with_components() -> None:
    index = build_code_index(ROWS, "Custom 1", ("Value", "Comment"))
    result = resolve_scan("IN-00005020", index, _export())
    assert result.state == STATE_OK
    assert result.feeders[0].machine == "M4"

    result = resolve_scan("IN-00004778", index, _export())
    assert result.state == STATE_PART_MISSING
    assert [e.part for e in result.entries] == ["DSS36"]


def test_no_export_loaded_reports_part_missing() -> None:
    index = build_code_index(ROWS, "Custom 1", ("Value", "Comment"))
    result = resolve_scan("IN-00004594", index, None)
    assert result.state == STATE_PART_MISSING
    assert result.entries


def test_blank_code_returns_unknown() -> None:
    index = build_code_index(ROWS, "Custom 1", ("Value", "Comment"))
    assert resolve_scan("   ", index, _export()).state == STATE_UNKNOWN_CODE
