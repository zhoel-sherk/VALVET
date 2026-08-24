"""Tests for Yamaha ``.Tou`` reader (``machine_library/yamaha_tou.py``)."""

from __future__ import annotations

from pathlib import Path

from machine_library.yamaha_tou import (
    TOU_COMPONENT_NAME_SIZE,
    TOU_COMPONENT_SIZE,
    load_tou_items,
    load_tou_partname_set,
)


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
