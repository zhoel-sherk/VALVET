"""Machine lib preview: four display columns + PARTGROUP Type join (Qt-free)."""

from __future__ import annotations

import pandas as pd

from hanwha_mdb_edit.core.part_group import join_part_group_names

MACHINE_LIB_PREVIEW_COLUMNS: tuple[str, ...] = (
    "PARTNAME",
    "PARTDESC",
    "CONFIDENCE_LEVEL",
    "UPDPARTGROUPNAME",
)


def attach_part_group_type(
    parts: pd.DataFrame,
    profile: pd.DataFrame,
    group_map: pd.DataFrame,
) -> pd.DataFrame:
    """Join ``UPDPARTGROUPNAME`` via PART_Det.PROFILENAME → PROFILE_Det → PARTGROUP_Map."""
    out = parts.copy()
    if (
        not out.empty
        and "PROFILENAME" in out.columns
        and profile is not None
        and not profile.empty
        and "PROFILENAME" in profile.columns
        and "UPDPARTGROUPID" in profile.columns
    ):
        prof = profile.drop_duplicates(subset=["PROFILENAME"], keep="first")
        prof = prof[["PROFILENAME", "UPDPARTGROUPID"]]
        if "UPDPARTGROUPID" in out.columns:
            out = out.drop(columns=["UPDPARTGROUPID"])
        out = out.merge(prof, on="PROFILENAME", how="left")
    return join_part_group_names(out, group_map)


def machine_lib_preview_frame(df: pd.DataFrame) -> pd.DataFrame:
    """View for the Machine lib table: Part name, Description, Level, Type only."""
    out = pd.DataFrame() if df is None else df.copy()
    for col in MACHINE_LIB_PREVIEW_COLUMNS:
        if col not in out.columns:
            out[col] = pd.NA
    return out.loc[:, list(MACHINE_LIB_PREVIEW_COLUMNS)]
