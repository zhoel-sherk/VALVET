"""File browse/load and PnP layer merge (MainWindow mixin)."""

from __future__ import annotations

import os

from PySide6 import QtCore, QtWidgets
import pandas as pd

from services.file_loading import read_pnp_dataframe as _service_read_pnp
from smt_processor import SMTProcessorError, read_file
from ui.project_tab import configure_path_label
from working_copy import save_snapshot

import logger


class FilesMixin:
    def _browse_bom(self):
        start = str(self._settings.value("ui/dialog_last_dir_bom", "") or "")
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select BOM file",
            start,
            "Supported (*.xls *.xlsx *.csv *.ods *.txt *.tab);;All (*.*)",
        )
        if path:
            self._settings.setValue("ui/dialog_last_dir_bom", os.path.dirname(path))
            self._load_bom(path)
    def _browse_pnp(self):
        start = str(self._settings.value("ui/dialog_last_dir_pnp", "") or "")
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select PnP file",
            start,
            "Supported (*.xls *.xlsx *.csv *.ods *.txt *.tab);;All (*.*)",
        )
        if path:
            self._settings.setValue("ui/dialog_last_dir_pnp", os.path.dirname(path))
            self._load_pnp(path)
    def _browse_pnp_secondary(self) -> None:
        start = str(self._settings.value("ui/dialog_last_dir_pnp", "") or "")
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            self.ui_tr("project.pnp_select_optional"),
            start,
            "Supported (*.xls *.xlsx *.csv *.ods *.txt *.tab);;All (*.*)",
        )
        if not path:
            return
        self._settings.setValue("ui/dialog_last_dir_pnp", os.path.dirname(path))
        self._pnp_secondary_path = path
        configure_path_label(
            self.pnp_path2_label,
            path,
            empty_text=self.ui_tr("project.no_file"),
        )
        primary = (self._pnp_source_path or "").strip()
        if not primary or not os.path.isfile(primary):
            self._log(self.ui_tr("msg.pnp_secondary_need_primary"), "warning")
            return
        self._load_pnp(primary)
    def _clear_pnp_secondary_only(self) -> None:
        primary = (self._pnp_source_path or "").strip()
        if primary and os.path.isfile(primary) and self._pnp_dirty:
            if not self._confirm_reload_original("pnp"):
                return
        self._pnp_secondary_path = ""
        configure_path_label(
            self.pnp_path2_label, "", empty_text=self.ui_tr("project.no_file")
        )
        if primary and os.path.isfile(primary):
            self._load_pnp(primary, force_original=True)
    def _on_pnp_layer_override_toggled(self, on: bool) -> None:
        self.edit_pnp_layer_tokens.setEnabled(bool(on))
    def _schedule_pnp_layer_prefs_reload(self) -> None:
        if self._loading_working_copy or self._restoring_settings:
            return
        if not getattr(self, "_pnp_layer_reload_timer", None):
            return
        self._pnp_layer_reload_timer.start(450)
    def _on_pnp_layer_reload_timer(self) -> None:
        primary = (self._pnp_source_path or "").strip()
        if not primary or not os.path.isfile(primary):
            return
        if self._pnp_dirty and not self._confirm_reload_original("pnp"):
            return
        self._load_pnp(primary, force_original=True)
    def _pnp_snapshot_identity_path(self) -> str:
        """Stable path string for autosave / per-file UI settings when merging two PnP files."""
        p1 = (self._pnp_source_path or "").strip()
        p2 = (self._pnp_secondary_path or "").strip()
        if p2 and os.path.isfile(p2):
            return p1 + "\n+pnp_merge:\n" + p2
        return p1
    def _pnp_report_paths_display(self) -> str:
        p1 = (self._pnp_source_path or "").strip()
        p2 = (self._pnp_secondary_path or "").strip()
        if p2 and os.path.isfile(p2):
            return p1 + " + " + p2
        return p1
    def _read_pnp_dataframe_from_disk(
        self,
        path: str,
        sep: str,
        first: int,
        last: int,
    ) -> pd.DataFrame:
        return _service_read_pnp(path, sep, first, last)
    def _pnp_mapped_layer_column_index(self) -> int | None:
        if self._pnp_df is None or not getattr(self, "pnp_col_combos", None):
            return None
        cols = list(self._pnp_df.columns)
        for i, combo in enumerate(self.pnp_col_combos):
            if i < len(cols) and self._mapping_combo_role(combo) == "Layer":
                return i
        return None
    def _inject_pnp_layer_values(self) -> None:
        """Fill Layer column for merged rows (expects combos already built)."""
        if self._pnp_df is None or len(self._pnp_df) == 0:
            return
        if not self.chk_pnp_layer_override.isChecked():
            return
        n = len(self._pnp_df)
        n1 = max(0, min(int(self._pnp_primary_row_count), n))
        n2 = n - n1
        toks = self.edit_pnp_layer_tokens.text().split()
        if n2 <= 0:
            if len(toks) >= 1:
                fill = toks[0]
            else:
                fill = "T"
            v1, v2 = fill, None
        else:
            if len(toks) >= 2:
                v1, v2 = toks[0], toks[1]
            elif len(toks) == 1:
                v1, v2 = toks[0], "B"
            else:
                v1, v2 = "T", "B"
        j = self._pnp_mapped_layer_column_index()
        if j is None:
            return
        if n1 > 0:
            self._pnp_df.iloc[:n1, j] = v1
        if n2 > 0 and v2 is not None:
            self._pnp_df.iloc[n1:, j] = v2
    def _load_bom(self, path: str, *, force_original: bool = False):
        try:
            recovered = (
                None if force_original else self._recover_snapshot_choice(path, "bom")
            )
            if isinstance(recovered, str) and recovered == "cancel":
                return
            if not isinstance(recovered, pd.DataFrame):
                self._restore_bom_tab_load_params(path)
            sep = self.bom_separator.currentText()
            first = int(self.bom_first_row.text() or 1) - 1  # 0-based
            last_text = self.bom_last_row.text()
            last = int(last_text) - 1 if last_text else -1

            if isinstance(recovered, pd.DataFrame):
                self._bom_df = recovered
                self._bom_dirty = True
                recovered_note = "recovered working copy"
            else:
                self._bom_df = read_file(
                    path,
                    first_row=first,
                    last_row=last,
                    separator=sep,
                    column_headers_from_file=False,
                )
                self._bom_dirty = False
                recovered_note = "original file"
            self._bom_source_path = path
            configure_path_label(
                self.bom_path_label,
                path,
                empty_text=self.ui_tr("project.no_file"),
            )
            self._loading_working_copy = True
            self.bom_model.update_dataframe(self._bom_df)
            self._loading_working_copy = False
            self._refresh_active_row_highlight("bom")
            self._fill_bom_combos()
            self._restore_bom_mappings_after_fill(path)
            QtCore.QTimer.singleShot(0, self._autoresize_bom_columns)

            if path not in self._recent_bom:
                self._recent_bom.insert(0, path)
                if len(self._recent_bom) > 10:
                    self._recent_bom.pop()

            self._log(
                f"Loaded BOM ({recovered_note}): {len(self._bom_df)} rows, {len(self._bom_df.columns)} cols",
                "info",
            )
            self._log(f"Columns: {list(self._bom_df.columns)}", "debug")
            if force_original:
                save_snapshot(
                    self._bom_df,
                    self._bom_source_path,
                    "bom",
                    self._autosave_dir,
                    dirty=False,
                )
            QtCore.QTimer.singleShot(0, self._save_bom_tab_settings_to_disk)
            self._hide_merge_cross_check_ok_banner()
            self._register_session_link()
        except SMTProcessorError as e:
            self._log(f"Error loading BOM: {e}", "error")
            QtWidgets.QMessageBox.critical(self, "Error", str(e))

        finally:
            self._loading_working_copy = False
    def _load_pnp(self, path: str, *, force_original: bool = False):
        self._pnp_layer_reload_timer.stop()
        try:
            p_secondary = (self._pnp_secondary_path or "").strip()
            dual = bool(p_secondary and os.path.isfile(p_secondary))
            if dual or force_original:
                recovered = None
            else:
                recovered = self._recover_snapshot_choice(path, "pnp")
            if isinstance(recovered, str) and recovered == "cancel":
                return
            if isinstance(recovered, pd.DataFrame):
                pnp_settings_key = path
            else:
                pnp_settings_key = self._pnp_snapshot_identity_path()
            if not isinstance(recovered, pd.DataFrame):
                self._restore_pnp_tab_load_params(pnp_settings_key)
            sep = self.pnp_separator.currentText()
            first = int(self.pnp_first_row.text() or 1) - 1
            last_text = self.pnp_last_row.text()
            last = int(last_text) - 1 if last_text else -1

            if isinstance(recovered, pd.DataFrame):
                self._pnp_df = recovered
                self._pnp_dirty = True
                recovered_note = "recovered working copy"
                self._pnp_primary_row_count = len(self._pnp_df)
            else:
                df1 = self._read_pnp_dataframe_from_disk(path, sep, first, last)
                self._pnp_primary_row_count = len(df1)
                if dual:
                    df2 = self._read_pnp_dataframe_from_disk(
                        p_secondary, sep, first, last
                    )
                    self._pnp_df = pd.concat([df1, df2], axis=0, ignore_index=True)
                    recovered_note = "merged (2 files)"
                else:
                    self._pnp_df = df1
                    recovered_note = "original file"
                if (
                    self.chk_pnp_layer_override.isChecked()
                    and "Layer" not in self._pnp_df.columns
                ):
                    self._pnp_df["Layer"] = ""
                self._pnp_dirty = False
            self._pnp_source_path = path
            configure_path_label(
                self.pnp_path_label,
                path,
                empty_text=self.ui_tr("project.no_file"),
            )
            if dual:
                configure_path_label(
                    self.pnp_path2_label,
                    p_secondary,
                    empty_text=self.ui_tr("project.no_file"),
                )
            self._loading_working_copy = True
            self.pnp_model.update_dataframe(self._pnp_df)
            self._loading_working_copy = False
            self._refresh_active_row_highlight("pnp")
            self._fill_pnp_combos()
            self._restore_pnp_mappings_after_fill(pnp_settings_key)
            if self.chk_pnp_layer_override.isChecked():
                self._inject_pnp_layer_values()
                if self._pnp_mapped_layer_column_index() is None:
                    self._log(self.ui_tr("msg.pnp_layer_override_no_column"), "warning")
                self._loading_working_copy = True
                self.pnp_model.update_dataframe(self._pnp_df)
                self._loading_working_copy = False
            QtCore.QTimer.singleShot(0, self._autoresize_pnp_columns)

            if path not in self._recent_pnp:
                self._recent_pnp.insert(0, path)
                if len(self._recent_pnp) > 10:
                    self._recent_pnp.pop()
            if dual and p_secondary not in self._recent_pnp:
                self._recent_pnp.insert(0, p_secondary)
                if len(self._recent_pnp) > 10:
                    self._recent_pnp.pop()

            self._log(
                f"Loaded PnP ({recovered_note}): {len(self._pnp_df)} rows, {len(self._pnp_df.columns)} cols",
                "info",
            )
            self._log(f"Columns: {list(self._pnp_df.columns)}", "debug")
            if force_original:
                extra = None
                if dual and not isinstance(recovered, pd.DataFrame):
                    extra = {"pnp_primary_row_count": int(self._pnp_primary_row_count)}
                save_snapshot(
                    self._pnp_df,
                    pnp_settings_key,
                    "pnp",
                    self._autosave_dir,
                    dirty=False,
                    extra=extra,
                )
            QtCore.QTimer.singleShot(0, self._save_pnp_tab_settings_to_disk)
            self._hide_merge_cross_check_ok_banner()
            self._register_session_link()
        except SMTProcessorError as e:
            self._log(f"Error loading PnP: {e}", "error")
            QtWidgets.QMessageBox.critical(self, "Error", str(e))
        finally:
            self._loading_working_copy = False
    def _reload_bom(self):
        path = (self._bom_source_path or "").strip()
        if path and os.path.isfile(path) and self._confirm_reload_original("bom"):
            self._load_bom(path, force_original=True)
    def _reload_pnp(self):
        path = (self._pnp_source_path or "").strip()
        if path and os.path.isfile(path) and self._confirm_reload_original("pnp"):
            self._load_pnp(path, force_original=True)
    def _drop_pnp_secondary(self, path: str) -> None:
        self._pnp_secondary_path = path
        configure_path_label(
            self.pnp_path2_label,
            path,
            empty_text=self.ui_tr("project.no_file"),
        )
        primary = (self._pnp_source_path or "").strip()
        if not primary or not os.path.isfile(primary):
            self._log(self.ui_tr("msg.pnp_secondary_need_primary"), "warning")
            return
        self._load_pnp(primary)
    def _confirm_reload_original(self, kind: str) -> bool:
        dirty = self._bom_dirty if kind == "bom" else self._pnp_dirty
        if not dirty:
            return True
        res = QtWidgets.QMessageBox.question(
            self,
            "Reload original file?",
            f"Reload {kind.upper()} from original file?\n\n"
            "Unsaved working changes and new columns in this table will be replaced.",
            QtWidgets.QMessageBox.StandardButton.Yes
            | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        return res == QtWidgets.QMessageBox.StandardButton.Yes
    def _mark_working_dirty(self, kind: str, *, autosave: bool = True) -> None:
        if self._loading_working_copy or self._restoring_settings:
            return
        if kind == "bom":
            self._sync_bom_df_from_model()
            self._bom_dirty = True
        elif kind == "pnp":
            self._sync_pnp_df_from_model()
            self._pnp_dirty = True
        else:
            return
        if autosave:
            self._autosave_timer.start(1500)
    def _autosave_dirty_working_copies(self) -> None:
        try:
            if self._bom_dirty and self._bom_source_path and self._bom_df is not None:
                save_snapshot(
                    self._bom_df,
                    self._bom_source_path,
                    "bom",
                    self._autosave_dir,
                    dirty=True,
                )
                self._log("BOM working copy autosaved", "debug")
            if self._pnp_dirty and self._pnp_source_path and self._pnp_df is not None:
                snap_path = self._pnp_snapshot_identity_path()
                save_snapshot(
                    self._pnp_df,
                    snap_path,
                    "pnp",
                    self._autosave_dir,
                    dirty=True,
                )
                self._log("PnP working copy autosaved", "debug")
        except Exception as e:
            self._log(f"Working copy autosave failed: {e}", "warning")
            logger.warning("Working copy autosave failed: %s", e)
