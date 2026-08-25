"""Merge tab and cross-check / merge operations (MainWindow mixin)."""

from __future__ import annotations

from typing import Any, Optional

from PySide6 import QtCore, QtWidgets
import pandas as pd

from qt_models import SortableTableModel
from smt_processor import SMTDataProcessor, SMTProcessorError
from services.processor_config import build_processor_config
from mmd_export import merge_dataframe_to_mmd_mercury
from report_html import result_dataframe_to_html

try:
    from app.workers import CrossCheckThread
except ImportError:
    from typing import Optional as _Optional

    class CrossCheckThread(QtCore.QThread):
        """Runs SMTDataProcessor.cross_check() off the GUI thread."""

        result_ready = QtCore.Signal(object, str)

        def __init__(self, proc: SMTDataProcessor, parent: _Optional[QtCore.QObject] = None):
            super().__init__(parent)
            self._proc = proc

        def run(self) -> None:
            try:
                r = self._proc.cross_check()
            except SMTProcessorError as e:
                self.result_ready.emit(None, str(e))
            except Exception as e:
                self.result_ready.emit(None, str(e))
            else:
                self.result_ready.emit(r, "")


class MergeTabMixin:

    def _create_merge_tab(self):
        """Merge tab — combine BOM and PnP."""
        tab = QtWidgets.QWidget()
        self._register_main_tab("merge", tab)

        layout = QtWidgets.QVBoxLayout(tab)

        info = QtWidgets.QLabel("Merge uses column settings from BOM and PnP tabs")
        layout.addWidget(info)

        self.merge_cc_ok_banner = QtWidgets.QFrame()
        self.merge_cc_ok_banner.setObjectName("mergeCcOkBanner")
        self.merge_cc_ok_banner.setVisible(False)
        self.merge_cc_ok_banner.setStyleSheet(
            "QFrame#mergeCcOkBanner { background-color: rgba(46, 125, 50, 0.22); "
            "border: 1px solid #43a047; border-radius: 4px; padding: 6px 8px; }"
        )
        cc_ok_lay = QtWidgets.QHBoxLayout(self.merge_cc_ok_banner)
        cc_ok_lay.setContentsMargins(8, 4, 8, 4)
        self.merge_cc_ok_icon = QtWidgets.QLabel("\u2713")
        self.merge_cc_ok_icon.setStyleSheet(
            "color: #66bb6a; font-size: 22px; font-weight: bold; border: none; background: transparent;"
        )
        self.merge_cc_ok_label = QtWidgets.QLabel("PnP is good, ready for Export!")
        self.merge_cc_ok_label.setStyleSheet(
            "color: #c8e6c9; font-weight: bold; border: none; background: transparent;"
        )
        self.merge_cc_ok_hint = QtWidgets.QLabel(
            "Cross-check reported no issues — run Merge below, then save or export."
        )
        self.merge_cc_ok_hint.setStyleSheet(
            "color: #a5d6a7; border: none; background: transparent;"
        )
        cc_ok_lay.addWidget(
            self.merge_cc_ok_icon, 0, QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        vtxt = QtWidgets.QVBoxLayout()
        vtxt.setSpacing(0)
        vtxt.addWidget(self.merge_cc_ok_label)
        vtxt.addWidget(self.merge_cc_ok_hint)
        cc_ok_lay.addLayout(vtxt)
        cc_ok_lay.addStretch()
        layout.addWidget(self.merge_cc_ok_banner)

        # TODO(full Merge): import paired TOP + BOT (see examples/example9) and align with
        # Manual_BOM when present; current UI merges a single loaded BOM+PnP only.

        # Options
        options = QtWidgets.QHBoxLayout()
        self.merge_delete_dnp = QtWidgets.QCheckBox("Delete DNP components")
        self.merge_delete_dnp.stateChanged.connect(self._on_merge_settings_changed)
        options.addWidget(self.merge_delete_dnp)
        options.addSpacing(16)
        options.addWidget(QtWidgets.QLabel("PnP XY:"))
        self.merge_pnp_units_mm = QtWidgets.QRadioButton("mm")
        self.merge_pnp_units_mils = QtWidgets.QRadioButton("mils")
        self.merge_pnp_units_mm.setChecked(True)
        self.merge_pnp_units_mm.setToolTip(self.pnp_units_mm.toolTip())
        self.merge_pnp_units_mils.setToolTip(self.pnp_units_mils.toolTip())
        self.merge_pnp_units_mm.toggled.connect(
            lambda on: on and self._on_user_pnp_xy_unit_choice(True)
        )
        self.merge_pnp_units_mils.toggled.connect(
            lambda on: on and self._on_user_pnp_xy_unit_choice(False)
        )
        options.addWidget(self.merge_pnp_units_mm)
        options.addWidget(self.merge_pnp_units_mils)
        options.addStretch()
        layout.addLayout(options)

        # Table actions
        table_actions = QtWidgets.QHBoxLayout()
        self.btn_merge = QtWidgets.QPushButton("Merge")
        self.btn_merge.clicked.connect(self._run_merge)
        table_actions.addWidget(self.btn_merge)

        self.btn_replace_pnp_from_merge = QtWidgets.QPushButton("Replace PNP")
        self.btn_replace_pnp_from_merge.setToolTip(
            "Replace all rows/columns on the PnP tab with the current Merge result."
        )
        self.btn_replace_pnp_from_merge.clicked.connect(self._replace_pnp_from_merge)
        table_actions.addWidget(self.btn_replace_pnp_from_merge)
        table_actions.addStretch()
        layout.addLayout(table_actions)

        # File export actions
        files_group = QtWidgets.QGroupBox(self.ui_tr("merge.files_group"))
        buttons = QtWidgets.QHBoxLayout(files_group)

        self.btn_save_merge_csv = QtWidgets.QPushButton("Save CSV")
        self.btn_save_merge_csv.clicked.connect(self._save_merge_csv)
        buttons.addWidget(self.btn_save_merge_csv)

        self.btn_save_merge_excel = QtWidgets.QPushButton("Save Excel")
        self.btn_save_merge_excel.clicked.connect(self._save_merge_excel)
        buttons.addWidget(self.btn_save_merge_excel)

        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.Shape.VLine)
        sep.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        buttons.addWidget(sep)

        self.btn_export_top = QtWidgets.QPushButton("Export Top")
        self.btn_export_top.setToolTip(
            "Export Merge rows whose Layer matches the selected TOP value."
        )
        self.btn_export_top.clicked.connect(lambda: self._export_merge_layer("top"))
        buttons.addWidget(self.btn_export_top)
        self.merge_top_layer_combo = QtWidgets.QComboBox()
        self.merge_top_layer_combo.setMinimumWidth(90)
        buttons.addWidget(self.merge_top_layer_combo)

        sep2 = QtWidgets.QFrame()
        sep2.setFrameShape(QtWidgets.QFrame.Shape.VLine)
        sep2.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        buttons.addWidget(sep2)

        self.btn_export_bot = QtWidgets.QPushButton("Export Bot")
        self.btn_export_bot.setToolTip(
            "Export Merge rows whose Layer matches the selected BOT/mirror value."
        )
        self.btn_export_bot.clicked.connect(lambda: self._export_merge_layer("bot"))
        buttons.addWidget(self.btn_export_bot)
        self.merge_bot_layer_combo = QtWidgets.QComboBox()
        self.merge_bot_layer_combo.setMinimumWidth(90)
        buttons.addWidget(self.merge_bot_layer_combo)

        sep_mmd = QtWidgets.QFrame()
        sep_mmd.setFrameShape(QtWidgets.QFrame.Shape.VLine)
        sep_mmd.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        buttons.addWidget(sep_mmd)

        self.btn_export_mmd_top = QtWidgets.QPushButton("Export MMD Top")
        self.btn_export_mmd_top.setToolTip(
            "Export MERCURY-style .mmd (INI) for placements whose Layer matches the selected TOP value; "
            "coordinates use mm × 25.4 as in examples/mmd."
        )
        self.btn_export_mmd_top.clicked.connect(
            lambda: self._export_merge_layer_mmd("top")
        )
        buttons.addWidget(self.btn_export_mmd_top)

        self.btn_export_mmd_bot = QtWidgets.QPushButton("Export MMD Bot")
        self.btn_export_mmd_bot.setToolTip(
            "Export MERCURY-style .mmd (INI) for placements whose Layer matches the selected BOT/mirror value."
        )
        self.btn_export_mmd_bot.clicked.connect(
            lambda: self._export_merge_layer_mmd("bot")
        )
        buttons.addWidget(self.btn_export_mmd_bot)

        self._update_merge_layer_export_controls()
        buttons.addStretch()
        layout.addWidget(files_group)

        # Merge result table
        self.merge_table = QtWidgets.QTableView()
        self.merge_table.setAlternatingRowColors(True)
        self.merge_model = SortableTableModel(pd.DataFrame())
        self.merge_table.setModel(self.merge_model)
        layout.addWidget(self.merge_table, 1)

    def _on_merge_settings_changed(self) -> None:
        if not self._restoring_settings and hasattr(self, "merge_delete_dnp"):
            self._settings.setValue(
                "merge/delete_dnp", self.merge_delete_dnp.isChecked()
            )

    def _configure_processor_from_ui(self) -> Optional[SMTDataProcessor]:
        self._sync_bom_df_from_model()
        self._sync_pnp_df_from_model()
        if self._bom_df is None:
            self._log("BOM not loaded", "warning")
            return None
        if self._pnp_df is None:
            self._log("PnP not loaded", "warning")
            return None
        if not hasattr(self, "pnp_col_combos") or not self.pnp_col_combos:
            self._log("PnP dropdowns not created - reload PnP file", "error")
            return None
        if not hasattr(self, "bom_col_combos") or not self.bom_col_combos:
            self._log("BOM dropdowns not created - reload BOM file", "error")
            return None

        bom_mappings: dict[str, str] = {}
        for i, combo in enumerate(self.bom_col_combos):
            mapping = self._mapping_combo_role(combo)
            if mapping != "-":
                bom_mappings[mapping] = list(self._bom_df.columns)[i]

        pnp_mappings: dict[str, str] = {}
        for i, combo in enumerate(self.pnp_col_combos):
            mapping = self._mapping_combo_role(combo)
            if mapping != "-":
                pnp_mappings[mapping] = list(self._pnp_df.columns)[i]

        pnp_ref = pnp_mappings.get("REF")
        if not pnp_ref:
            for col in self._pnp_df.columns:
                if "DESIGNATOR" in str(col).upper():
                    pnp_ref = col
                    self._log(f"PnP: auto-detected REF as '{col}'", "debug")
                    break

        return build_processor_config(
            self._bom_df,
            self._pnp_df,
            bom_mappings,
            pnp_mappings,
            pnp_xy_are_mils=not self._pnp_xy_stored_in_mm(),
            overlap_min_mm=float(self.spin_overlap_mm.value()),
            check_overlap=self.chk_overlap.isChecked(),
            progress_callback=lambda m, level: self.log_message.emit(m, level),
        )

    def _hide_merge_cross_check_ok_banner(self) -> None:
        if hasattr(self, "merge_cc_ok_banner"):
            self.merge_cc_ok_banner.setVisible(False)

    def _show_merge_cross_check_ok_banner(self) -> None:
        if hasattr(self, "merge_cc_ok_banner"):
            self.merge_cc_ok_banner.setVisible(True)

    def _run_cross_check(self) -> None:
        t = self._cc_thread
        if t is not None:
            try:
                if t.isRunning():
                    self._log("Cross-check already running", "warning")
                    return
            except RuntimeError:
                self._cc_thread = None
        self._hide_merge_cross_check_ok_banner()
        self._log("Running cross-check...", "info")
        proc = self._configure_processor_from_ui()
        if not proc:
            return
        self.processor = proc
        self.btn_cross_check.setEnabled(False)
        self._cc_thread = CrossCheckThread(proc, self)
        self._cc_thread.result_ready.connect(self._on_cross_check_finished)
        self._cc_thread.finished.connect(self._on_cross_check_thread_finished)
        self._cc_thread.start()

    def _on_cross_check_thread_finished(self) -> None:
        """Clear reference before deleteLater so we never call methods on a deleted QThread."""
        self.btn_cross_check.setEnabled(True)
        t = self._cc_thread
        self._cc_thread = None
        if t is not None:
            t.deleteLater()

    def _on_cross_check_finished(self, result: Any, err: str) -> None:
        if err:
            self._hide_merge_cross_check_ok_banner()
            self._log(f"Cross-check error: {err}", "error")
            self._last_report_html = ""
            self.btn_copy_html.setEnabled(False)
            self.btn_save_report_html.setEnabled(False)
            QtWidgets.QMessageBox.critical(self, "Error", err)
            return
        if result is None:
            self._hide_merge_cross_check_ok_banner()
            return
        cross_check_clean = bool(result.empty)
        try:
            filtered = result
            if not self.chk_critical.isChecked():
                filtered = filtered[filtered["Severity"] != "critical"]
            if not self.chk_warning.isChecked():
                filtered = filtered[filtered["Severity"] != "warning"]
            if not self.chk_info.isChecked():
                filtered = filtered[filtered["Severity"] != "info"]
            self._result_df = filtered
            self.result_model.update_dataframe(filtered)

            critical = (
                int((filtered["Severity"] == "critical").sum())
                if not filtered.empty
                else 0
            )
            warn_n = (
                int((filtered["Severity"] == "warning").sum())
                if not filtered.empty
                else 0
            )
            info_n = (
                int((filtered["Severity"] == "info").sum()) if not filtered.empty else 0
            )

            if cross_check_clean:
                self._show_merge_cross_check_ok_banner()
                self._log(
                    "Cross-check complete: no issues — BOM and PnP are consistent. "
                    "Use the Merge tab to merge and export.",
                    "info",
                )
                QtWidgets.QMessageBox.information(
                    self,
                    "Cross-check",
                    "No issues found. BOM and PnP look consistent.\n\n"
                    "Go to the Merge tab to run Merge and export CSV, Excel, or layer files.",
                )
            else:
                self._hide_merge_cross_check_ok_banner()
                self._log(
                    f"Cross-check complete: {len(filtered)} issue(s) in report view",
                    "info",
                )
                self._log(f"  Critical: {critical}", "info")
                self._log(f"  Warning: {warn_n}", "info")
                self._log(f"  Info: {info_n}", "info")

            bom_p = self.bom_path_label.text()
            pnp_p = self._pnp_report_paths_display()
            self._last_report_html = result_dataframe_to_html(
                filtered,
                bom_p if not bom_p.startswith("<") else "",
                pnp_p if not pnp_p.startswith("<") else "",
            )
            has_report = bool(self._last_report_html)
            self.btn_copy_html.setEnabled(has_report)
            self.btn_save_report_html.setEnabled(has_report)
        except Exception as e:
            self._hide_merge_cross_check_ok_banner()
            self._log(f"Cross-check result handling error: {e}", "error")
            self._last_report_html = ""
            self.btn_copy_html.setEnabled(False)
            self.btn_save_report_html.setEnabled(False)
            QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def _run_merge(self) -> None:
        self._log("Running merge...", "info")
        try:
            proc = self._configure_processor_from_ui()
            if not proc:
                return
            self.processor = proc
            include_dnp = not self.merge_delete_dnp.isChecked()
            merged = self.processor.merge_bom_pnp(include_dnp=include_dnp)
            self._last_merge_df = merged
            self.merge_model.update_dataframe(merged)
            self._update_merge_layer_export_controls()
            self._log(f"Merge complete: {len(merged)} rows", "info")
        except SMTProcessorError as e:
            self._log(f"Merge error: {e}", "error")
            self._last_merge_df = None
            self._update_merge_layer_export_controls()
            QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def _replace_pnp_from_merge(self) -> None:
        if self._last_merge_df is None or self._last_merge_df.empty:
            self._log("No merge data to replace PnP — run Merge first", "warning")
            QtWidgets.QMessageBox.warning(
                self, "Replace PNP", "Run Merge first; there is no merge result yet."
            )
            return
        res = QtWidgets.QMessageBox.question(
            self,
            "Replace PNP from Merge?",
            "Replace all data on the PnP tab with the current Merge result?\n\n"
            "This changes the working PnP copy; use Reload on the PnP tab to restore the original file.",
            QtWidgets.QMessageBox.StandardButton.Yes
            | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if res != QtWidgets.QMessageBox.StandardButton.Yes:
            return

        self._pnp_df = self._last_merge_df.copy()
        self._loading_working_copy = True
        self.pnp_model.update_dataframe(self._pnp_df)
        self._loading_working_copy = False
        self._fill_pnp_combos()
        self._autoresize_pnp_columns()
        self._mark_working_dirty("pnp")
        self._log(
            f"PnP replaced from Merge: {len(self._pnp_df)} rows, {len(self._pnp_df.columns)} cols",
            "info",
        )
        self._hide_merge_cross_check_ok_banner()

    def _merge_layer_column(self) -> Optional[str]:
        if self._last_merge_df is None:
            return None
        for col in self._last_merge_df.columns:
            if str(col).strip().lower() == "layer":
                return col
        return None

    @staticmethod
    def _display_layer_value(value: Any) -> str:
        if pd.isna(value):
            return "None"
        text = str(value).strip()
        if not text or text.lower() in ("nan", "none"):
            return "None"
        return text

    @staticmethod
    def _is_bot_layer_value(value: str) -> bool:
        return value.strip().lower() in (
            "m",
            "b",
            "bot",
            "bottom",
            "bottomlayer",
            "mirror",
        )

    @staticmethod
    def _is_top_layer_value(value: str) -> bool:
        return value.strip().lower() in ("t", "top", "toplayer")

    def _merge_layer_values(self) -> list[str]:
        if self._last_merge_df is None or self._last_merge_df.empty:
            return []
        layer_col = self._merge_layer_column()
        if layer_col is None:
            return []
        values: list[str] = []
        for raw in self._last_merge_df[layer_col].tolist():
            val = self._display_layer_value(raw)
            if val not in values:
                values.append(val)
        return values

    def _select_merge_layer_defaults(
        self, values: list[str]
    ) -> tuple[str | None, str | None]:
        if not values:
            return None, None
        top = next((v for v in values if self._is_top_layer_value(v)), None)
        bot = next((v for v in values if self._is_bot_layer_value(v)), None)
        if top is None and "None" in values:
            top = "None"
        if bot is None:
            bot = next((v for v in values if v != top), None)
        if top is None:
            top = next((v for v in values if v != bot), values[0])
        return top, bot

    def _populate_layer_combo(
        self, combo: QtWidgets.QComboBox, values: list[str], selected: str | None
    ) -> None:
        combo.blockSignals(True)
        combo.clear()
        for value in values:
            combo.addItem(value, value)
        if selected is not None:
            idx = combo.findData(selected)
            if idx >= 0:
                combo.setCurrentIndex(idx)
        combo.blockSignals(False)

    def _update_merge_layer_export_controls(self) -> None:
        if not hasattr(self, "btn_export_top"):
            return
        has_merge = self._last_merge_df is not None and not self._last_merge_df.empty
        values = self._merge_layer_values()
        if not values and has_merge:
            values = ["All"]
        top, bot = self._select_merge_layer_defaults(values)
        self._populate_layer_combo(self.merge_top_layer_combo, values, top)
        self._populate_layer_combo(self.merge_bot_layer_combo, values, bot)
        has_layer_split = len(values) > 1 and values != ["All"]
        self.btn_export_top.setEnabled(has_merge)
        self.merge_top_layer_combo.setEnabled(has_merge and bool(values))
        self.btn_export_bot.setEnabled(
            has_merge and has_layer_split and bot is not None
        )
        self.merge_bot_layer_combo.setEnabled(
            has_merge and has_layer_split and bot is not None
        )
        if hasattr(self, "btn_export_mmd_top"):
            self.btn_export_mmd_top.setEnabled(has_merge)
        if hasattr(self, "btn_export_mmd_bot"):
            self.btn_export_mmd_bot.setEnabled(
                has_merge and has_layer_split and bot is not None
            )

    def _merge_filtered_by_layer(self, selected: str) -> pd.DataFrame:
        if self._last_merge_df is None:
            return pd.DataFrame()
        if selected == "All":
            return self._last_merge_df.copy()
        layer_col = self._merge_layer_column()
        if layer_col is None:
            return self._last_merge_df.copy()
        mask = self._last_merge_df[layer_col].map(self._display_layer_value) == selected
        return self._last_merge_df.loc[mask].copy()

    def _export_merge_layer(self, side: str) -> None:
        if self._last_merge_df is None or self._last_merge_df.empty:
            self._log("No merge data to export — run Merge first", "warning")
            return
        combo = (
            self.merge_bot_layer_combo if side == "bot" else self.merge_top_layer_combo
        )
        selected = str(combo.currentData() or combo.currentText() or "All")
        out_df = self._merge_filtered_by_layer(selected)
        if out_df.empty:
            self._log(
                f"Merge {side.upper()} export is empty for Layer={selected}", "warning"
            )
            return
        default_name = f"merge_{side}_{selected.lower().replace(' ', '_')}.csv"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, f"Export {side.upper()} CSV", default_name, "CSV (*.csv);;All (*.*)"
        )
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        try:
            self.processor.export_csv(out_df, path)
            self._log(
                f"Exported {side.upper()} CSV ({selected}): {len(out_df)} rows -> {path}",
                "info",
            )
        except Exception as e:
            self._log(f"Export {side.upper()} CSV error: {e}", "error")
            QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def _export_merge_layer_mmd(self, side: str) -> None:
        if self._last_merge_df is None or self._last_merge_df.empty:
            self._log("No merge data to export — run Merge first", "warning")
            return
        combo = (
            self.merge_bot_layer_combo if side == "bot" else self.merge_top_layer_combo
        )
        selected = str(combo.currentData() or combo.currentText() or "All")
        out_df = self._merge_filtered_by_layer(selected)
        if out_df.empty:
            self._log(
                f"Merge {side.upper()} MMD export is empty for Layer={selected}",
                "warning",
            )
            return
        default_name = f"merge_{side}_{selected.lower().replace(' ', '_')}.mmd"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, f"Export {side.upper()} MMD", default_name, "MMD (*.mmd);;All (*.*)"
        )
        if not path:
            return
        if not path.lower().endswith(".mmd"):
            path += ".mmd"
        try:
            text = merge_dataframe_to_mmd_mercury(
                out_df, pnp_xy_are_mm=self._pnp_xy_stored_in_mm()
            )
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
            self._log(
                f"Exported {side.upper()} MMD ({selected}): {len(out_df)} rows -> {path}",
                "info",
            )
        except Exception as e:
            self._log(f"Export {side.upper()} MMD error: {e}", "error")
            QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def _save_merge_csv(self) -> None:
        if self._last_merge_df is None or self._last_merge_df.empty:
            self._log("No merge data to save — run Merge first", "warning")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save merged CSV", "", "CSV (*.csv);;All (*.*)"
        )
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        try:
            self.processor.export_csv(self._last_merge_df, path)
            self._log(f"Saved CSV: {path}", "info")
        except Exception as e:
            self._log(f"Save CSV error: {e}", "error")
            QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def _save_merge_excel(self) -> None:
        if self._last_merge_df is None or self._last_merge_df.empty:
            self._log("No merge data to save — run Merge first", "warning")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save merged Excel", "", "Excel (*.xlsx);;All (*.*)"
        )
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        try:
            self.processor.export_excel(self._last_merge_df, path)
            self._log(f"Saved Excel: {path}", "info")
        except Exception as e:
            self._log(f"Save Excel error: {e}", "error")
            QtWidgets.QMessageBox.critical(self, "Error", str(e))
