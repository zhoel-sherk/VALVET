"""Hidden Scan tab: visibility, Merge button, barcode flow and big output."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("PySide6")

from parsers.tolp_export import SIDE_REAR, TolpExport, TolpFeeder  # noqa: E402


def _reset(main_window) -> None:
    main_window.merge_model.update_dataframe(pd.DataFrame())
    main_window._last_merge_df = None
    main_window._bom_df = None
    tab = main_window._scan_tab
    tab._export = None
    tab._export_dir = ""
    tab.folder_edit.setText("")
    tab.history_list.clear()
    tab.code_label.setText("")
    tab.part_label.setText("")
    tab.places_label.setText("")
    tab.hint_label.setText("")


def _merge_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Ref": ["R1,R2"],
            "Value": ["0201_10K_1%"],
            "Custom 1": ["IN-00004594"],
        }
    )


def _export() -> TolpExport:
    return TolpExport(
        folder=Path("."),
        feeders=(
            TolpFeeder("M1", "DECANS2", SIDE_REAR, 18, "0201_10K_1%"),
            TolpFeeder("M3", "DECANL2", "Front", 44, "0201_10K_1%"),
        ),
        machines={"M1": "DECANS2", "M3": "DECANL2"},
    )


def test_scan_tab_is_not_in_the_tab_bar(main_window) -> None:
    idx = main_window.tabs.indexOf(main_window._scan_tab)
    assert idx >= 0
    assert not main_window.tabs.isTabVisible(idx)
    assert idx >= len(main_window._tab_keys_in_order)


def test_merge_has_a_scan_button(main_window) -> None:
    assert main_window.btn_scan.text()
    main_window.btn_scan.click()
    assert main_window.tabs.currentWidget() is main_window._scan_tab


def test_scan_renders_feeder_positions_in_the_big_font(main_window) -> None:
    _reset(main_window)
    tab = main_window._scan_tab
    main_window.merge_model.update_dataframe(_merge_df())
    tab._export = _export()
    tab._refresh_sources()
    assert tab.custom_combo.count() == 1

    tab.scan_edit.setText("IN-00004594")
    tab.scan_edit.returnPressed.emit()

    assert "M1" in tab.places_label.text()
    assert "Rear · 18" in tab.places_label.text()
    assert "M3" in tab.places_label.text()
    assert f"font-size: {tab.font_spin.value()}px" in tab.places_label.styleSheet()
    assert tab.scan_edit.text() == ""  # ready for the next reel
    assert tab.history_list.count() == 1


def test_unknown_code_state(main_window) -> None:
    _reset(main_window)
    tab = main_window._scan_tab
    main_window.merge_model.update_dataframe(_merge_df())
    tab._export = _export()
    tab._refresh_sources()

    tab.scan_edit.setText("IN-99999999")
    tab._on_scan()
    assert tab.places_label.text() == tab._tr("scan.unknown_code")


def test_known_code_without_feeder_state(main_window) -> None:
    _reset(main_window)
    tab = main_window._scan_tab
    df = pd.DataFrame({"Ref": ["U1"], "Value": ["not-in-export"], "Custom 1": ["IN-1"]})
    main_window.merge_model.update_dataframe(df)
    tab._export = _export()
    tab._refresh_sources()

    tab.scan_edit.setText("IN-1")
    tab._on_scan()
    assert tab.places_label.text() == tab._tr("scan.part_missing")
    assert "not-in-export" in tab.part_label.text()


def test_no_source_state(main_window) -> None:
    _reset(main_window)
    tab = main_window._scan_tab
    tab._refresh_sources()
    tab.scan_edit.setText("IN-1")
    tab._on_scan()
    assert tab.places_label.text() == tab._tr("scan.no_source")


def test_font_is_clamped_and_persisted(main_window) -> None:
    _reset(main_window)
    tab = main_window._scan_tab
    tab.font_spin.setValue(200)
    assert "font-size: 72px" in tab.places_label.styleSheet()
    assert main_window._settings.value("scan/font_px", type=int) == 72
    tab.font_spin.setValue(1)
    assert "font-size: 25px" in tab.places_label.styleSheet()


def test_swap_checkbox_persists(main_window) -> None:
    _reset(main_window)
    tab = main_window._scan_tab
    tab.swap_check.setChecked(True)
    assert main_window._settings.value("scan/swap_sides", False, type=bool) is True
    tab.swap_check.setChecked(False)


def test_bom_fallback_uses_custom_roles(main_window) -> None:
    """Without Merge the tab maps BOM Comment + Custom columns from the dropdowns."""
    _reset(main_window)
    tab = main_window._scan_tab
    bom = pd.DataFrame(
        [["IN-00004594", "0201_10K_1%", "R1,R2"]],
        columns=["0", "1", "2"],
    )
    main_window._bom_df = bom
    main_window.bom_model.update_dataframe(bom)
    main_window._fill_bom_combos(preserved_roles=["Custom", "Comment", "REF"])
    tab._export = _export()
    tab._refresh_sources()

    assert tab.custom_combo.count() == 1
    assert tab.custom_combo.currentData() == "0"
    tab.scan_edit.setText("IN-00004594")
    tab._on_scan()
    assert "Rear · 18" in tab.places_label.text()
