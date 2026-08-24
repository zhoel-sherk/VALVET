"""Tests for Yamaha ``Ver500`` ``.Lib`` reader (``machine_library/yamaha_devlib.py``)."""

from __future__ import annotations

from pathlib import Path

from machine_library.yamaha_devlib import (
    DEVLIB2_COMPONENT_SIZE,
    DEVLIB_COMPONENT_NAME_SIZE,
    DEVLIB_COMPONENT_SIZE,
    DEVLIB_OFFSET,
    load_devlib_items,
    load_devlib_partname_set,
)


def _pad_header(buf: bytearray) -> None:
    buf[:6] = b"Ver500"


def _put_devlib_name(buf: bytearray, record_base: int, text: str) -> None:
    raw = text.encode("utf-8")[:DEVLIB_COMPONENT_NAME_SIZE]
    chunk = raw + b"\x00" * (DEVLIB_COMPONENT_NAME_SIZE - len(raw))
    buf[record_base : record_base + DEVLIB_COMPONENT_NAME_SIZE] = chunk


def test_devlib_bad_header(tmp_path: Path) -> None:
    p = tmp_path / "bad.lib"
    p.write_bytes(b"NoHead" + b"\x00" * 200)
    assert load_devlib_items(p) == {}


def test_devlib_v1_single(tmp_path: Path) -> None:
    total = DEVLIB_OFFSET + DEVLIB_COMPONENT_SIZE
    buf = bytearray(total)
    _pad_header(buf)
    _put_devlib_name(buf, DEVLIB_OFFSET, "2512_R_7,5R/5%/1W(3)")
    p = tmp_path / "v1.lib"
    p.write_bytes(buf)
    items = load_devlib_items(p)
    assert items == {"2512_r_7,5r/5%/1w": ["2512_R_7,5R/5%/1W"]}
    assert load_devlib_partname_set(p) == {"2512_R_7,5R/5%/1W"}


def test_devlib_ed2_after_v1_fails(tmp_path: Path) -> None:
    """v1 stride hits NUL-prefixed name at second slot → retry Ed2."""
    total = DEVLIB_OFFSET + DEVLIB2_COMPONENT_SIZE
    buf = bytearray(total)
    _pad_header(buf)
    _put_devlib_name(buf, DEVLIB_OFFSET, "ONLY2048")
    second_base = DEVLIB_OFFSET + DEVLIB_COMPONENT_SIZE
    _put_devlib_name(buf, second_base, "")
    buf[second_base] = 0
    p = tmp_path / "ed2.lib"
    p.write_bytes(buf)
    names = load_devlib_partname_set(p)
    assert names == {"ONLY2048"}
