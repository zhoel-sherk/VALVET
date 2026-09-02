# SPDX-License-Identifier: MIT
"""Map footprint/package name strings to VSPD heuristic outlines (Qt-free)."""

from __future__ import annotations

from collections.abc import Callable

from package_vspd.outline import heuristic_outline
from package_vspd.parse import parse_package
from pcb_preview.types import FootprintOutlineMM


def footprint_name_keys(name: str) -> list[str]:
    """Lookup chain: raw, path tail, KiCad lib:NAME tail. Order is first-hit."""
    raw = (name or "").strip()
    if not raw:
        return []
    keys: list[str] = []

    def _add(part: str) -> None:
        text = part.strip()
        if text and text not in keys:
            keys.append(text)

    _add(raw)
    slash = raw.replace("\\", "/")
    tail = slash.split("/")[-1]
    _add(tail)
    if ":" in tail:
        _add(tail.rsplit(":", 1)[-1])
    elif ":" in raw:
        _add(raw.rsplit(":", 1)[-1])
    return keys


def _vspd_id_for_key(key: str) -> str:
    if not key:
        return ""
    hit = parse_package(key)
    vid = (hit.vspd_id or "").strip()
    if not vid or vid.upper() == "OTHER":
        return ""
    return vid


def outline_for_footprint_name(name: str) -> FootprintOutlineMM:
    """Resolve one name via parse_package → heuristic_outline; empty if unmatched."""
    raw = (name or "").strip()
    if not raw or raw.lower() in {"nan", "none"}:
        return FootprintOutlineMM(source="none")
    vid = ""
    for cand in footprint_name_keys(raw):
        vid = _vspd_id_for_key(cand)
        if vid:
            break
    if not vid:
        return FootprintOutlineMM(source="none")
    out = heuristic_outline(vid)
    if out is None:
        return FootprintOutlineMM(source="none")
    return out


def resolve_named_outlines(
    names: list[str],
    *,
    should_stop: Callable[[], bool] | None = None,
) -> dict[str, FootprintOutlineMM]:
    """Unique names only; same VSPD id shares one outline object."""
    by_vspd: dict[str, FootprintOutlineMM] = {}
    result: dict[str, FootprintOutlineMM] = {}
    seen: set[str] = set()
    for raw in names:
        if should_stop is not None and should_stop():
            break
        key = (raw or "").strip()
        if key in seen:
            continue
        seen.add(key)
        chain = footprint_name_keys(key)
        vid = ""
        for cand in chain:
            vid = _vspd_id_for_key(cand)
            if vid:
                break
        if not vid:
            empty = FootprintOutlineMM(source="none")
            for cand in chain:
                result[cand] = empty
            continue
        if vid not in by_vspd:
            out = heuristic_outline(vid)
            by_vspd[vid] = out if out is not None else FootprintOutlineMM(source="none")
        packed = by_vspd[vid]
        for cand in chain:
            result[cand] = packed
    return result
