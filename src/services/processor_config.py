"""Build ``SMTDataProcessor`` from plain configuration values (no Qt).

Replaces ``MainWindow._configure_processor_from_ui()``.
"""

from __future__ import annotations

from typing import Callable

import pandas as pd

from smt_processor import (
    SMTDataProcessor,
    ColumnConfig,
    ProcessorConfig,
)

HIDDEN_TABLE_HAS_HEADER_ROW = False


def build_processor_config(
    bom_df: pd.DataFrame,
    pnp_df: pd.DataFrame,
    bom_mappings: dict[str, str],
    pnp_mappings: dict[str, str],
    *,
    pnp_xy_are_mils: bool = False,
    overlap_min_mm: float = 3.0,
    check_overlap: bool = False,
    progress_callback: Callable[[str, str], None] | None = None,
) -> SMTDataProcessor:
    bom_ref = bom_mappings.get("REF")
    bom_comment = bom_mappings.get("Comment")
    if not bom_ref:
        bom_ref = list(bom_df.columns)[0]
    bom_comment_col = bom_comment if bom_comment else "_skip_"

    pnp_ref = pnp_mappings.get("REF")
    if not pnp_ref:
        for col in pnp_df.columns:
            if "DESIGNATOR" in str(col).upper():
                pnp_ref = col
                break
    if not pnp_ref:
        pnp_ref = list(pnp_df.columns)[0]

    pnp_foot = pnp_mappings.get("Footprint")
    if not pnp_foot:
        for col in pnp_df.columns:
            if "FOOTPRINT" in str(col).upper():
                pnp_foot = col
                break

    pnp_x = pnp_mappings.get("X")
    pnp_y = pnp_mappings.get("Y")
    pnp_rot = pnp_mappings.get("Rotation")
    pnp_layer = pnp_mappings.get("Layer")
    pnp_val = pnp_mappings.get("Comment") or pnp_mappings.get("Value")
    pnp_comment_col = pnp_val if pnp_val else "_skip_"

    bom_cfg = ColumnConfig(
        designator=str(bom_ref),
        comment=str(bom_comment_col),
        has_header=HIDDEN_TABLE_HAS_HEADER_ROW,
    )
    pnp_cfg = ColumnConfig(
        designator=str(pnp_ref),
        comment=str(pnp_comment_col),
        footprint=str(pnp_foot) if pnp_foot else "_skip_",
        coord_x=str(pnp_x) if pnp_x else "_skip_",
        coord_y=str(pnp_y) if pnp_y else "_skip_",
        rotation=str(pnp_rot) if pnp_rot else "_skip_",
        layer=str(pnp_layer) if pnp_layer else "_skip_",
        has_header=HIDDEN_TABLE_HAS_HEADER_ROW,
    )

    proc = SMTDataProcessor(
        ProcessorConfig(
            overlap_xy_are_mm=not pnp_xy_are_mils,
            min_distance_mm=overlap_min_mm,
            check_overlap=check_overlap,
            progress_log=progress_callback,
        )
    )
    proc.set_dataframes(bom_df, pnp_df, bom_cfg, pnp_cfg)
    return proc
