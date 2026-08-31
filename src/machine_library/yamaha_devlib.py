# SPDX-License-Identifier: MIT
"""Yamaha ``DevLibEd`` / ``DevLibEd2`` ``Ver500`` ``.Lib`` component names (binary).

Logic ported from ``yedytor/src/devlib_reader.py`` (MIT,
https://github.com/marmidr/yedytor). Qt-free; no PySide6.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Union

PathLike = Union[str, Path]

DEVLIB_OFFSET = 160
DEVLIB_HEADER = b"Ver500"
DEVLIB_COMPONENT_SIZE = 640
DEVLIB2_COMPONENT_SIZE = 2048
DEVLIB_COMPONENT_NAME_SIZE = 82
DEVLIB_COMPONENT_BASENAME_SIZE = 44
DEVLIB_BASENAME_OFF = 82

_log = logging.getLogger(__name__)


def _decode_devlib_name(idx: int, raw: bytes) -> str | None:
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    _log.warning("DevLib entry %s: undecodable name bytes: %r", idx, raw[:32])
    return None


def _normalize_devlib_display_name(name_str: str) -> str:
    name_str = name_str.strip()
    if name_str.endswith(")"):
        par_open = name_str.rfind("(")
        if par_open >= 0:
            name_str = name_str[:par_open]
    return name_str.strip()


@dataclass(frozen=True)
class DevLibRecord:
    name: str
    basename: str
    record_index: int

    @property
    def key(self) -> str:
        return self.name.lower()


def _scan_devlib_records(data: bytes, lib_v1: bool) -> list[DevLibRecord] | None:
    """Like yedytor ``__scan``: return part index, or ``None`` to try the other stride."""
    if len(data) < len(DEVLIB_HEADER) or data[: len(DEVLIB_HEADER)] != DEVLIB_HEADER:
        _log.error("DevLib file has no expected Ver500 header")
        return None

    component_size = DEVLIB_COMPONENT_SIZE if lib_v1 else DEVLIB2_COMPONENT_SIZE
    records: list[DevLibRecord] = []
    n = 0
    while True:
        base = DEVLIB_OFFSET + n * component_size
        n += 1
        if base + DEVLIB_COMPONENT_NAME_SIZE > len(data):
            break
        name_bytes = data[base : base + DEVLIB_COMPONENT_NAME_SIZE]
        if len(name_bytes) < DEVLIB_COMPONENT_NAME_SIZE:
            break
        if name_bytes[0] == 0:
            _log.warning("DevLib component name starts with NULL — Ed2.Lib?")
            return None
        nul = name_bytes.find(0)
        if nul >= 0:
            name_bytes = name_bytes[:nul]
        name_raw = _decode_devlib_name(n, name_bytes)
        if not name_raw:
            continue
        name_str = _normalize_devlib_display_name(name_raw)
        if not name_str:
            continue
        b_off = base + DEVLIB_BASENAME_OFF
        b_end = b_off + DEVLIB_COMPONENT_BASENAME_SIZE
        basename = ""
        if b_end <= len(data):
            braw = data[b_off:b_end]
            if braw and braw[0] != 0:
                nul_b = braw.find(0)
                if nul_b >= 0:
                    braw = braw[:nul_b]
                decoded = _decode_devlib_name(n, braw)
                basename = (decoded or "").strip()
        records.append(
            DevLibRecord(name=name_str, basename=basename, record_index=n)
        )
        _log.debug("DevLib %s %s", n, name_str)
    return records


def _pick_devlib_scan(data: bytes) -> list[DevLibRecord]:
    first = _scan_devlib_records(data, True)
    if first is None:
        second = _scan_devlib_records(data, False)
        return second if second is not None else []
    return first


def load_devlib_records(path: PathLike) -> list[DevLibRecord]:
    """Named DevLib rows with optional basename (yedytor field at +82)."""
    return _pick_devlib_scan(Path(path).read_bytes())


def load_devlib_items(path: PathLike) -> dict[str, list[str]]:
    """Load ``.Lib`` with v1 vs Ed2 stride auto-detection (same strategy as yedytor ``DevLibFile``)."""
    items: dict[str, list[str]] = {}
    for rec in load_devlib_records(path):
        key = rec.key
        if key in items:
            if rec.name not in items[key]:
                items[key].append(rec.name)
        else:
            items[key] = [rec.name]
    return items


def load_devlib_partname_set(path: PathLike) -> set[str]:
    """Unique display names from ``load_devlib_items``."""
    return {nm for variants in load_devlib_items(path).values() for nm in variants}
