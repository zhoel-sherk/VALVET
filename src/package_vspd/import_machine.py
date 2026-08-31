# SPDX-License-Identifier: MIT
"""Import unique machine-library *packages* (not every part SKU) into a PackageStore."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from package_vspd.outline import outline_to_json
from package_vspd.parse import parse_package
from package_vspd.store import PackageStore


@dataclass(frozen=True)
class MachineImportStats:
    groups_seen: int
    mapped: int
    skipped: int
    outlines: int


def _unique_tokens(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in values:
        s = str(raw).strip()
        if not s or s.lower() in {"nan", "none", "-"}:
            continue
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def import_machine_packages(
    store: PackageStore,
    *,
    part_groups: Iterable[str],
    yamaha_names: Iterable[str] = (),
    extra_tokens: Iterable[str] = (),
    group_to_profile: Mapping[str, str] | None = None,
    cache_dir: str = "",
) -> MachineImportStats:
    """Map unique part-group / Yamaha package strings to VSPD; copy UPD outlines.

    Unmatched SKUs are skipped (not dumped onto OTHER). SOT23 / SOT_23 / SOT-23
    share ``normalize_package_key`` so they become one alias row.
    """
    store.clear_other_noise()
    tokens = _unique_tokens(
        list(part_groups) + list(yamaha_names) + list(extra_tokens)
    )
    mapped_ids: set[str] = set()
    skipped = 0
    outlines = 0
    gmap = dict(group_to_profile or {})
    for raw in tokens:
        compact = "".join(ch for ch in raw if ch.isalnum())
        if compact.isdigit() and len(compact) >= 6:
            skipped += 1
            continue
        hit = parse_package(raw)
        vid = hit.vspd_id
        if not vid or vid == "OTHER":
            skipped += 1
            continue
        store.add_alias(raw, vid, "hanwha", commit=False)
        store.add_link("partgroup", raw, vid, commit=False)
        mapped_ids.add(vid)
        if cache_dir and not store.has_outline(vid):
            prof = gmap.get(raw) or ""
            if not prof:
                for g, p in gmap.items():
                    if parse_package(g).vspd_id == vid:
                        prof = p
                        break
            if prof:
                try:
                    from machine_library.hanwha_sqlite_cache import (
                        build_outline_from_sqlite,
                    )

                    result = build_outline_from_sqlite(cache_dir, prof)
                except (OSError, ValueError, TypeError):
                    result = None
                if (
                    result is not None
                    and not result.error
                    and result.outline.source not in ("none", "")
                    and (result.outline.lines or result.outline.pads)
                ):
                    store.set_outline_json(vid, outline_to_json(result.outline))
                    outlines += 1
    store.commit()
    return MachineImportStats(
        groups_seen=len(tokens),
        mapped=len(mapped_ids),
        skipped=skipped,
        outlines=outlines,
    )


def import_machine_names(
    store: PackageStore,
    names: Iterable[str],
    *,
    kind: str,
    standard: str,
) -> int:
    """Legacy: import strings that parse to a known package (skips OTHER)."""
    stats = import_machine_packages(store, part_groups=names)
    _ = (kind, standard)
    return stats.mapped
