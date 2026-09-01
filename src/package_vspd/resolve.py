# SPDX-License-Identifier: MIT
"""Resolve VSPD ids for unique merge Values (store → machine → PnP → BOM)."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Literal, Mapping, Optional, Sequence

from package_vspd.parse import parse_package
from package_vspd.store import PackageStore

ResolveSource = Literal["store", "machine", "pnp", "bom", "unmatched"]

_EMPTY = frozenset({"", "nan", "none"})


@dataclass(frozen=True)
class ResolveHit:
    vspd_id: Optional[str]
    source: ResolveSource


def _cell(raw: Any) -> str:
    if raw is None:
        return ""
    try:
        if raw != raw:  # NaN
            return ""
    except Exception:
        pass
    s = str(raw).strip()
    if s.lower() in _EMPTY:
        return ""
    return s


def group_key(
    value: Any,
    footprint: Any = "",
    ref: Any = "",
) -> str:
    """Stable unique-part key: Value, else Footprint, else REF."""
    v = _cell(value)
    if v:
        return v
    fp = _cell(footprint)
    if fp:
        return f"\x1ffp:{fp}"
    r = _cell(ref).upper()
    return f"\x1fref:{r}"


def _usable_parse(text: str) -> Optional[str]:
    if not _cell(text):
        return None
    hit = parse_package(text)
    vid = (hit.vspd_id or "").strip()
    if not vid or vid.upper() == "OTHER":
        return None
    return vid


def _majority_vspd(texts: Iterable[str]) -> Optional[str]:
    counts: Counter[str] = Counter()
    for t in texts:
        vid = _usable_parse(t)
        if vid:
            counts[vid] += 1
    if not counts:
        return None
    return counts.most_common(1)[0][0]


def resolve_unique_packages(
    rows: Sequence[Mapping[str, Any]],
    *,
    store: Optional[PackageStore] = None,
    machine_lookup: Optional[Callable[[str], Optional[str]]] = None,
    bom_by_ref: Optional[Mapping[str, str]] = None,
    value_key: str = "Value",
    footprint_key: str = "Footprint",
    ref_key: str = "Ref",
) -> dict[str, ResolveHit]:
    """One hit per unique Value (or Footprint/REF fallback). Never assigns OTHER."""
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        gk = group_key(row.get(value_key), row.get(footprint_key), row.get(ref_key))
        groups[gk].append(row)

    out: dict[str, ResolveHit] = {}
    for gk, grows in groups.items():
        value = _cell(grows[0].get(value_key))
        fps = [_cell(r.get(footprint_key)) for r in grows]
        refs = [_cell(r.get(ref_key)) for r in grows]
        identity = (
            value or next((f for f in fps if f), "") or next((r for r in refs if r), "")
        )

        vid: Optional[str] = None
        source: ResolveSource = "unmatched"
        if store is not None and identity:
            vid = store.lookup_vspd(identity)
            if vid:
                source = "store"
        if vid is None and machine_lookup is not None and value:
            m = machine_lookup(value)
            if m and str(m).strip().upper() != "OTHER":
                vid = str(m).strip()
                source = "machine"
        if vid is None:
            pnp = _majority_vspd(fps)
            if pnp:
                vid = pnp
                source = "pnp"
        if vid is None:
            bom_texts: list[str] = []
            if bom_by_ref:
                for ref in refs:
                    if not ref:
                        continue
                    t = bom_by_ref.get(ref) or bom_by_ref.get(ref.upper())
                    if t:
                        bom_texts.append(t)
            if value:
                bom_texts.append(value)
            bom = _majority_vspd(bom_texts)
            if bom:
                vid = bom
                source = "bom"
        out[gk] = ResolveHit(vspd_id=vid, source=source)
    return out


def apply_hits_to_rows(
    rows: Sequence[Mapping[str, Any]],
    hits: Mapping[str, ResolveHit],
    *,
    value_key: str = "Value",
    footprint_key: str = "Footprint",
    ref_key: str = "Ref",
) -> int:
    """Write vspd_id into Footprint on mapped rows. Unmatched keep prior text."""
    n = 0
    for row in rows:
        if not hasattr(row, "__setitem__"):
            continue
        gk = group_key(row.get(value_key), row.get(footprint_key), row.get(ref_key))
        hit = hits.get(gk)
        if hit is None or not hit.vspd_id:
            continue
        row[footprint_key] = hit.vspd_id  # type: ignore[index]
        n += 1
    return n


def apply_hits_to_dataframe(
    df: Any,
    hits: Mapping[str, ResolveHit],
    *,
    value_key: str = "Value",
    footprint_key: str = "Footprint",
    ref_key: str = "Ref",
) -> int:
    n = 0
    for i in df.index:
        gk = group_key(
            df.at[i, value_key] if value_key in df.columns else "",
            df.at[i, footprint_key] if footprint_key in df.columns else "",
            df.at[i, ref_key] if ref_key in df.columns else "",
        )
        hit = hits.get(gk)
        if hit is None or not hit.vspd_id:
            continue
        df.at[i, footprint_key] = hit.vspd_id
        n += 1
    return n


def machine_lookup_from_part_rows(
    rows: Sequence[Mapping[str, Any]],
    partnames: Optional[Iterable[str]] = None,
    *,
    partname_key: str = "PARTNAME",
    partdesc_key: str = "PARTDESC",
    group_key_name: str = "UPDPARTGROUPNAME",
) -> Callable[[str], Optional[str]]:
    """Map PARTNAME → first usable parse of PARTDESC / part group."""
    allowed: Optional[set[str]] = None
    if partnames is not None:
        allowed = {str(n).strip().casefold() for n in partnames if str(n).strip()}
    index: dict[str, list[str]] = {}
    for row in rows:
        pn = _cell(row.get(partname_key))
        if not pn:
            continue
        cf = pn.casefold()
        if allowed is not None and cf not in allowed:
            continue
        texts = index.setdefault(cf, [])
        for col in (partdesc_key, group_key_name):
            t = _cell(row.get(col))
            if t and t not in texts:
                texts.append(t)

    def lookup(value: str) -> Optional[str]:
        texts = index.get(_cell(value).casefold())
        if not texts:
            return None
        return _majority_vspd(texts)

    return lookup


def count_sources(hits: Mapping[str, ResolveHit]) -> dict[str, int]:
    c = {
        "parts": len(hits),
        "store": 0,
        "machine": 0,
        "pnp": 0,
        "bom": 0,
        "unmatched": 0,
        "filled": 0,
    }
    for hit in hits.values():
        c[hit.source] = c.get(hit.source, 0) + 1
        if hit.vspd_id:
            c["filled"] += 1
    return c
