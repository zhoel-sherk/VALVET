"""Clean BOM: independent Original cells and explicit fragment combination."""

from __future__ import annotations

import pandas as pd

from clean_component import clean_preview_inputs
from clean_types import CleanConfig
from cli.pipeline import clean_comments
from cli.session import CliSession
from services.clean_import import (
    import_bom_comment_inputs,
    import_bom_comments_for_clean,
)


def test_single_original_ignores_the_legacy_join_separator() -> None:
    rows = clean_preview_inputs(
        [("RES 0402 10 OHM +/-1% RoHS - Y01",)],
        CleanConfig(double_comment_separator="0"),
    )
    assert rows[0]["Cleaned"] == "0402_10R_1%"
    assert rows[0]["Type"] == "RESISTOR"
    assert rows[0]["input_index"] == 0


def test_arbiter_uses_the_leftmost_original_on_equal_scores() -> None:
    rows = clean_preview_inputs(
        [("RES 0402 10K OHM +/-1%", "RES 0603 10K OHM +/-1%")],
        CleanConfig(regex_master_enabled=True),
    )
    assert rows[0]["Cleaned"] == "0402_10K_1%"
    assert rows[0]["Win%"] == "90"
    assert rows[0]["input_index"] == 0


def test_arbiter_can_choose_a_vendor_pn_from_original_two() -> None:
    rows = clean_preview_inputs(
        [("RES 0402 10K OHM +/-1%", "RC0402JR-0710KL")],
        CleanConfig(regex_master_enabled=True),
    )
    assert rows[0]["Cleaned"] == "0402_10K_5%"
    assert rows[0]["Source"] == "pn"
    assert rows[0]["input_index"] == 1


def test_non_arbiter_skips_a_prefix_only_result() -> None:
    rows = clean_preview_inputs([("RES", "RES 0402 10K OHM +/-1%")], CleanConfig())
    assert rows[0]["Cleaned"] == "0402_10K_1%"
    assert rows[0]["input_index"] == 1


def test_combine_columns_parses_fragments_as_one_component() -> None:
    rows = clean_preview_inputs(
        [("R0402", "0.1uF", "X5R 10V")],
        CleanConfig(combine_input_columns=True),
    )
    assert rows[0]["Cleaned"] == "0402_0.1uF_10V_X5R"
    assert rows[0]["combined"] is True


def test_import_preserves_original_positions_and_skips_nan() -> None:
    bom = pd.DataFrame(
        {
            "description": ["RES 0402 10K OHM", float("nan")],
            "mpn": [None, "RC0402JR-0710KL"],
        }
    )
    rows = import_bom_comment_inputs(bom, ["description", "mpn"], [0, 1])
    assert rows == [("RES 0402 10K OHM", ""), ("", "RC0402JR-0710KL")]


def test_single_column_legacy_import_does_not_warn_about_separator(caplog) -> None:
    bom = pd.DataFrame({"description": ["RES 0402 10 OHM +/-1%"]})
    assert import_bom_comments_for_clean(
        bom, ["description"], [0], double_comment_separator="0"
    ) == ["RES 0402 10 OHM +/-1%"]
    assert not [rec for rec in caplog.records if "separator" in rec.message]


def test_cli_uses_the_same_multi_original_winner() -> None:
    session = CliSession(bom_mappings={"Comment": "description", "PnJoin": "mpn"})
    session.bom_df = pd.DataFrame(
        {
            "description": ["RES 0402 10K OHM +/-1%"],
            "mpn": ["RC0402JR-0710KL"],
        }
    )
    preview = clean_comments(session, config=CleanConfig(regex_master_enabled=True))
    assert preview[0]["Cleaned"] == "0402_10K_5%"
    assert preview[0]["input_index"] == 1


def test_cli_can_combine_fragment_columns() -> None:
    session = CliSession(bom_mappings={"Comment": "description", "PnJoin": "details"})
    session.bom_df = pd.DataFrame(
        {"description": ["R0402"], "details": ["0.1uF X5R 10V"]}
    )
    preview = clean_comments(session, config=CleanConfig(combine_input_columns=True))
    assert preview[0]["Cleaned"] == "0402_0.1uF_10V_X5R"


def test_empty_multi_input_row_has_no_winner() -> None:
    rows = clean_preview_inputs([("", None)], CleanConfig())
    assert rows[0]["Cleaned"] == ""
    assert rows[0]["Type"] == "OTHER"
    assert rows[0]["input_index"] is None
