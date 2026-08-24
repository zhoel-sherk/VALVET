"""Extract BOM comments for Clean BOM preview (no Qt).

Replaces ``MainWindow._clean_import()``.
"""

from __future__ import annotations

import pandas as pd

from parsers.bom_text_utils import merge_clean_comment_cell_parts


def import_bom_comments_for_clean(
    bom_df: pd.DataFrame,
    comment_column_names: list[str],
    active_row_indices: list[int],
    *,
    double_comment_enabled: bool = False,
    double_comment_separator: str = " ",
) -> list[str]:
    if not comment_column_names:
        return []
    if double_comment_enabled:
        if len(comment_column_names) < 2:
            return []
        comment_cols = comment_column_names
    else:
        comment_cols = [comment_column_names[0]]

    for col in comment_cols:
        if col not in bom_df.columns:
            return []

    if double_comment_enabled and len(comment_cols) > 1:
        comments = [
            merge_clean_comment_cell_parts(
                [bom_df.iloc[i][c] for c in comment_cols],
                double_comment_separator,
            )
            for i in active_row_indices
        ]
    else:
        primary_col = comment_cols[0]
        comments = [
            str(bom_df.iloc[i][primary_col]) for i in active_row_indices
        ]

    return comments
