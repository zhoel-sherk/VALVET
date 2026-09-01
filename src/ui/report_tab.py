"""HTML copy/save for Cross-check (window buttons; no Report tab)."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6 import QtCore, QtWidgets

from report_html import html_document_from_fragment, result_dataframe_plain_text


class ReportTabMixin:
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
