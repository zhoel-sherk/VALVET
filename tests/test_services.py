"""GUI-free ``src/services/`` unit tests (no Qt)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from tools.clean_corpus_lib import load_corpus_profile

import clean_component
import pn_original
from clean_types import CleanConfig
from services import (
    apply_clean_preview_to_bom,
    build_clean_config,
    build_processor_config,
    find_and_replace,
    import_bom_comments_for_clean,
    read_pnp_dataframe,
)
from smt_processor import ColumnConfig

_ASSETS = Path(__file__).resolve().parent / "assets"


def test_find_replace_substring_case_insensitive() -> None:
    df = pd.DataFrame([["Hello", "World"]])
    out, n = find_and_replace(
        df, "ell", "ipp", [(0, 0)], match_case=False, whole_cell=False
    )
    assert n == 1
    assert out.iat[0, 0] == "Hippo"


def test_find_replace_whole_cell() -> None:
    df = pd.DataFrame([["abc", "abcd"]])
    out, n = find_and_replace(df, "abc", "X", [(0, 0), (0, 1)], whole_cell=True)
    assert n == 1
    assert out.iat[0, 0] == "X"
    assert out.iat[0, 1] == "abcd"


def test_find_replace_skips_out_of_range_indexes() -> None:
    df = pd.DataFrame([["a"]])
    out, n = find_and_replace(df, "a", "b", [(9, 0), (0, 9)])
    assert n == 0
    assert out.iat[0, 0] == "a"


def test_import_bom_comments_single_column() -> None:
    bom = pd.DataFrame({"Comment": ["RES 0402 10K", "CAP 1uF"]})
    got = import_bom_comments_for_clean(bom, ["Comment"], [0, 1])
    assert got == ["RES 0402 10K", "CAP 1uF"]


def test_import_bom_comments_double_merge() -> None:
    bom = pd.DataFrame(
        {
            "A": ["MLCC_2.2uF", None],
            "B": ["三星(Samsung)", float("nan")],
        }
    )
    got = import_bom_comments_for_clean(
        bom,
        ["A", "B"],
        [0, 1],
        double_comment_separator=" | ",
    )
    assert got[0] == "MLCC_2.2uF | 三星(Samsung)"
    assert got[1] == ""


def test_import_bom_three_join_matches_name_plus_two_join() -> None:
    bom = pd.DataFrame(
        {"A": ["x"], "B": ["y"], "C": ["z"]},
    )
    sep = " | "
    three_join = import_bom_comments_for_clean(
        bom, ["A", "B", "C"], [0], double_comment_separator=sep
    )
    name_plus_two = import_bom_comments_for_clean(
        bom, ["A", "B", "C"], [0], double_comment_separator=sep
    )
    assert three_join == name_plus_two == ["x | y | z"]


def test_import_bom_single_column_no_separator() -> None:
    bom = pd.DataFrame({"PN": ["0402_10K"]})
    got = import_bom_comments_for_clean(
        bom, ["PN"], [0], double_comment_separator=" | "
    )
    assert got == ["0402_10K"]


def test_apply_clean_preview_meta_columns() -> None:
    bom = pd.DataFrame({"Comment": ["orig1", "orig2"]})
    preview = [
        (1, "orig1", "0402_10K", "RESISTOR", "regex"),
        (2, "orig2", "0402_1uF", "CAP", "vendor"),
    ]
    out = apply_clean_preview_to_bom(
        bom, preview, [0, 1], "Comment", replace_source=False
    )
    assert out.at[0, "comment"] == "0402_10K"
    assert out.at[0, "clean_type"] == "RESISTOR"
    assert out.at[0, "clean_part_code"] == "RES"
    assert out.at[1, "clean_vendor"] == "vendor"


def test_apply_clean_preview_replace_source_and_source_indices() -> None:
    bom = pd.DataFrame({"Comment": ["a", "b", "c"]})
    preview = [(1, "a", "A1", "OTHER", "")]
    out = apply_clean_preview_to_bom(
        bom, preview, [2], "Comment", replace_source=True
    )
    assert out.at[2, "Comment"] == "A1"
    assert "Comment_cleaned" not in out.columns


def test_apply_clean_preview_uses_comment_column() -> None:
    bom = pd.DataFrame({"Part": ["orig"], "comment": [""]})
    preview = [(1, "orig", "cleaned_val", "CAP", "regex")]
    out = apply_clean_preview_to_bom(
        bom, preview, [0], "Part", replace_source=False
    )
    assert "comment" in out.columns
    assert out.at[0, "comment"] == "cleaned_val"
    assert "Part_cleaned" not in out.columns


def test_apply_clean_preview_seven_column_rows() -> None:
    bom = pd.DataFrame({"Comment": ["x"]})
    preview = [(1, "x", "cleaned", "CAP", "src", "arb", "99")]
    out = apply_clean_preview_to_bom(bom, preview, [0], "Comment")
    assert out.at[0, "comment"] == "cleaned"
    assert out.at[0, "clean_type"] == "CAP"


def test_apply_clean_preview_snapshot_dirty(tmp_path: Path) -> None:
    import working_copy

    bom = pd.DataFrame({"Comment": ["RES 10K 0402"]})
    preview = [(1, "RES 10K 0402", "0402_10K", "RESISTOR", "regex")]
    out = apply_clean_preview_to_bom(bom, preview, [0], "Comment")
    assert out.at[0, "comment"] == "0402_10K"
    src = tmp_path / "bom.csv"
    src.write_text("x\n", encoding="utf-8")
    autosave = tmp_path / "autosave"
    autosave.mkdir()
    working_copy.save_snapshot(out, str(src), "bom", autosave, dirty=True)
    snap = working_copy.find_snapshot(str(src), "bom", autosave)
    assert snap is not None
    assert snap.meta["dirty"] is True


def test_find_replace_table_state_helpers_exist() -> None:
    from app_pyside6 import MainWindow

    assert hasattr(MainWindow, "_capture_table_edit_state")
    assert hasattr(MainWindow, "_restore_table_edit_state")


def test_build_clean_config_cap_template_and_pipeline() -> None:
    def getter(key: str, default: str = "") -> str:
        data = {
            "clean/pipeline_order": json.dumps(["vendor", "regex"]),
            "clean/pipeline_disabled": json.dumps(["hanwha"]),
            "clean/regex_master_enabled": "true",
            "clean/regex_master_preview_scores": "true",
        }
        return data.get(key, default)

    cfg = build_clean_config(
        res_template=("pack", "%"),
        cap_template=("pack", "V (volt)", "film", "%"),
        ind_template=(),
        settings_getter=getter,
    )
    assert cfg.cap_include_package is True
    assert cfg.cap_include_voltage is True
    assert cfg.cap_include_dielectric is True
    assert "vendor" in cfg.clean_pipeline_order
    assert "hanwha" in cfg.clean_pipeline_disabled
    assert cfg.regex_master_enabled is True
    assert cfg.regex_master_preview_scores is True


def test_build_processor_config_fallback_and_skip() -> None:
    bom = pd.DataFrame({"Ref": ["R1"], "Note": ["10K"]})
    pnp = pd.DataFrame(
        {
            "DESIGNATOR": ["R1"],
            "FOOTPRINT": ["0402"],
            "X": [1.0],
            "Y": [2.0],
        }
    )
    proc = build_processor_config(
        bom,
        pnp,
        {"REF": "Ref", "Comment": "Note"},
        {"REF": "", "Footprint": "", "Comment": ""},
    )
    bom_cfg = proc._bom_config
    pnp_cfg = proc._pnp_config
    assert bom_cfg is not None and pnp_cfg is not None
    assert bom_cfg.designator == "Ref"
    assert bom_cfg.comment == "Note"
    assert pnp_cfg.designator == "DESIGNATOR"
    assert pnp_cfg.footprint == "FOOTPRINT"
    assert pnp_cfg.comment == "_skip_"
    assert isinstance(bom_cfg, ColumnConfig)


def test_build_processor_config_prefers_pn_name_over_join() -> None:
    bom = pd.DataFrame(
        {"Ref": ["R1"], "Name": ["10K"], "Extra": ["vendor"]}
    )
    pnp = pd.DataFrame({"DESIGNATOR": ["R1"], "X": [1.0], "Y": [2.0]})
    proc = build_processor_config(
        bom,
        pnp,
        {"REF": "Ref", "Comment": "Name", "PnJoin": "Extra"},
        {"REF": "DESIGNATOR"},
        bom_column_roles=["REF", "Comment", "PnJoin"],
    )
    assert proc._bom_config is not None
    assert proc._bom_config.comment == "Name"


def test_build_processor_config_first_join_when_no_pn_name() -> None:
    bom = pd.DataFrame({"Ref": ["R1"], "J1": ["a"], "J2": ["b"]})
    pnp = pd.DataFrame({"DESIGNATOR": ["R1"], "X": [1.0], "Y": [2.0]})
    proc = build_processor_config(
        bom,
        pnp,
        {"REF": "Ref", "PnJoin": "J2"},
        {"REF": "DESIGNATOR"},
        bom_column_roles=["REF", "PnJoin", "PnJoin"],
    )
    assert proc._bom_config is not None
    assert proc._bom_config.comment == "J1"


def test_build_processor_config_refuses_comment_as_silent_ref() -> None:
    from smt_processor import SMTColumnNotFoundError

    bom = pd.DataFrame({"comment_orig": ["HDMI-PORT"], "comment": ["HDMI-PORT"]})
    pnp = pd.DataFrame({"Value": ["HDMI-PORT"], "X": [1.0]})
    with pytest.raises(SMTColumnNotFoundError, match="REF"):
        build_processor_config(bom, pnp, {}, {})


def test_read_pnp_dataframe_comma_csv() -> None:
    path = str(_ASSETS / "comma.csv")
    df = read_pnp_dataframe(path, ",", first_row=0, last_row=-1)
    assert len(df) >= 2
    assert "R52" in df.iloc[:, 0].astype(str).values


def test_read_pnp_dataframe_spaces_trim() -> None:
    path = str(_ASSETS / "spaces.csv")
    df = read_pnp_dataframe(path, "spaces", first_row=2, last_row=2)
    assert len(df) == 1
    assert str(df.iloc[0, 0]) == "Fid6"


@pytest.fixture(scope="module")
def corpus_cfg() -> CleanConfig:
    pn_original.CONVERTERS.clear()
    pn_original.load_converters()
    return load_corpus_profile()


def test_import_join_then_clean_one_samsung(corpus_cfg: CleanConfig) -> None:
    join_line = (
        "MLCC_2.2uF_X5R_6.3V_+/-20%_0402_0.5MM+-0.05MM_SMD | 三星(Samsung) | "
        "CL05A225MQ5NSNC"
    )
    prose, vendor, mpn = join_line.split(" | ")
    bom = pd.DataFrame({"Prose": [prose], "Vendor": [vendor], "MPN": [mpn]})
    comments = import_bom_comments_for_clean(
        bom,
        ["Prose", "Vendor", "MPN"],
        [0],
        double_comment_separator=" | ",
    )
    assert comments[0] == join_line
    got = clean_component.clean_one(comments[0], corpus_cfg)[0]
    assert got == "0402_2.2uF_X5R_20%_6.3V"
