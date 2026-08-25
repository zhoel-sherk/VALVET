"""Join PARTGROUP_Map names onto a PART/PROFILE frame (Qt-free)."""

from __future__ import annotations

import pandas as pd


def join_part_group_names(
    parts: pd.DataFrame, group_map: pd.DataFrame
) -> pd.DataFrame:
    """Left-join ``UPDPARTGROUPNAME`` on ``UPDPARTGROUPID`` (id may be int or str)."""
    out = parts.copy()
    if out.empty or "UPDPARTGROUPID" not in out.columns:
        if "UPDPARTGROUPNAME" not in out.columns:
            out["UPDPARTGROUPNAME"] = pd.NA
        return out
    if (
        group_map is None
        or group_map.empty
        or "UPDPARTGROUPID" not in group_map.columns
        or "UPDPARTGROUPNAME" not in group_map.columns
    ):
        if "UPDPARTGROUPNAME" not in out.columns:
            out["UPDPARTGROUPNAME"] = pd.NA
        return out
    g = group_map[["UPDPARTGROUPID", "UPDPARTGROUPNAME"]].drop_duplicates(
        subset=["UPDPARTGROUPID"], keep="first"
    )
    left = out.copy()
    left["_gid"] = pd.to_numeric(left["UPDPARTGROUPID"], errors="coerce")
    g = g.copy()
    g["_gid"] = pd.to_numeric(g["UPDPARTGROUPID"], errors="coerce")
    g = g.drop(columns=["UPDPARTGROUPID"])
    if "UPDPARTGROUPNAME" in left.columns:
        left = left.drop(columns=["UPDPARTGROUPNAME"])
    merged = left.merge(g, on="_gid", how="left").drop(columns=["_gid"])
    return merged
