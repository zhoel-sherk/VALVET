"""Translatable static texts and live examples."""

from __future__ import annotations

import logger
from parsers.formatting import (
    format_cap_fields,
    format_inductor_fields,
    format_resistor_fields,
)


class CleanTextsMixin:
    def _refresh_clean_tab_static_texts(self) -> None:
        if not hasattr(self, "btn_clean_import"):
            return
        self.btn_clean_help.setToolTip(self.ui_tr("clean.help_title"))
        self.gb_clean_parser.setTitle(self.ui_tr("clean.everyday"))
        self.gb_clean_everyday.setTitle("")
        self.gb_clean_advanced.setTitle("")
        self.lbl_clean_spacer.setText(self.ui_tr("clean.spacer"))
        self.clean_spacer_cust.setPlaceholderText(self.ui_tr("clean.spacer_custom"))
        _si = self.clean_spacer_combo.currentIndex()
        self.clean_spacer_combo.blockSignals(True)
        for i, key in enumerate(
            (
                "clean.spacer_underscore",
                "clean.spacer_hyphen",
                "clean.spacer_space",
                "clean.spacer_tab",
                "clean.spacer_custom_item",
            )
        ):
            if i < self.clean_spacer_combo.count():
                self.clean_spacer_combo.setItemText(i, self.ui_tr(key))
        self.clean_spacer_combo.setCurrentIndex(_si)
        self.clean_spacer_combo.blockSignals(False)
        self.clean_from_db.setText(self.ui_tr("clean.from_db"))
        self.clean_from_db.setToolTip(self.ui_tr("clean.from_db_tip"))
        self.clean_from_hanwha_mdb.setText(self.ui_tr("clean.from_machine"))
        self.clean_from_hanwha_mdb.setToolTip(self.ui_tr("clean.from_machine_tip"))
        self.gb_clean_pn.setText(self.ui_tr("clean.pn"))
        self.gb_clean_pn.setToolTip(self.ui_tr("clean.pn_tip"))
        self.clean_use_vendor.setText(self.ui_tr("clean.pn_vendor_label"))
        self.clean_use_vendor.setToolTip(self.ui_tr("clean.pn_vendor_tip"))
        self.lbl_clean_preset.setText(self.ui_tr("clean.preset"))
        self.clean_format_preset.blockSignals(True)
        self.clean_format_preset.setItemText(0, self.ui_tr("clean.preset_smt"))
        self.clean_format_preset.setItemText(1, self.ui_tr("clean.preset_compact"))
        self.clean_format_preset.setItemText(2, self.ui_tr("clean.preset_custom"))
        self.clean_format_preset.blockSignals(False)
        self.clean_prefix_use_separator.setText(self.ui_tr("clean.prefix_spacer"))
        self.clean_prefix_use_separator.setToolTip(
            self.ui_tr("clean.prefix_spacer_tip")
        )
        self.lbl_clean_double_join.setText(self.ui_tr("clean.combine_inputs"))
        self.clean_combine_inputs.setToolTip(self.ui_tr("clean.combine_inputs_tip"))
        if hasattr(self, "btn_clean_pn_join_help"):
            self.btn_clean_pn_join_help.setToolTip(
                self.ui_tr("mapping.pn_join_help_title")
            )
        self.btn_clean_debug.setText(self.ui_tr("clean.advanced_debug"))
        self.btn_clean_debug.setToolTip(self.ui_tr("clean.advanced_debug_tip"))
        self.clean_hanwha_partial_match.setText(self.ui_tr("clean.partial_match"))
        self.clean_hanwha_partial_match.setToolTip(
            self.ui_tr("clean.partial_match_tip")
        )
        self.clean_regex_master.setText(self.ui_tr("clean.regex_master"))
        self.clean_regex_master.setToolTip(self.ui_tr("clean.regex_master_tip"))
        self.clean_regex_master_scores.setText(self.ui_tr("clean.regex_master_scores"))
        self.clean_regex_master_scores.setToolTip(
            self.ui_tr("clean.regex_master_scores_tip")
        )
        self.chk_clean_res.setText(self.ui_tr("clean.resistor"))
        self.chk_clean_res.setToolTip(self.ui_tr("clean.resistor_tip"))
        self.chk_clean_cap.setText(self.ui_tr("clean.capacitor"))
        self.chk_clean_cap.setToolTip(self.ui_tr("clean.capacitor_tip"))
        self.chk_clean_ind.setText(self.ui_tr("clean.inductor"))
        self.chk_clean_ind.setToolTip(self.ui_tr("clean.inductor_tip"))
        self.lbl_clean_res_prefix.setText(self.ui_tr("clean.prefix"))
        self.lbl_clean_cap_prefix.setText(self.ui_tr("clean.prefix"))
        self.lbl_clean_ind_prefix.setText(self.ui_tr("clean.prefix"))
        if hasattr(self, "lbl_clean_rcl_type_hdr"):
            self.lbl_clean_rcl_type_hdr.setText(self.ui_tr("clean.rcl_type"))
        if hasattr(self, "lbl_clean_rcl_prefix_hdr"):
            self.lbl_clean_rcl_prefix_hdr.setText(self.ui_tr("clean.prefix"))
        self.clean_res_ohm_r.setText(self.ui_tr("clean.ohm_r"))
        self.clean_res_ohm_r.setToolTip(self.ui_tr("clean.ohm_r_tip"))
        self.clean_res_watt_from_pack.setText(self.ui_tr("clean.watt_from_pack"))
        self.clean_res_watt_from_pack.setToolTip(self.ui_tr("clean.watt_from_pack_tip"))
        self.clean_cap_nf.setText(self.ui_tr("clean.cap_nf"))
        self.clean_cap_uf_micro.setText(self.ui_tr("clean.cap_uf_micro"))
        self.clean_cap_uf_micro.setToolTip(self.ui_tr("clean.cap_uf_micro_tip"))
        self.gb_clean_mpn.setTitle(self.ui_tr("clean.mpn_group"))
        self.lbl_clean_mpn_search.setText(self.ui_tr("clean.mpn_search_label"))
        self.btn_mpn_open_search.setText(self.ui_tr("clean.mpn_open"))
        self.btn_clean_import.setText(self.ui_tr("clean.btn_import"))
        self.btn_clean_import.setToolTip(self.ui_tr("clean.btn_import_tip"))
        self.btn_clean_convert.setText(self.ui_tr("clean.btn_convert"))
        self.btn_clean_convert.setToolTip(self.ui_tr("clean.btn_convert_tip"))
        self.btn_clean_apply.setText(self.ui_tr("clean.btn_apply"))
        self.btn_clean_apply.setToolTip(self.ui_tr("clean.btn_apply_tip"))
        self.btn_clean_save.setText(self.ui_tr("clean.btn_save"))
        self.btn_clean_go_bom.setText(self.ui_tr("clean.go_to_bom"))
        self.btn_clean_options_toggle.setText(self.ui_tr("clean.rules_toggle"))
        self.btn_clean_options_toggle.setToolTip(self.ui_tr("clean.rules_toggle_tip"))
        self.lbl_clean_empty_title.setText(self.ui_tr("clean.empty_title"))
        self.lbl_clean_empty_hint.setText(self.ui_tr("clean.empty_hint"))
        self.btn_clean_empty_bom.setText(self.ui_tr("clean.empty_bom"))
        self.lbl_clean_stale.setText(self.ui_tr("clean.stale_badge"))
        self._render_clean_alert()
        for btn, name in (
            (self.btn_clean_import, "clean.btn_import"),
            (self.btn_clean_convert, "clean.btn_convert"),
            (self.btn_clean_apply, "clean.btn_apply"),
            (self.btn_clean_learn_other, "clean.btn_learn"),
            (self.btn_clean_save, "clean.btn_save"),
            (self.btn_clean_empty_bom, "clean.empty_bom"),
            (self.btn_clean_options_toggle, "clean.rules_toggle"),
        ):
            btn.setAccessibleName(self.ui_tr(name))
        self.clean_preview_table.setAccessibleName(self.ui_tr("clean.preview_aria"))
        self.clean_preview_empty.setAccessibleName(self.ui_tr("clean.empty_title"))
        self.lbl_clean_source.setAccessibleName(self.ui_tr("clean.summary_aria"))
        self.lbl_clean_rules_summary.setAccessibleName(self.ui_tr("clean.rules_toggle"))
        self.clean_splitter.setAccessibleName(self.ui_tr("clean.preview_aria"))
        for lbl in (
            self.lbl_clean_res_prefix,
            self.lbl_clean_cap_prefix,
            self.lbl_clean_ind_prefix,
        ):
            lbl.setToolTip(self.ui_tr("clean.tip_prefix"))
        for combo in (
            *self.clean_res_template_combos,
            *self.clean_cap_template_combos,
            *self.clean_ind_template_combos,
        ):
            combo.setToolTip(self.ui_tr("clean.tip_slot_order"))
        for h in getattr(self, "_clean_rcl_slot_headers", []):
            h.setToolTip(self.ui_tr("clean.tip_slot_order"))
        self._sync_clean_parser_grid_sizes()
        self._sync_clean_primary_buttons()
        self._sync_clean_preview_view()
        self._update_clean_rules_summary()
        self._update_clean_preview_min_height()

    def _update_clean_rcl_examples(self) -> None:
        if not hasattr(self, "lbl_clean_res_example"):
            return
        cfg = self._clean_config_from_ui()
        raw_res = "0402 12K 1%"
        raw_cap = "0402 12pF 5%"
        raw_ind = "4.7uH 0805"
        try:
            res_out = format_resistor_fields(
                {"pack": "0402", "nom": "12K", "%": "1%"}, cfg
            )
            cap_out = format_cap_fields({"pack": "0402", "nom": "12pF", "%": "5%"}, cfg)
            ind_out = format_inductor_fields({"pack": "0805", "nom": "4.7uH"}, cfg)
        except Exception as e:
            # Example previews are decorative; a formatter failure must not
            # break the tab, so show "—" and keep the reason in the log.
            logger.warning("Clean BOM: rules example formatting failed: %s", e)
            res_out = cap_out = ind_out = ""
        self.lbl_clean_res_example.setText(
            self.ui_tr("clean.example_res", raw=raw_res, out=res_out or "—")
        )
        self.lbl_clean_cap_example.setText(
            self.ui_tr("clean.example_cap", raw=raw_cap, out=cap_out or "—")
        )
        self.lbl_clean_ind_example.setText(
            self.ui_tr("clean.example_ind", raw=raw_ind, out=ind_out or "—")
        )
