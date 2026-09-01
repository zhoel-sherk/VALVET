"""Golden tests for Merge layer display vs PCB Preview board side."""

from __future__ import annotations

import pandas as pd

from layer_side import (
    display_layer_value,
    is_bot_layer_token,
    is_top_layer_token,
    parse_board_side,
    select_merge_layer_defaults,
)


def test_display_layer_value() -> None:
    assert display_layer_value(float("nan")) == "None"
    assert display_layer_value(None) == "None"
    assert display_layer_value("") == "None"
    assert display_layer_value("  ") == "None"
    assert display_layer_value("nan") == "None"
    assert display_layer_value("NONE") == "None"
    assert display_layer_value("  Top  ") == "Top"
    assert display_layer_value("m") == "m"


def test_is_bot_and_top_tokens() -> None:
    for tok in ("m", "B", "bot", "BOTTOM", "bottomlayer", "mirror"):
        assert is_bot_layer_token(tok)
        assert not is_top_layer_token(tok)
    for tok in ("t", "TOP", "toplayer"):
        assert is_top_layer_token(tok)
        assert not is_bot_layer_token(tok)
    assert not is_bot_layer_token("TOP")
    assert not is_bot_layer_token("TOPSIDE")
    assert not is_top_layer_token("N")
    assert not is_bot_layer_token("N")


def test_select_merge_layer_defaults() -> None:
    assert select_merge_layer_defaults([]) == (None, None)
    assert select_merge_layer_defaults(["Top", "Bottom"]) == ("Top", "Bottom")
    assert select_merge_layer_defaults(["TOP", "BOTTOM"]) == ("TOP", "BOTTOM")
    assert select_merge_layer_defaults(["T", "B"]) == ("T", "B")
    assert select_merge_layer_defaults(["None", "Top"]) == ("Top", "None")
    assert select_merge_layer_defaults(["None"]) == ("None", None)
    assert select_merge_layer_defaults(["SideA", "SideB"]) == ("SideB", "SideA")
    assert select_merge_layer_defaults(["All"]) == ("All", "All")


def test_parse_board_side() -> None:
    assert parse_board_side("m") == "bottom"
    assert parse_board_side("b") == "bottom"
    assert parse_board_side("BOT") == "bottom"
    assert parse_board_side("BOTTOM") == "bottom"
    assert parse_board_side("t") == "top"
    assert parse_board_side("TOP") == "top"
    assert parse_board_side("") == "top"
    assert parse_board_side(None) == "top"
    assert parse_board_side(float("nan")) == "top"
    assert parse_board_side("none") == "top"
    assert parse_board_side("B.") == "bottom"
    assert parse_board_side("F.Cu") == "top"
    assert parse_board_side("weird") == "top"


def test_filter_simulation_display_exact_match() -> None:
    df = pd.DataFrame({"Layer": ["Top", "m", None]})
    mapped = df["Layer"].map(display_layer_value)
    assert int((mapped == "Top").sum()) == 1
    assert int((mapped == "m").sum()) == 1
    assert int((mapped == "None").sum()) == 1
    assert parse_board_side("Top") == "top"
    assert parse_board_side("m") == "bottom"
    assert parse_board_side(None) == "top"
