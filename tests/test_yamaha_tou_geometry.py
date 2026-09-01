"""Yamaha name-based footprint silhouette and .Tou placement metadata."""

from __future__ import annotations

import pytest

from machine_library.yamaha_tou import iter_tou_records
from machine_library.yamaha_tou_geometry import (
    build_outline_from_name,
    build_outline_from_tou_record,
    package_size_mm,
)
from yamaha_paths import YAMAHA_TOU_TOP


def test_package_size_imperial_and_metric() -> None:
    assert package_size_mm("C1206_100nF 250V") == (3.2, 1.6)
    assert package_size_mm("FP-SR1206-MFG_100k 1206") == (3.2, 1.6)
    assert package_size_mm("CAPC1005X56N_10nF") == (1.0, 0.5)
    assert package_size_mm("L0603-BLM18PG121") == (1.6, 0.8)
    assert package_size_mm("NOCODE") is None


def test_outline_from_name_1206() -> None:
    r = build_outline_from_name("C1206_100nF 250V", kind="Lib")
    assert r.error == ""
    assert r.outline.source == "yamaha_heuristic"
    assert r.size_x_mm == pytest.approx(3.2)
    assert r.size_y_mm == pytest.approx(1.6)
    assert r.outline.bbox.width == pytest.approx(3.2)
    assert r.outline.bbox.height == pytest.approx(1.6)
    assert len(r.outline.lines) == 4


def test_outline_from_real_tou_1206() -> None:
    recs = [
        rec for rec in iter_tou_records(YAMAHA_TOU_TOP) if "1206" in rec.name.upper()
    ]
    assert recs
    r = build_outline_from_tou_record(recs[0])
    assert r.error == ""
    assert r.outline.source == "yamaha_tou"
    assert r.size_x_mm == pytest.approx(3.2)
    assert r.size_y_mm == pytest.approx(1.6)
    assert recs[0].refdes
    assert any("ref=" in w for w in r.warnings)
