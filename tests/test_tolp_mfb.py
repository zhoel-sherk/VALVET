"""T-OLP ``.mfb`` (machine feeder base): attachment slots per machine side."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "src")
)

from parsers.tolp_export import (  # noqa: E402
    SIDE_FRONT,
    SIDE_REAR,
    TolpFeeder,
    _compare_feeder_sets,
    _mfb_width,
    load_tolp_export,
)

_REPO = Path(__file__).resolve().parents[1]
_SAMPLE = _REPO / "examples" / "tolp_mfb" / "Techbook_C"
_MB_TOP = _SAMPLE / "mb_top.mfb"


@pytest.fixture(scope="module")
def export():
    if not _MB_TOP.is_file():
        pytest.skip("mfb sample fixture not present")
    return load_tolp_export(_MB_TOP)


def test_width_table_matches_the_t_olp_layout() -> None:
    assert _mfb_width("TapeFeeder8mmSME") == 1
    assert _mfb_width("TapeFeeder12mmSME") == 2
    assert _mfb_width("TapeFeeder16mmSME") == 2
    assert _mfb_width("TapeFeeder24mmSME") == 3
    assert _mfb_width("TapeFeeder36mmSME") == 4
    assert _mfb_width("TapeFeeder44mmSME") == 4
    assert _mfb_width("TapeFeeder56mmSME") == 5
    assert _mfb_width("TapeFeeder88mmSME") == 7
    assert _mfb_width("STF-100D") == 2


def test_source_is_mfb(export) -> None:
    assert export.source == "mfb"


def test_machine_sides_are_parsed(export) -> None:
    counts: dict[tuple[str, str], int] = {}
    for feeder in export.feeders:
        counts[(feeder.machine, feeder.side)] = (
            counts.get((feeder.machine, feeder.side), 0) + 1
        )
    assert counts[("M1", SIDE_FRONT)] == 59
    assert counts[("M1", SIDE_REAR)] == 36
    assert counts[("M3", SIDE_FRONT)] == 23
    assert counts[("M4", SIDE_REAR)] == 6


def test_m1_front_matches_the_t_olp_table(export) -> None:
    """Screenshot M1 Front: Slot 1..7 = 1K, 110K, 75K, 5.6K, 43, 27pF, 270K."""
    slots = {
        f.slot: f.part
        for f in export.feeders
        if f.machine == "M1" and f.side == SIDE_FRONT
    }
    assert slots[1] == "0201_1K_1%"
    assert slots[2] == "0201_110K_1%"
    assert slots[3] == "0201_75K"
    assert slots[4] == "0201_5.6K_1%"
    assert slots[5] == "0201_43_1%"
    assert slots[6] == "0201_27pF_50V_NP0_5%"
    assert slots[7] == "0201_270K_1%"


def test_wide_feeders_consume_following_positions(export) -> None:
    """M3 Front: 44mm at 1, 24mm at 5, 16mm at 8/10/12/14/16/18 (T-OLP No.)."""
    rows = [
        (f.slot, f.part)
        for f in export.feeders
        if f.machine == "M3" and f.side == SIDE_FRONT
    ]
    assert rows[:8] == [
        (1, "CSTM_0673_111M"),
        (5, "FPC0515_30B2_S3R_B"),
        (8, "WF12_022S3R"),
        (10, "W25Q256JVEIQ"),
        (12, "STPI0603_R22M_T2DB1"),
        (14, "STPI0603_R15M_T6DB1"),
        (16, "RT3624BEGQW"),
        (18, "MCW_0630_1R0_N2"),
    ]


def test_tray_feeders_take_every_second_position(export) -> None:
    """M4 Rear is a pallet (tray) feeder: attachment positions 1,3,5,7,9,11."""
    rows = [
        (f.slot, f.part)
        for f in export.feeders
        if f.machine == "M4" and f.side == SIDE_REAR
    ]
    assert [slot for slot, _part in rows] == [1, 3, 5, 7, 9, 11]
    assert {part for _slot, part in rows} == {"I3_1220P"}


def test_folder_collects_every_machine_and_side() -> None:
    """mb_top (newest) wins M1..M4; db_top adds M5..M7."""
    if not _SAMPLE.is_dir():
        pytest.skip("mfb sample fixture not present")
    export = load_tolp_export(_SAMPLE)
    assert export.source == "mfb"
    machines = {f.machine for f in export.feeders}
    assert {"M1", "M2", "M3", "M4", "M5", "M6", "M7"} <= machines


def test_single_mfb_path_works() -> None:
    if not _MB_TOP.is_file():
        pytest.skip("mfb sample fixture not present")
    export = load_tolp_export(str(_MB_TOP))
    assert export.source == "mfb"
    assert export.feeders


def test_mfb_pcb_disagreement_is_reported() -> None:
    mfb = [TolpFeeder("M1", "", SIDE_FRONT, 1, "0201_10K_1%")]
    pcb = [TolpFeeder("M1", "DECANS2", SIDE_FRONT, 7, "0201_10K_1%")]
    warnings = _compare_feeder_sets(mfb, pcb)
    assert warnings and "disagree" in warnings[0]


def test_mfb_pcb_agreement_is_silent() -> None:
    mfb = [TolpFeeder("M1", "", SIDE_FRONT, 1, "0201_10K_1%")]
    pcb = [TolpFeeder("M1", "DECANS2", SIDE_FRONT, 1, "0201_10K_1%")]
    assert _compare_feeder_sets(mfb, pcb) == []
