# SPDX-License-Identifier: MIT
"""Map footprint/package name strings to VSPD heuristic outlines (Qt-free)."""

from __future__ import annotations

from collections.abc import Callable, Mapping

import logger
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


def _lower_profile_map(group_to_profile: Mapping[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw_k, raw_v in group_to_profile.items():
        key = str(raw_k or "").strip()
        prof = str(raw_v or "").strip()
        if not key:
            continue
        if not prof:
            prof = key
        out[key.lower()] = prof
    return out


def _profiles_for_name(name: str, group_to_profile: Mapping[str, str]) -> list[str]:
    """Candidate Hanwha PROFILENAME values: aliases, map, then VSPD-id groups."""
    profiles: list[str] = []
    lowered = _lower_profile_map(group_to_profile)

    def _add(profile: str) -> None:
        text = (profile or "").strip()
        if text and text not in profiles:
            profiles.append(text)

    for cand in footprint_name_keys(name):
        _add(cand)
        _add(lowered.get(cand.lower(), ""))
    vid = ""
    for cand in footprint_name_keys(name):
        vid = _vspd_id_for_key(cand)
        if vid:
            break
    if vid:
        for group, prof in group_to_profile.items():
            g = str(group or "").strip()
            p = str(prof or "").strip() or g
            if _vspd_id_for_key(g) == vid or _vspd_id_for_key(p) == vid:
                _add(p)
    return profiles


def _hanwha_outline_for_name(
    name: str,
    cache_dir: str,
    group_to_profile: Mapping[str, str],
) -> tuple[FootprintOutlineMM | None, list[str]]:
    """Lookup Hanwha UPD geometry. Returns (outline_or_none, profiles_tried)."""
    import machine_library.hanwha_sqlite_cache as hanwha_cache

    tried = _profiles_for_name(name, group_to_profile)
    for profile in tried:
        try:
            built = hanwha_cache.build_outline_from_sqlite(cache_dir, profile)
        except (OSError, ValueError, TypeError) as e:
            logger.warning(
                "PCB package outline: hanwha_upd sqlite failed (%s); skipped profile %s",
                e,
                profile,
            )
            continue
        ol = built.outline
        if (
            built.error
            or ol.source in ("none", "")
            or not (ol.lines or ol.pads or ol.circles)
        ):
            continue
        return ol, tried
    return None, tried


def resolve_named_outlines(
    names: list[str],
    *,
    should_stop: Callable[[], bool] | None = None,
    mdb_cache_dir: str | None = None,
    group_to_profile: Mapping[str, str] | None = None,
) -> tuple[dict[str, FootprintOutlineMM], dict[str, int]]:
    """Unique names only; same VSPD id shares one outline object.

    Second value: hanwha fallback stats (hits, misses) when ``mdb_cache_dir`` is set.
    """
    by_vspd: dict[str, FootprintOutlineMM] = {}
    result: dict[str, FootprintOutlineMM] = {}
    seen: set[str] = set()
    stats = {"hits": 0, "misses": 0}
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
    cache = (mdb_cache_dir or "").strip()
    if cache:
        stats = _apply_hanwha_mdb_fallback(
            result,
            cache_dir=cache,
            group_to_profile=group_to_profile or {},
            should_stop=should_stop,
        )
    return result, stats


def _apply_hanwha_mdb_fallback(
    result: dict[str, FootprintOutlineMM],
    *,
    cache_dir: str,
    group_to_profile: Mapping[str, str],
    should_stop: Callable[[], bool] | None = None,
) -> dict[str, int]:
    import machine_library.hanwha_sqlite_cache as hanwha_cache

    stats = {"hits": 0, "misses": 0}
    pending = [k for k, o in result.items() if o.source != "hanwha_upd"]
    if not pending:
        return stats
    if not hanwha_cache.sqlite_path(cache_dir).is_file():
        logger.warning(
            "PCB package outline: VSPD miss fallback requested; "
            "hanwha sqlite cache missing (%s)",
            cache_dir,
        )
        stats["misses"] = len(pending)
        return stats
    for key in pending:
        if should_stop is not None and should_stop():
            break
        cur = result.get(key)
        if cur is None or cur.source == "hanwha_upd":
            continue
        prev = cur.source
        hit, tried = _hanwha_outline_for_name(key, cache_dir, group_to_profile)
        if hit is None:
            stats["misses"] += 1
            logger.info(
                "PCB package outline: hanwha_upd miss for %s (VSPD %s; tried %s)",
                key,
                prev,
                ",".join(tried[:12]) or "-",
            )
            continue
        logger.info(
            "PCB package outline: VSPD %s; using hanwha_upd sqlite for %s",
            prev,
            key,
        )
        stats["hits"] += 1
        for cand in footprint_name_keys(key):
            old = result.get(cand)
            if old is None or old.source != "hanwha_upd":
                result[cand] = hit
    return stats
