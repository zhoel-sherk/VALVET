"""Apply clean preview rows back to BOM DataFrame (no Qt).

Replaces ``MainWindow._clean_apply()``.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

import logger

# ``clean_preview`` rows: (#, original, cleaned, type_tag, source[, arbiter, win%]).
_PREVIEW_MIN_LEN = 5

_CLEAN_OUTPUT_COLUMN = "comment"


def _preview_row_fields(row: tuple[Any, ...] | list[Any]) -> tuple[str, str, str]:
    if len(row) < _PREVIEW_MIN_LEN:
        return "", "", ""
    cleaned = str(row[2] if len(row) > 2 else "")
    typ = str(row[3] if len(row) > 3 else "")
    source = str(row[4] if len(row) > 4 else "")
    return cleaned, typ, source


def _resolve_clean_target_column(
    df: pd.DataFrame, source_column: str, *, replace_source: bool
) -> str:
    # Not replace_source: every path lands on the single output column, so the
    # `df.columns` probe was dead - the caller creates the column when missing.
    del df
    if replace_source:
        return source_column
    return _CLEAN_OUTPUT_COLUMN


def apply_clean_preview_to_bom(
    bom_df: pd.DataFrame,
    preview_rows: list[tuple],
    source_indices: list[int],
    source_column: str,
    *,
    replace_source: bool = False,
) -> pd.DataFrame:
    df = bom_df.copy()
    target_col = _resolve_clean_target_column(
        df, source_column, replace_source=replace_source
    )
    if not replace_source and target_col not in df.columns:
        df[target_col] = ""
    if not replace_source:
        for meta_col in ("clean_type", "clean_part_code", "clean_vendor"):
            if meta_col not in df.columns:
                df[meta_col] = ""

    # Rows beyond len(source_indices) fall back to positional df_i = preview_i,
    # which silently writes into the wrong row. Say so instead.
    if len(source_indices) != len(preview_rows):
        logger.warning(
            "Clean apply: %d preview rows vs %d source indices - the extra "
            "rows fall back to positional matching and may hit the wrong row",
            len(preview_rows),
            len(source_indices),
        )

    for preview_i, row in enumerate(preview_rows):
        if preview_i < len(source_indices):
            df_i = source_indices[preview_i]
        else:
            df_i = preview_i
        if df_i < 0 or df_i >= len(df):
            logger.warning(
                "Clean apply: preview row %d maps to BOM row %s (out of range for "
                "%d rows) - skipped",
                preview_i,
                df_i,
                len(df),
            )
            continue
        cleaned, typ, source = _preview_row_fields(row)
        part_code = "RES" if typ == "RESISTOR" else "IND" if typ == "INDUCTOR" else typ
        # df.index[df_i] is a positional lookup: hoisting it out of the column
        # writes keeps the loop O(n) instead of O(n^2) on long BOMs.
        label = df.index[df_i]
        df.at[label, target_col] = cleaned
        if not replace_source:
            df.at[label, "clean_type"] = typ
            df.at[label, "clean_part_code"] = part_code
            df.at[label, "clean_vendor"] = source

    return df
