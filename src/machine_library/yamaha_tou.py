# SPDX-License-Identifier: MIT
"""Yamaha ``.Tou`` machine component list (fixed-width binary records).

Logic ported from ``yedytor/src/tou_reader.py`` (MIT,
https://github.com/marmidr/yedytor). Qt-free; no PySide6.

Bytes 40–319 are a placement/job payload (not a geometry library): refdes,
board XY, rotation, comment. Body size is not stored; see
``yamaha_tou_geometry``.
"""

from __future__ import annotations

import struct
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Union

PathLike = Union[str, Path]

TOU_COMPONENT_SIZE = 320
TOU_COMPONENT_NAME_SIZE = 40
TOU_REFDES_OFF = 40
TOU_REFDES_SIZE = 16
TOU_X_OFF = 56
TOU_Y_OFF = 60
TOU_ROT_OFF = 68
TOU_COMMENT_OFF = 82
TOU_COMMENT_SIZE = 40
# Placement XY appears to be 0.001 mm (µm stored as int32).
TOU_XY_TO_MM = 0.001
TOU_ROT_TO_DEG = 0.001


def _nul_str(raw: bytes) -> str:
    nul = raw.find(0)
    if nul >= 0:
        raw = raw[:nul]
    raw = raw.rstrip(b" ")
    if not raw:
        return ""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return raw.decode("latin-1")
        except UnicodeDecodeError:
            return raw.decode("latin-1", errors="replace")


def _i32(rec: bytes, off: int) -> int | None:
    if off + 4 > len(rec):
        return None
    return int(struct.unpack_from("<i", rec, off)[0])


@dataclass(frozen=True)
class TouRecord:
    """One 320-byte ``.Tou`` slot with a non-empty component name."""

    name: str
    record_index: int
    source_path: str
    refdes: str = ""
    comment: str = ""
    x_mm: float | None = None
    y_mm: float | None = None
    rotation_deg: float | None = None

    @property
    def key(self) -> str:
        return self.name.lower()


def _xy_mm(raw: int | None) -> float | None:
    if raw is None:
        return None
    mm = raw * TOU_XY_TO_MM
    if abs(mm) > 1_000.0:
        return None
    return mm


def _rot_deg(raw: int | None) -> float | None:
    if raw is None:
        return None
    deg = raw * TOU_ROT_TO_DEG
    if abs(deg) > 720.0:
        return None
    return deg


def iter_tou_records(path: PathLike) -> Iterator[TouRecord]:
    """Yield named records in file order (blank name slots skipped)."""
    p = Path(path)
    data = p.read_bytes()
    src = str(p)
    n = 0
    while True:
        off = n * TOU_COMPONENT_SIZE
        rec_i = n
        n += 1
        if off + TOU_COMPONENT_NAME_SIZE > len(data):
            break
        rec = data[off : off + TOU_COMPONENT_SIZE]
        if len(rec) < TOU_COMPONENT_NAME_SIZE:
            break
        name = _nul_str(rec[:TOU_COMPONENT_NAME_SIZE])
        if not name:
            continue
        refdes = _nul_str(rec[TOU_REFDES_OFF : TOU_REFDES_OFF + TOU_REFDES_SIZE])
        comment = _nul_str(rec[TOU_COMMENT_OFF : TOU_COMMENT_OFF + TOU_COMMENT_SIZE])
        yield TouRecord(
            name=name,
            record_index=rec_i,
            source_path=src,
            refdes=refdes,
            comment=comment,
            x_mm=_xy_mm(_i32(rec, TOU_X_OFF)),
            y_mm=_xy_mm(_i32(rec, TOU_Y_OFF)),
            rotation_deg=_rot_deg(_i32(rec, TOU_ROT_OFF)),
        )


def tou_files_in_dir(folder: PathLike) -> list[Path]:
    """``*.tou`` / ``*.TOU`` in ``folder`` (non-recursive), sorted by name."""
    d = Path(folder)
    if not d.is_dir():
        return []
    return sorted(
        p for p in d.iterdir() if p.is_file() and p.suffix.lower() == ".tou"
    )


def load_tou_items(path: PathLike) -> dict[str, list[str]]:
    """Load ``.Tou``: lowercase key → list of original spellings (case variants)."""
    items: dict[str, list[str]] = {}
    for rec in iter_tou_records(path):
        key = rec.key
        if key in items:
            if rec.name not in items[key]:
                items[key].append(rec.name)
        else:
            items[key] = [rec.name]
    return items


def load_tou_partname_set(path: PathLike) -> set[str]:
    """Unique display names from ``load_tou_items``."""
    return {nm for variants in load_tou_items(path).values() for nm in variants}


def merge_tou_items(paths: list[PathLike]) -> dict[str, list[str]]:
    """Union of ``load_tou_items`` for several files (folder scan)."""
    items: dict[str, list[str]] = {}
    for path in paths:
        for key, variants in load_tou_items(path).items():
            if key not in items:
                items[key] = list(variants)
                continue
            seen = set(items[key])
            for nm in variants:
                if nm not in seen:
                    items[key].append(nm)
                    seen.add(nm)
    return items
