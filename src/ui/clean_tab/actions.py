"""User actions: Import, Convert, Apply, Learn OTHER, Save, lookup."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import quote

import pandas as pd
from PySide6 import QtCore, QtGui, QtWidgets

import logger
from clean_component import clean_preview_inputs
from clean_debug_dialog import CleanPipelineDebugDialog
from component_library import append_component, default_components_path
from pn_original import normalize_mpn_bare
from qt_models import CleanPreviewTableModel
from services.clean_apply import apply_clean_preview_to_bom
from services.clean_import import import_bom_comment_inputs
from ui.clean_tab.helpers import _clean_preview_frame


class CleanActionsMixin:
    def _clean_preview_context_menu(self, pos) -> None:
        idx = self.clean_preview_table.indexAt(pos)
        if idx.isValid():
            self.clean_preview_table.setCurrentIndex(idx)
        menu = QtWidgets.QMenu(self.clean_preview_table)
        act = menu.addAction(self.ui_tr("clean.mpn_search"))
        chosen = menu.exec(self.clean_preview_table.viewport().mapToGlobal(pos))
        if chosen is act:
            self._open_mpn_search_browser()

    def _get_bom_comment_column_names(
        self, df: pd.DataFrame | None = None
    ) -> list[Any]:
        """BOM columns mapped to PN name or PN join (table order).

        Returns **actual** column labels from ``df`` (same types as ``df.columns``), not
        stringified names — otherwise ``col in df.columns`` fails for integer/RangeIndex
        headers (e.g. ``1`` vs ``"1"``).
        """
        if df is None:
            self._sync_bom_df_from_model()
            df = self._bom_df
        if df is None or df.empty:
            return []
        cols: list[Any] = []
        if hasattr(self, "bom_col_combos") and self.bom_col_combos:
            for i, combo in enumerate(self.bom_col_combos):
                if i >= len(df.columns):
                    break
                if self._mapping_combo_role(combo) in ("Comment", "PnJoin"):
                    cols.append(df.columns[i])
        if cols:
            return cols
        for col in df.columns:
            u = str(col).upper()
            if "COMMENT" in u or u == "VALUE" or "NAME" in u:
                return [col]
        return [df.columns[0]]

    def _get_bom_comment_column_name(self) -> Any | None:
        names = self._get_bom_comment_column_names()
        return names[0] if names else None

    def _open_clean_pipeline_debug(self) -> None:
        if not hasattr(self, "_settings"):
            return
        dlg = CleanPipelineDebugDialog(self, self._settings)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._log("Clean BOM: debug pipeline / components.txt path saved", "info")

    def _open_mpn_search_browser(self) -> None:
        idx = self.clean_preview_table.currentIndex()
        if not idx.isValid():
            self._log("Clean BOM: select a row in the preview table first", "warning")
            return
        row = idx.row()
        df = self.clean_preview_model.get_dataframe()
        if df is None or df.empty or row < 0 or row >= len(df):
            self._log("Clean BOM: no preview data", "warning")
            return
        if "Original" not in df.columns:
            self._log("Clean BOM: preview has no Original column", "error")
            return
        orig = str(df.iloc[row]["Original"])
        mpn = normalize_mpn_bare(orig)
        if not mpn:
            self._log("Clean BOM: empty MPN after normalize", "warning")
            return
        prov = self.clean_mpn_search_provider.currentData() or "digikey"
        q = quote(mpn, safe="")
        if prov == "digikey":
            url = f"https://www.digikey.com/en/products/result?keywords={q}"
        elif prov == "mouser":
            url = f"https://www.mouser.com/c/?q={q}"
        else:
            url = f"https://octopart.com/search?q={q}"
        if not QtGui.QDesktopServices.openUrl(QtCore.QUrl(url)):
            self._log("Could not open default browser for MPN search", "error")
        else:
            self._log(f"MPN search opened for {mpn!r} ({prov})", "info")

    def _clean_import(self) -> None:
        self._sync_bom_df_from_model()
        df = (
            self.bom_model.get_dataframe()
            if hasattr(self, "bom_model")
            else self._bom_df
        )
        if df is not None and not df.empty:
            self._bom_df = df
        if df is None or df.empty:
            self._log("Clean BOM: load BOM on BOM tab first", "warning")
            logger.warning("Clean BOM: no BOM loaded")
            self._show_clean_alert("clean.err_no_bom")
            return
        comment_cols = self._get_bom_comment_column_names(df)
        if not comment_cols:
            self._log(
                "Clean BOM: map PN name and/or PN join on the BOM tab",
                "warning",
            )
            logger.error("Clean BOM: BOM PN column not configured")
            self._show_clean_alert("clean.err_no_mapping")
            return
        for col in comment_cols:
            if col not in df.columns:
                self._log(f"Clean BOM: column «{col}» missing from BOM", "warning")
                self._show_clean_alert("clean.err_column_missing")
                return
        primary_col = comment_cols[0]
        self._clean_source_column = primary_col
        self._clean_source_indices = list(range(len(df)))
        if not self._clean_source_indices:
            self._log("Clean BOM: BOM table is empty", "warning")
            self._show_clean_alert("clean.err_empty_bom")
            return

        try:
            imported_comments = import_bom_comment_inputs(
                df, comment_cols, self._clean_source_indices
            )
        except Exception as e:
            logger.exception("Clean BOM: importing BOM comments failed")
            self._log(f"Clean BOM: Import failed: {e}", "error")
            self._show_clean_alert("clean.err_import_failed", severity="error")
            return
        self._clean_imported_comments = imported_comments
        n = len(self._clean_imported_comments)
        joined = "», «".join(str(c) for c in comment_cols)
        col_desc = (
            "«" + joined + "» (merged)" if len(comment_cols) > 1 else f"«{primary_col}»"
        )
        logger.info("Imported %d comments from BOM columns %s", n, comment_cols)
        self._log(
            f"BOM → Clean: imported {n} row(s) from column(s) {col_desc} using active BOM range",
            "info",
        )
        # Row number and length only. The comment text is the customer's free
        # text from the BOM, and this panel is mirrored into the session log
        # that ships inside the release zip, so the text itself is not logged.
        for i, c in enumerate(self._clean_imported_comments[:5], start=1):
            one = str(c).replace("\n", " ")
            self._log(f"  sample row {i}: {len(one)} char(s) imported", "info")
        if n > 5:
            self._log(
                f"  … plus {n - 5} more rows (see Original column in the table)", "info"
            )
        self.btn_clean_convert.setEnabled(True)
        self.btn_clean_apply.setEnabled(False)
        self.btn_clean_learn_other.setEnabled(False)
        self._clean_last_preview = []
        self._clean_preview_stale = False
        self._clean_applied = False
        self._clear_clean_alert()
        self._hide_clean_apply_banner()
        self._sync_clean_primary_buttons()
        if hasattr(self, "_refresh_shell_status"):
            self._refresh_shell_status()
        raw_df = _clean_preview_frame(
            self._clean_imported_comments,
            None,
            combined_label=self.ui_tr("clean.input_combined"),
        )
        self.clean_preview_model.update_dataframe(raw_df)
        self._sync_clean_preview_view()
        self._sync_clean_primary_buttons()

    def _warn_if_machine_library_is_importing(self) -> None:
        """Explain a Hanwha match miss that is only a race with the MDB import.

        The partname set comes from the last finished import, so running
        Convert! while a fresh ``.mdb`` is still landing matches against the
        previous library - or nothing on a new profile - and the preview looks
        broken for no visible reason.
        """
        ml = getattr(self, "_machine_library_tab", None)
        if ml is None or not self.clean_from_hanwha_mdb.isChecked():
            return
        busy = getattr(ml, "mdb_import_in_progress", None)
        if not callable(busy) or not busy():
            return
        self._log(
            "Clean BOM: Hanwha .mdb is still importing — parts from it are not "
            "matched yet. Wait for the import to finish, then run Convert! again.",
            "warning",
        )
        logger.warning(
            "Clean BOM: Convert! ran while the Hanwha MDB import was in progress"
        )

    def _run_clean_preview(self) -> None:
        if not self._clean_imported_comments:
            self._log("Clean BOM: run Import from BOM first, then Convert!", "warning")
            logger.error("Clean BOM: no comments imported")
            self._show_clean_alert("clean.err_import_first")
            return
        self._warn_if_machine_library_is_importing()
        n = len(self._clean_imported_comments)
        logger.info("Generating clean preview for %d components…", n)
        self._log(f"Clean BOM: generating clean preview for {n} component(s)…", "info")
        cfg = self._clean_config_from_ui()
        try:
            rows = clean_preview_inputs(self._clean_imported_comments, cfg)
        except Exception as e:
            self._log(f"Clean BOM: Convert! error: {e}", "error")
            logger.exception("Clean BOM clean_preview failed")
            self._show_clean_alert("clean.err_convert_failed", severity="error")
            return
        self._clean_last_preview = rows
        self._clean_preview_stale = False
        self._clean_applied = False
        df = _clean_preview_frame(
            self._clean_imported_comments,
            rows,
            combined_label=self.ui_tr("clean.input_combined"),
        )
        use_hl = cfg.regex_master_enabled and cfg.regex_master_preview_scores
        if isinstance(self.clean_preview_model, CleanPreviewTableModel):
            self.clean_preview_model.set_arbiter_score_highlight(use_hl)
        self.clean_preview_model.update_dataframe(df)
        logger.info("Clean preview generated: %d rows", len(rows))
        self._log(
            f"Clean BOM: Convert! done — {len(rows)} row(s) (check Cleaned / Type / Source)",
            "info",
        )
        self._clear_clean_alert()
        self._hide_clean_apply_banner()
        self.btn_clean_apply.setEnabled(bool(rows))
        self._sync_clean_preview_view()
        self._sync_clean_primary_buttons()
        if hasattr(self, "_refresh_shell_status"):
            self._refresh_shell_status()

    def _footprint_for_clean_row(self, one_based_row: int) -> str:
        self._sync_bom_df_from_model()
        if self._bom_df is None or self._bom_df.empty:
            return ""
        preview_idx = one_based_row - 1
        if 0 <= preview_idx < len(self._clean_source_indices):
            idx = self._clean_source_indices[preview_idx]
        else:
            idx = preview_idx
        if idx < 0 or idx >= len(self._bom_df):
            return ""
        for col in self._bom_df.columns:
            if "FOOTPRINT" in str(col).upper():
                val = self._bom_df.iloc[idx].get(col, "")
                return "" if pd.isna(val) else str(val).strip()
        return ""

    def _learn_selected_other(self) -> None:
        idx = self.clean_preview_table.currentIndex()
        if not idx.isValid():
            self._log("Clean BOM: select an OTHER row first", "warning")
            return
        df = self.clean_preview_model.get_dataframe()
        if df is None or df.empty or idx.row() >= len(df):
            self._log("Clean BOM: preview table is empty", "warning")
            return
        row = df.iloc[idx.row()]
        typ = str(row.get("Type", "")).upper()
        if typ != "OTHER":
            self._log("Clean BOM: selected row is not OTHER", "warning")
            return
        input_name = str(row.get("Input", "")).strip()
        if input_name in df.columns:
            original = str(row.get(input_name, "")).strip()
        elif input_name:
            original = " ".join(
                str(row.get(col, "")).strip()
                for col in df.columns
                if str(col).startswith("Original") and str(row.get(col, "")).strip()
            )
        else:
            original = str(row.get("Original", "")).strip()
        cleaned = str(row.get("Cleaned", "")).strip()
        try:
            one_based = int(row.get("#", idx.row() + 1))
        except (TypeError, ValueError):
            # The printed row number is decorative; the Qt row is the real position.
            one_based = idx.row() + 1
        footprint = self._footprint_for_clean_row(one_based)

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Learn OTHER component")
        form = QtWidgets.QFormLayout(dlg)
        raw_edit = QtWidgets.QLineEdit(original)
        raw_edit.setReadOnly(True)
        clean_edit = QtWidgets.QLineEdit(cleaned or original)
        type_combo = QtWidgets.QComboBox()
        for label in ("OTHER", "CAP", "RES", "IND"):
            type_combo.addItem(label, label)
        fp_edit = QtWidgets.QLineEdit(footprint)
        form.addRow("Original", raw_edit)
        form.addRow("Canonical name", clean_edit)
        form.addRow("Type", type_combo)
        form.addRow("Footprint", fp_edit)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Save
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)
        if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        lib_path = (
            str(self._settings.value("clean/components_txt_path", "") or "").strip()
            if hasattr(self, "_settings")
            else ""
        )
        ok = append_component(
            raw_edit.text(),
            clean_edit.text(),
            type_combo.currentData() or "OTHER",
            fp_edit.text(),
            path=lib_path if lib_path else None,
        )
        path = Path(lib_path) if lib_path else default_components_path()
        if ok:
            # basename only: session logs ship inside the release zip, so an
            # absolute path would leak the user's folder layout.
            self._log(f"Learned component saved to {path.name}", "info")
        else:
            self._log("Component already exists in user library", "warning")

    def _clean_apply(self) -> None:
        self._sync_bom_df_from_model()
        if self._bom_df is None or self._bom_df.empty:
            logger.warning("Clean BOM apply: no BOM data")
            self._show_clean_alert("clean.err_no_bom")
            return
        col = self._clean_source_column or self._get_bom_comment_column_name()
        if not col or col not in self._bom_df.columns:
            self._log("Clean BOM: no Comment column", "warning")
            logger.error("Clean BOM apply: comment column missing")
            self._show_clean_alert("clean.err_no_mapping")
            return
        if not self._clean_last_preview:
            self._log("Clean BOM: run Convert! before Apply", "warning")
            self._show_clean_alert("clean.err_convert_first")
            return

        logger.info(
            "Applying clean preview to BOM (%d preview rows)…",
            len(self._clean_last_preview),
        )

        preserved_roles = (
            self._mapping_roles_from_combos(self.bom_col_combos)
            if getattr(self, "bom_col_combos", None)
            else []
        )
        self._clean_applying = True
        try:
            self._bom_df = apply_clean_preview_to_bom(
                self._bom_df,
                self._clean_last_preview,
                self._clean_source_indices,
                col,
                replace_source=False,
            )
            after_cols = list(self._bom_df.columns)
            self.bom_model.update_dataframe(self._bom_df)
            from services.column_mapping import roles_after_clean_apply

            comment_target = "comment"
            if comment_target in after_cols:
                roles = roles_after_clean_apply(
                    preserved_roles, after_cols, comment_column=comment_target
                )
                self._fill_bom_combos(preserved_roles=roles)
            msg = self.ui_tr(
                "clean.apply_added",
                count=len(self._clean_last_preview),
            )
            self._log(f"Clean Apply → BOM: {msg}", "info")
            logger.info("Applied clean to BOM: %s", msg)
            # Rewriting the BOM also rewrites the mapping combos; keep the
            # preview from marking itself stale while this intentional update runs.
            self._mark_working_dirty("bom")
        except Exception as e:
            logger.exception("Clean BOM: apply to BOM failed")
            self._log(f"Clean BOM: Apply failed: {e}", "error")
            self._show_clean_alert("clean.err_apply_failed", severity="error")
            return
        finally:
            self._clean_applying = False
        self._clean_applied = True
        self._clear_clean_alert()
        self._show_clean_apply_banner(self.ui_tr("clean.apply_ok_banner"))
        self._sync_clean_preview_view()
        self._sync_clean_primary_buttons()
        if hasattr(self, "_refresh_shell_status"):
            self._refresh_shell_status()

    def _clean_save_excel(self) -> None:
        self._sync_bom_df_from_model()
        if self._bom_df is None or self._bom_df.empty:
            self._log("Clean BOM: no BOM to save", "warning")
            return
        from ui.dialog_paths import save_file_dialog

        path, _ = save_file_dialog(
            self,
            "Save cleaned BOM as Excel",
            "Excel (*.xlsx);;All (*.*)",
            settings=self._settings,
            history_key="clean/last_save_excel_dir",
        )
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        try:
            self._bom_df.to_excel(path, index=False)
            # basename only: session logs ship inside the release zip, so an
            # absolute path would leak the user's folder layout.
            name = Path(path).name
            self._log(f"Clean BOM: saved {name}", "info")
            logger.info("Clean BOM saved Excel: %s", name)
        except Exception as e:
            self._log(f"Save Excel error: {e}", "error")
            logger.exception("Clean BOM save Excel failed")
            QtWidgets.QMessageBox.critical(self, "Error", str(e))
