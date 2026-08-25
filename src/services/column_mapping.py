"""Qt-free BOM/PnP column role heuristics (REF vs PN/Comment)."""

from __future__ import annotations

from collections.abc import Sequence

_EXCLUSIVE_ROLES = (
    "REF",
    "Comment",
    "Value",
    "Footprint",
    "X",
    "Y",
    "Rotation",
    "Layer",
)

_PN_TOKENS = ("COMMENT", "VALUE", "PART", "PN")
BOM_EXCLUSIVE_ROLES = ("REF", "Comment")
PN_CLEAN_ROLES = ("Comment", "PnJoin")


def _compact(name: str) -> str:
    return (
        str(name)
        .strip()
        .upper()
        .replace(" ", "")
        .replace("_", "")
        .replace("-", "")
    )


def is_designator_header(name: str) -> bool:
    """True for Designator / Ref / RefDes — not PREFERRED or comment_orig."""
    compact = _compact(name)
    if compact in {"REF", "REFS", "REFERENCE", "REFERENCES"}:
        return True
    u = str(name).strip().upper()
    if "DESIGNATOR" in u:
        return True
    if "REFDES" in compact:
        return True
    return False


def looks_like_pn_header(name: str) -> bool:
    """Comment / value / part-number style header (not a designator)."""
    if is_designator_header(name):
        return False
    u = str(name).strip().upper()
    return any(tok in u for tok in _PN_TOKENS)


def guess_bom_role(col_name: str) -> str:
    if is_designator_header(col_name):
        return "REF"
    u = str(col_name).strip().upper()
    if "COMMENT" in u or (u == "VALUE") or u.endswith(" VALUE"):
        return "Comment"
    return "-"


def guess_pnp_role(col_name: str) -> str:
    col_name_str = str(col_name) if col_name else ""
    col_upper = col_name_str.upper()
    compact = _compact(col_name_str)
    if is_designator_header(col_name_str):
        return "REF"
    if "POS-X" in compact and "MIL" not in col_upper:
        return "X"
    if "POS-Y" in compact and "MIL" not in col_upper:
        return "Y"
    if "MID-X" in col_upper or "MID-Y" in col_upper:
        return "-"
    if (
        "FOOTPRINT" in col_upper
        or "PATTERN" in col_upper
        or "PACKAGE" in col_upper
    ):
        return "Footprint"
    if col_upper.strip() == "X" and "MIL" not in col_upper and "PAD" not in col_upper:
        return "X"
    if col_upper.strip() == "Y" and "MIL" not in col_upper and "PAD" not in col_upper:
        return "Y"
    if "CENTER-X" in col_upper and "MID" not in col_upper:
        return "X"
    if "CENTER-Y" in col_upper and "MID" not in col_upper:
        return "Y"
    if "ROTATION" in col_upper:
        return "Rotation"
    if "LAYER" in col_upper or "SIDE" in col_upper or "MIRROR" in col_upper:
        return "Layer"
    if compact == "VALUE":
        return "Comment"
    return "-"


def uniquify_roles(
    roles: Sequence[str],
    *,
    exclusive: Sequence[str] = _EXCLUSIVE_ROLES,
    last_wins: Sequence[str] = ("Comment",),
) -> list[str]:
    """Keep one exclusive role. REF is first-wins; Comment last-wins by default.

    Pass ``exclusive=("REF", "Comment")`` and ``last_wins=()`` for BOM so
    several ``PnJoin`` columns stay mapped.
    """
    last_set = set(last_wins)
    excl = set(exclusive)
    out = list(roles)
    seen_first: dict[str, int] = {}
    last_idx: dict[str, int] = {}
    for i, role in enumerate(out):
        if role not in excl:
            continue
        if role not in seen_first:
            seen_first[role] = i
        last_idx[role] = i
    keep: dict[str, int] = {}
    for role, i in seen_first.items():
        keep[role] = last_idx[role] if role in last_set else i
    for i, role in enumerate(out):
        if role in excl and keep.get(role) != i:
            out[i] = "-"
    return out


def pn_columns_in_order(
    columns: Sequence[object], roles: Sequence[str]
) -> list[str]:
    """BOM columns mapped to PN name or PN join, left-to-right."""
    out: list[str] = []
    for col, role in zip(columns, roles, strict=False):
        if role in PN_CLEAN_ROLES:
            out.append(str(col) if not isinstance(col, str) else col)
    return out


def pick_merge_pn_column(
    columns: Sequence[object], roles: Sequence[str]
) -> str | None:
    """Merge/cross-check Value: PN name, else first PN name/join column."""
    for col, role in zip(columns, roles, strict=False):
        if role == "Comment":
            return str(col)
    for col, role in zip(columns, roles, strict=False):
        if role in PN_CLEAN_ROLES:
            return str(col)
    return None


def roles_after_clean_apply(
    preserved: Sequence[str],
    columns: Sequence[str],
    *,
    comment_column: str,
) -> list[str]:
    """Keep REF and PnJoin; put PN name on ``comment_column`` only."""
    roles = list(preserved)
    while len(roles) < len(columns):
        roles.append("-")
    roles = roles[: len(columns)]
    roles = uniquify_roles(
        roles, exclusive=BOM_EXCLUSIVE_ROLES, last_wins=()
    )
    for i, _name in enumerate(roles):
        if roles[i] == "Comment":
            roles[i] = "-"
    target = str(comment_column)
    for i, name in enumerate(columns):
        if str(name) == target:
            roles[i] = "Comment"
            break
    return uniquify_roles(
        roles, exclusive=BOM_EXCLUSIVE_ROLES, last_wins=()
    )


def merge_result_pnp_roles(columns: Sequence[str]) -> list[str]:
    """Map merge output headers Ref/Value/Footprint/X/Y/Rotation/Layer."""
    by_compact = {
        "REF": "REF",
        "DESIGNATOR": "REF",
        "REFDES": "REF",
        "VALUE": "Comment",
        "FOOTPRINT": "Footprint",
        "X": "X",
        "Y": "Y",
        "ROTATION": "Rotation",
        "LAYER": "Layer",
    }
    out: list[str] = []
    for name in columns:
        out.append(by_compact.get(_compact(str(name)), guess_pnp_role(str(name))))
    return uniquify_roles(out)


def pick_ref_column(
    columns: Sequence[object], explicit: str | None = None
) -> str | None:
    cols = [str(c) for c in columns]
    if explicit:
        want = str(explicit).strip().upper()
        if want and want not in {"?", "_SKIP_", ""}:
            for c in cols:
                if c.strip().upper() == want:
                    return c
    for c in cols:
        if is_designator_header(c):
            return c
    return None


def likely_ref_mapped_to_pn(
    bom_keys: Sequence[str],
    pnp_keys: Sequence[str],
    pnp_values: Sequence[str],
) -> bool:
    """True when BOM 'designators' look like PnP part values, not refs."""
    bom = {str(k).strip().upper() for k in bom_keys if str(k).strip()}
    pnp = {str(k).strip().upper() for k in pnp_keys if str(k).strip()}
    if len(bom) < 3 or len(pnp) < 3:
        return False
    overlap = len(bom & pnp) / max(len(bom), 1)
    if overlap >= 0.15:
        return False
    vals = {str(v).strip().upper() for v in pnp_values if str(v).strip()}
    hits = sum(1 for k in bom if k in vals)
    return (hits / len(bom)) >= 0.25
