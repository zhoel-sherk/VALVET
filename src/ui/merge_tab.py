"""Merge tab and cross-check / merge operations (MainWindow mixin)."""

from __future__ import annotations

from typing import Any, Optional

import pandas as pd
from PySide6 import QtCore, QtWidgets

from layer_side import (
    display_layer_value,
    is_bot_layer_token,
    is_top_layer_token,
    select_merge_layer_defaults,
)
from mmd_export import merge_dataframe_to_mmd_mercury
from qt_models import SortableTableModel
from report_html import result_dataframe_to_html
from services.processor_config import build_processor_config
from smt_processor import SMTDataProcessor, SMTProcessorError

try:
    from app.workers import CrossCheckThread
except ImportError:
    from typing import Optional as _Optional

    class CrossCheckThread(QtCore.QThread):
        """Runs SMTDataProcessor.cross_check() off the GUI thread."""

        result_ready = QtCore.Signal(object, str)

        def __init__(
            self, proc: SMTDataProcessor, parent: _Optional[QtCore.QObject] = None
        ):
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

        from ui.chrome import (
            ACTION_BTN_MIN_H,
            CHROME_MARGIN,
            CHROME_SPACING,
            action_button,
            apply_equal_widths,
            help_button,
            left_rail_widget,
            segmented_control,
            switch_checkbox,
        )

        root = QtWidgets.QHBoxLayout(tab)
        root.setContentsMargins(
            CHROME_MARGIN, CHROME_MARGIN, CHROME_MARGIN, CHROME_MARGIN
        )
        root.setSpacing(CHROME_SPACING)

        left = left_rail_widget()
        left_l = QtWidgets.QVBoxLayout(left)
        left_l.setContentsMargins(0, 0, 8, 0)
        left_l.setSpacing(CHROME_SPACING)

        merge_group = QtWidgets.QGroupBox(self.ui_tr("merge.group"))
        self.gb_merge = merge_group
        merge_l = QtWidgets.QVBoxLayout(merge_group)
        merge_row = QtWidgets.QHBoxLayout()
        merge_row.setSpacing(CHROME_SPACING)
        self.btn_merge = action_button("Merge")
        self.btn_merge.clicked.connect(self._run_merge)
        merge_row.addWidget(self.btn_merge, 1)
        self.btn_merge_help = help_button(self._show_merge_help)
        self.btn_merge_help.setToolTip(self.ui_tr("merge.help_title"))
        self.btn_merge_help.setMinimumHeight(ACTION_BTN_MIN_H)
        merge_row.addWidget(self.btn_merge_help)
        merge_l.addLayout(merge_row)
        self.merge_delete_dnp = switch_checkbox("Delete DNP")
        self.merge_delete_dnp.setToolTip(
            "When merging, drop PnP placements that are not in the BOM "
            "(unused / extra refs) and rows whose value is DNP or DNP_FROM_BOM."
        )
        self.merge_delete_dnp.stateChanged.connect(self._on_merge_settings_changed)
        merge_l.addWidget(self.merge_delete_dnp)
        xy_row = QtWidgets.QHBoxLayout()
        xy_row.addWidget(QtWidgets.QLabel("PnP XY:"))
        merge_seg, _, merge_btns = segmented_control(("mm", "mil"), parent=merge_group)
        self.merge_pnp_units_mm, self.merge_pnp_units_mils = merge_btns
        self.merge_pnp_units_mm.setChecked(True)
        self.merge_pnp_units_mm.setToolTip(self.pnp_units_mm.toolTip())
        self.merge_pnp_units_mils.setToolTip(self.pnp_units_mils.toolTip())
        self.merge_pnp_units_mm.toggled.connect(
            lambda on: on and self._on_user_pnp_xy_unit_choice(True)
        )
        self.merge_pnp_units_mils.toggled.connect(
            lambda on: on and self._on_user_pnp_xy_unit_choice(False)
        )
        xy_row.addWidget(merge_seg, 1)
        merge_l.addLayout(xy_row)
        self.btn_replace_pnp_from_merge = action_button("Replace PNP")
        self.btn_replace_pnp_from_merge.setToolTip(
            "Replace all rows/columns on the PnP tab with the current Merge result."
        )
        self.btn_replace_pnp_from_merge.clicked.connect(self._replace_pnp_from_merge)
        merge_l.addWidget(self.btn_replace_pnp_from_merge)
        self.btn_find_package = action_button(self.ui_tr("package.find"))
        self.btn_find_package.setToolTip(self.ui_tr("package.find_tip"))
        self.btn_find_package.clicked.connect(self._find_package)
        merge_l.addWidget(self.btn_find_package)
        left_l.addWidget(merge_group)

        cc_group = QtWidgets.QGroupBox("Cross-check")
        cc_l = QtWidgets.QVBoxLayout(cc_group)
        self.btn_cross_check = action_button("Cross-check")
        self.btn_cross_check.clicked.connect(self._run_cross_check)
        cc_l.addWidget(self.btn_cross_check)
        self.chk_critical = switch_checkbox("Critical")
        self.chk_critical.setChecked(True)
        self.chk_critical.toggled.connect(self._on_cross_check_filter_toggled)
        cc_l.addWidget(self.chk_critical)
        self.chk_warning = switch_checkbox("Warning")
        self.chk_warning.setChecked(True)
        self.chk_warning.toggled.connect(self._on_cross_check_filter_toggled)
        cc_l.addWidget(self.chk_warning)
        self.chk_info = switch_checkbox("Info")
        self.chk_info.setChecked(True)
        self.chk_info.toggled.connect(self._on_cross_check_filter_toggled)
        cc_l.addWidget(self.chk_info)
        self.chk_overlap = switch_checkbox("Overlap: mm")
        self.chk_overlap.setChecked(False)
        self.chk_overlap.setToolTip(
            "If enabled, report pairs of placements on the same layer when center distance "
            "(after scaling PnP X/Y per the PnP / Merge / PCB Preview mm↔mils choice) "
            "is below this threshold. Distance limit is always in millimeters. "
            "O(n²) in PnP size — leave off for very dense panels."
        )
        self.spin_overlap_mm = QtWidgets.QDoubleSpinBox()
        self.spin_overlap_mm.setRange(0.1, 999.0)
        self.spin_overlap_mm.setDecimals(2)
        self.spin_overlap_mm.setValue(3.0)
        self.spin_overlap_mm.setEnabled(False)
        self.chk_overlap.toggled.connect(self.spin_overlap_mm.setEnabled)
        self.chk_overlap.toggled.connect(self._save_report_overlap_settings)
        self.spin_overlap_mm.valueChanged.connect(self._save_report_overlap_settings)
        cc_l.addWidget(self.chk_overlap)
        cc_l.addWidget(self.spin_overlap_mm)
        left_l.addWidget(cc_group)

        files_group = QtWidgets.QGroupBox(self.ui_tr("merge.files_group"))
        self.gb_merge_files = files_group
        files_l = QtWidgets.QVBoxLayout(files_group)
        self.btn_save_merge_csv = action_button("Save CSV")
        self.btn_save_merge_csv.clicked.connect(self._save_merge_csv)
        files_l.addWidget(self.btn_save_merge_csv)
        self.btn_save_merge_excel = action_button("Save Excel")
        self.btn_save_merge_excel.clicked.connect(self._save_merge_excel)
        files_l.addWidget(self.btn_save_merge_excel)
        self.btn_export_top = action_button("Export Top")
        self.btn_export_top.setToolTip(
            "Export Merge rows whose Layer matches the selected TOP value."
        )
        self.btn_export_top.clicked.connect(lambda: self._export_merge_layer("top"))
        files_l.addWidget(self.btn_export_top)
        self.merge_top_layer_combo = QtWidgets.QComboBox()
        files_l.addWidget(self.merge_top_layer_combo)
        self.btn_export_bot = action_button("Export Bot")
        self.btn_export_bot.setToolTip(
            "Export Merge rows whose Layer matches the selected BOT/mirror value."
        )
        self.btn_export_bot.clicked.connect(lambda: self._export_merge_layer("bot"))
        files_l.addWidget(self.btn_export_bot)
        self.merge_bot_layer_combo = QtWidgets.QComboBox()
        files_l.addWidget(self.merge_bot_layer_combo)
        self.btn_export_mmd_top = action_button("Export MMD Top")
        self.btn_export_mmd_top.setToolTip(
            "Export MERCURY-style .mmd (INI) for placements whose Layer matches the selected TOP value; "
            "coordinates use mm × 25.4 as in examples/mmd."
        )
        self.btn_export_mmd_top.clicked.connect(
            lambda: self._export_merge_layer_mmd("top")
        )
        files_l.addWidget(self.btn_export_mmd_top)
        self.btn_export_mmd_bot = action_button("Export MMD Bot")
        self.btn_export_mmd_bot.setToolTip(
            "Export MERCURY-style .mmd (INI) for placements whose Layer matches the selected BOT/mirror value."
        )
        self.btn_export_mmd_bot.clicked.connect(
            lambda: self._export_merge_layer_mmd("bot")
        )
        files_l.addWidget(self.btn_export_mmd_bot)
        self._update_merge_layer_export_controls()
        left_l.addWidget(files_group)
        apply_equal_widths(
            (
                self.btn_merge,
                self.btn_cross_check,
                self.btn_replace_pnp_from_merge,
                self.btn_find_package,
                self.btn_save_merge_csv,
                self.btn_save_merge_excel,
                self.btn_export_top,
                self.btn_export_bot,
                self.btn_export_mmd_top,
                self.btn_export_mmd_bot,
            )
        )
        left_l.addStretch(1)
        root.addWidget(left)

        right = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(right)
        layout.setContentsMargins(0, 0, 0, 0)

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
            "Cross-check reported no issues — run Merge, then save or export."
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

        self.merge_cc_issue_banner = QtWidgets.QFrame()
        self.merge_cc_issue_banner.setObjectName("mergeCcIssueBanner")
        self.merge_cc_issue_banner.setVisible(False)
        self.merge_cc_issue_banner.setStyleSheet(
            "QFrame#mergeCcIssueBanner { background-color: rgba(183, 110, 0, 0.22); "
            "border: 1px solid #fb8c00; border-radius: 4px; padding: 6px 8px; }"
        )
        cc_bad_lay = QtWidgets.QHBoxLayout(self.merge_cc_issue_banner)
        cc_bad_lay.setContentsMargins(8, 4, 8, 4)
        self.merge_cc_issue_icon = QtWidgets.QLabel("!")
        self.merge_cc_issue_icon.setStyleSheet(
            "color: #ffb74d; font-size: 22px; font-weight: bold; border: none; background: transparent;"
        )
        self.merge_cc_issue_label = QtWidgets.QLabel("You have issues in BOM/PnP!")
        self.merge_cc_issue_label.setStyleSheet(
            "color: #ffe0b2; font-weight: bold; border: none; background: transparent;"
        )
        self.merge_cc_issue_hint = QtWidgets.QLabel("")
        self.merge_cc_issue_hint.setStyleSheet(
            "color: #ffcc80; border: none; background: transparent;"
        )
        self.merge_cc_issue_hint.setWordWrap(True)
        cc_bad_lay.addWidget(
            self.merge_cc_issue_icon, 0, QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        vbad = QtWidgets.QVBoxLayout()
        vbad.setSpacing(0)
        vbad.addWidget(self.merge_cc_issue_label)
        vbad.addWidget(self.merge_cc_issue_hint)
        cc_bad_lay.addLayout(vbad)
        cc_bad_lay.addStretch()
        layout.addWidget(self.merge_cc_issue_banner)

        self.merge_table = QtWidgets.QTableView()
        self.merge_table.setAlternatingRowColors(True)
        self.merge_model = SortableTableModel(pd.DataFrame())
        self.merge_table.setModel(self.merge_model)
        layout.addWidget(self.merge_table, 1)
        root.addWidget(right, 1)

        self.result_model = SortableTableModel(pd.DataFrame())
        self._cc_window: Optional[Any] = None
        self._cc_full_df: Optional[pd.DataFrame] = None
        self._cc_user_accepted: bool = False

    def _show_merge_help(self) -> None:
        QtWidgets.QMessageBox.information(
            self,
            self.ui_tr("merge.help_title"),
            self.ui_tr("merge.help_body"),
        )

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

        bom_roles = [self._mapping_combo_role(combo) for combo in self.bom_col_combos]
        bom_cols = list(self._bom_df.columns)
        bom_mappings: dict[str, str] = {}
        for i, mapping in enumerate(bom_roles):
            if mapping not in ("-", "PnJoin") and i < len(bom_cols):
                bom_mappings[mapping] = bom_cols[i]

        pnp_mappings: dict[str, str] = {}
        for i, combo in enumerate(self.pnp_col_combos):
            mapping = self._mapping_combo_role(combo)
            if mapping != "-":
                pnp_mappings[mapping] = list(self._pnp_df.columns)[i]

        from smt_processor import SMTColumnNotFoundError

        try:
            return build_processor_config(
                self._bom_df,
                self._pnp_df,
                bom_mappings,
                pnp_mappings,
                bom_column_roles=bom_roles,
                pnp_xy_are_mils=not self._pnp_xy_stored_in_mm(),
                overlap_min_mm=float(self.spin_overlap_mm.value()),
                check_overlap=self.chk_overlap.isChecked(),
                progress_callback=lambda m, level: self.log_message.emit(m, level),
            )
        except SMTColumnNotFoundError as e:
            self._log(str(e), "error")
            QtWidgets.QMessageBox.warning(self, "Column mapping", str(e))
            return None

    def _hide_merge_cross_check_ok_banner(self) -> None:
        if hasattr(self, "merge_cc_ok_banner"):
            self.merge_cc_ok_banner.setVisible(False)
        if hasattr(self, "merge_cc_issue_banner"):
            self.merge_cc_issue_banner.setVisible(False)

    def _show_merge_cross_check_ok_banner(self) -> None:
        if hasattr(self, "merge_cc_issue_banner"):
            self.merge_cc_issue_banner.setVisible(False)
        if hasattr(self, "merge_cc_ok_banner"):
            self.merge_cc_ok_banner.setVisible(True)

    def _show_merge_cross_check_issue_banner(self, hint: str) -> None:
        if hasattr(self, "merge_cc_ok_banner"):
            self.merge_cc_ok_banner.setVisible(False)
        if hasattr(self, "merge_cc_issue_hint"):
            self.merge_cc_issue_hint.setText(hint)
        if hasattr(self, "merge_cc_issue_banner"):
            self.merge_cc_issue_banner.setVisible(True)

    def _ensure_cross_check_window(self) -> Any:
        w = getattr(self, "_cc_window", None)
        if w is not None:
            try:
                w.windowTitle()
                return w
            except RuntimeError:
                self._cc_window = None
        from ui.cross_check_window import CrossCheckResultWindow

        win = CrossCheckResultWindow(
            model=self.result_model,
            on_copy=self._copy_report_html,
            on_save=self._save_report_html,
            parent=self,
        )
        win.proceedAsOk.connect(self._on_cross_check_proceed_as_ok)
        win.returnRequested.connect(self._on_cross_check_return)
        self._cc_window = win
        self.btn_copy_html = win.btn_copy_html
        self.btn_save_report_html = win.btn_save_report_html
        self.result_table = win.result_table
        return win

    def _filter_cross_check_df(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty or "Severity" not in df.columns:
            return df
        filtered = df
        if not self.chk_critical.isChecked():
            filtered = filtered[filtered["Severity"] != "critical"]
        if not self.chk_warning.isChecked():
            filtered = filtered[filtered["Severity"] != "warning"]
        if not self.chk_info.isChecked():
            filtered = filtered[filtered["Severity"] != "info"]
        return filtered

    def _rebuild_cross_check_html(self, filtered: pd.DataFrame) -> None:
        bom_p = self.bom_path_label.text()
        pnp_p = self._pnp_report_paths_display()
        self._last_report_html = result_dataframe_to_html(
            filtered,
            bom_p if not bom_p.startswith("<") else "",
            pnp_p if not pnp_p.startswith("<") else "",
        )
        has_report = bool(self._last_report_html)
        if hasattr(self, "btn_copy_html"):
            self.btn_copy_html.setEnabled(has_report)
        if hasattr(self, "btn_save_report_html"):
            self.btn_save_report_html.setEnabled(has_report)

    def _on_cross_check_filter_toggled(self, *_args: object) -> None:
        self._save_report_filter_settings()
        full = getattr(self, "_cc_full_df", None)
        if full is None:
            return
        filtered = self._filter_cross_check_df(full)
        self._result_df = filtered
        if hasattr(self, "result_model"):
            self.result_model.update_dataframe(
                filtered if filtered is not None else pd.DataFrame()
            )
        self._rebuild_cross_check_html(
            filtered if filtered is not None else pd.DataFrame()
        )

    def _save_report_filter_settings(self) -> None:
        if self._restoring_settings or not hasattr(self, "_settings"):
            return
        if not hasattr(self, "chk_critical"):
            return
        s = self._settings
        s.setValue("report/show_critical", self.chk_critical.isChecked())
        s.setValue("report/show_warning", self.chk_warning.isChecked())
        s.setValue("report/show_info", self.chk_info.isChecked())

    def _save_report_overlap_settings(self) -> None:
        if self._restoring_settings or not hasattr(self, "_settings"):
            return
        s = self._settings
        s.setValue("report/check_overlap", self.chk_overlap.isChecked())
        s.setValue("report/overlap_mm", float(self.spin_overlap_mm.value()))

    def _on_cross_check_proceed_as_ok(self) -> None:
        self._cc_user_accepted = True
        self._show_merge_cross_check_ok_banner()
        self._log("Cross-check: proceeded as OK", "info")

    def _cross_check_return_tab_key(self) -> str | None:
        full = getattr(self, "_cc_full_df", None)
        if full is None or full.empty or "IssueType" not in full.columns:
            return None
        types = set(str(x) for x in full["IssueType"].tolist())
        bom_only = types <= {"missing_in_pnp"}
        pnp_only = types <= {"missing_in_bom", "duplicate_coord", "overlapping"}
        if bom_only:
            return "bom"
        if pnp_only:
            return "pnp"
        return None

    def _on_cross_check_return(self) -> None:
        w = getattr(self, "_cc_window", None)
        if w is not None:
            w.hide()
        full = getattr(self, "_cc_full_df", None)
        clean = full is None or getattr(full, "empty", True)
        if clean or getattr(self, "_cc_user_accepted", False):
            if clean:
                self._show_merge_cross_check_ok_banner()
            return
        filtered = self._result_df
        crit = warn_n = info_n = 0
        if (
            filtered is not None
            and not filtered.empty
            and "Severity" in filtered.columns
        ):
            crit = int((filtered["Severity"] == "critical").sum())
            warn_n = int((filtered["Severity"] == "warning").sum())
            info_n = int((filtered["Severity"] == "info").sum())
        hint = f"Critical: {crit}  Warning: {warn_n}  Info: {info_n}"
        self._show_merge_cross_check_issue_banner(hint)
        key = self._cross_check_return_tab_key()
        if key:
            idx = self._tab_index(key)
            if idx >= 0:
                self.tabs.setCurrentIndex(idx)

    def _run_cross_check(self) -> None:
        t = self._cc_thread
        if t is not None:
            try:
                if t.isRunning():
                    self._log("Cross-check already running", "warning")
                    return
            except RuntimeError:
                self._cc_thread = None
        self._cc_user_accepted = False
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
            t.wait(5000)
            t.deleteLater()

    def _on_cross_check_finished(self, result: Any, err: str) -> None:
        if err:
            self._hide_merge_cross_check_ok_banner()
            self._log(f"Cross-check error: {err}", "error")
            self._last_report_html = ""
            self._cc_full_df = None
            QtWidgets.QMessageBox.critical(self, "Error", err)
            return
        if result is None:
            self._hide_merge_cross_check_ok_banner()
            return
        from services.column_mapping import likely_ref_mapped_to_pn

        if not result.empty and "IssueType" in result.columns:
            miss_pnp = result[result["IssueType"] == "missing_in_pnp"]
            miss_bom = result[result["IssueType"] == "missing_in_bom"]
            if likely_ref_mapped_to_pn(
                miss_pnp["Designator"].astype(str),
                miss_bom["Designator"].astype(str),
                miss_bom["PnP_Value"].astype(str),
            ):
                msg = (
                    "Cross-check keys barely overlap: BOM REF looks like part numbers "
                    "(PN), while PnP REF looks like designators. "
                    "On the BOM tab set REF to the designator column and PN name "
                    "to the cleaned comment column, then run Cross-check again."
                )
                self._log(msg, "warning")
                QtWidgets.QMessageBox.warning(self, "Column mapping", msg)
        cross_check_clean = bool(result.empty)
        try:
            self._cc_full_df = result
            filtered = self._filter_cross_check_df(result)
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
                self._cc_user_accepted = True
                self._show_merge_cross_check_ok_banner()
                self._log(
                    "Cross-check complete: no issues — BOM and PnP are consistent.",
                    "info",
                )
            else:
                self._log(
                    f"Cross-check complete: {len(filtered)} issue(s) in report view",
                    "info",
                )
                self._log(f"  Critical: {critical}", "info")
                self._log(f"  Warning: {warn_n}", "info")
                self._log(f"  Info: {info_n}", "info")

            self._rebuild_cross_check_html(filtered)
            win = self._ensure_cross_check_window()
            win.present(
                clean=cross_check_clean,
                filtered=filtered,
                has_html=bool(self._last_report_html),
            )
        except Exception as e:
            self._hide_merge_cross_check_ok_banner()
            self._log(f"Cross-check result handling error: {e}", "error")
            self._last_report_html = ""
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
            self._log(
                f"Merge complete: {len(merged)} rows (Merge → dataframe)",
                "info",
            )
            self._refresh_pcb_preview_from_ui(force=False)
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
        from services.column_mapping import merge_result_pnp_roles

        self._fill_pnp_combos(
            preserved_roles=merge_result_pnp_roles(list(self._pnp_df.columns))
        )
        self._autoresize_pnp_columns()
        self._mark_working_dirty("pnp")
        self._log(
            f"Merge → PnP: replaced {len(self._pnp_df)} rows, "
            f"{len(self._pnp_df.columns)} cols",
            "info",
        )
        self._hide_merge_cross_check_ok_banner()

    def _find_package(self) -> None:
        if self._last_merge_df is None or self._last_merge_df.empty:
            self._log(self.ui_tr("package.find_need_merge"), "warning")
            QtWidgets.QMessageBox.warning(
                self,
                self.ui_tr("package.find"),
                self.ui_tr("package.find_need_merge"),
            )
            return
        from package_vspd.resolve import (
            apply_hits_to_dataframe,
            count_sources,
            machine_lookup_from_part_rows,
            resolve_unique_packages,
        )

        df = self._last_merge_df
        store = None
        pkg = getattr(self, "_package_tab", None)
        if pkg is not None:
            store = getattr(pkg, "_store", None)
        machine_lookup = None
        ml = getattr(self, "_machine_library_tab", None)
        hdf = getattr(ml, "_hanwha_df", None) if ml is not None else None
        if ml is not None and hdf is not None and not hdf.empty:
            records = hdf.to_dict("records")
            machine_lookup = machine_lookup_from_part_rows(
                records, ml.hanwha_partname_set()
            )
        bom_by_ref = self._bom_comments_by_ref()
        rows = df.to_dict("records")
        hits = resolve_unique_packages(
            rows,
            store=store,
            machine_lookup=machine_lookup,
            bom_by_ref=bom_by_ref or None,
        )
        n_write = apply_hits_to_dataframe(df, hits)
        self.merge_model.update_dataframe(df)
        c = count_sources(hits)
        msg = self.ui_tr(
            "package.find_status",
            n=c["parts"],
            k=c["store"] + c["machine"],
            p=c["pnp"],
            b=c["bom"],
            u=c["unmatched"],
        )
        self._log(f"Find package → Merge: {msg} ({n_write} rows)", "info")

    def _bom_comments_by_ref(self) -> dict[str, str]:
        self._sync_bom_df_from_model()
        bom = self._bom_df
        if bom is None or bom.empty:
            return {}
        if not getattr(self, "bom_col_combos", None):
            return {}
        bom_cols = list(bom.columns)
        ref_col = None
        comment_cols: list[str] = []
        for i, combo in enumerate(self.bom_col_combos):
            if i >= len(bom_cols):
                break
            role = self._mapping_combo_role(combo)
            if role == "REF":
                ref_col = bom_cols[i]
            elif role == "Comment":
                comment_cols.append(bom_cols[i])
        if ref_col is None:
            return {}
        if not comment_cols:
            for name in bom_cols:
                low = str(name).strip().lower()
                if low in {"comment", "value", "part", "pn"}:
                    comment_cols.append(name)
        out: dict[str, str] = {}
        for _, rec in bom.iterrows():
            ref = str(rec.get(ref_col, "") or "").strip()
            if not ref:
                continue
            parts: list[str] = []
            for col in comment_cols:
                val = rec.get(col, "")
                if pd.isna(val):
                    continue
                s = str(val).strip()
                if s and s.lower() not in {"nan", "none"}:
                    parts.append(s)
            if parts:
                out[ref] = " ".join(parts)
                out[ref.upper()] = out[ref]
        return out

    def _sync_merge_df_from_model(self) -> None:
        if not hasattr(self, "merge_model"):
            return
        df = self.merge_model.get_dataframe()
        if df is not None:
            self._last_merge_df = df

    def _merge_layer_column(self) -> Optional[str]:
        if self._last_merge_df is None:
            return None
        for col in self._last_merge_df.columns:
            if str(col).strip().lower() == "layer":
                return col
        return None

    @staticmethod
    def _display_layer_value(value: Any) -> str:
        return display_layer_value(value)

    @staticmethod
    def _is_bot_layer_value(value: str) -> bool:
        return is_bot_layer_token(value)

    @staticmethod
    def _is_top_layer_value(value: str) -> bool:
        return is_top_layer_token(value)

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
        return select_merge_layer_defaults(values)

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
