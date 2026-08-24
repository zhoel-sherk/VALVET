"""Serialize / deserialize BOM path ↔ PnP identity session edges (no Qt)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def session_links_to_pairs(bom_to_pnp: dict[str, set[str]]) -> list[dict[str, str]]:
    pairs: list[dict[str, str]] = []
    for bk, pids in bom_to_pnp.items():
        for pid in pids:
            pairs.append({"bom": bk, "pnp": pid})
    return pairs


def apply_session_links_payload(
    raw: Any,
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Return fresh (bom_to_pnp, pnp_to_bom) defaultdicts from profile JSON list."""
    bom_to_pnp: dict[str, set[str]] = defaultdict(set)
    pnp_to_bom: dict[str, set[str]] = defaultdict(set)
    if not isinstance(raw, list):
        return bom_to_pnp, pnp_to_bom
    for item in raw:
        if not isinstance(item, dict):
            continue
        bk = str(item.get("bom", "") or "")
        pid = str(item.get("pnp", "") or "")
        if bk and pid:
            bom_to_pnp[bk].add(pid)
            pnp_to_bom[pid].add(bk)
    return bom_to_pnp, pnp_to_bom
