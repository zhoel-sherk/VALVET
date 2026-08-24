"""Read PnP and BOM files from disk (no Qt).

Replaces ``MainWindow._read_pnp_dataframe_from_disk()`` and core
load/orchestration helpers for ``_load_bom()`` / ``_load_pnp()``.
"""

from __future__ import annotations

import pandas as pd

from smt_processor import read_file, read_pnp_whitespace


def read_pnp_dataframe(
    path: str,
    separator: str,
    first_row: int,
    last_row: int,
) -> pd.DataFrame:
    if separator == "spaces":
        return read_pnp_whitespace(path, first_row=first_row, last_row=last_row)
    return read_file(
        path,
        first_row=first_row,
        last_row=last_row,
        separator=separator,
        column_headers_from_file=False,
    )
