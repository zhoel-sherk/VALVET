"""
Filter Hanwha PART_Det PARTNAME rows for Clean BOM / machine-library matching.

Qt-free: used by corpus CLI, pytest fixtures, and optionally Machine lib tab.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import AbstractSet, Any, Mapping, Sequence

import pandas as pd

from hanwha_mdb_edit.core.part_filters import is_standard_library_s_row
from machine_library.hanwha_mdbtools import (
    HanwhaMdbToolsError,
    load_part_det_from_mdb,
    part_det_rows_to_dataframe,
)
from parsers.constants import PACKAGE_PATTERN
from parsers.regex_api import I, fullmatch, search

HANWHA_CONFIDENCE_KNOWN_LEVELS: frozenset[int] = frozenset((0, 10, 20, 40))

_DEFAULT_MIN_PARTNAME_LEN = 5
_PACKAGE_ONLY_RE = re.compile(rf"^({PACKAGE_PATTERN})$", I)

# Chip passives in Hanwha user libs (PARTDESC / PARTNAME templates).
_CHIP_PASSIVE = (
    "0201",
    "0402",
    "0603",
    "0805",
    "1206",
    "1210",
    "1005",
    "1608",
    "2010",
    "2512",
    "3216",
)
_CHIP_PASSIVE_ALT = "|".join(_CHIP_PASSIVE)
_PASSIVE_RC_PARTDESC_RE = re.compile(
    rf"^[CR](?:{_CHIP_PASSIVE_ALT})$",
    I,
)
_PASSIVE_RC_PARTDESC_PKG_ONLY_RE = re.compile(
    rf"^(?:{_CHIP_PASSIVE_ALT})$",
    I,
)
# Skip Hanwha matching for lines that look like ESD/TVS/NTC etc. in 0402 footprint.
_PASSIVE_RC_PARTNAME_EXCEPTION_RE = re.compile(
    r"(?:ESDA|TVS|NTC|NCP\d|NTCG|THERMISTOR|POLYSWITCH|FUSE|BEAD|BLM\d|LQG\d|"
    r"FERRITE|INDUCTOR|CHOKE|CRYSTAL|XTAL|OSCILLATOR|CONNECTOR|USB|HDMI|LED)",
    I,
)
_PKG_FIRST_CAP_RE = re.compile(
    rf"^(?:{_CHIP_PASSIVE_ALT})[_-].*"
    r"(?:\d+(?:\.\d+)?\s*[uUnNpP][fF]|\d+\s*[pP][fF]|X5R|X7R|Y5V|COG|C0G|NP0|NPO)",
    I,
)
_PKG_FIRST_RES_RE = re.compile(
    rf"^(?:{_CHIP_PASSIVE_ALT})[_-].*"
    r"(?:\d+(?:\.\d+)?\s*[KMR](?:OHM)?|\d+\s*OHM|_\d+%|\d+%\s*$|\d+(?:\.\d+)?R\b|4P2R)",
    I,
)
_INFERIT_CAP_PREFIX_RE = re.compile(rf"^C(?:{_CHIP_PASSIVE_ALT})[_-]", I)
_INFERIT_RES_PREFIX_RE = re.compile(rf"^R(?:{_CHIP_PASSIVE_ALT})[_-]", I)


def default_upd_mdb_paths(boomer_root: Path | None = None) -> list[Path]:
    """Search order: examples/UPD.MDB, sibling UPD.MDB (legacy)."""
    root = boomer_root or Path(__file__).resolve().parents[2]
    return [
        root / "examples" / "UPD.MDB",
        root.parent / "UPD.MDB",
    ]


def resolve_upd_mdb_path(
    explicit: str | Path | None = None,
    *,
    boomer_root: Path | None = None,
) -> Path:
    if explicit is not None:
        p = Path(explicit)
        if not p.is_file():
            raise HanwhaMdbToolsError(f"Not a file: {p}")
        return p
    for cand in default_upd_mdb_paths(boomer_root):
        if cand.is_file():
            return cand
    raise HanwhaMdbToolsError(
        "UPD.MDB not found; expected examples/UPD.MDB or sibling UPD.MDB"
    )


def load_part_det_dataframe(mdb_path: str | Path) -> pd.DataFrame:
    rows = load_part_det_from_mdb(mdb_path)
    return part_det_rows_to_dataframe(rows)


def _confidence_level(raw: object) -> int:
    try:
        if raw is None or (isinstance(raw, float) and pd.isna(raw)):
            return 0
        return int(raw)
    except (TypeError, ValueError):
        return 0


def filter_by_confidence_levels(
    df: pd.DataFrame,
    levels: AbstractSet[int],
    *,
    include_unknown_levels: bool = True,
) -> pd.DataFrame:
    """Keep rows whose CONFIDENCE_LEVEL is in ``levels`` (unknown tiers optional)."""
    if df is None or df.empty or "CONFIDENCE_LEVEL" not in df.columns:
        return df
    enabled = {int(x) for x in levels}

    def _ok(raw: object) -> bool:
        v = _confidence_level(raw)
        if v not in HANWHA_CONFIDENCE_KNOWN_LEVELS:
            return include_unknown_levels
        return v in enabled

    mask = df["CONFIDENCE_LEVEL"].map(_ok)
    return df.loc[mask].copy()


def is_junk_hanwha_partname(
    partname: Any,
    partdesc: Any = None,
    *,
    min_len: int = _DEFAULT_MIN_PARTNAME_LEN,
) -> bool:
    """
    True if PARTNAME should not participate in Hanwha Clean matching.

    Filters package-only tokens (``0603``), template rows (``_NewC0201``),
    standard-library «S» rows, trailing underscore junk (``0402__``), etc.
    """
    pn = (
        ""
        if partname is None or (isinstance(partname, float) and pd.isna(partname))
        else str(partname).strip()
    )
    if not pn:
        return True
    if is_standard_library_s_row(pn, partdesc):
        return True
    if pn.startswith("_New"):
        return True
    if "__" in pn:
        return True
    if len(pn) <= 6 and pn.endswith("_"):
        return True
    if _PACKAGE_ONLY_RE.fullmatch(pn):
        return True
    if len(pn) < min_len:
        return True
    if not search(r"[A-Za-z]", pn):
        return True
    return False


def is_passive_rc_hanwha_partname(
    partname: Any,
    partdesc: Any = None,
) -> bool:
    """
    True if the row is a chip resistor or MLCC-style capacitor.

    Clean BOM already parses RES/CAP without MDB; Hanwha snapshots for corpus/GUI
    should focus on ICs, connectors, and other machine-library-specific names.
    """
    pn = (
        ""
        if partname is None or (isinstance(partname, float) and pd.isna(partname))
        else str(partname).strip()
    )
    if not pn or _PASSIVE_RC_PARTNAME_EXCEPTION_RE.search(pn):
        return False
    pd_ = (
        ""
        if partdesc is None or (isinstance(partdesc, float) and pd.isna(partdesc))
        else str(partdesc).strip()
    )
    if pd_ and _PASSIVE_RC_PARTDESC_RE.fullmatch(pd_):
        return True
    if _INFERIT_CAP_PREFIX_RE.match(pn) or _INFERIT_RES_PREFIX_RE.match(pn):
        return True
    if _PKG_FIRST_CAP_RE.match(pn):
        return True
    if _PKG_FIRST_RES_RE.match(pn) and not search(
        r"\d+(?:\.\d+)?\s*[uUnNpP][fF]|\d+\s*[pP][fF]|X5R|X7R|COG|NP0",
        pn,
        I,
    ):
        return True
    if pd_ and _PASSIVE_RC_PARTDESC_PKG_ONLY_RE.fullmatch(pd_):
        if _PKG_FIRST_CAP_RE.match(pn) or _PKG_FIRST_RES_RE.match(pn):
            return True
    return False


def partnames_for_clean(
    df: pd.DataFrame,
    *,
    enabled_confidence_levels: AbstractSet[int] | None = None,
    min_partname_len: int = _DEFAULT_MIN_PARTNAME_LEN,
    exclude_passive_rc: bool = True,
) -> set[str]:
    """PARTNAME set after confidence filter and junk rejection."""
    if df is None or df.empty or "PARTNAME" not in df.columns:
        return set()
    work = df
    if enabled_confidence_levels is not None:
        work = filter_by_confidence_levels(work, enabled_confidence_levels)
    out: set[str] = set()
    has_desc = "PARTDESC" in work.columns
    for _, row in work.iterrows():
        pn = row["PARTNAME"]
        pd_ = row["PARTDESC"] if has_desc else None
        if is_junk_hanwha_partname(pn, pd_, min_len=min_partname_len):
            continue
        if exclude_passive_rc and is_passive_rc_hanwha_partname(pn, pd_):
            continue
        t = str(pn).strip()
        if t:
            out.add(t)
    return out


def export_partnames_snapshot(
    mdb_path: str | Path,
    out_path: str | Path,
    *,
    confidence_levels: AbstractSet[int] | frozenset[int] = frozenset({40}),
    min_partname_len: int = _DEFAULT_MIN_PARTNAME_LEN,
    exclude_passive_rc: bool = True,
    dump_rejects_path: str | Path | None = None,
) -> Mapping[str, Any]:
    """
    Load MDB, filter, write JSON snapshot for CI / clean corpus profile.

    Returns metadata dict (also written under ``meta`` in JSON).
    """
    mdb = Path(mdb_path)
    df_all = load_part_det_dataframe(mdb)
    total = len(df_all)
    df_conf = filter_by_confidence_levels(df_all, set(confidence_levels))
    after_conf = len(df_conf)

    accepted = partnames_for_clean(
        df_conf,
        enabled_confidence_levels=None,
        min_partname_len=min_partname_len,
        exclude_passive_rc=exclude_passive_rc,
    )
    rejects: list[dict[str, str]] = []
    has_desc = "PARTDESC" in df_conf.columns
    passive_rc_rejected = 0
    for _, row in df_conf.iterrows():
        pn = str(row["PARTNAME"]).strip()
        if not pn or pn in accepted:
            continue
        pd_ = row["PARTDESC"] if has_desc else None
        if (
            exclude_passive_rc
            and not is_junk_hanwha_partname(pn, pd_, min_len=min_partname_len)
            and is_passive_rc_hanwha_partname(pn, pd_)
        ):
            passive_rc_rejected += 1
            rejects.append({"partname": pn, "reason": "passive_rc"})
            continue
        reason = _junk_reason(row["PARTNAME"], pd_, min_partname_len)
        rejects.append({"partname": pn, "reason": reason})

    if dump_rejects_path is not None:
        rp = Path(dump_rejects_path)
        rp.parent.mkdir(parents=True, exist_ok=True)
        lines = ["partname\treason"] + [f"{r['partname']}\t{r['reason']}" for r in rejects]
        rp.write_text("\n".join(lines) + "\n", encoding="utf-8")

    meta = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_mdb": str(mdb.resolve()),
        "confidence_levels": sorted(int(x) for x in confidence_levels),
        "min_partname_len": min_partname_len,
        "exclude_passive_rc": exclude_passive_rc,
        "counts": {
            "total_rows": total,
            "after_confidence": after_conf,
            "accepted_partnames": len(accepted),
            "rejected_passive_rc": passive_rc_rejected,
            "rejected_junk": len(rejects) - passive_rc_rejected,
            "rejected_total": len(rejects),
        },
    }
    payload = {
        "meta": meta,
        "partnames": sorted(accepted),
    }
    op = Path(out_path)
    op.parent.mkdir(parents=True, exist_ok=True)
    op.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return meta


def load_partnames_snapshot(path: str | Path) -> set[str]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    names = data.get("partnames") or []
    return {str(x).strip() for x in names if str(x).strip()}


def _junk_reason(partname: Any, partdesc: Any, min_len: int) -> str:
    pn = str(partname).strip() if partname is not None else ""
    if not pn:
        return "empty"
    if is_standard_library_s_row(pn, partdesc):
        return "standard_library_s"
    if pn.startswith("_New"):
        return "template_new"
    if "__" in pn:
        return "double_underscore"
    if len(pn) <= 6 and pn.endswith("_"):
        return "trailing_underscore_short"
    if _PACKAGE_ONLY_RE.fullmatch(pn):
        return "package_only"
    if len(pn) < min_len:
        return "too_short"
    if not search(r"[A-Za-z]", pn):
        return "no_letters"
    return "unknown"
