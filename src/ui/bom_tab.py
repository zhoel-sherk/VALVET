"""BOM tab layout and workspace (MainWindow mixin)."""

from __future__ import annotations

import pandas as pd
from PySide6 import QtCore, QtWidgets

from app.constants import _DANGER_CLEAR_BTN_STYLE
from qt_models import SortableTableModel
from ui.project_tab import configure_path_label


class BomTabMixin:
    def _create_bom_tab(self):
        """BOM tab — table view and column mapping."""
        tab = QtWidgets.QWidget()
        self._bom_tab_widget = tab
        self._register_main_tab("bom", tab)

        from ui.chrome import (
            CHROME_MARGIN,
            CHROME_SPACING,
            action_button,
            apply_equal_widths,
            help_button,
            left_rail_widget,
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

        self.gb_bom_file = QtWidgets.QGroupBox(self.ui_tr("bom.group_file"))
        file_l = QtWidgets.QVBoxLayout(self.gb_bom_file)
        sep_row = QtWidgets.QHBoxLayout()
        self.lbl_bom_separator = QtWidgets.QLabel(self.ui_tr("bom.separator"))
        sep_row.addWidget(self.lbl_bom_separator)
        self.bom_separator = QtWidgets.QComboBox()
        self.bom_separator.addItems(["auto", ",", ";", "\\t", "space"])
        self.bom_separator.setCurrentText("auto")
        self.bom_separator.setMinimumWidth(70)
        sep_row.addWidget(self.bom_separator, 1)
        self.btn_bom_pn_join_help = help_button(self._show_pn_join_help)
        self.btn_bom_pn_join_help.setToolTip(self.ui_tr("mapping.pn_join_help_title"))
        sep_row.addWidget(self.btn_bom_pn_join_help)
        file_l.addLayout(sep_row)
        self.btn_reload_bom = action_button(self.ui_tr("bom.reload"))
        self.btn_reload_bom.clicked.connect(self._reload_bom)
        file_l.addWidget(self.btn_reload_bom)
        left_l.addWidget(self.gb_bom_file)

        self.gb_bom_edit = QtWidgets.QGroupBox(self.ui_tr("bom.group_edit"))
        edit_l = QtWidgets.QVBoxLayout(self.gb_bom_edit)
        self.btn_bom_undo = action_button(self.ui_tr("bom.undo"))
        self.btn_bom_redo = action_button(self.ui_tr("bom.redo"))
        self.btn_bom_undo.setEnabled(False)
        self.btn_bom_redo.setEnabled(False)
        self._bom_undo_stack.canUndoChanged.connect(self.btn_bom_undo.setEnabled)
        self._bom_undo_stack.canRedoChanged.connect(self.btn_bom_redo.setEnabled)
        self.btn_bom_undo.clicked.connect(self._bom_undo_stack.undo)
        self.btn_bom_redo.clicked.connect(self._bom_undo_stack.redo)
        edit_l.addWidget(self.btn_bom_undo)
        edit_l.addWidget(self.btn_bom_redo)
        self.btn_bom_find = action_button(self.ui_tr("bom.find_replace"))
        self.btn_bom_find.clicked.connect(lambda: self._find_replace_table("bom"))
        edit_l.addWidget(self.btn_bom_find)
        left_l.addWidget(self.gb_bom_edit)

        self.gb_bom_workspace = QtWidgets.QGroupBox(self.ui_tr("bom.group_workspace"))
        ws_l = QtWidgets.QVBoxLayout(self.gb_bom_workspace)
        self.btn_clear_bom = action_button(self.ui_tr("bom.clear_workspace"))
        self.btn_clear_bom.setObjectName("dangerClearBtn")
        self.btn_clear_bom.setStyleSheet(_DANGER_CLEAR_BTN_STYLE)
        self.btn_clear_bom.setToolTip(self.ui_tr("bom.clear_workspace_tip"))
        self.btn_clear_bom.clicked.connect(self._confirm_clear_bom_workspace)
        ws_l.addWidget(self.btn_clear_bom)
        left_l.addWidget(self.gb_bom_workspace)
        apply_equal_widths(
            (
                self.btn_reload_bom,
                self.btn_bom_undo,
                self.btn_bom_redo,
                self.btn_bom_find,
                self.btn_clear_bom,
            )
        )
        left_l.addStretch(1)
        root.addWidget(left)

        self.bom_preview_stack = QtWidgets.QWidget()
        bom_pv = QtWidgets.QVBoxLayout(self.bom_preview_stack)
        bom_pv.setContentsMargins(0, 0, 0, 0)
        bom_pv.setSpacing(0)

        self.bom_table = QtWidgets.QTableView()
        self.bom_table.setAlternatingRowColors(True)
        self.bom_model = SortableTableModel(pd.DataFrame(), editable=True)
        self.bom_model.set_undo_stack(
            self._bom_undo_stack,
            table_id="bom",
            audit_callback=self._on_table_audit_log,
        )
        self.bom_table.setModel(self.bom_model)
        self._install_mapping_header(self.bom_table)
        self.bom_table.horizontalHeader().sectionResized.connect(
            self._on_bom_section_resized
        )
        self.bom_table.horizontalHeader().sectionClicked.connect(
            self._on_bom_header_click
        )
        self.bom_table.setContextMenuPolicy(
            QtCore.Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.bom_table.customContextMenuRequested.connect(
            lambda pos: self._on_table_context_menu(pos, "bom")
        )
        self.bom_model.dataChanged.connect(
            lambda *args: self._mark_working_dirty("bom")
        )
        bom_pv.addWidget(self.bom_table, 1)
        root.addWidget(self.bom_preview_stack, 1)

        self.bom_separator.currentTextChanged.connect(
            lambda *_: self._schedule_save_bom_tab_settings()
        )

    def _sync_bom_df_from_model(self) -> None:
        if not hasattr(self, "bom_model"):
            return
        df = self.bom_model.get_dataframe()
        if df is not None:
            self._bom_df = df

    def _confirm_clear_bom_workspace(self) -> None:
        if self._bom_df is None or self._bom_df.empty:
            self._clear_bom_workspace()
            return
        res = QtWidgets.QMessageBox.warning(
            self,
            self.ui_tr("bom.clear_workspace"),
            self.ui_tr("msg.bom_clear_confirm"),
            QtWidgets.QMessageBox.StandardButton.Yes
            | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if res == QtWidgets.QMessageBox.StandardButton.Yes:
            self._clear_bom_workspace()

    def _clear_bom_workspace(self) -> None:
        self._prune_session_links_for_bom(self._bom_session_key())
        self._bom_df = None
        self._bom_source_path = ""
        self._bom_dirty = False
        self._loading_working_copy = True
        self.bom_model.update_dataframe(pd.DataFrame())
        self._loading_working_copy = False
        hh = self._mapping_header(self.bom_table)
        if hh is not None:
            hh.clear_mapping_combos()
        self.bom_col_combos = []
        configure_path_label(
            self.bom_path_label, "", empty_text=self.ui_tr("project.no_file")
        )
        self._hide_merge_cross_check_ok_banner()
        self._profile_restore_bom_mappings = None
        self._log(self.ui_tr("msg.bom_cleared"), "info")

    def _apply_pending_profile_bom_mappings(self) -> None:
        pm = getattr(self, "_profile_restore_bom_mappings", None)
        if not pm or not getattr(self, "bom_col_combos", None):
            return
        if len(pm) != len(self.bom_col_combos):
            return
        self._bom_ui_restoring = True
        try:
            self._apply_bom_role_list(
                [str(r) if isinstance(r, str) else "-" for r in pm]
            )
        finally:
            self._bom_ui_restoring = False
        self._profile_restore_bom_mappings = None
