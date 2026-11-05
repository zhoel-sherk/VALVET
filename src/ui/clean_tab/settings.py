"""Settings: UI <-> CleanConfig, presets, persistence."""

from __future__ import annotations

from typing import Any

from PySide6 import QtWidgets

from app.constants import _RCL_ROW_DISABLED_STYLE
from clean_component import CleanConfig
from clean_debug_dialog import load_pipeline_from_settings
from services.clean_config import build_clean_config
from ui.clean_prefs import CleanPrefs
from ui.clean_tab.helpers import _CLEAN_PRESET_COMPACT, _CLEAN_PRESET_SMT


class CleanSettingsMixin:
    def _clean_template_tuple(self, combos: list) -> tuple[str, ...]:
        return tuple(self._template_from_combos(combos))

    def _sync_clean_preset_from_combos(self) -> None:
        if getattr(self, "_applying_clean_preset", False):
            return
        if not hasattr(self, "clean_format_preset"):
            return
        res = self._clean_template_tuple(self.clean_res_template_combos)
        cap = self._clean_template_tuple(self.clean_cap_template_combos)
        ind = self._clean_template_tuple(self.clean_ind_template_combos)
        if (
            res == _CLEAN_PRESET_SMT["res"]
            and cap == _CLEAN_PRESET_SMT["cap"]
            and ind == _CLEAN_PRESET_SMT["ind"]
        ):
            key = "smt"
        elif (
            res == _CLEAN_PRESET_COMPACT["res"]
            and cap == _CLEAN_PRESET_COMPACT["cap"]
            and ind == _CLEAN_PRESET_COMPACT["ind"]
        ):
            key = "compact"
        else:
            key = "custom"
        idx = self.clean_format_preset.findData(key)
        self.clean_format_preset.blockSignals(True)
        if idx >= 0:
            self.clean_format_preset.setCurrentIndex(idx)
        self.clean_format_preset.blockSignals(False)
        self._set_clean_custom_slots_visible(key == "custom")

    def _on_clean_preset_changed(self, *_args) -> None:
        if getattr(self, "_applying_clean_preset", False):
            return
        if not hasattr(self, "clean_res_template_combos"):
            return
        key = self.clean_format_preset.currentData()
        if key == "custom":
            self._set_clean_custom_slots_visible(True)
            return
        preset = _CLEAN_PRESET_SMT if key == "smt" else _CLEAN_PRESET_COMPACT
        self._applying_clean_preset = True
        try:
            self._set_template_combos(
                self.clean_res_template_combos, ",".join(preset["res"]), preset["res"]
            )
            self._set_template_combos(
                self.clean_cap_template_combos, ",".join(preset["cap"]), preset["cap"]
            )
            self._set_template_combos(
                self.clean_ind_template_combos, ",".join(preset["ind"]), preset["ind"]
            )
        finally:
            self._applying_clean_preset = False
        self._set_clean_custom_slots_visible(False)
        self._update_clean_rcl_examples()
        self._save_clean_settings()

    def _clean_output_separator(self) -> str:
        d = self.clean_spacer_combo.currentData()
        if d == "cust":
            return self.clean_spacer_cust.text()
        if isinstance(d, str):
            return d
        return "_"

    def _on_clean_spacer_changed(self) -> None:
        d = self.clean_spacer_combo.currentData()
        if d == "cust":
            self.clean_spacer_cust.setEnabled(True)
        else:
            self.clean_spacer_cust.setEnabled(False)
            self.clean_spacer_cust.clear()
        self._save_clean_settings()

    def _apply_clean_spacer_to_ui(self, sep: str) -> None:
        """Set combo and optional custom line from a saved output_separator string."""
        for i in range(self.clean_spacer_combo.count()):
            data = self.clean_spacer_combo.itemData(i)
            if data == "cust" or data is None:
                continue
            if data == sep:
                self.clean_spacer_combo.setCurrentIndex(i)
                self.clean_spacer_cust.setEnabled(False)
                self.clean_spacer_cust.clear()
                return
        idx = self.clean_spacer_combo.findData("cust")
        if idx < 0:
            return
        self.clean_spacer_combo.setCurrentIndex(idx)
        self.clean_spacer_cust.setText(sep)
        self.clean_spacer_cust.setEnabled(True)

    def _on_gb_clean_res_toggled(self, on: bool) -> None:
        for w in (
            *self.clean_res_template_combos,
            self.clean_res_prefix,
            self.clean_res_ohm_r,
            self.clean_res_watt_from_pack,
        ):
            w.setEnabled(on)
        self.clean_res_frame.setProperty("rclDisabled", not on)
        self.clean_res_frame.setStyleSheet(_RCL_ROW_DISABLED_STYLE if not on else "")
        self.clean_res_frame.style().unpolish(self.clean_res_frame)
        self.clean_res_frame.style().polish(self.clean_res_frame)
        self._update_clean_rcl_examples()
        self._save_clean_settings()

    def _on_clean_regex_master_toggled(self, on: bool) -> None:
        self.clean_regex_master_scores.setEnabled(on)
        if not on:
            self.clean_regex_master_scores.setChecked(False)
        self._save_clean_settings()

    def _on_gb_clean_cap_toggled(self, on: bool) -> None:
        for w in (
            *self.clean_cap_template_combos,
            self.clean_cap_nf,
            self.clean_cap_uf_micro,
            self.clean_cap_prefix,
        ):
            w.setEnabled(on)
        self.clean_cap_frame.setProperty("rclDisabled", not on)
        self.clean_cap_frame.setStyleSheet(_RCL_ROW_DISABLED_STYLE if not on else "")
        self.clean_cap_frame.style().unpolish(self.clean_cap_frame)
        self.clean_cap_frame.style().polish(self.clean_cap_frame)
        self._update_clean_rcl_examples()
        self._save_clean_settings()

    def _on_gb_clean_ind_toggled(self, on: bool) -> None:
        for w in (*self.clean_ind_template_combos, self.clean_ind_prefix):
            w.setEnabled(on)
        self.clean_ind_frame.setProperty("rclDisabled", not on)
        self.clean_ind_frame.setStyleSheet(_RCL_ROW_DISABLED_STYLE if not on else "")
        self.clean_ind_frame.style().unpolish(self.clean_ind_frame)
        self.clean_ind_frame.style().polish(self.clean_ind_frame)
        self._update_clean_rcl_examples()
        self._save_clean_settings()

    def _on_gb_clean_pn_toggled(self, on: bool) -> None:
        self.clean_use_vendor.setEnabled(on)
        self._save_clean_settings()

    def _save_clean_mpn_lookup_settings(self) -> None:
        if getattr(self, "_restoring_settings", False) or not hasattr(
            self, "_settings"
        ):
            return
        s = self._settings
        prov = self.clean_mpn_search_provider.currentData()
        s.setValue("clean/mpn_search_provider", prov if prov else "digikey")
        s.setValue("clean/octopart_api_key", self.clean_octopart_api_key.text())

    def _template_from_combos(
        self, combos: list[QtWidgets.QComboBox]
    ) -> tuple[str, ...]:
        values: list[str] = []
        for combo in combos:
            data = combo.currentData()
            key = str(data) if data is not None else "none"
            values.append(key)
        return tuple(values)

    def _set_template_combos(
        self, combos: list[QtWidgets.QComboBox], raw: object, default: tuple[str, ...]
    ) -> None:
        if isinstance(raw, str) and raw.strip():
            values = [x.strip() for x in raw.split(",")]
        else:
            values = list(default)
        for i, combo in enumerate(combos):
            key = values[i] if i < len(values) else "none"
            if key == "W":
                key = "V"
            # Legacy: cap voltage combo used addItem("V", "V (volt)") — userData was wrong.
            if key == "V (volt)":
                key = "V"
            idx = combo.findData(key)
            if idx < 0:
                idx = combo.findData("none")
            if idx >= 0:
                combo.setCurrentIndex(idx)

    def _clean_config_from_ui(self) -> CleanConfig:
        res_template = self._template_from_combos(self.clean_res_template_combos)
        cap_template = self._template_from_combos(self.clean_cap_template_combos)
        ind_template = self._template_from_combos(self.clean_ind_template_combos)
        hanwha_names = None
        if self.clean_from_hanwha_mdb.isChecked() and hasattr(
            self, "_machine_library_tab"
        ):
            hs = self._machine_library_tab.machine_partname_set()
            hanwha_names = hs if hs else None
        pipe_order, pipe_disabled = load_pipeline_from_settings(self._settings)
        regex_master_enabled = self.clean_regex_master.isChecked()
        regex_master_preview_scores = (
            regex_master_enabled and self.clean_regex_master_scores.isChecked()
        )
        return build_clean_config(
            res_template=res_template,
            cap_template=cap_template,
            ind_template=ind_template,
            cap_nf_to_uf=self.clean_cap_nf.isChecked(),
            cap_uf_micro_sign=self.clean_cap_uf_micro.isChecked(),
            res_ohm_r_suffix=self.clean_res_ohm_r.isChecked(),
            infer_resistor_watt_from_package=self.clean_res_watt_from_pack.isChecked(),
            use_pn_codecs=self.gb_clean_pn.isChecked(),
            use_vendor_pn=self.gb_clean_pn.isChecked()
            and self.clean_use_vendor.isChecked(),
            parse_resistors=self.chk_clean_res.isChecked(),
            parse_capacitors=self.chk_clean_cap.isChecked(),
            parse_inductors=self.chk_clean_ind.isChecked(),
            output_separator=self._clean_output_separator(),
            # Raw Original cells are evaluated independently; legacy split is off.
            double_comment_separator=None,
            combine_input_columns=self.clean_combine_inputs.isChecked(),
            res_prefix=self.clean_res_prefix.text().strip(),
            cap_prefix=self.clean_cap_prefix.text().strip(),
            ind_prefix=self.clean_ind_prefix.text().strip(),
            prefix_use_separator=self.clean_prefix_use_separator.isChecked(),
            use_component_library=self.clean_from_db.isChecked(),
            use_hanwha_mdb=self.clean_from_hanwha_mdb.isChecked(),
            hanwha_partial_match=self.clean_hanwha_partial_match.isChecked(),
            hanwha_partnames=hanwha_names,
            clean_pipeline_order=pipe_order,
            clean_pipeline_disabled=pipe_disabled,
            component_library_path=None,
            regex_master_enabled=regex_master_enabled,
            regex_master_preview_scores=regex_master_preview_scores,
            settings_getter=lambda k, d: str(self._settings.value(k, d) or ""),
        )

    def _save_clean_settings(self) -> None:
        if getattr(self, "_restoring_settings", False) or not hasattr(
            self, "_settings"
        ):
            return
        s = self._settings
        s.setValue(
            "clean/res_template",
            ",".join(self._template_from_combos(self.clean_res_template_combos)),
        )
        s.setValue(
            "clean/cap_template",
            ",".join(self._template_from_combos(self.clean_cap_template_combos)),
        )
        s.setValue(
            "clean/ind_template",
            ",".join(self._template_from_combos(self.clean_ind_template_combos)),
        )
        s.setValue("clean/cap_nf", self.clean_cap_nf.isChecked())
        s.setValue("clean/cap_uf_micro", self.clean_cap_uf_micro.isChecked())
        s.setValue("clean/res_ohm_r_suffix", self.clean_res_ohm_r.isChecked())
        s.setValue(
            "clean/infer_resistor_watt_from_package",
            self.clean_res_watt_from_pack.isChecked(),
        )
        s.setValue("clean/use_vendor", self.clean_use_vendor.isChecked())
        s.setValue("clean/group_res", self.chk_clean_res.isChecked())
        s.setValue("clean/group_cap", self.chk_clean_cap.isChecked())
        s.setValue("clean/group_ind", self.chk_clean_ind.isChecked())
        s.setValue("clean/group_pn", self.gb_clean_pn.isChecked())
        s.setValue("clean/output_separator", self._clean_output_separator())
        s.setValue("clean/res_prefix", self.clean_res_prefix.text().strip())
        s.setValue("clean/cap_prefix", self.clean_cap_prefix.text().strip())
        s.setValue("clean/ind_prefix", self.clean_ind_prefix.text().strip())
        s.setValue(
            "clean/prefix_use_separator", self.clean_prefix_use_separator.isChecked()
        )
        if hasattr(self, "clean_from_db"):
            s.setValue("clean/from_db", self.clean_from_db.isChecked())
        if hasattr(self, "clean_from_hanwha_mdb"):
            s.setValue("clean/from_hanwha_mdb", self.clean_from_hanwha_mdb.isChecked())
        if hasattr(self, "clean_hanwha_partial_match"):
            s.setValue(
                "clean/hanwha_partial_match",
                self.clean_hanwha_partial_match.isChecked(),
            )
        if hasattr(self, "clean_regex_master"):
            s.setValue(
                "clean/regex_master_enabled",
                self.clean_regex_master.isChecked(),
            )
            s.setValue(
                "clean/regex_master_preview_scores",
                self.clean_regex_master_scores.isChecked(),
            )
        s.setValue("clean/combine_input_columns", self.clean_combine_inputs.isChecked())
        # Legacy Replace-source toggle removed; drop its old persisted key.
        s.remove("clean/apply_replace")
        if hasattr(self, "btn_clean_options_toggle"):
            s.setValue(
                "clean/options_expanded",
                self.btn_clean_options_toggle.isChecked(),
            )
        self._save_clean_splitter_sizes()
        self._update_clean_rules_summary()

    def _gather_clean_prefs_payload(self) -> dict[str, Any]:
        if not hasattr(self, "clean_res_template_combos"):
            return {}
        prov = "digikey"
        if hasattr(self, "clean_mpn_search_provider"):
            prov = self.clean_mpn_search_provider.currentData() or "digikey"
        key = str(prov) if prov is not None else "digikey"
        return CleanPrefs(
            res_template=",".join(
                self._template_from_combos(self.clean_res_template_combos)
            ),
            cap_template=",".join(
                self._template_from_combos(self.clean_cap_template_combos)
            ),
            ind_template=",".join(
                self._template_from_combos(self.clean_ind_template_combos)
            ),
            cap_nf=self.clean_cap_nf.isChecked(),
            cap_uf_micro=self.clean_cap_uf_micro.isChecked(),
            res_ohm_r_suffix=self.clean_res_ohm_r.isChecked(),
            infer_resistor_watt_from_package=self.clean_res_watt_from_pack.isChecked(),
            use_vendor=self.clean_use_vendor.isChecked(),
            from_db=self.clean_from_db.isChecked(),
            from_hanwha_mdb=self.clean_from_hanwha_mdb.isChecked(),
            hanwha_partial_match=self.clean_hanwha_partial_match.isChecked(),
            regex_master_enabled=self.clean_regex_master.isChecked(),
            regex_master_preview_scores=self.clean_regex_master_scores.isChecked(),
            prefix_use_separator=self.clean_prefix_use_separator.isChecked(),
            res_prefix=self.clean_res_prefix.text(),
            cap_prefix=self.clean_cap_prefix.text(),
            ind_prefix=self.clean_ind_prefix.text(),
            group_res=self.chk_clean_res.isChecked(),
            group_cap=self.chk_clean_cap.isChecked(),
            group_ind=self.chk_clean_ind.isChecked(),
            group_pn=self.gb_clean_pn.isChecked(),
            combine_input_columns=self.clean_combine_inputs.isChecked(),
            output_separator=self._clean_output_separator(),
            mpn_search_provider=key,
            octopart_api_key=self.clean_octopart_api_key.text()
            if hasattr(self, "clean_octopart_api_key")
            else "",
            options_expanded=self.btn_clean_options_toggle.isChecked()
            if hasattr(self, "btn_clean_options_toggle")
            else False,
        ).to_dict()

    def _apply_clean_prefs_dict(self, c: dict[str, Any]) -> None:
        if not hasattr(self, "clean_res_template_combos"):
            return
        prefs = CleanPrefs.from_dict(c)
        if hasattr(self, "chk_clean_res"):
            for gb in (
                self.chk_clean_res,
                self.chk_clean_cap,
                self.chk_clean_ind,
                self.gb_clean_pn,
            ):
                gb.blockSignals(True)
        for w in (
            *self.clean_res_template_combos,
            *self.clean_cap_template_combos,
            *self.clean_ind_template_combos,
            self.clean_cap_nf,
            self.clean_cap_uf_micro,
            self.clean_use_vendor,
            self.clean_from_db,
            self.clean_from_hanwha_mdb,
            self.clean_hanwha_partial_match,
            self.clean_prefix_use_separator,
            self.clean_res_prefix,
            self.clean_res_ohm_r,
            self.clean_res_watt_from_pack,
            self.clean_cap_prefix,
            self.clean_ind_prefix,
            self.clean_combine_inputs,
        ):
            w.blockSignals(True)
        self._set_template_combos(
            self.clean_res_template_combos,
            prefs.res_template,
            ("nom", "pack", "watt", "%"),
        )
        self._set_template_combos(
            self.clean_cap_template_combos,
            prefs.cap_template,
            ("nom", "pack", "film", "%", "V"),
        )
        self._set_template_combos(
            self.clean_ind_template_combos,
            prefs.ind_template,
            ("pack", "nom", "%", "Imax", "DCR"),
        )
        self.clean_cap_nf.setChecked(prefs.cap_nf)
        self.clean_cap_uf_micro.setChecked(prefs.cap_uf_micro)
        self.clean_res_ohm_r.setChecked(prefs.res_ohm_r_suffix)
        self.clean_res_watt_from_pack.setChecked(prefs.infer_resistor_watt_from_package)
        self.clean_use_vendor.setChecked(prefs.use_vendor)
        self.clean_from_db.setChecked(prefs.from_db)
        self.clean_from_hanwha_mdb.setChecked(prefs.from_hanwha_mdb)
        self.clean_hanwha_partial_match.setChecked(prefs.hanwha_partial_match)
        if hasattr(self, "clean_regex_master"):
            rm = prefs.regex_master_enabled
            self.clean_regex_master.blockSignals(True)
            self.clean_regex_master.setChecked(rm)
            self.clean_regex_master.blockSignals(False)
            self.clean_regex_master_scores.setEnabled(rm)
            self.clean_regex_master_scores.blockSignals(True)
            self.clean_regex_master_scores.setChecked(
                rm and prefs.regex_master_preview_scores
            )
            self.clean_regex_master_scores.blockSignals(False)
        self.clean_prefix_use_separator.setChecked(prefs.prefix_use_separator)
        self.clean_res_prefix.setText(prefs.res_prefix)
        self.clean_cap_prefix.setText(prefs.cap_prefix)
        self.clean_ind_prefix.setText(prefs.ind_prefix)
        if hasattr(self, "chk_clean_res"):
            self.chk_clean_res.setChecked(prefs.group_res)
            self.chk_clean_cap.setChecked(prefs.group_cap)
            self.chk_clean_ind.setChecked(prefs.group_ind)
            self.gb_clean_pn.setChecked(prefs.group_pn)
        self.clean_combine_inputs.setChecked(prefs.combine_input_columns)
        self.clean_spacer_combo.blockSignals(True)
        self.clean_spacer_cust.blockSignals(True)
        self._apply_clean_spacer_to_ui(prefs.output_separator)
        self.clean_spacer_combo.blockSignals(False)
        self.clean_spacer_cust.blockSignals(False)
        for w in (
            *self.clean_res_template_combos,
            *self.clean_cap_template_combos,
            *self.clean_ind_template_combos,
            self.clean_cap_nf,
            self.clean_cap_uf_micro,
            self.clean_use_vendor,
            self.clean_from_db,
            self.clean_from_hanwha_mdb,
            self.clean_hanwha_partial_match,
            self.clean_prefix_use_separator,
            self.clean_res_prefix,
            self.clean_res_ohm_r,
            self.clean_res_watt_from_pack,
            self.clean_cap_prefix,
            self.clean_ind_prefix,
            self.clean_combine_inputs,
        ):
            w.blockSignals(False)
        if hasattr(self, "clean_mpn_search_provider"):
            self.clean_mpn_search_provider.blockSignals(True)
            self.clean_octopart_api_key.blockSignals(True)
            prov = prefs.mpn_search_provider
            for i in range(self.clean_mpn_search_provider.count()):
                if self.clean_mpn_search_provider.itemData(i) == prov:
                    self.clean_mpn_search_provider.setCurrentIndex(i)
                    break
            self.clean_octopart_api_key.setText(prefs.octopart_api_key)
            self.clean_mpn_search_provider.blockSignals(False)
            self.clean_octopart_api_key.blockSignals(False)
        if hasattr(self, "chk_clean_res"):
            for gb in (
                self.chk_clean_res,
                self.chk_clean_cap,
                self.chk_clean_ind,
                self.gb_clean_pn,
            ):
                gb.blockSignals(False)
            self._on_gb_clean_res_toggled(self.chk_clean_res.isChecked())
            self._on_gb_clean_cap_toggled(self.chk_clean_cap.isChecked())
            self._on_gb_clean_ind_toggled(self.chk_clean_ind.isChecked())
            self._on_gb_clean_pn_toggled(self.gb_clean_pn.isChecked())
        if hasattr(self, "btn_clean_options_toggle"):
            expanded = prefs.options_expanded
            self.btn_clean_options_toggle.blockSignals(True)
            self.btn_clean_options_toggle.setChecked(expanded)
            self.btn_clean_options_toggle.blockSignals(False)
            self._apply_clean_options_visibility(expanded)
        self._sync_clean_preset_from_combos()
        self._sync_clean_preview_view()
        self._sync_clean_primary_buttons()
        self._update_clean_rules_summary()
