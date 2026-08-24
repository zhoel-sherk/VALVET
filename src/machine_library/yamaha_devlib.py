# SPDX-License-Identifier: MIT
"""Yamaha ``DevLibEd`` / ``DevLibEd2`` ``Ver500`` ``.Lib`` component names (binary).

Logic ported from ``yedytor/src/devlib_reader.py`` (MIT,
https://github.com/marmidr/yedytor). Qt-free; no PySide6.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Union

PathLike = Union[str, Path]

DEVLIB_OFFSET = 160
DEVLIB_HEADER = b"Ver500"
DEVLIB_COMPONENT_SIZE = 640
DEVLIB2_COMPONENT_SIZE = 2048
DEVLIB_COMPONENT_NAME_SIZE = 82

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


def _scan_devlib_records(data: bytes, lib_v1: bool) -> dict[str, list[str]] | None:
    """Like yedytor ``__scan``: return part index, or ``None`` to try the other stride."""
    if len(data) < len(DEVLIB_HEADER) or data[: len(DEVLIB_HEADER)] != DEVLIB_HEADER:
        _log.error("DevLib file has no expected Ver500 header")
        return None

    component_size = DEVLIB_COMPONENT_SIZE if lib_v1 else DEVLIB2_COMPONENT_SIZE
    items: dict[str, list[str]] = {}
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
        key = name_str.lower()
        if key in items:
            items[key].append(name_str)
        else:
            items[key] = [name_str]
        _log.debug("DevLib %s %s", n, name_str)
    return items


def load_devlib_items(path: PathLike) -> dict[str, list[str]]:
    """Load ``.Lib`` with v1 vs Ed2 stride auto-detection (same strategy as yedytor ``DevLibFile``)."""
    data = Path(path).read_bytes()
    first = _scan_devlib_records(data, True)
    if first is None:
        second = _scan_devlib_records(data, False)
        return second if second is not None else {}
    return first


def load_devlib_partname_set(path: PathLike) -> set[str]:
    """Unique display names from ``load_devlib_items``."""
    return {nm for variants in load_devlib_items(path).values() for nm in variants}
