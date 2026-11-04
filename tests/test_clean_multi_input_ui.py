"""Clean multi-input UI: Original columns, Apply, Learn and fragment mode."""

from __future__ import annotations

import pandas as pd
from PySide6 import QtWidgets


def _load_bom(main_window, rows, roles) -> None:
    bom = pd.DataFrame(rows)
    bom.columns = [str(c) for c in bom.columns]
    main_window._bom_df = bom
    main_window.bom_model.update_dataframe(bom)
    main_window._fill_bom_combos(preserved_roles=roles)


def test_multi_original_preview_and_apply_keep_their_columns(main_window) -> None:
    _load_bom(
        main_window,
        [["RES 0402 10K OHM +/-1%", "RC0402JR-0710KL", "R1"]],
        ["Comment", "PnJoin", "REF"],
    )
    main_window.clean_regex_master.setChecked(True)
    main_window.clean_regex_master_scores.setChecked(True)
    main_window._clean_import()
    main_window._run_clean_preview()
    df = main_window.clean_preview_model.get_dataframe()
    assert list(df.columns) == [
        "#",
        "Original",
        "Original 2",
        "Cleaned",
        "Type",
        "Input",
        "Source",
        "Arbiter",
        "Win%",
        "Alert",
    ]
    assert df.iloc[0]["Input"] == "Original 2"
    assert df.iloc[0]["Cleaned"] == "10K_0402_5%"

    main_window._clean_apply()
    assert main_window._bom_df.iloc[0]["0"] == "RES 0402 10K OHM +/-1%"
    assert main_window._bom_df.iloc[0]["1"] == "RC0402JR-0710KL"
    assert main_window._bom_df.iloc[0]["comment"] == "10K_0402_5%"


def test_fragment_checkbox_produces_a_combined_preview_input(main_window) -> None:
    _load_bom(
        main_window,
        [["R0402", "0.1uF", "X5R 10V", "C1"]],
        ["Comment", "PnJoin", "PnJoin", "REF"],
    )
    main_window.clean_combine_inputs.setChecked(True)
    main_window._clean_import()
    main_window._run_clean_preview()
    df = main_window.clean_preview_model.get_dataframe()
    assert df.iloc[0]["Cleaned"] == "0.1uF_0402_X5R_10V"
    assert df.iloc[0]["Input"] == main_window.ui_tr("clean.input_combined")
    main_window._save_clean_settings()
    assert (
        main_window._settings.value("clean/combine_input_columns", False, type=bool)
        is True
    )
    assert not hasattr(main_window, "clean_double_comment_sep")


def test_learn_other_uses_the_winning_original(main_window, monkeypatch) -> None:
    import ui.clean_tab as clean_tab

    preview = pd.DataFrame(
        [
            {
                "#": 1,
                "Original": "not a component",
                "Original 2": "IC KTS1677",
                "Cleaned": "KTS1677",
                "Type": "OTHER",
                "Input": "Original 2",
            }
        ]
    )
    main_window.clean_preview_model.update_dataframe(preview)
    main_window.clean_preview_table.selectRow(0)
    captured = {}
    monkeypatch.setattr(
        QtWidgets.QDialog,
        "exec",
        lambda _self: QtWidgets.QDialog.DialogCode.Accepted,
    )
    monkeypatch.setattr(
        clean_tab,
        "append_component",
        lambda raw, cleaned, typ, footprint, **kwargs: (
            captured.update(raw=raw, cleaned=cleaned) or True
        ),
    )
    main_window._learn_selected_other()
    assert captured == {"raw": "IC KTS1677", "cleaned": "KTS1677"}
