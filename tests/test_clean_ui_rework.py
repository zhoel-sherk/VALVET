"""Clean BOM UI rework: table, stepper, notification strip, rules and splitter."""

from __future__ import annotations

import re

import pandas as pd
import pytest

pytest.importorskip("PySide6")

from PySide6 import QtCore, QtWidgets


def _preview_frame(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def _base_row(**overrides) -> dict:
    row = {
        "#": 1,
        "Original": "RES 0402 10K 1%",
        "Original 2": "RC0402FR-0710KL",
        "Cleaned": "10K_0402_1%",
        "Type": "RESISTOR",
        "Input": "Original 2",
        "Source": "vendor",
        "Arbiter": "vendor",
        "Win%": "92",
        "Alert": "",
    }
    row.update(overrides)
    return row


def _show_preview(win, rows: list[dict]) -> None:
    win.clean_preview_model.update_dataframe(_preview_frame(rows))
    win._sync_clean_preview_view()


def _load_bom(win, rows: list[list[str]], roles: list[str]) -> None:
    bom = pd.DataFrame(rows)
    bom.columns = [str(c) for c in bom.columns]
    win._bom_df = bom
    win.bom_model.update_dataframe(bom)
    win._fill_bom_combos(preserved_roles=roles)


def test_table_hides_vertical_header_and_keeps_dynamic_columns(main_window) -> None:
    win = main_window
    _show_preview(win, [_base_row()])
    table = win.clean_preview_table
    assert table.verticalHeader().isVisible() is False
    header = table.horizontalHeader()
    assert header.stretchLastSection() is False
    names = [str(c) for c in win.clean_preview_model.get_dataframe().columns]
    modes = QtWidgets.QHeaderView.ResizeMode
    for col, name in enumerate(names):
        mode = header.sectionResizeMode(col)
        if name.startswith("Original") or name == "Cleaned":
            assert mode == modes.Stretch, name
        elif name == "Alert":
            assert mode == modes.Interactive, name
        else:
            assert mode == modes.ResizeToContents, name
    # Dynamic multi-input columns survive the presentation change.
    assert "Original 2" in names
    assert "Input" in names
    assert "Arbiter" in names
    assert "Win%" in names


def test_alert_column_hidden_only_when_every_value_is_empty(main_window) -> None:
    win = main_window
    _show_preview(win, [_base_row(), _base_row()])
    alert_col = list(win.clean_preview_model.get_dataframe().columns).index("Alert")
    assert win.clean_preview_table.isColumnHidden(alert_col) is True

    _show_preview(win, [_base_row(Alert="missing=film;present=2/3")])
    assert win.clean_preview_table.isColumnHidden(alert_col) is False


def test_empty_state_replaces_the_table_and_navigates_to_bom(main_window) -> None:
    win = main_window
    _show_preview(win, [])
    assert win.clean_preview_stack.currentWidget() is win.clean_preview_empty
    assert win.clean_preview_empty.accessibleName()
    assert win.btn_clean_empty_bom.accessibleName()

    win.tabs.setCurrentIndex(win._tab_index("clean_bom"))
    win._clean_empty_go_bom()
    assert win.tabs.currentIndex() == win._tab_index("bom")

    _show_preview(win, [])
    assert win.lbl_clean_source.text() == win.ui_tr("clean.summary_empty")
    _show_preview(win, [_base_row()])
    assert win.clean_preview_stack.currentWidget() is win.clean_preview_table


def test_header_tooltips_follow_the_language(main_window) -> None:
    win = main_window
    _show_preview(win, [_base_row()])
    header = win.clean_preview_table.horizontalHeader()
    names = [str(c) for c in win.clean_preview_model.get_dataframe().columns]
    idx = names.index("Source")

    def tip() -> str:
        return header.model().headerData(
            idx,
            QtCore.Qt.Orientation.Horizontal,
            QtCore.Qt.ItemDataRole.ToolTipRole,
        )

    assert tip() == win.ui_tr("clean.header_tip_source")
    original_locale = win._i18n.locale
    try:
        win._i18n.set_locale("ru")
        win._refresh_clean_tab_static_texts()
        assert tip() == win.ui_tr("clean.header_tip_source")
        assert tip() != ""
    finally:
        win._i18n.set_locale(original_locale)
        win._refresh_clean_tab_static_texts()


def test_summary_counts_come_from_the_preview(main_window) -> None:
    win = main_window
    _show_preview(
        win,
        [
            _base_row(),
            _base_row(
                **{
                    "#": 2,
                    "Type": "OTHER",
                    "Cleaned": "Q1",
                    "Source": "PARTIAL hanwha_mdb",
                    "Alert": "missing=film",
                }
            ),
        ],
    )
    expected = win.ui_tr(
        "clean.summary_counts",
        rows=2,
        clean=2,
        partial=1,
        other=1,
        errors=1,
    )
    assert win.lbl_clean_source.text() == expected


def test_import_convert_apply_states_and_stale_badge(main_window) -> None:
    win = main_window
    win.tabs.setCurrentIndex(win._tab_index("clean_bom"))
    win._clean_imported_comments = ["RES 0402 10K 1%"]
    win._clean_last_preview = []
    win._clean_preview_stale = False
    win._clean_applied = False
    win.btn_clean_convert.setEnabled(True)
    win.btn_clean_apply.setEnabled(False)
    win._sync_clean_primary_buttons()
    assert win.btn_clean_import.property("cleanStepState") == "done"
    assert win.btn_clean_import.text() == "✓ " + win.ui_tr("clean.btn_import")
    assert win.btn_clean_convert.property("cleanStep") == "active"
    assert win.btn_clean_convert.property("cleanStepState") == "next"
    assert win.btn_clean_convert.text() == "▶ " + win.ui_tr("clean.btn_convert")

    win._clean_last_preview = [{}]
    win.btn_clean_apply.setEnabled(True)
    win._sync_clean_primary_buttons()
    assert win.btn_clean_convert.property("cleanStepState") == "done"
    assert win.btn_clean_apply.property("cleanStepState") == "next"

    win._show_clean_apply_banner("applied")
    assert win.clean_apply_ok_banner.isHidden() is False
    win._on_clean_preview_setting_changed()
    assert win.clean_apply_ok_banner.isHidden() is True
    assert win.lbl_clean_stale.isHidden() is False
    assert win.btn_clean_convert.property("cleanStepState") == "stale"
    assert "Convert" in win.btn_clean_apply.toolTip()

    win._clean_preview_stale = False
    win._clean_applied = True
    win._sync_clean_primary_buttons()
    win._refresh_clean_stale_badge()
    assert win.btn_clean_apply.property("cleanStepState") == "done"
    assert win.lbl_clean_stale.isHidden() is True


def test_replace_source_control_is_gone(main_window) -> None:
    win = main_window
    assert not hasattr(win, "clean_apply_replace")
    assert not win._settings.contains("clean/apply_replace")


def test_learn_other_shows_count_and_disables_at_zero(main_window) -> None:
    win = main_window
    win._clean_last_preview = [{}]
    _show_preview(win, [_base_row(), _base_row(**{"#": 2, "Type": "OTHER"})])
    win._sync_clean_preview_view()
    assert win.btn_clean_learn_other.text() == win.ui_tr(
        "clean.btn_learn_count", count=1
    )
    assert win.btn_clean_learn_other.isEnabled() is True

    _show_preview(win, [_base_row()])
    win._sync_clean_preview_view()
    assert win.btn_clean_learn_other.text() == win.ui_tr(
        "clean.btn_learn_count", count=0
    )
    assert win.btn_clean_learn_other.isEnabled() is False
    assert win.btn_clean_learn_other.toolTip() == win.ui_tr("clean.btn_learn_zero_tip")


def test_rules_summary_reflects_live_settings(main_window) -> None:
    win = main_window
    win.chk_clean_res.setChecked(True)
    win.clean_combine_inputs.setChecked(True)
    win._update_clean_rules_summary()
    text = win._clean_rules_summary_full
    assert win.ui_tr("clean.rules_short_res") in text
    assert win.ui_tr("clean.rules_combine_on") in text
    assert win.clean_spacer_combo.currentData() in text


def test_disabled_step_tooltips_name_the_missing_action(main_window) -> None:
    win = main_window
    win._clean_imported_comments = []
    win._clean_last_preview = []
    win._clean_preview_stale = False
    win.btn_clean_convert.setEnabled(False)
    win.btn_clean_apply.setEnabled(False)
    win._sync_clean_primary_buttons()
    assert win.btn_clean_convert.toolTip() == win.ui_tr(
        "clean.btn_convert_disabled_import"
    )
    assert win.btn_clean_apply.toolTip() == win.ui_tr(
        "clean.btn_apply_disabled_convert"
    )


def test_apply_does_not_mark_its_own_preview_stale(main_window) -> None:
    win = main_window
    win._clean_preview_stale = False
    win._clean_last_preview = [{}]
    win._clean_applying = True
    try:
        win._mark_clean_preview_stale()
    finally:
        win._clean_applying = False
    assert win._clean_preview_stale is False


def test_splitter_sizes_persist_as_plain_integers(main_window) -> None:
    win = main_window
    win.btn_clean_options_toggle.setChecked(True)
    win.clean_splitter.setSizes([420, 180])
    win._save_clean_splitter_sizes()
    win._settings.sync()
    raw = win._settings.value("clean/splitter_sizes")
    assert len(raw) == 2
    assert all(isinstance(v, int) for v in raw)
    assert [int(v) for v in raw] == win.clean_splitter.sizes()
    assert win._stored_clean_splitter_sizes() == [int(v) for v in raw]

    win.btn_clean_options_toggle.setChecked(False)
    assert win.clean_options_panel.isHidden() is True
    win._save_clean_splitter_sizes()
    raw_collapsed = win._settings.value("clean/splitter_sizes")
    assert [int(v) for v in raw_collapsed] == [int(v) for v in raw]
    win.btn_clean_options_toggle.setChecked(True)
    assert win.clean_options_panel.isHidden() is False


def test_warning_strip_details_and_dismiss(main_window) -> None:
    win = main_window
    win.tabs.setCurrentIndex(win._tab_index("clean_bom"))
    win._show_clean_alert("clean.err_no_mapping")
    assert win.clean_alert_frame.isHidden() is False
    assert win.lbl_clean_alert.text() == win.ui_tr("clean.err_no_mapping")
    assert win.btn_clean_alert_details.text() == win.ui_tr("clean.err_details")

    win.btn_clean_alert_details.click()
    assert win._console_window is not None
    assert win._console_window.isVisible() is True
    win._console_window.close()

    win.btn_clean_alert_dismiss.click()
    assert win.clean_alert_frame.isHidden() is True


def test_no_bom_import_shows_strip_and_log(main_window) -> None:
    win = main_window
    win.tabs.setCurrentIndex(win._tab_index("clean_bom"))
    win._bom_df = None
    win.bom_model.update_dataframe(pd.DataFrame())
    messages: list[str] = []

    def capture(text: str, _level: str) -> None:
        messages.append(text)

    win.log_message.connect(capture)
    try:
        win._clean_import()
    finally:
        win.log_message.disconnect(capture)
    assert win.clean_alert_frame.isHidden() is False
    assert win.lbl_clean_alert.text() == win.ui_tr("clean.err_no_bom")
    assert any("load BOM" in message for message in messages)


def test_malformed_stored_splitter_sizes_fall_back_to_empty(main_window) -> None:
    from ui.clean_tab import _clean_int_list

    assert _clean_int_list(None) == []
    assert _clean_int_list([]) == []
    assert _clean_int_list("400, 200") == [400, 200]
    assert _clean_int_list("junk") == []
    assert _clean_int_list([400, object()]) == []


def test_ru_clean_labels_are_translated_and_clean() -> None:
    from ui_i18n import load_catalog

    ru = load_catalog("ru")
    assert "?" not in ru["clean.btn_import"]
    assert re.search("[А-Яа-яЁё]", ru["clean.btn_learn"])
    assert re.search("[А-Яа-яЁё]", ru["clean.btn_learn_count"])
    assert re.search("[А-Яа-яЁё]", ru["clean.btn_save"])
    assert re.search("[А-Яа-яЁё]", ru["clean.pn_vendor_label"])
    assert ru["clean.btn_import"].startswith("1. ")


def test_import_failure_reaches_strip_and_log(main_window, monkeypatch) -> None:
    import ui.clean_tab as clean_tab

    win = main_window
    win.tabs.setCurrentIndex(win._tab_index("clean_bom"))
    _load_bom(win, [["RES 0402 10K 1%", "R1"]], ["Comment", "REF"])
    win._clear_clean_alert()

    def boom(*_args, **_kwargs):
        raise ValueError("import boom")

    monkeypatch.setattr(clean_tab, "import_bom_comment_inputs", boom)
    messages: list[str] = []

    def capture(text: str, _level: str) -> None:
        messages.append(text)

    win.log_message.connect(capture)
    try:
        win._clean_import()
    finally:
        win.log_message.disconnect(capture)
    assert win.clean_alert_frame.isHidden() is False
    assert win.lbl_clean_alert.text() == win.ui_tr("clean.err_import_failed")
    assert any("Import failed" in message for message in messages)


def test_apply_failure_reaches_strip_and_log(main_window, monkeypatch) -> None:
    import ui.clean_tab as clean_tab

    win = main_window
    win.tabs.setCurrentIndex(win._tab_index("clean_bom"))
    bom = pd.DataFrame({"comment": ["old"], "REF": ["R1"]})
    win._bom_df = bom
    win.bom_model.update_dataframe(bom)
    win._clean_source_column = "comment"
    win._clean_source_indices = [0]
    win._clean_last_preview = [{"Cleaned": "new"}]
    win._clean_applying = False
    win._hide_clean_apply_banner()
    win._clear_clean_alert()

    def boom(*_args, **_kwargs):
        raise ValueError("apply boom")

    monkeypatch.setattr(clean_tab, "apply_clean_preview_to_bom", boom)
    messages: list[str] = []

    def capture(text: str, _level: str) -> None:
        messages.append(text)

    win.log_message.connect(capture)
    try:
        win._clean_apply()
    finally:
        win.log_message.disconnect(capture)
    assert win.clean_alert_frame.isHidden() is False
    assert win.lbl_clean_alert.text() == win.ui_tr("clean.err_apply_failed")
    assert win.clean_apply_ok_banner.isHidden() is True
    assert win._clean_applying is False
    assert any("Apply failed" in message for message in messages)


@pytest.mark.parametrize("size", [(1000, 650), (1920, 1080), (2600, 1200)])
def test_expanded_rules_splitter_gets_usable_space(
    qapp, tmp_path, size: tuple[int, int]
) -> None:
    from app.window import MainWindow

    settings = QtCore.QSettings(
        str(tmp_path / "split.ini"), QtCore.QSettings.Format.IniFormat
    )
    settings.setValue("experimental/enable_step_3d", False)
    settings.setValue("clean/options_expanded", True)
    win = MainWindow(settings=settings)
    try:
        win.resize(*size)
        win.tabs.setCurrentIndex(win._tab_index("clean_bom"))
        win.show()
        qapp.processEvents()
        win._apply_default_clean_splitter_sizes()
        qapp.processEvents()
        table_h, rules_h = win.clean_splitter.sizes()
        total = table_h + rules_h
        assert rules_h >= max(120, int(total * 0.35)), (size, table_h, rules_h)
        assert win.clean_preview_stack.height() >= (
            win.clean_preview_stack.minimumHeight() - 1
        )
        assert win.clean_options_panel.isHidden() is False
        assert win.clean_options_panel.height() > 0
        grid = win.clean_rules_grid
        if size[0] >= 2600:
            assert win._clean_rules_layout_mode == "side"
            pos = grid.getItemPosition(grid.indexOf(win.gb_clean_everyday))
            assert pos[:2] == (0, 0)
            assert grid.itemAtPosition(0, 0).widget() is win.gb_clean_everyday
            assert grid.itemAtPosition(0, 1).widget() is win.gb_clean_advanced
        elif size[0] < 1280:
            assert win._clean_rules_layout_mode == "stack"
            assert grid.itemAtPosition(1, 0).widget() is win.gb_clean_advanced
    finally:
        win.close()
