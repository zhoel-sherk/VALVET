"""Machine-library match status and optional strict export (Qt-free)."""

from __future__ import annotations

import pandas as pd


def hanwha_match_status(source: str) -> str:
    """Map Clean Source note to matched / ambiguous / none."""
    s = str(source or "").strip().casefold()
    if not s:
        return "none"
    if s == "hanwha_mdb":
        return "matched"
    if "ambiguous" in s or s.startswith("partial"):
        return "ambiguous"
    return "none"


def strict_export_blocked(preview_df: pd.DataFrame | None) -> bool:
    """True when OTHER rows lack a Hanwha match (matched)."""
    if preview_df is None or preview_df.empty:
        return False
    if "Type" not in preview_df.columns:
        return False
    other = preview_df[preview_df["Type"].astype(str).str.upper() == "OTHER"]
    if other.empty:
        return False
    if "Match" in other.columns:
        return not other["Match"].astype(str).str.casefold().eq("matched").all()
    if "Source" in other.columns:
        return not other["Source"].map(hanwha_match_status).eq("matched").all()
    return True
