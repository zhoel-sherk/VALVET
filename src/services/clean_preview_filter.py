"""Filter Clean BOM preview rows (Qt-free)."""

from __future__ import annotations

import pandas as pd


def filter_clean_preview(
    df: pd.DataFrame,
    *,
    type_value: str = "",
    source_value: str = "",
    regex_only: bool = False,
    other_only: bool = False,
) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    work = df
    if other_only and "Type" in work.columns:
        work = work[work["Type"].astype(str).str.upper() == "OTHER"]
    if regex_only and "Source" in work.columns:
        work = work[work["Source"].astype(str).str.casefold() == "regex"]
    tv = (type_value or "").strip()
    if tv and tv.casefold() not in {"", "all"} and "Type" in work.columns:
        work = work[work["Type"].astype(str).str.upper() == tv.upper()]
    sv = (source_value or "").strip()
    if sv and sv.casefold() not in {"", "all"} and "Source" in work.columns:
        work = work[work["Source"].astype(str).str.casefold() == sv.casefold()]
    return work.copy()


def unresolved_preview_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Rows still OTHER or without a machine-library match."""
    if df is None or df.empty:
        return df
    typ = df["Type"].astype(str).str.upper() if "Type" in df.columns else None
    src = df["Source"].astype(str) if "Source" in df.columns else None
    match = df["Match"].astype(str).str.casefold() if "Match" in df.columns else None
    mask = pd.Series(False, index=df.index)
    if typ is not None:
        mask = mask | (typ == "OTHER")
    if match is not None:
        mask = mask | match.isin({"none", "", "nan"})
    elif src is not None:
        mask = mask | ~src.str.casefold().str.contains("hanwha", na=False)
    cols = [
        c for c in ("Original", "Cleaned", "Type", "Source", "Match") if c in df.columns
    ]
    return df.loc[mask, cols].copy() if cols else df.loc[mask].copy()
