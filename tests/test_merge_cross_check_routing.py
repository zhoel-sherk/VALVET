"""Merge Cross-check Return tab routing (no widgets)."""

from __future__ import annotations

import pandas as pd
import pytest

pytest.importorskip("PySide6")

from ui.merge_tab import MergeTabMixin


def test_cross_check_return_tab_key_bom_pnp_and_mixed() -> None:
    mixin = MergeTabMixin.__new__(MergeTabMixin)
    mixin._cc_full_df = pd.DataFrame({"IssueType": ["missing_in_pnp"]})
    assert mixin._cross_check_return_tab_key() == "bom"

    mixin._cc_full_df = pd.DataFrame({"IssueType": ["missing_in_bom"]})
    assert mixin._cross_check_return_tab_key() == "pnp"

    mixin._cc_full_df = pd.DataFrame(
        {"IssueType": ["missing_in_bom", "duplicate_coord"]}
    )
    assert mixin._cross_check_return_tab_key() == "pnp"

    mixin._cc_full_df = pd.DataFrame(
        {"IssueType": ["missing_in_pnp", "missing_in_bom"]}
    )
    assert mixin._cross_check_return_tab_key() is None

    mixin._cc_full_df = pd.DataFrame()
    assert mixin._cross_check_return_tab_key() is None
