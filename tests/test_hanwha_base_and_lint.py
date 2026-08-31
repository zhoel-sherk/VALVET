"""Tests for Part Group join, case lint, project file, preview filter, match status."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from hanwha_case_lint import case_lint_alert_text, lint_cleaned_case
from hanwha_mdb_edit.core.column_labels import label_and_tooltip_for_column
from hanwha_mdb_edit.core.part_group import join_part_group_names
from services.clean_preview_filter import filter_clean_preview, unresolved_preview_rows
from services.hanwha_match_status import hanwha_match_status, strict_export_blocked
from services.project_file import (
    load_project_file,
    project_payload,
    push_mru,
    save_project_file,
)


def test_join_part_group_names_maps_id_to_chip_class() -> None:
    parts = pd.DataFrame(
        {
            "PARTNAME": ["_NewTrimmer", "C0402_1u"],
            "UPDPARTGROUPID": [7, 2],
        }
    )
    gmap = pd.DataFrame(
        {
            "UPDPARTGROUPID": [7, 2],
            "UPDPARTGROUPNAME": ["Trimmer", "Chip-C1005(0402)"],
        }
    )
    out = join_part_group_names(parts, gmap)
    by_name = dict(zip(out["PARTNAME"], out["UPDPARTGROUPNAME"]))
    assert by_name["_NewTrimmer"] == "Trimmer"
    assert by_name["C0402_1u"] == "Chip-C1005(0402)"


def test_join_part_group_names_missing_map_adds_empty_column() -> None:
    parts = pd.DataFrame({"PARTNAME": ["a"], "UPDPARTGROUPID": [1]})
    out = join_part_group_names(parts, pd.DataFrame())
    assert "UPDPARTGROUPNAME" in out.columns


def test_parent_profile_label_is_not_chip_base() -> None:
    label, tip = label_and_tooltip_for_column("PARENTPROFILE")
    assert "Parent profile" == label
    assert "Chip" in tip
    g_label, g_tip = label_and_tooltip_for_column("UPDPARTGROUPNAME")
    assert "Type" == g_label
    assert "Chip-0201" in g_tip or "Chip" in g_tip


def test_case_lint_other_must_be_caps() -> None:
    assert lint_cleaned_case("STM32F407", "OTHER") == ()
    hits = lint_cleaned_case("stm32f407", "OTHER")
    assert hits and hits[0].code == "other_not_caps"


def test_case_lint_cap_uf_not_uf() -> None:
    assert lint_cleaned_case("0402_10Uf_16V", "CAP") == ()
    assert lint_cleaned_case("0402_10UF_16V", "CAP")
    assert "cap_uf" in case_lint_alert_text("0402_10uF", "CAP")


def test_case_lint_res_m_vs_m() -> None:
    assert lint_cleaned_case("0402_10m", "RES") == ()
    assert lint_cleaned_case("0402_10M", "RES") == ()
    assert lint_cleaned_case("0402_10mOHM", "RES")


def test_project_file_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / ".valvet-project.json"
    payload = project_payload(bom_path="a.xlsx", pnp_path="b.csv", mdb_path="c.mdb")
    save_project_file(path, payload)
    loaded = load_project_file(path)
    assert loaded["bom_path"] == "a.xlsx"
    assert loaded["mdb_path"] == "c.mdb"
    assert push_mru(["old.mdb"], "c.mdb")[0] == "c.mdb"


def test_filter_clean_preview_other_and_regex() -> None:
    df = pd.DataFrame(
        {
            "Original": ["a", "b", "c"],
            "Type": ["OTHER", "CAP", "OTHER"],
            "Source": ["regex", "vendor", "hanwha_mdb"],
        }
    )
    other = filter_clean_preview(df, other_only=True)
    assert list(other["Original"]) == ["a", "c"]
    regex = filter_clean_preview(df, regex_only=True)
    assert list(regex["Original"]) == ["a"]


def test_unresolved_and_strict_export() -> None:
    df = pd.DataFrame(
        {
            "Original": ["x", "y"],
            "Cleaned": ["X", "Y"],
            "Type": ["OTHER", "CAP"],
            "Source": ["regex", "vendor"],
            "Match": ["none", "none"],
        }
    )
    u = unresolved_preview_rows(df)
    assert "x" in list(u["Original"])
    assert strict_export_blocked(df) is True
    ok = df.copy()
    ok.loc[0, "Match"] = "matched"
    ok.loc[0, "Source"] = "hanwha_mdb"
    assert strict_export_blocked(ok) is False


def test_hanwha_match_status_tiers() -> None:
    assert hanwha_match_status("hanwha_mdb") == "matched"
    assert hanwha_match_status("PARTIAL hanwha_mdb") == "ambiguous"
    assert hanwha_match_status("AMBIGUOUS hanwha_mdb") == "ambiguous"
    assert hanwha_match_status("regex") == "none"
    assert hanwha_match_status("") == "none"
