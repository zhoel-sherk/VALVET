"""Profile storage and legacy settings (MainWindow mixin)."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from PySide6 import QtWidgets
from PySide6.QtCore import QSettings

from app.constants import (
    PROFILE_LAST_ACTIVE_KEY,
    PROFILE_NAMES_KEY,
    PROFILE_STATE_VERSION,
)
from themes.colour_prefs import merge_table_colours, merge_ui_colours
from ui.project_tab import configure_path_label
from ui_i18n import SUPPORTED_UI_LOCALES


class ProfilesMixin:

    @staticmethod
    def _sanitize_profile_id(name: str) -> str:
        t = (name or "").strip().replace(" ", "_")
        if not t:
            return "default"
        out = re.sub(r"[^a-zA-Z0-9_-]", "", t)
        return out[:64] or "default"

    def _current_profile_id(self) -> str:
        return self._sanitize_profile_id(self.profile_combo.currentText())

    def _load_profile_combo_from_storage(self) -> None:
        s = self._settings
        raw = str(s.value(PROFILE_NAMES_KEY, "") or "").strip()
        names: list[str] = ["default"]
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list) and parsed:
                    names = [str(x) for x in parsed]
            except json.JSONDecodeError:
                pass
        names = [self._sanitize_profile_id(x) for x in names]
        if "default" not in names:
            names.insert(0, "default")
        last = self._sanitize_profile_id(
            str(s.value(PROFILE_LAST_ACTIVE_KEY, "default") or "default")
        )
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        for n in names:
            if self.profile_combo.findText(n) < 0:
                self.profile_combo.addItem(n)
        idx = self.profile_combo.findText(last)
        self.profile_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.profile_combo.blockSignals(False)

    def _gather_profile_payload(self) -> dict[str, Any]:
        bom_maps: list[str] = []
        if getattr(self, "bom_col_combos", None):
            bom_maps = self._mapping_roles_from_combos(self.bom_col_combos)
        pnp_maps: list[str] = []
        if getattr(self, "pnp_col_combos", None):
            pnp_maps = self._mapping_roles_from_combos(self.pnp_col_combos)
        pcb: dict[str, Any] = {}
        if hasattr(self, "_pcb_tab") and hasattr(self._pcb_tab, "export_ui_prefs"):
            pcb = self._pcb_tab.export_ui_prefs()
        lang = "en"
        if hasattr(self, "lang_combo"):
            lang = str(self.lang_combo.currentData() or "en")
        return {
            "v": PROFILE_STATE_VERSION,
            "ui": {
                "language": lang if lang in SUPPORTED_UI_LOCALES else "en",
                "colorful_logs": self.chk_colorful.isChecked()
                if hasattr(self, "chk_colorful")
                else True,
                "colours": dict(self._ui_colours),
            },
            "bom": {
                "separator": self.bom_separator.currentText(),
                "first_row": self.bom_first_row.text(),
                "last_row": self.bom_last_row.text(),
                "mappings": bom_maps,
            },
            "pnp": {
                "separator": self.pnp_separator.currentText(),
                "first_row": self.pnp_first_row.text(),
                "last_row": self.pnp_last_row.text(),
                "units": "mm" if self._pnp_xy_stored_in_mm() else "mils",
                "mappings": pnp_maps,
                "secondary_path": (self._pnp_secondary_path or ""),
                "layer_override": self.chk_pnp_layer_override.isChecked()
                if hasattr(self, "chk_pnp_layer_override")
                else False,
                "layer_tokens": self.edit_pnp_layer_tokens.text()
                if hasattr(self, "edit_pnp_layer_tokens")
                else "",
            },
            "merge": {"delete_dnp": self.merge_delete_dnp.isChecked()},
            "report": {
                "show_critical": self.chk_critical.isChecked(),
                "show_warning": self.chk_warning.isChecked(),
                "show_info": self.chk_info.isChecked(),
                "overlap": self.chk_overlap.isChecked(),
                "overlap_mm": float(self.spin_overlap_mm.value()),
            },
            "clean": self._gather_clean_prefs_payload(),
            "pcb_preview": pcb,
            "session_links": self._session_links_to_payload(),
            "table_colours": dict(self._table_colours),
        }

    def _apply_profile_payload(self, data: dict[str, Any]) -> None:
        ui = data.get("ui") or {}
        lang = str(ui.get("language", "en"))
        if lang not in SUPPORTED_UI_LOCALES:
            lang = "en"
        if hasattr(self, "chk_colorful"):
            self.chk_colorful.setChecked(bool(ui.get("colorful_logs", True)))
        csub = ui.get("colours")
        self._ui_colours = merge_ui_colours(csub if isinstance(csub, dict) else None)
        tc = data.get("table_colours")
        self._table_colours = merge_table_colours(tc if isinstance(tc, dict) else None)
        bom = data.get("bom") or {}
        bsep = str(bom.get("separator", "auto"))
        if self.bom_separator.findText(bsep) >= 0:
            self.bom_separator.setCurrentText(bsep)
        self.bom_first_row.setText(str(bom.get("first_row", "1")))
        self.bom_last_row.setText(str(bom.get("last_row", "")))
        bm = bom.get("mappings")
        self._profile_restore_bom_mappings = (
            [str(x) for x in bm] if isinstance(bm, list) else None
        )
        pnp = data.get("pnp") or {}
        psep = str(pnp.get("separator", "auto"))
        if self.pnp_separator.findText(psep) >= 0:
            self.pnp_separator.setCurrentText(psep)
        self.pnp_first_row.setText(str(pnp.get("first_row", "1")))
        self.pnp_last_row.setText(str(pnp.get("last_row", "")))
        self._apply_pnp_xy_units_everywhere(
            str(pnp.get("units", "mm")).lower() != "mils",
            save_settings=False,
        )
        pm = pnp.get("mappings")
        self._profile_restore_pnp_mappings = (
            [str(x) for x in pm] if isinstance(pm, list) else None
        )
        if hasattr(self, "chk_pnp_layer_override"):
            self.chk_pnp_layer_override.blockSignals(True)
            self.chk_pnp_layer_override.setChecked(
                bool(pnp.get("layer_override", False))
            )
            self.chk_pnp_layer_override.blockSignals(False)
            self.edit_pnp_layer_tokens.setText(str(pnp.get("layer_tokens", "") or ""))
            self._on_pnp_layer_override_toggled(self.chk_pnp_layer_override.isChecked())
        sp2 = str(pnp.get("secondary_path", "") or "").strip()
        if sp2 and os.path.isfile(sp2):
            self._pnp_secondary_path = sp2
            if hasattr(self, "pnp_path2_label"):
                configure_path_label(
                    self.pnp_path2_label,
                    sp2,
                    empty_text=self.ui_tr("project.no_file"),
                )
        else:
            self._pnp_secondary_path = ""
            if hasattr(self, "pnp_path2_label"):
                configure_path_label(
                    self.pnp_path2_label,
                    "",
                    empty_text=self.ui_tr("project.no_file"),
                )
        sl = data.get("session_links")
        self._apply_session_links_payload(sl)
        merge = data.get("merge") or {}
        self.merge_delete_dnp.setChecked(bool(merge.get("delete_dnp", False)))
        rep = data.get("report") or {}
        self.chk_critical.setChecked(bool(rep.get("show_critical", True)))
        self.chk_warning.setChecked(bool(rep.get("show_warning", True)))
        self.chk_info.setChecked(bool(rep.get("show_info", True)))
        self.chk_overlap.blockSignals(True)
        self.spin_overlap_mm.blockSignals(True)
        self.chk_overlap.setChecked(bool(rep.get("overlap", False)))
        self.spin_overlap_mm.setValue(float(rep.get("overlap_mm", 3.0)))
        self.spin_overlap_mm.setEnabled(self.chk_overlap.isChecked())
        self.spin_overlap_mm.blockSignals(False)
        self.chk_overlap.blockSignals(False)
        clean = data.get("clean")
        if isinstance(clean, dict) and clean:
            self._apply_clean_prefs_dict(clean)
        pcb = data.get("pcb_preview")
        if isinstance(pcb, dict) and hasattr(self, "_pcb_tab"):
            self._pcb_tab.apply_ui_prefs(pcb)
        if hasattr(self, "lang_combo"):
            self.lang_combo.blockSignals(True)
            li = self.lang_combo.findData(lang)
            if li >= 0:
                self.lang_combo.setCurrentIndex(li)
            self.lang_combo.blockSignals(False)
        self._apply_ui_language(lang, save=False)
        self._refresh_active_row_highlight("bom")
        self._refresh_active_row_highlight("pnp")

    def _save_full_profile_snapshot(self) -> None:
        if not hasattr(self, "_settings"):
            return
        self._save_clean_settings()
        if hasattr(self, "_save_clean_mpn_lookup_settings"):
            self._save_clean_mpn_lookup_settings()
        self._save_report_overlap_settings()
        if hasattr(self, "chk_critical"):
            self._settings.setValue(
                "report/show_critical", self.chk_critical.isChecked()
            )
            self._settings.setValue("report/show_warning", self.chk_warning.isChecked())
            self._settings.setValue("report/show_info", self.chk_info.isChecked())
        pid = self._current_profile_id()
        payload = self._gather_profile_payload()
        self._settings.setValue(
            f"profiles/{pid}/state_json", json.dumps(payload, ensure_ascii=False)
        )
        self._settings.setValue(PROFILE_LAST_ACTIVE_KEY, pid)
        names = [
            self.profile_combo.itemText(i) for i in range(self.profile_combo.count())
        ]
        self._settings.setValue(PROFILE_NAMES_KEY, json.dumps(names))
        self._settings.remove("files/last_bom")
        self._settings.remove("files/last_pnp")

    def _on_profile_combo_changed(self, _text: str) -> None:
        if getattr(self, "_restoring_settings", False):
            return
        pid = self._current_profile_id()
        self._settings.setValue(PROFILE_LAST_ACTIVE_KEY, pid)
        raw = str(self._settings.value(f"profiles/{pid}/state_json", "") or "").strip()
        if not raw:
            self._log(self.ui_tr("msg.profile_empty_kept_ui", name=pid), "info")
            return
        try:
            self._restoring_settings = True
            self._apply_profile_payload(json.loads(raw))
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            self._log(self.ui_tr("msg.profile_load_failed", err=str(e)), "warning")
        finally:
            self._restoring_settings = False
        self._refresh_application_stylesheet()

    def _on_profile_clone_clicked(self) -> None:
        name, ok = QtWidgets.QInputDialog.getText(
            self,
            self.ui_tr("project.profile_clone"),
            self.ui_tr("msg.profile_clone_prompt"),
        )
        if not ok:
            return
        pid = self._sanitize_profile_id(name)
        if pid == "default":
            QtWidgets.QMessageBox.warning(
                self,
                self.ui_tr("project.profile_clone"),
                self.ui_tr("msg.profile_reserved_default"),
            )
            return
        if self.profile_combo.findText(pid) >= 0:
            QtWidgets.QMessageBox.warning(
                self,
                self.ui_tr("project.profile_clone"),
                self.ui_tr("msg.profile_exists", name=pid),
            )
            return
        src = self._current_profile_id()
        blob = self._settings.value(f"profiles/{src}/state_json", "")
        self._settings.setValue(f"profiles/{pid}/state_json", blob)
        self.profile_combo.addItem(pid)
        self.profile_combo.setCurrentText(pid)
        self._log(self.ui_tr("msg.profile_cloned", src=src, dst=pid), "info")

    def _on_profile_delete_clicked(self) -> None:
        pid = self._current_profile_id()
        if pid == "default":
            QtWidgets.QMessageBox.information(
                self,
                self.ui_tr("project.profile_delete"),
                self.ui_tr("msg.profile_cannot_delete_default"),
            )
            return
        res = QtWidgets.QMessageBox.question(
            self,
            self.ui_tr("project.profile_delete"),
            self.ui_tr("msg.profile_delete_confirm", name=pid),
            QtWidgets.QMessageBox.StandardButton.Yes
            | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if res != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        self._settings.remove(f"profiles/{pid}/state_json")
        idx = self.profile_combo.currentIndex()
        self.profile_combo.removeItem(idx)
        self.profile_combo.setCurrentText("default")
        names = [
            self.profile_combo.itemText(i) for i in range(self.profile_combo.count())
        ]
        self._settings.setValue(PROFILE_NAMES_KEY, json.dumps(names))
        self._log(self.ui_tr("msg.profile_deleted", name=pid), "info")

    def _load_legacy_settings_flat(self, s: QSettings) -> None:
        if hasattr(self, "chk_colorful"):
            self.chk_colorful.setChecked(s.value("ui/colorful_logs", True, type=bool))
        if hasattr(self, "merge_delete_dnp") and s.contains("merge/delete_dnp"):
            self.merge_delete_dnp.setChecked(
                s.value("merge/delete_dnp", False, type=bool)
            )
        if hasattr(self, "clean_res_template_combos"):
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
                self.clean_res_ohm_r,
                self.clean_use_vendor,
                self.clean_from_db,
                self.clean_from_hanwha_mdb,
                self.clean_hanwha_partial_match,
                self.clean_prefix_use_separator,
                self.clean_res_prefix,
                self.clean_cap_prefix,
                self.clean_ind_prefix,
                self.clean_apply_replace,
                self.clean_double_comment_import,
            ):
                w.blockSignals(True)
            if hasattr(self, "clean_double_comment_sep"):
                self.clean_double_comment_sep.blockSignals(True)
            res_template = s.value("clean/res_template", "nom,pack,watt,%", str)
            cap_template = s.value("clean/cap_template", "nom,pack,film,%,V", str)
            ind_template = s.value("clean/ind_template", "pack,nom,%,Imax,DCR", str)
            self._set_template_combos(
                self.clean_res_template_combos,
                res_template,
                ("nom", "pack", "watt", "%"),
            )
            self._set_template_combos(
                self.clean_cap_template_combos,
                cap_template,
                ("nom", "pack", "film", "%", "V"),
            )
            self._set_template_combos(
                self.clean_ind_template_combos,
                ind_template,
                ("pack", "nom", "%", "Imax", "DCR"),
            )
            self.clean_cap_nf.setChecked(s.value("clean/cap_nf", False, type=bool))
            self.clean_cap_uf_micro.setChecked(
                s.value("clean/cap_uf_micro", False, type=bool)
            )
            self.clean_res_ohm_r.setChecked(
                s.value("clean/res_ohm_r_suffix", True, type=bool)
            )
            self.clean_use_vendor.setChecked(
                s.value("clean/use_vendor", False, type=bool)
            )
            self.clean_from_db.setChecked(s.value("clean/from_db", True, type=bool))
            self.clean_from_hanwha_mdb.setChecked(
                s.value("clean/from_hanwha_mdb", False, type=bool)
            )
            if hasattr(self, "clean_hanwha_partial_match"):
                self.clean_hanwha_partial_match.setChecked(
                    s.value("clean/hanwha_partial_match", False, type=bool)
                )
            self.clean_prefix_use_separator.setChecked(
                s.value("clean/prefix_use_separator", True, type=bool)
            )
            self.clean_res_prefix.setText(s.value("clean/res_prefix", "", str))
            self.clean_cap_prefix.setText(s.value("clean/cap_prefix", "", str))
            self.clean_ind_prefix.setText(s.value("clean/ind_prefix", "", str))
            self.clean_apply_replace.setChecked(
                s.value("clean/apply_replace", False, type=bool)
            )
            if hasattr(self, "clean_double_comment_import"):
                self.clean_double_comment_import.setChecked(
                    s.value("clean/double_comment_import", False, type=bool)
                )
            if hasattr(self, "clean_double_comment_sep"):
                self.clean_double_comment_sep.setText(
                    s.value("clean/double_comment_sep", " | ", str)
                )
            if hasattr(self, "chk_clean_res"):
                self.chk_clean_res.setChecked(
                    s.value("clean/group_res", True, type=bool)
                )
                self.chk_clean_cap.setChecked(
                    s.value("clean/group_cap", True, type=bool)
                )
                self.chk_clean_ind.setChecked(
                    s.value("clean/group_ind", True, type=bool)
                )
                self.gb_clean_pn.setChecked(s.value("clean/group_pn", True, type=bool))
            self.clean_spacer_combo.blockSignals(True)
            self.clean_spacer_cust.blockSignals(True)
            raw_sep = s.value("clean/output_separator", "_")
            if isinstance(raw_sep, str):
                sep = raw_sep
            elif raw_sep is not None:
                sep = str(raw_sep)
            else:
                sep = "_"
            self._apply_clean_spacer_to_ui(sep)
            self.clean_spacer_combo.blockSignals(False)
            self.clean_spacer_cust.blockSignals(False)
            for w in (
                *self.clean_res_template_combos,
                *self.clean_cap_template_combos,
                *self.clean_ind_template_combos,
                self.clean_cap_nf,
                self.clean_cap_uf_micro,
                self.clean_res_ohm_r,
                self.clean_use_vendor,
                self.clean_from_db,
                self.clean_from_hanwha_mdb,
                self.clean_hanwha_partial_match,
                self.clean_prefix_use_separator,
                self.clean_res_prefix,
                self.clean_cap_prefix,
                self.clean_ind_prefix,
                self.clean_apply_replace,
                self.clean_double_comment_import,
            ):
                w.blockSignals(False)
            if hasattr(self, "clean_double_comment_sep"):
                self.clean_double_comment_sep.blockSignals(False)
            if hasattr(self, "clean_mpn_search_provider"):
                self.clean_mpn_search_provider.blockSignals(True)
                self.clean_octopart_api_key.blockSignals(True)
                prov = s.value("clean/mpn_search_provider", "digikey", str)
                for i in range(self.clean_mpn_search_provider.count()):
                    if self.clean_mpn_search_provider.itemData(i) == prov:
                        self.clean_mpn_search_provider.setCurrentIndex(i)
                        break
                self.clean_octopart_api_key.setText(
                    s.value("clean/octopart_api_key", "", str)
                )
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
        if hasattr(self, "chk_critical"):
            self.chk_critical.setChecked(
                s.value("report/show_critical", True, type=bool)
            )
            self.chk_warning.setChecked(s.value("report/show_warning", True, type=bool))
            self.chk_info.setChecked(s.value("report/show_info", True, type=bool))
        if hasattr(self, "chk_overlap") and hasattr(self, "spin_overlap_mm"):
            self.chk_overlap.blockSignals(True)
            self.spin_overlap_mm.blockSignals(True)
            self.chk_overlap.setChecked(
                s.value("report/check_overlap", False, type=bool)
            )
            ov = s.value("report/overlap_mm", 3.0)
            self.spin_overlap_mm.setValue(float(ov) if ov is not None else 3.0)
            self.spin_overlap_mm.setEnabled(self.chk_overlap.isChecked())
            self.spin_overlap_mm.blockSignals(False)
            self.chk_overlap.blockSignals(False)
        units = s.value("pnp/units", "mm", str)
        stored_mm = str(units).lower() != "mils"
        self._apply_pnp_xy_units_everywhere(stored_mm, save_settings=False)
        lang_raw = s.value("ui/language", "en")
        lang = str(lang_raw) if lang_raw is not None else "en"
        if lang not in SUPPORTED_UI_LOCALES:
            lang = "en"
        if hasattr(self, "lang_combo"):
            self.lang_combo.blockSignals(True)
            li = self.lang_combo.findData(lang)
            if li >= 0:
                self.lang_combo.setCurrentIndex(li)
            self.lang_combo.blockSignals(False)
        self._apply_ui_language(lang, save=False)
