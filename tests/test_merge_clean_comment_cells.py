"""Double Comment import: joining BOM cells with configurable separator."""

from __future__ import annotations

from parsers.bom_text_utils import (
    DEFAULT_DOUBLE_COMMENT_JOIN,
    merge_clean_comment_cell_parts,
)


def test_merge_empty_sep_raw_uses_default_pipe() -> None:
    assert merge_clean_comment_cell_parts(["a", "b"], "") == f"a{DEFAULT_DOUBLE_COMMENT_JOIN}b"


def test_merge_single_space_separator() -> None:
    assert merge_clean_comment_cell_parts(["RC0603", "10K"], " ") == "RC0603 10K"


def test_merge_space_separator_preserves_leading_trailing_in_sep() -> None:
    # Separator is used as-is (no strip on the whole string).
    assert merge_clean_comment_cell_parts(["x", "y"], "  ") == "x  y"


def test_merge_pipe_default_explicit() -> None:
    assert merge_clean_comment_cell_parts(["p", "q"], " | ") == "p | q"


def test_merge_skips_nan_none_empty() -> None:
    assert merge_clean_comment_cell_parts(["a", None, "", "nan", float("nan")], " ") == "a"
    assert merge_clean_comment_cell_parts([float("nan")], "|") == ""


def test_merge_inf_skipped_like_bad_float() -> None:
    assert merge_clean_comment_cell_parts([float("inf"), "z"], " ") == "z"
