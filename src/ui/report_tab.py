"""Cross-check report tab (MainWindow mixin)."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6 import QtCore, QtWidgets
import pandas as pd

from qt_models import SortableTableModel
from report_html import html_document_from_fragment, result_dataframe_plain_text


class ReportTabMixin:

    def _create_report_tab(self):
        """Cross-check report tab."""
        tab = QtWidgets.QWidget()
        self._register_main_tab("report", tab)

        from ui.chrome import CHROME_MARGIN, CHROME_SPACING, action_button, apply_equal_widths, left_rail_widget

        root = QtWidgets.QHBoxLayout(tab)
        root.setContentsMargins(CHROME_MARGIN, CHROME_MARGIN, CHROME_MARGIN, CHROME_MARGIN)
        root.setSpacing(CHROME_SPACING)

        left = left_rail_widget()
        left_l = QtWidgets.QVBoxLayout(left)
        left_l.setContentsMargins(0, 0, 8, 0)
        left_l.setSpacing(CHROME_SPACING)

        self.btn_cross_check = action_button("Cross-check")
        self.btn_cross_check.clicked.connect(self._run_cross_check)
        left_l.addWidget(self.btn_cross_check)
        self.btn_copy_html = action_button("Copy HTML")
        self.btn_copy_html.setEnabled(False)
        self.btn_copy_html.setToolTip("Copy last cross-check result as HTML")
        self.btn_copy_html.clicked.connect(self._copy_report_html)
        left_l.addWidget(self.btn_copy_html)
        self.btn_save_report_html = action_button("Save HTML report…")
        self.btn_save_report_html.setEnabled(False)
        self.btn_save_report_html.setToolTip(
            "Save last cross-check report as a standalone .html file (same styling as Copy HTML)"
        )
        self.btn_save_report_html.clicked.connect(self._save_report_html)
        left_l.addWidget(self.btn_save_report_html)

        self.chk_critical = QtWidgets.QCheckBox("Critical")
        self.chk_critical.setChecked(True)
        left_l.addWidget(self.chk_critical)
        self.chk_warning = QtWidgets.QCheckBox("Warning")
        self.chk_warning.setChecked(True)
        left_l.addWidget(self.chk_warning)
        self.chk_info = QtWidgets.QCheckBox("Info")
        self.chk_info.setChecked(True)
        left_l.addWidget(self.chk_info)

        self.chk_overlap = QtWidgets.QCheckBox("Overlap: min center distance (mm)")
        self.chk_overlap.setChecked(False)
        self.chk_overlap.setToolTip(
            "If enabled, report pairs of placements on the same layer when center distance (after scaling "
            "PnP X/Y per the **PnP / Merge / Report / PCB Preview** mm↔mils choice) is below this threshold. "
            "Distance limit is always in millimeters. O(n²) in PnP size — leave off for very dense panels."
        )
        self.spin_overlap_mm = QtWidgets.QDoubleSpinBox()
        self.spin_overlap_mm.setRange(0.1, 999.0)
        self.spin_overlap_mm.setDecimals(2)
        self.spin_overlap_mm.setValue(3.0)
        self.spin_overlap_mm.setEnabled(False)
        self.chk_overlap.toggled.connect(self.spin_overlap_mm.setEnabled)
        self.chk_overlap.toggled.connect(self._save_report_overlap_settings)
        self.spin_overlap_mm.valueChanged.connect(self._save_report_overlap_settings)
        left_l.addWidget(self.chk_overlap)
        left_l.addWidget(self.spin_overlap_mm)

        xy_row = QtWidgets.QHBoxLayout()
        xy_row.addWidget(QtWidgets.QLabel("PnP XY:"))
        self.report_pnp_units_mm = QtWidgets.QRadioButton("mm")
        self.report_pnp_units_mils = QtWidgets.QRadioButton("mils")
        self.report_pnp_units_mm.setChecked(True)
        self.report_pnp_units_mm.setToolTip(self.pnp_units_mm.toolTip())
        self.report_pnp_units_mils.setToolTip(self.pnp_units_mils.toolTip())
        self.report_pnp_units_mm.toggled.connect(
            lambda on: on and self._on_user_pnp_xy_unit_choice(True)
        )
        self.report_pnp_units_mils.toggled.connect(
            lambda on: on and self._on_user_pnp_xy_unit_choice(False)
        )
        xy_row.addWidget(self.report_pnp_units_mm)
        xy_row.addWidget(self.report_pnp_units_mils)
        xy_row.addStretch(1)
        left_l.addLayout(xy_row)
        apply_equal_widths(
            (self.btn_cross_check, self.btn_copy_html, self.btn_save_report_html)
        )
        left_l.addStretch(1)
        root.addWidget(left)

        self.result_table = QtWidgets.QTableView()
        self.result_table.setAlternatingRowColors(True)
        self.result_model = SortableTableModel(pd.DataFrame())
        self.result_table.setModel(self.result_model)
        root.addWidget(self.result_table, 1)

    def _save_report_overlap_settings(self) -> None:
        if self._restoring_settings or not hasattr(self, "_settings"):
            return
        s = self._settings
        s.setValue("report/check_overlap", self.chk_overlap.isChecked())
        s.setValue("report/overlap_mm", float(self.spin_overlap_mm.value()))

    def _copy_report_html(self) -> None:
        if not self._last_report_html:
            self._log("No report HTML — run Cross-check first", "warning")
            return
        app = QtWidgets.QApplication.instance()
        if app is None:
            return
        clip = app.clipboard()
        mime = QtCore.QMimeData()
        plain = (
            result_dataframe_plain_text(self._result_df)
            if self._result_df is not None
            else ""
        )
        mime.setHtml(self._last_report_html)
        mime.setText(plain if plain else self._last_report_html)
        clip.setMimeData(mime)
        self._log("Report copied to clipboard (HTML + text)", "info")

    def _save_report_html(self) -> None:
        if not self._last_report_html:
            self._log("No report HTML — run Cross-check first", "warning")
            QtWidgets.QMessageBox.warning(
                self,
                "Save HTML report",
                "Run Cross-check first; there is no report to save.",
            )
            return
        bom_t = self.bom_path_label.text()
        pnp_t = (self._pnp_source_path or "").strip() or self.pnp_path_label.text()
        start_dir = os.getcwd()
        suggest = "cross_check_report.html"
        for p in (bom_t, pnp_t):
            if not p or p.startswith("<"):
                continue
            path_obj = Path(p).expanduser()
            try:
                resolved = path_obj.resolve()
            except OSError:
                continue
            parent = resolved.parent
            if parent.is_dir():
                start_dir = str(parent)
            if path_obj.is_file():
                suggest = f"{path_obj.stem}_cross_check_report.html"
                break
            if path_obj.stem:
                suggest = f"{path_obj.stem}_cross_check_report.html"
                break

        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save HTML report",
            os.path.join(start_dir, suggest),
            "HTML files (*.html);;All files (*)",
        )
        if not path:
            return
        if not path.lower().endswith(".html"):
            path += ".html"
        try:
            doc = html_document_from_fragment(self._last_report_html)
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(doc)
        except OSError as e:
            self._log(f"Save HTML report failed: {e}", "error")
            QtWidgets.QMessageBox.critical(self, "Save HTML report", str(e))
            return
        self._log(f"Saved HTML report: {path}", "info")
