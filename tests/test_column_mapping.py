"""Qt-free REF vs PN mapping helpers."""

from __future__ import annotations

from services.column_mapping import (
    guess_bom_role,
    is_designator_header,
    likely_ref_mapped_to_pn,
    merge_result_pnp_roles,
    pick_merge_pn_column,
    pick_ref_column,
    pn_columns_in_order,
    roles_after_clean_apply,
    uniquify_roles,
    BOM_EXCLUSIVE_ROLES,
)


def test_preferred_is_not_ref() -> None:
    assert not is_designator_header("PREFERRED")
    assert guess_bom_role("PREFERRED") == "-"
    assert is_designator_header("Ref")
    assert is_designator_header("Designator")


def test_uniquify_comment_last_wins() -> None:
    roles = uniquify_roles(["REF", "Comment", "-", "Comment"])
    assert roles[0] == "REF"
    assert roles[1] == "-"
    assert roles[3] == "Comment"


def test_bom_exclusive_keeps_multiple_pn_join() -> None:
    roles = uniquify_roles(
        ["REF", "PnJoin", "PnJoin", "Comment"],
        exclusive=BOM_EXCLUSIVE_ROLES,
        last_wins=(),
    )
    assert roles == ["REF", "PnJoin", "PnJoin", "Comment"]


def test_bom_exclusive_second_ref_and_pn_name_cleared() -> None:
    roles = uniquify_roles(
        ["REF", "REF", "Comment", "Comment"],
        exclusive=BOM_EXCLUSIVE_ROLES,
        last_wins=(),
    )
    assert roles == ["REF", "-", "Comment", "-"]


def test_pick_merge_pn_prefers_name() -> None:
    cols = ["Ref", "JoinA", "Name", "JoinB"]
    roles = ["REF", "PnJoin", "Comment", "PnJoin"]
    assert pick_merge_pn_column(cols, roles) == "Name"


def test_pick_merge_pn_first_join_without_name() -> None:
    cols = ["Ref", "JoinA", "JoinB"]
    roles = ["REF", "PnJoin", "PnJoin"]
    assert pick_merge_pn_column(cols, roles) == "JoinA"


def test_pn_columns_three_join_same_order_as_name_plus_joins() -> None:
    cols = ["A", "B", "C"]
    three_join = pn_columns_in_order(cols, ["PnJoin", "PnJoin", "PnJoin"])
    name_plus = pn_columns_in_order(cols, ["Comment", "PnJoin", "PnJoin"])
    assert three_join == name_plus == ["A", "B", "C"]


def test_roles_after_clean_apply_keeps_ref() -> None:
    cols = ["Designator", "comment_orig", "comment", "clean_type"]
    preserved = ["REF", "Comment", "-", "-"]
    out = roles_after_clean_apply(preserved, cols, comment_column="comment")
    assert out[0] == "REF"
    assert out[1] == "-"
    assert out[2] == "Comment"


def test_roles_after_clean_apply_keeps_pn_join() -> None:
    cols = ["Designator", "A", "B", "comment"]
    preserved = ["REF", "PnJoin", "PnJoin", "-"]
    out = roles_after_clean_apply(preserved, cols, comment_column="comment")
    assert out == ["REF", "PnJoin", "PnJoin", "Comment"]


def test_merge_result_pnp_roles_maps_ref() -> None:
    roles = merge_result_pnp_roles(
        ["Ref", "Value", "Footprint", "X", "Y", "Rotation", "Layer"]
    )
    assert roles[0] == "REF"
    assert roles[1] == "Comment"
    assert roles[3] == "X"


def test_pick_ref_column_skips_comment_orig() -> None:
    cols = ["comment_orig", "comment", "Designator"]
    assert pick_ref_column(cols) == "Designator"
    assert pick_ref_column(cols, "Designator") == "Designator"
    assert pick_ref_column(["comment_orig", "comment"]) is None


def test_likely_ref_mapped_to_pn_hdmi_pattern() -> None:
    bom_keys = [f"PN-{i}" for i in range(8)]
    pnp_keys = [f"U{i}" for i in range(8)]
    pnp_vals = list(bom_keys)
    assert likely_ref_mapped_to_pn(bom_keys, pnp_keys, pnp_vals)
    assert not likely_ref_mapped_to_pn(pnp_keys, pnp_keys, pnp_vals)
