"""Qt-free unique-part VSPD resolution (store → machine → PnP → BOM)."""

from __future__ import annotations

from pathlib import Path

import pytest

from package_vspd.parse import parse_package
from package_vspd.resolve import (
    apply_hits_to_rows,
    machine_lookup_from_part_rows,
    resolve_unique_packages,
)
from package_vspd.store import PackageStore

_XLSX = Path(__file__).resolve().parents[1] / "user_temp" / "component_test.xlsx"


def _store(tmp_path: Path) -> PackageStore:
    return PackageStore(tmp_path / "vspd.sqlite")


def test_store_beats_footprint(tmp_path: Path) -> None:
    store = _store(tmp_path)
    try:
        rows = [
            {
                "Ref": "R1",
                "Value": "Chip-R0402",
                "Footprint": "SOIC-8_3.9x4.9mm_P1.27mm",
            },
            {
                "Ref": "R2",
                "Value": "Chip-R0402",
                "Footprint": "SOIC-8_3.9x4.9mm_P1.27mm",
            },
        ]
        hits = resolve_unique_packages(rows, store=store)
        assert hits["Chip-R0402"].vspd_id == "CHIP-0402"
        assert hits["Chip-R0402"].source == "store"
        n = apply_hits_to_rows(rows, hits)
        assert n == 2
        assert rows[0]["Footprint"] == "CHIP-0402"
        assert rows[1]["Footprint"] == "CHIP-0402"
    finally:
        store.close()


def test_footprint_when_store_miss(tmp_path: Path) -> None:
    store = _store(tmp_path)
    try:
        rows = [
            {
                "Ref": "U1",
                "Value": "MysteryPartXYZ",
                "Footprint": "SOIC-8_3.9x4.9mm_P1.27mm",
            }
        ]
        hits = resolve_unique_packages(rows, store=store)
        assert hits["MysteryPartXYZ"].vspd_id == "SOIC-8"
        assert hits["MysteryPartXYZ"].source == "pnp"
    finally:
        store.close()


def test_bom_by_ref_when_store_and_footprint_miss(tmp_path: Path) -> None:
    store = _store(tmp_path)
    try:
        rows = [
            {
                "Ref": "R1",
                "Value": "MysteryPartXYZ",
                "Footprint": "no-such-pkg-zzzz",
            }
        ]
        hits = resolve_unique_packages(
            rows,
            store=store,
            bom_by_ref={"R1": "CAP 0402 100nF"},
        )
        assert hits["MysteryPartXYZ"].vspd_id == "CHIP-0402"
        assert hits["MysteryPartXYZ"].source == "bom"
    finally:
        store.close()


def test_mixed_footprints_majority(tmp_path: Path) -> None:
    store = _store(tmp_path)
    try:
        rows = [
            {
                "Ref": "U1",
                "Value": "MysteryIC",
                "Footprint": "SOIC-8_3.9x4.9mm_P1.27mm",
            },
            {
                "Ref": "U2",
                "Value": "MysteryIC",
                "Footprint": "SOIC-8_3.9x4.9mm_P1.27mm",
            },
            {
                "Ref": "U3",
                "Value": "MysteryIC",
                "Footprint": "R0402",
            },
        ]
        hits = resolve_unique_packages(rows, store=store)
        assert hits["MysteryIC"].vspd_id == "SOIC-8"
        assert hits["MysteryIC"].source == "pnp"
    finally:
        store.close()


def test_other_and_numeric_junk_not_written(tmp_path: Path) -> None:
    store = _store(tmp_path)
    try:
        rows = [
            {"Ref": "X1", "Value": "JunkSKU", "Footprint": "103020015"},
            {"Ref": "X2", "Value": "AlsoJunk", "Footprint": "SOP"},
        ]
        hits = resolve_unique_packages(rows, store=store)
        assert hits["JunkSKU"].source == "unmatched"
        assert hits["JunkSKU"].vspd_id is None
        assert hits["AlsoJunk"].vspd_id is None
        apply_hits_to_rows(rows, hits)
        assert rows[0]["Footprint"] == "103020015"
        assert rows[1]["Footprint"] == "SOP"
    finally:
        store.close()


def test_machine_lookup_beats_footprint(tmp_path: Path) -> None:
    store = _store(tmp_path)
    try:
        lookup = machine_lookup_from_part_rows(
            [{"PARTNAME": "TR2_USER", "PARTDESC": "SOT-23", "UPDPARTGROUPNAME": ""}],
            {"TR2_USER"},
        )
        rows = [
            {
                "Ref": "Q1",
                "Value": "TR2_USER",
                "Footprint": "SOIC-8_3.9x4.9mm_P1.27mm",
            }
        ]
        hits = resolve_unique_packages(rows, store=store, machine_lookup=lookup)
        assert hits["TR2_USER"].vspd_id == "SOT-23"
        assert hits["TR2_USER"].source == "machine"
    finally:
        store.close()


@pytest.mark.skipif(not _XLSX.is_file(), reason="component_test.xlsx not present")
def test_component_test_xlsx_parse_coverage() -> None:
    import pandas as pd

    df = pd.read_excel(_XLSX, header=None)
    col_a = [str(x).strip() for x in df.iloc[:, 0].tolist() if str(x).strip()]
    unique = list(dict.fromkeys(col_a))
    mapped = sum(1 for t in unique if parse_package(t).vspd_id != "OTHER")
    assert mapped / len(unique) >= 0.75
