"""Tests for Yamaha ``.Tou`` reader (``machine_library/yamaha_tou.py``)."""

from __future__ import annotations

from pathlib import Path

import pytest

from machine_library.yamaha_tou import (
    TOU_COMMENT_OFF,
    TOU_COMPONENT_NAME_SIZE,
    TOU_COMPONENT_SIZE,
    TOU_REFDES_OFF,
    TOU_ROT_OFF,
    TOU_X_OFF,
    TOU_Y_OFF,
    iter_tou_records,
    load_tou_items,
    load_tou_partname_set,
    merge_tou_items,
    tou_files_in_dir,
)
from yamaha_paths import YAMAHA_TOU_BOT, YAMAHA_TOU_TOP


def _tou_record(name: str) -> bytes:
    raw = name.encode("utf-8")[:TOU_COMPONENT_NAME_SIZE]
    raw = raw + b"\x00" * (TOU_COMPONENT_NAME_SIZE - len(raw))
    return raw + b"\x00" * (TOU_COMPONENT_SIZE - TOU_COMPONENT_NAME_SIZE)


def test_tou_empty_and_truncated(tmp_path: Path) -> None:
    p = tmp_path / "empty.tou"
    p.write_bytes(b"")
    assert load_tou_items(p) == {}
    assert load_tou_partname_set(p) == set()

    short = tmp_path / "short.tou"
    short.write_bytes(b"x" * 20)
    assert load_tou_items(short) == {}


def test_tou_one_component(tmp_path: Path) -> None:
    p = tmp_path / "one.tou"
    p.write_bytes(_tou_record("SOT23_BSS138"))
    items = load_tou_items(p)
    assert items == {"sot23_bss138": ["SOT23_BSS138"]}
    assert load_tou_partname_set(p) == {"SOT23_BSS138"}


def test_tou_case_variants(tmp_path: Path) -> None:
    p = tmp_path / "case.tou"
    p.write_bytes(_tou_record("AbC") + _tou_record("aBc"))
    items = load_tou_items(p)
    assert "abc" in items
    assert set(items["abc"]) == {"AbC", "aBc"}


def test_tou_skips_blank_name(tmp_path: Path) -> None:
    p = tmp_path / "blank.tou"
    p.write_bytes(_tou_record("") + _tou_record("ONLY"))
    assert load_tou_partname_set(p) == {"ONLY"}


def test_tou_placement_fields(tmp_path: Path) -> None:
    import struct

    rec = bytearray(_tou_record("CAPC1005X56N_10nF"))
    rec[TOU_REFDES_OFF : TOU_REFDES_OFF + 3] = b"C41"
    struct.pack_into("<i", rec, TOU_X_OFF, 56934)
    struct.pack_into("<i", rec, TOU_Y_OFF, 12359)
    struct.pack_into("<i", rec, TOU_ROT_OFF, 180000)
    rec[TOU_COMMENT_OFF : TOU_COMMENT_OFF + 4] = b"10nF"
    p = tmp_path / "place.tou"
    p.write_bytes(bytes(rec))
    got = list(iter_tou_records(p))
    assert len(got) == 1
    assert got[0].refdes == "C41"
    assert got[0].comment == "10nF"
    assert got[0].x_mm == pytest.approx(56.934)
    assert got[0].y_mm == pytest.approx(12.359)
    assert got[0].rotation_deg == pytest.approx(180.0)


def test_yedytor_example_unique_keys() -> None:
    assert YAMAHA_TOU_TOP.is_file()
    assert YAMAHA_TOU_BOT.is_file()
    assert len(load_tou_items(YAMAHA_TOU_TOP)) == 29
    assert len(load_tou_items(YAMAHA_TOU_BOT)) == 49


def test_tou_folder_merge(tmp_path: Path) -> None:
    a = tmp_path / "a.tou"
    b = tmp_path / "b.TOU"
    a.write_bytes(_tou_record("AAA"))
    b.write_bytes(_tou_record("BBB"))
    paths = tou_files_in_dir(tmp_path)
    assert {p.name for p in paths} == {"a.tou", "b.TOU"}
    items = merge_tou_items(paths)
    assert set(items) == {"aaa", "bbb"}
