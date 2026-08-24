"""Find and replace logic for pandas DataFrames (no Qt dependency)."""

from __future__ import annotations

import re

import pandas as pd


def find_and_replace(
    df: pd.DataFrame,
    needle: str,
    replacement: str,
    indexes: list[tuple[int, int]],
    *,
    match_case: bool = False,
    whole_cell: bool = False,
) -> tuple[pd.DataFrame, int]:
    """
    Replace text in a DataFrame at the given cell indexes.

    Args:
        df: Source DataFrame.
        needle: Text to find.
        replacement: Text to replace with.
        indexes: List of ``(row, column)`` tuples to consider.
        match_case: When False, case-insensitive comparison.
        whole_cell: When True, require exact cell match (not substring).

    Returns:
        ``(new_df, changed_count)`` — a new copy with replacements applied.
    """
    if not needle:
        return df.copy(), 0

    changed = 0
    new_df = df.copy()
    cmp_needle = needle if match_case else needle.lower()

    for row, col in indexes:
        if row >= len(new_df) or col >= len(new_df.columns):
            continue
        value = new_df.iat[row, col]
        text = "" if pd.isna(value) else str(value)
        cmp_text = text if match_case else text.lower()

        if whole_cell:
            if cmp_text != cmp_needle:
                continue
            out = replacement
        else:
            if cmp_needle not in cmp_text:
                continue
            if match_case:
                out = text.replace(needle, replacement)
            else:
                out = re.sub(re.escape(needle), replacement, text, flags=re.IGNORECASE)

        if out != text:
            new_df.iat[row, col] = out
            changed += 1

    return new_df, changed
