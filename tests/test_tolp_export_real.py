"""Golden test on the real T-OLP export used during development.

The folder is outside the repository, so the module skips when it is absent
(CI). Its layout is what ``test_tolp_export.py`` models synthetically.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "src")
)

from parsers.tolp_export import SIDE_FRONT, SIDE_REAR, load_tolp_export  # noqa: E402

_FOLDER = Path(r"C:\PCB")
pytestmark = pytest.mark.skipif(
    not (_FOLDER / "M1").is_dir(), reason="T-OLP export folder not present"
)


@pytest.fixture(scope="module")
def export():
    return load_tolp_export(_FOLDER)


def test_machines_and_models(export) -> None:
    assert export.machines == {
        "M1": "DECANS2",
        "M2": "DECANF2FS",
        "M3": "DECANL2",
        "M4": "SM485P",
    }


def test_feeder_counts_per_machine_and_side(export) -> None:
    counts: dict[tuple[str, str], int] = {}
    for feeder in export.feeders:
        counts[(feeder.machine, feeder.side)] = (
            counts.get((feeder.machine, feeder.side), 0) + 1
        )
    assert counts == {
        ("M1", SIDE_FRONT): 51,
        ("M1", SIDE_REAR): 9,
        ("M2", SIDE_FRONT): 20,
        ("M2", SIDE_REAR): 52,
        ("M3", SIDE_FRONT): 44,
        ("M3", SIDE_REAR): 12,
        ("M4", SIDE_FRONT): 19,
    }
    assert len(export.feeders) == 207
    assert not export.warnings


def test_known_slots(export) -> None:
    def slot(part: str, machine: str) -> tuple[str, int] | None:
        for feeder in export.by_part(part):
            if feeder.machine == machine:
                return feeder.side, feeder.slot
        return None

    assert slot("0201_220_1%", "M1") == (SIDE_FRONT, 8)
    assert slot("0201_10K_1%", "M1") == (SIDE_REAR, 18)
    assert slot("0402_10.7K_1%", "M2") == (SIDE_REAR, 1)
    assert slot("FH82HM770", "M4") == (SIDE_FRONT, 1)


def test_slot_numbers_are_unique_per_machine_and_side(export) -> None:
    seen = set()
    for feeder in export.feeders:
        key = (feeder.machine, feeder.side, feeder.slot)
        assert key not in seen, key
        seen.add(key)


def test_no_part_name_is_truncated(export) -> None:
    """The 2-byte shift that cut ``0201_`` to ``01_`` must not come back."""
    parts = {f.part for f in export.feeders}
    assert all(part == part.strip() for part in parts)
    assert not [p for p in parts if p.startswith("01_") and p != "01"]
    assert "0201_220_1%" in parts


_BOM_XLSX = Path(
    r"C:\Users\SMD\Documents\Production\Techbook_C\BOM_PNP_NEW\1235_1220.xlsx"
)


@pytest.mark.skipif(not _BOM_XLSX.is_file(), reason="production BOM not present")
def test_scan_chain_on_production_bom(export) -> None:
    """IN-00004594 -> 0201_10K_1% -> M1 Rear slot 18, straight from the files."""
    from services.scan_match import build_code_index, resolve_scan
    from smt_processor import read_file

    bom = read_file(
        str(_BOM_XLSX),
        first_row=0,
        last_row=-1,
        separator="auto",
        sheet_name="1235",
        column_headers_from_file=False,
    )
    index = build_code_index(bom.to_dict("records"), "0", ["1"], ref_key="3")
    result = resolve_scan("IN-00004594", index, export)
    assert result.ok
    assert [(f.machine, f.side, f.slot) for f in result.feeders] == [
        ("M1", SIDE_REAR, 18)
    ]
    assert result.entries[0].part == "0201_10K_1%"
