"""Table edit, context menu, and per-file tab settings (MainWindow mixin)."""

from __future__ import annotations

import os
from typing import Any

from PySide6 import QtCore, QtWidgets

from settings_paths import path_settings_hash
from services.find_replace import find_and_replace


class TableActionsMixin:
    def _capture_table_edit_state(self, kind: str) -> dict[str, Any]:
        table = self.bom_table if kind == "bom" else self.pnp_table
        model = self.bom_model if kind == "bom" else self.pnp_model
        combos = (
            self.bom_col_combos if kind == "bom" else self.pnp_col_combos
        )
        df = model.get_dataframe()
        selected = sorted(
            {
                (idx.row(), idx.column())
                for idx in table.selectionModel().selectedIndexes()
            }
        )
        widths = [table.columnWidth(c) for c in range(model.columnCount())]
        mappings = self._mapping_roles_from_combos(combos) if combos else []
        return {
            "columns": list(df.columns) if df is not None else [],
            "selected": selected,
            "widths": widths,
            "mappings": mappings,
        }
    def _restore_table_edit_state(self, kind: str, state: dict[str, Any]) -> bool:
        table = self.bom_table if kind == "bom" else self.pnp_table
        model = self.bom_model if kind == "bom" else self.pnp_model
        combos = (
            self.bom_col_combos if kind == "bom" else self.pnp_col_combos
        )
        df = model.get_dataframe()
        if df is None or list(df.columns) != state.get("columns", []):
            return False
        widths = state.get("widths") or []
        for c, w in enumerate(widths):
            if c < model.columnCount() and w > 0:
                table.setColumnWidth(c, w)
        if combos and state.get("mappings"):
            restoring = "_bom_ui_restoring" if kind == "bom" else "_pnp_ui_restoring"
            setattr(self, restoring, True)
            try:
                self._restore_mapping_roles_to_combos(combos, state["mappings"])
            finally:
                setattr(self, restoring, False)
        sel = state.get("selected") or []
        if sel:
            sm = table.selectionModel()
            sm.clearSelection()
            for row, col in sel:
                if row < model.rowCount() and col < model.columnCount():
                    idx = model.index(row, col)
                    sm.select(
                        idx,
                        QtCore.QItemSelectionModel.SelectionFlag.Select
                        | QtCore.QItemSelectionModel.SelectionFlag.Rows,
                    )
            if sel:
                table.setCurrentIndex(model.index(sel[0][0], sel[0][1]))
        if kind == "bom":
            self._sync_bom_all_combos_width()
        else:
            self._sync_pnp_all_combos_width()
        return True
    def _on_table_context_menu(self, pos: QtCore.QPoint, kind: str) -> None:
        table = self.bom_table if kind == "bom" else self.pnp_table
        model = self.bom_model if kind == "bom" else self.pnp_model
        if model.rowCount() <= 0 and model.columnCount() <= 0:
            return
        menu = QtWidgets.QMenu(self)
        act_rows = menu.addAction(self.ui_tr("table.delete_rows"))
        act_cols = menu.addAction(self.ui_tr("table.delete_columns"))
        chosen = menu.exec(table.viewport().mapToGlobal(pos))
        if chosen is act_rows:
            self._delete_table_rows(kind)
        elif chosen is act_cols:
            self._delete_table_columns(kind)
    def _delete_table_rows(self, kind: str) -> None:
        table = self.bom_table if kind == "bom" else self.pnp_table
        model = self.bom_model if kind == "bom" else self.pnp_model
        df = model.get_dataframe()
        if df is None or df.empty:
            return
        rows = sorted(
            {idx.row() for idx in table.selectionModel().selectedIndexes()},
            reverse=True,
        )
        if not rows:
            cur = table.currentIndex()
            if cur.isValid():
                rows = [cur.row()]
        if not rows:
            return
        new_df = df.drop(df.index[rows]).reset_index(drop=True)
        model.update_dataframe(new_df)
        if kind == "bom":
            self._bom_df = new_df
            self._mark_working_dirty("bom")
            self._refresh_active_row_highlight("bom")
        else:
            self._pnp_df = new_df
            self._mark_working_dirty("pnp")
            self._refresh_active_row_highlight("pnp")
            self._refresh_pcb_preview_from_ui()
    def _delete_table_columns(self, kind: str) -> None:
        table = self.bom_table if kind == "bom" else self.pnp_table
        model = self.bom_model if kind == "bom" else self.pnp_model
        combos = (
            self.bom_col_combos if kind == "bom" else self.pnp_col_combos
        )
        df = model.get_dataframe()
        if df is None or df.empty or not combos:
            return
        cols = sorted(
            {idx.column() for idx in table.selectionModel().selectedIndexes()},
            reverse=True,
        )
        if not cols:
            cur = table.currentIndex()
            if cur.isValid():
                cols = [cur.column()]
        if not cols:
            return
        roles = self._mapping_roles_from_combos(combos)
        colnames = list(df.columns)
        drop_names = [colnames[c] for c in cols if c < len(colnames)]
        new_df = df.drop(columns=drop_names, errors="ignore")
        kept_roles = [r for i, r in enumerate(roles) if i not in cols]
        model.update_dataframe(new_df)
        if kind == "bom":
            self._bom_df = new_df
            self._fill_bom_combos(preserved_roles=kept_roles)
            self._mark_working_dirty("bom")
            QtCore.QTimer.singleShot(0, self._autoresize_bom_columns)
        else:
            self._pnp_df = new_df
            self._fill_pnp_combos(preserved_roles=kept_roles)
            self._mark_working_dirty("pnp")
            QtCore.QTimer.singleShot(0, self._autoresize_pnp_columns)
            self._refresh_pcb_preview_from_ui()
    def _find_replace_table(self, kind: str) -> None:
        table = self.bom_table if kind == "bom" else self.pnp_table
        model = self.bom_model if kind == "bom" else self.pnp_model
        df = model.get_dataframe()
        if df is None or df.empty:
            self._log(f"{kind.upper()}: no table data for Find / Replace", "warning")
            return

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(f"{kind.upper()} Find / Replace")
        form = QtWidgets.QFormLayout(dlg)
        find_edit = QtWidgets.QLineEdit()
        replace_edit = QtWidgets.QLineEdit()
        scope_combo = QtWidgets.QComboBox()
        scope_combo.addItem("Selected cells", "selected")
        scope_combo.addItem("Current column", "column")
        scope_combo.addItem("Whole table", "all")
        match_case = QtWidgets.QCheckBox("Match case")
        whole_cell = QtWidgets.QCheckBox("Whole cell")
        form.addRow("Find", find_edit)
        form.addRow("Replace with", replace_edit)
        form.addRow("Scope", scope_combo)
        form.addRow(match_case)
        form.addRow(whole_cell)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Apply
            | QtWidgets.QDialogButtonBox.StandardButton.Close
        )
        buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Apply).setText(
            "Replace all"
        )
        form.addRow(buttons)

        def replace_all() -> None:
            needle = find_edit.text()
            if not needle:
                self._log("Find / Replace: empty Find text", "warning")
                return
            repl = replace_edit.text()
            scope = scope_combo.currentData()
            indexes: list[tuple[int, int]] = []
            if scope == "selected":
                indexes = sorted(
                    {
                        (idx.row(), idx.column())
                        for idx in table.selectionModel().selectedIndexes()
                    }
                )
                if not indexes:
                    self._log("Find / Replace: no selected cells", "warning")
                    return
            elif scope == "column":
                cur = table.currentIndex()
                if not cur.isValid():
                    self._log(
                        "Find / Replace: select a current cell/column first", "warning"
                    )
                    return
                indexes = [(r, cur.column()) for r in range(len(df))]
            else:
                indexes = [
                    (r, c) for r in range(len(df)) for c in range(len(df.columns))
                ]

            new_df, changed = find_and_replace(
                df, needle, repl, indexes,
                match_case=match_case.isChecked(),
                whole_cell=whole_cell.isChecked(),
            )
            if changed:
                edit_state = self._capture_table_edit_state(kind)
                model.update_dataframe(new_df)
                columns_unchanged = list(new_df.columns) == edit_state.get(
                    "columns", []
                )
                if kind == "bom":
                    self._bom_df = new_df
                    self._mark_working_dirty("bom")
                else:
                    self._pnp_df = new_df
                    self._mark_working_dirty("pnp")
                if columns_unchanged:
                    self._restore_table_edit_state(kind, edit_state)
                elif kind == "bom":
                    self._fill_bom_combos()
                    QtCore.QTimer.singleShot(0, self._autoresize_bom_columns)
                else:
                    self._fill_pnp_combos()
                    QtCore.QTimer.singleShot(0, self._autoresize_pnp_columns)
            self._log(
                f"{kind.upper()} Find / Replace: {changed} cell(s) changed", "info"
            )

        buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Apply).clicked.connect(
            replace_all
        )
        buttons.rejected.connect(dlg.reject)
        dlg.resize(420, 180)
        dlg.exec()
    def _active_row_indices(
        self,
        total_rows: int,
        first_widget: QtWidgets.QLineEdit,
        last_widget: QtWidgets.QLineEdit,
    ) -> list[int]:
        if total_rows <= 0:
            return []
        try:
            first = max(0, int(first_widget.text() or "1") - 1)
        except ValueError:
            first = 0
        try:
            last_text = last_widget.text().strip()
            last = int(last_text) - 1 if last_text else total_rows - 1
        except ValueError:
            last = total_rows - 1
        last = min(max(last, first), total_rows - 1)
        if first >= total_rows:
            return []
        return list(range(first, last + 1))
    def _active_row_numbers(
        self,
        total_rows: int,
        first_widget: QtWidgets.QLineEdit,
        last_widget: QtWidgets.QLineEdit,
    ) -> tuple[int | None, int | None]:
        if total_rows <= 0:
            return None, None
        try:
            first = max(1, int(first_widget.text() or "1"))
        except ValueError:
            first = 1
        try:
            last_text = last_widget.text().strip()
            last = int(last_text) if last_text else total_rows
        except ValueError:
            last = total_rows
        if first > total_rows:
            return None, None
        return first, min(max(last, first), total_rows)
    def _refresh_active_row_highlight(self, kind: str) -> None:
        if kind == "bom" and hasattr(self, "bom_model"):
            first, last = self._active_row_numbers(
                self.bom_model.rowCount(), self.bom_first_row, self.bom_last_row
            )
            self.bom_model.set_active_row_range(first, last)
            self.bom_table.verticalHeader().viewport().update()
        elif kind == "pnp" and hasattr(self, "pnp_model"):
            first, last = self._active_row_numbers(
                self.pnp_model.rowCount(), self.pnp_first_row, self.pnp_last_row
            )
            self.pnp_model.set_active_row_range(first, last)
            self.pnp_table.verticalHeader().viewport().update()
    def _on_bom_first_last_row_changed(self, *_args) -> None:
        self._refresh_active_row_highlight("bom")
        self._schedule_save_bom_tab_settings()
        if hasattr(self, "_mark_clean_preview_stale"):
            self._mark_clean_preview_stale()
    def _on_pnp_first_last_row_changed(self, *_args) -> None:
        self._refresh_active_row_highlight("pnp")
        self._schedule_save_pnp_tab_settings()
    def _schedule_save_bom_tab_settings(self) -> None:
        if self._bom_ui_restoring or self._restoring_settings:
            return
        self._bom_tab_settings_timer.start(400)
    def _schedule_save_pnp_tab_settings(self) -> None:
        if self._pnp_ui_restoring or self._restoring_settings:
            return
        self._pnp_tab_settings_timer.start(400)
    def _save_bom_tab_settings_to_disk(self) -> None:
        if self._bom_ui_restoring or self._restoring_settings:
            return
        path = self._bom_source_path
        if not path or not os.path.isfile(path):
            return
        h = path_settings_hash(path)
        self._settings.beginGroup(f"bom/ui/{h}")
        self._settings.setValue("separator", self.bom_separator.currentText())
        self._settings.setValue("first_row", self.bom_first_row.text())
        self._settings.setValue("last_row", self.bom_last_row.text())
        if hasattr(self, "bom_col_combos") and self.bom_col_combos:
            self._settings.setValue(
                "mappings",
                self._mapping_roles_from_combos(self.bom_col_combos),
            )
        self._settings.endGroup()
    def _save_pnp_tab_settings_to_disk(self) -> None:
        if self._pnp_ui_restoring or self._restoring_settings:
            return
        path = self._pnp_snapshot_identity_path()
        if not path or not os.path.isfile(path.split("\n+pnp_merge:\n", 1)[0]):
            return
        h = path_settings_hash(path)
        self._settings.beginGroup(f"pnp/ui/{h}")
        self._settings.setValue("separator", self.pnp_separator.currentText())
        self._settings.setValue("first_row", self.pnp_first_row.text())
        self._settings.setValue("last_row", self.pnp_last_row.text())
        if hasattr(self, "pnp_col_combos") and self.pnp_col_combos:
            self._settings.setValue(
                "mappings",
                self._mapping_roles_from_combos(self.pnp_col_combos),
            )
        self._settings.endGroup()
    def _restore_bom_tab_load_params(self, path: str) -> None:
        if not path or not os.path.isfile(path):
            return
        h = path_settings_hash(path)
        self._settings.beginGroup(f"bom/ui/{h}")
        try:
            if not self._settings.contains("separator"):
                return
            self._bom_ui_restoring = True
            sep = self._settings.value("separator", "auto")
            if isinstance(sep, str) and self.bom_separator.findText(sep) >= 0:
                self.bom_separator.setCurrentText(sep)
            elif isinstance(sep, str):
                idx = self.bom_separator.findText(sep)
                if idx >= 0:
                    self.bom_separator.setCurrentIndex(idx)
            self.bom_first_row.setText(str(self._settings.value("first_row", "1")))
            self.bom_last_row.setText(str(self._settings.value("last_row", "")))
        finally:
            self._bom_ui_restoring = False
            self._settings.endGroup()
    def _restore_pnp_tab_load_params(self, path: str) -> None:
        if not path:
            return
        primary = path.split("\n+pnp_merge:\n", 1)[0]
        if not primary or not os.path.isfile(primary):
            return
        h = path_settings_hash(path)
        self._settings.beginGroup(f"pnp/ui/{h}")
        try:
            if not self._settings.contains("separator"):
                return
            self._pnp_ui_restoring = True
            sep = self._settings.value("separator", "auto")
            if isinstance(sep, str) and self.pnp_separator.findText(sep) >= 0:
                self.pnp_separator.setCurrentText(sep)
            self.pnp_first_row.setText(str(self._settings.value("first_row", "1")))
            self.pnp_last_row.setText(str(self._settings.value("last_row", "")))
        finally:
            self._pnp_ui_restoring = False
            self._settings.endGroup()
    def _restore_bom_mappings_after_fill(self, path: str) -> None:
        if not path or not hasattr(self, "bom_col_combos") or not self.bom_col_combos:
            return
        h = path_settings_hash(path)
        self._settings.beginGroup(f"bom/ui/{h}")
        mappings = self._settings.value("mappings", [])
        self._settings.endGroup()
        if not isinstance(mappings, list) or len(mappings) != len(self.bom_col_combos):
            return
        self._bom_ui_restoring = True
        try:
            for i, m in enumerate(mappings):
                role = str(m)
                combo = self.bom_col_combos[i]
                self._set_mapping_combo_role(combo, role)
        finally:
            self._bom_ui_restoring = False
    def _restore_pnp_mappings_after_fill(self, path: str) -> None:
        if not path or not hasattr(self, "pnp_col_combos") or not self.pnp_col_combos:
            return
        h = path_settings_hash(path)
        self._settings.beginGroup(f"pnp/ui/{h}")
        mappings = self._settings.value("mappings", [])
        self._settings.endGroup()
        if not isinstance(mappings, list) or len(mappings) != len(self.pnp_col_combos):
            return
        self._pnp_ui_restoring = True
        try:
            for i, m in enumerate(mappings):
                role = str(m)
                combo = self.pnp_col_combos[i]
                self._set_mapping_combo_role(combo, role)
        finally:
            self._pnp_ui_restoring = False
