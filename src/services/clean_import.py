"""Extract BOM comments for Clean BOM preview (no Qt).

Replaces ``MainWindow._clean_import()``.
"""

from __future__ import annotations

import pandas as pd

import logger
from parsers.bom_text_utils import (
    DEFAULT_DOUBLE_COMMENT_JOIN,
    merge_clean_comment_cell_parts,
)


def import_bom_comments_for_clean(
    bom_df: pd.DataFrame,
    comment_column_names: list[str],
    active_row_indices: list[int],
    *,
    double_comment_enabled: bool = True,
    double_comment_separator: str = " ",
) -> list[str]:
    """Join every PN name / PN join column in table order when there are two or more.

    ``double_comment_enabled`` is ignored (kept for call-site compatibility).

    Logs a warning when ``double_comment_separator`` appears inside any comment
    cell, because joining with such a separator can create false splits that
    ``split_joined_clean_comment`` cannot recover. This makes separators like
    ``"2"`` (which occurs inside values such as ``"25V"``) visible to the user
    instead of silently corrupting the result.
    """
    del double_comment_enabled
    if not comment_column_names:
        return []
    comment_cols = list(comment_column_names)
    for col in comment_cols:
        if col not in bom_df.columns:
            return []

    sep = double_comment_separator or DEFAULT_DOUBLE_COMMENT_JOIN
    for col in comment_cols:
        for i in active_row_indices:
            cell = str(bom_df.iloc[i][col])
            if sep in cell:
                preview = cell[:40] + "..." if len(cell) > 40 else cell
                logger.warning(
                    "Clean BOM: separator %r occurs inside comment cell "
                    "(row %s, column %r, value %r). Joined cells may split "
                    "incorrectly; change the separator in Clean options if the "
                    "result looks wrong.",
                    sep,
                    i,
                    col,
                    preview,
                )

    if len(comment_cols) >= 2:
        return [
            merge_clean_comment_cell_parts(
                [bom_df.iloc[i][c] for c in comment_cols],
                double_comment_separator,
            )
            for i in active_row_indices
        ]

    # Single column: route through the same helper so None / float NaN / "nan" are
    # skipped instead of reaching the parser as the literal string "nan".
    primary_col = comment_cols[0]
    return [
        merge_clean_comment_cell_parts(
            [bom_df.iloc[i][primary_col]],
            double_comment_separator,
        )
        for i in active_row_indices
    ]
