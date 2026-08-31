# SPDX-License-Identifier: MIT
"""Map footprint/package name strings to VSPD heuristic outlines (Qt-free)."""

from __future__ import annotations

from collections.abc import Callable

from package_vspd.outline import heuristic_outline
from package_vspd.parse import parse_package
from pcb_preview.types import FootprintOutlineMM


def outline_for_footprint_name(name: str) -> FootprintOutlineMM:
    """Resolve one name via parse_package → heuristic_outline; empty if unmatched."""
    raw = (name or "").strip()
    if not raw or raw.lower() in {"nan", "none"}:
        return FootprintOutlineMM(source="none")
    hit = parse_package(raw)
    vid = (hit.vspd_id or "").strip()
    if not vid or vid.upper() == "OTHER":
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
        hit = parse_package(key) if key else None
        vid = (hit.vspd_id or "").strip() if hit else ""
        if not vid or vid.upper() == "OTHER":
            result[key] = FootprintOutlineMM(source="none")
            continue
        if vid not in by_vspd:
            out = heuristic_outline(vid)
            by_vspd[vid] = out if out is not None else FootprintOutlineMM(source="none")
        result[key] = by_vspd[vid]
    return result
