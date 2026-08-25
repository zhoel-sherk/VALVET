"""PnP tab layout, workspace, and coordinate tools (MainWindow mixin)."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets
import pandas as pd

import pnp_coord
from app.constants import _DANGER_CLEAR_BTN_STYLE
from qt_models import SortableTableModel
from ui.project_tab import configure_path_label


class PnpTabMixin:
    def _create_pnp_tab(self):
        """PnP tab."""
        tab = QtWidgets.QWidget()
        self._pnp_tab_widget = tab
        self._register_main_tab("pnp", tab)

        from ui.chrome import (
            CHROME_MARGIN,
            CHROME_SPACING,
            action_button,
            apply_equal_widths,
            help_button,
            left_rail_widget,
        )

        root = QtWidgets.QHBoxLayout(tab)
        root.setContentsMargins(CHROME_MARGIN, CHROME_MARGIN, CHROME_MARGIN, CHROME_MARGIN)
        root.setSpacing(CHROME_SPACING)

        left = left_rail_widget()
        left_l = QtWidgets.QVBoxLayout(left)
        left_l.setContentsMargins(0, 0, 8, 0)
        left_l.setSpacing(CHROME_SPACING)

        self.gb_pnp_file = QtWidgets.QGroupBox(self.ui_tr("pnp.group_file"))
        file_l = QtWidgets.QVBoxLayout(self.gb_pnp_file)
        sep_row = QtWidgets.QHBoxLayout()
        self.lbl_pnp_separator = QtWidgets.QLabel(self.ui_tr("pnp.separator"))
        sep_row.addWidget(self.lbl_pnp_separator)
        self.pnp_separator = QtWidgets.QComboBox()
        self.pnp_separator.addItems(
            ["auto", ",", ";", "\\t", "space", "spaces", "2+sp", "fixed"]
        )
        self.pnp_separator.setCurrentText("auto")
        self.pnp_separator.setMinimumWidth(70)
        self.pnp_separator.setToolTip(self.ui_tr("pnp.separator_tip"))
        sep_row.addWidget(self.pnp_separator, 1)
        self.btn_pnp_help = help_button(self._show_pnp_help)
        self.btn_pnp_help.setToolTip(self.ui_tr("pnp.help_title"))
        sep_row.addWidget(self.btn_pnp_help)
        file_l.addLayout(sep_row)
        self.btn_reload_pnp = action_button(self.ui_tr("pnp.reload"))
        self.btn_reload_pnp.clicked.connect(self._reload_pnp)
        file_l.addWidget(self.btn_reload_pnp)
        left_l.addWidget(self.gb_pnp_file)

        self.gb_pnp_coords = QtWidgets.QGroupBox(self.ui_tr("pnp.group_coords"))
        coord_l = QtWidgets.QVBoxLayout(self.gb_pnp_coords)
        units_row = QtWidgets.QHBoxLayout()
        self.lbl_pnp_xy_units = QtWidgets.QLabel(self.ui_tr("pnp.xy_units"))
        units_row.addWidget(self.lbl_pnp_xy_units)
        self.pnp_units_mm = QtWidgets.QRadioButton("mm")
        self.pnp_units_mils = QtWidgets.QRadioButton("mils")
        self.pnp_units_mm.setChecked(True)
        self.pnp_units_mm.setToolTip(
            "PnP X/Y cells are millimetres. Same choice on Merge, Report, and PCB Preview tabs "
            "(changing any updates all). Overlap compares centre distance in mm."
        )
        self.pnp_units_mils.setToolTip(
            "PnP X/Y cells are mils (0.001 inch). Overlap converts ×0.0254 to mm vs threshold; "
            "PCB Preview and MERCURY .mmd export convert to mm. Tables keep raw numbers."
        )
        self.pnp_units_mm.toggled.connect(
            lambda on: on and self._on_user_pnp_xy_unit_choice(True)
        )
        self.pnp_units_mils.toggled.connect(
            lambda on: on and self._on_user_pnp_xy_unit_choice(False)
        )
        units_row.addWidget(self.pnp_units_mm)
        units_row.addWidget(self.pnp_units_mils)
        units_row.addStretch(1)
        coord_l.addLayout(units_row)
        self.btn_pnp_clean_xyr = action_button("Clean X/Y/R")
        self.btn_pnp_clean_xyr.setToolTip(
            "Strip junk from mapped X, Y, and Rotation columns — keeps digits and decimal separators "
            "(`.` `,` `-`); does not remove dots inside numbers."
        )
        self.btn_pnp_clean_xyr.clicked.connect(self._pnp_clean_xy_rot_columns)
        coord_l.addWidget(self.btn_pnp_clean_xyr)
        self.btn_pnp_mm_mil = action_button("MM→MIL")
        self.btn_pnp_mm_mil.setToolTip(
            "Convert mapped X and Y from millimeters to mils (explicit edit); four fractional digits."
        )
        self.btn_pnp_mm_mil.clicked.connect(self._pnp_convert_xy_mm_to_mil)
        coord_l.addWidget(self.btn_pnp_mm_mil)
        self.btn_pnp_mil_mm = action_button("MIL→MM")
        self.btn_pnp_mil_mm.setToolTip(
            "Convert mapped X and Y from mils to millimeters (explicit edit); four fractional digits."
        )
        self.btn_pnp_mil_mm.clicked.connect(self._pnp_convert_xy_mil_to_mm)
        coord_l.addWidget(self.btn_pnp_mil_mm)
        left_l.addWidget(self.gb_pnp_coords)

        self.gb_pnp_edit = QtWidgets.QGroupBox(self.ui_tr("pnp.group_edit"))
        edit_l = QtWidgets.QVBoxLayout(self.gb_pnp_edit)
        self.btn_pnp_undo = action_button(self.ui_tr("pnp.undo"))
        self.btn_pnp_redo = action_button(self.ui_tr("pnp.redo"))
        self.btn_pnp_undo.setEnabled(False)
        self.btn_pnp_redo.setEnabled(False)
        self._pnp_undo_stack.canUndoChanged.connect(self.btn_pnp_undo.setEnabled)
        self._pnp_undo_stack.canRedoChanged.connect(self.btn_pnp_redo.setEnabled)
        self.btn_pnp_undo.clicked.connect(self._pnp_undo_stack.undo)
        self.btn_pnp_redo.clicked.connect(self._pnp_undo_stack.redo)
        edit_l.addWidget(self.btn_pnp_undo)
        edit_l.addWidget(self.btn_pnp_redo)
        self.btn_pnp_find = action_button(self.ui_tr("pnp.find_replace"))
        self.btn_pnp_find.clicked.connect(lambda: self._find_replace_table("pnp"))
        edit_l.addWidget(self.btn_pnp_find)
        left_l.addWidget(self.gb_pnp_edit)

        self.gb_pnp_workspace = QtWidgets.QGroupBox(self.ui_tr("pnp.group_workspace"))
        ws_l = QtWidgets.QVBoxLayout(self.gb_pnp_workspace)
        self.btn_clear_pnp = action_button(self.ui_tr("pnp.clear_workspace"))
        self.btn_clear_pnp.setObjectName("dangerClearBtn")
        self.btn_clear_pnp.setStyleSheet(_DANGER_CLEAR_BTN_STYLE)
        self.btn_clear_pnp.setToolTip(self.ui_tr("pnp.clear_workspace_tip"))
        self.btn_clear_pnp.clicked.connect(self._confirm_clear_pnp_workspace)
        ws_l.addWidget(self.btn_clear_pnp)
        left_l.addWidget(self.gb_pnp_workspace)
        apply_equal_widths(
            (
                self.btn_reload_pnp,
                self.btn_pnp_clean_xyr,
                self.btn_pnp_mm_mil,
                self.btn_pnp_mil_mm,
                self.btn_pnp_undo,
                self.btn_pnp_redo,
                self.btn_pnp_find,
                self.btn_clear_pnp,
            )
        )
        left_l.addStretch(1)
        root.addWidget(left)

        self.pnp_preview_stack = QtWidgets.QWidget()
        pnp_pv = QtWidgets.QVBoxLayout(self.pnp_preview_stack)
        pnp_pv.setContentsMargins(0, 0, 0, 0)
        pnp_pv.setSpacing(0)

        self.pnp_table = QtWidgets.QTableView()
        self.pnp_table.setAlternatingRowColors(True)
        self.pnp_model = SortableTableModel(pd.DataFrame(), editable=True)
        self.pnp_model.set_undo_stack(
            self._pnp_undo_stack,
            table_id="pnp",
            audit_callback=self._on_table_audit_log,
        )
        self.pnp_table.setModel(self.pnp_model)
        self._install_mapping_header(self.pnp_table)
        self.pnp_table.horizontalHeader().sectionResized.connect(
            self._on_pnp_section_resized
        )
        self.pnp_table.horizontalHeader().sectionClicked.connect(
            self._on_pnp_header_click
        )
        self.pnp_table.setContextMenuPolicy(
            QtCore.Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.pnp_table.customContextMenuRequested.connect(
            lambda pos: self._on_table_context_menu(pos, "pnp")
        )
        self.pnp_model.dataChanged.connect(
            lambda *args: self._mark_working_dirty("pnp")
        )
        pnp_pv.addWidget(self.pnp_table, 1)
        root.addWidget(self.pnp_preview_stack, 1)

        self.pnp_separator.currentTextChanged.connect(
            lambda *_: self._schedule_save_pnp_tab_settings()
        )
    def _sync_pnp_df_from_model(self) -> None:
        if not hasattr(self, "pnp_model"):
            return
        df = self.pnp_model.get_dataframe()
        if df is not None:
            self._pnp_df = df
    def _confirm_clear_pnp_workspace(self) -> None:
        if self._pnp_df is None or self._pnp_df.empty:
            self._clear_pnp_workspace()
            return
        res = QtWidgets.QMessageBox.warning(
            self,
            self.ui_tr("pnp.clear_workspace"),
            self.ui_tr("msg.pnp_clear_confirm"),
            QtWidgets.QMessageBox.StandardButton.Yes
            | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if res == QtWidgets.QMessageBox.StandardButton.Yes:
            self._clear_pnp_workspace()
    def _show_pnp_help(self) -> None:
        QtWidgets.QMessageBox.information(
            self,
            self.ui_tr("pnp.help_title"),
            self.ui_tr("pnp.help_body"),
        )
    def _clear_pnp_workspace(self) -> None:
        self._prune_session_links_for_pnp_identity(self._pnp_snapshot_identity_path())
        self._pnp_df = None
        self._pnp_source_path = ""
        self._pnp_secondary_path = ""
        self._pnp_primary_row_count = 0
        self._pnp_dirty = False
        self._loading_working_copy = True
        self.pnp_model.update_dataframe(pd.DataFrame())
        self._loading_working_copy = False
        hh = self._mapping_header(self.pnp_table)
        if hh is not None:
            hh.clear_mapping_combos()
        self.pnp_col_combos = []
        configure_path_label(
            self.pnp_path_label, "", empty_text=self.ui_tr("project.no_file")
        )
        if hasattr(self, "pnp_path2_label"):
            configure_path_label(
                self.pnp_path2_label, "", empty_text=self.ui_tr("project.no_file")
            )
        self._hide_merge_cross_check_ok_banner()
        self._profile_restore_pnp_mappings = None
        self._refresh_pcb_preview_from_ui()
        self._log(self.ui_tr("msg.pnp_cleared"), "info")
    def _apply_pending_profile_pnp_mappings(self) -> None:
        pm = getattr(self, "_profile_restore_pnp_mappings", None)
        if not pm or not getattr(self, "pnp_col_combos", None):
            return
        if len(pm) != len(self.pnp_col_combos):
            return
        self._pnp_ui_restoring = True
        try:
            for i, role in enumerate(pm):
                if isinstance(role, str):
                    self._set_mapping_combo_role(self.pnp_col_combos[i], role)
        finally:
            self._pnp_ui_restoring = False
        self._profile_restore_pnp_mappings = None
    def _pnp_xy_stored_in_mm(self) -> bool:
        return not self.pnp_units_mils.isChecked()
    def _apply_pnp_xy_units_everywhere(
        self, stored_mm: bool, *, save_settings: bool = True
    ) -> None:
        if getattr(self, "_syncing_pnp_xy_units", False):
            return
        self._syncing_pnp_xy_units = True
        try:
            pairs = [
                (
                    getattr(self, "pnp_units_mm", None),
                    getattr(self, "pnp_units_mils", None),
                ),
                (
                    getattr(self, "merge_pnp_units_mm", None),
                    getattr(self, "merge_pnp_units_mils", None),
                ),
                (
                    getattr(self, "report_pnp_units_mm", None),
                    getattr(self, "report_pnp_units_mils", None),
                ),
            ]
            for rmm, rmil in pairs:
                if rmm is None or rmil is None:
                    continue
                rmm.blockSignals(True)
                rmil.blockSignals(True)
                rmm.setChecked(stored_mm)
                rmil.setChecked(not stored_mm)
                rmm.blockSignals(False)
                rmil.blockSignals(False)
            if hasattr(self, "_pcb_tab"):
                self._pcb_tab.sync_pnp_xy_units_ui(mm=stored_mm)
            if save_settings and hasattr(self, "_settings"):
                self._settings.setValue("pnp/units", "mm" if stored_mm else "mils")
            if getattr(self, "processor", None) is not None:
                self.processor.config.overlap_xy_are_mm = stored_mm
        finally:
            self._syncing_pnp_xy_units = False
        self._refresh_pcb_preview_from_ui()
    def _on_user_pnp_xy_unit_choice(self, stored_mm: bool) -> None:
        if self._restoring_settings:
            return
        self._apply_pnp_xy_units_everywhere(stored_mm, save_settings=True)
    def _pnp_clean_xy_rot_columns(self) -> None:
        self._sync_pnp_df_from_model()
        if self._pnp_df is None or self._pnp_df.empty:
            QtWidgets.QMessageBox.warning(
                self, "Clean X/Y/R", "Load a PnP table first."
            )
            return
        maps = self._pnp_mappings_from_combos()
        xc, yc, rc = maps.get("X"), maps.get("Y"), maps.get("Rotation")
        miss = [n for n, c in (("X", xc), ("Y", yc), ("Rotation", rc)) if not c]
        if miss:
            QtWidgets.QMessageBox.warning(
                self,
                "Clean X/Y/R",
                "Map these PnP columns first: " + ", ".join(miss),
            )
            return
        df = self._pnp_df.copy()
        for col in (xc, yc, rc):
            df[col] = df[col].map(
                lambda v: pnp_coord.clean_numeric_cell_keep_separators(v)
            )
        self._apply_pnp_dataframe(df)
        self._log("PnP: cleaned X / Y / Rotation cells", "info")
    def _pnp_convert_xy_mm_to_mil(self) -> None:
        self._sync_pnp_df_from_model()
        if self._pnp_df is None or self._pnp_df.empty:
            QtWidgets.QMessageBox.warning(self, "MM→MIL", "Load a PnP table first.")
            return
        maps = self._pnp_mappings_from_combos()
        xc, yc = maps.get("X"), maps.get("Y")
        if not xc or not yc:
            QtWidgets.QMessageBox.warning(
                self, "MM→MIL", "Map PnP columns X and Y first."
            )
            return
        df = self._pnp_df.copy()
        n = 0
        for i in df.index:
            xs, ys = pnp_coord.convert_xy_mm_to_mil_row(df.at[i, xc], df.at[i, yc])
            if xs and ys:
                df.at[i, xc] = xs
                df.at[i, yc] = ys
                n += 1
        self._apply_pnp_dataframe(df)
        self._log(f"PnP: MM→MIL on X/Y ({n} rows)", "info")
    def _pnp_convert_xy_mil_to_mm(self) -> None:
        self._sync_pnp_df_from_model()
        if self._pnp_df is None or self._pnp_df.empty:
            QtWidgets.QMessageBox.warning(self, "MIL→MM", "Load a PnP table first.")
            return
        maps = self._pnp_mappings_from_combos()
        xc, yc = maps.get("X"), maps.get("Y")
        if not xc or not yc:
            QtWidgets.QMessageBox.warning(
                self, "MIL→MM", "Map PnP columns X and Y first."
            )
            return
        df = self._pnp_df.copy()
        n = 0
        for i in df.index:
            xs, ys = pnp_coord.convert_xy_mil_to_mm_row(df.at[i, xc], df.at[i, yc])
            if xs and ys:
                df.at[i, xc] = xs
                df.at[i, yc] = ys
                n += 1
        self._apply_pnp_dataframe(df)
        self._log(f"PnP: MIL→MM on X/Y ({n} rows)", "info")
    def _apply_pnp_dataframe(self, df: pd.DataFrame) -> None:
        self._loading_working_copy = True
        self._pnp_df = df
        self.pnp_model.update_dataframe(df)
        self._loading_working_copy = False
        self._autoresize_pnp_columns()
        self._mark_working_dirty("pnp")
        self._refresh_pcb_preview_from_ui()
