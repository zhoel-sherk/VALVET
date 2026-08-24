# SPDX-License-Identifier: MIT
"""Yamaha ``.Tou`` machine component list (fixed-width binary records).

Logic ported from ``yedytor/src/tou_reader.py`` (MIT,
https://github.com/marmidr/yedytor). Qt-free; no PySide6.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Union

PathLike = Union[str, Path]

TOU_COMPONENT_SIZE = 320
TOU_COMPONENT_NAME_SIZE = 40

_log = logging.getLogger(__name__)


def load_tou_items(path: PathLike) -> dict[str, list[str]]:
    """Load ``.Tou``: lowercase key → list of original spellings (case variants)."""
    data = Path(path).read_bytes()
    items: dict[str, list[str]] = {}
    n = 0
    while True:
        off = n * TOU_COMPONENT_SIZE
        n += 1
        if off + TOU_COMPONENT_NAME_SIZE > len(data):
            break
        name_bytes = data[off : off + TOU_COMPONENT_NAME_SIZE]
        nul = name_bytes.find(0)
        if nul >= 0:
            name_bytes = name_bytes[:nul]
        if not name_bytes:
            continue
        try:
            name_str = name_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                name_str = name_bytes.decode("latin-1")
            except UnicodeDecodeError as e:
                _log.warning("Tou entry %s: invalid characters: %s", n, e)
                continue
        if not name_str:
            continue
        key = name_str.lower()
        if key in items:
            items[key].append(name_str)
        else:
            items[key] = [name_str]
    return items


def load_tou_partname_set(path: PathLike) -> set[str]:
    """Unique display names from ``load_tou_items``."""
    return {nm for variants in load_tou_items(path).values() for nm in variants}
