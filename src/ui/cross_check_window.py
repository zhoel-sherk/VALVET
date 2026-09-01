"""Non-modal Cross-check results window."""

from __future__ import annotations

from typing import Callable

import pandas as pd
from PySide6 import QtCore, QtGui, QtWidgets

from qt_models import SortableTableModel
from ui.chrome import action_button, apply_equal_widths


class CrossCheckResultWindow(QtWidgets.QWidget):
    """Standalone Cross-check view; does not block the main window."""

    proceedAsOk = QtCore.Signal()
    returnRequested = QtCore.Signal()

    def __init__(
        self,
        *,
        model: SortableTableModel,
        on_copy: Callable[[], None],
        on_save: Callable[[], None],
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cross-check")
        flags = QtCore.Qt.WindowType.Window
        self.setWindowFlags(self.windowFlags() | flags)
        self.resize(900, 560)
        self._closing = False

        root = QtWidgets.QVBoxLayout(self)
        self._status = QtWidgets.QLabel("No issues found")
        self._status.setWordWrap(True)
        root.addWidget(self._status)

        btn_row = QtWidgets.QHBoxLayout()
        self.btn_copy_html = action_button("Copy HTML")
        self.btn_copy_html.setToolTip("Copy last cross-check result as HTML")
        self.btn_copy_html.clicked.connect(on_copy)
        btn_row.addWidget(self.btn_copy_html)
        self.btn_save_report_html = action_button("Save HTML report…")
        self.btn_save_report_html.setToolTip(
            "Save last cross-check report as a standalone .html file"
        )
        self.btn_save_report_html.clicked.connect(on_save)
        btn_row.addWidget(self.btn_save_report_html)
        self.btn_proceed = action_button("Proceed as OK")
        self.btn_proceed.setToolTip(
            "Acknowledge findings and treat PnP as ready for Merge / Export."
        )
        self.btn_proceed.clicked.connect(self.proceedAsOk.emit)
        btn_row.addWidget(self.btn_proceed)
        self.btn_return = action_button("Return")
        self.btn_return.clicked.connect(self._on_return_clicked)
        btn_row.addWidget(self.btn_return)
        btn_row.addStretch(1)
        apply_equal_widths(
            (
                self.btn_copy_html,
                self.btn_save_report_html,
                self.btn_proceed,
                self.btn_return,
            )
        )
        root.addLayout(btn_row)

        self.result_table = QtWidgets.QTableView()
        self.result_table.setAlternatingRowColors(True)
        self.result_table.setModel(model)
        root.addWidget(self.result_table, 1)

    def present(self, *, clean: bool, filtered: pd.DataFrame, has_html: bool) -> None:
        self.btn_copy_html.setEnabled(has_html)
        self.btn_save_report_html.setEnabled(has_html)
        if clean:
            self._status.setText("No issues found. BOM and PnP look consistent.")
            self.btn_proceed.setVisible(False)
            self.result_table.setVisible(False)
            self.btn_copy_html.setVisible(False)
            self.btn_save_report_html.setVisible(False)
        else:
            n = 0 if filtered is None or filtered.empty else len(filtered)
            self._status.setText(
                f"Cross-check found {n} issue(s) in the current filters."
            )
            self.btn_proceed.setVisible(True)
            self.result_table.setVisible(True)
            self.btn_copy_html.setVisible(True)
            self.btn_save_report_html.setVisible(True)
        self.show()
        self.raise_()
        self.activateWindow()

    def _on_return_clicked(self) -> None:
        self._emit_return_and_hide()

    def _emit_return_and_hide(self) -> None:
        if self._closing:
            return
        self._closing = True
        self.hide()
        self.returnRequested.emit()
        self._closing = False

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        event.ignore()
        self._emit_return_and_hide()
