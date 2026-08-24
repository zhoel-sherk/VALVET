"""BOM tab layout and workspace (MainWindow mixin)."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets
import pandas as pd

from app.constants import _DANGER_CLEAR_BTN_STYLE
from qt_models import SortableTableModel
from ui.project_tab import configure_path_label


class BomTabMixin:
    def _create_bom_tab(self):
        """BOM tab — table view and column mapping."""
        tab = QtWidgets.QWidget()
        self._bom_tab_widget = tab
        self._register_main_tab("bom", tab)

        layout = QtWidgets.QVBoxLayout(tab)

        self.bom_preview_stack = QtWidgets.QWidget()
        bom_pv = QtWidgets.QVBoxLayout(self.bom_preview_stack)
        bom_pv.setContentsMargins(0, 0, 0, 0)
        bom_pv.setSpacing(0)

        self.bom_combo_vheader_spacer, self.bom_combo_inner, self.bom_combos_layout = (
            self._build_mapping_row_widgets()
        )
        bom_pv.addWidget(
            self._wrap_mapping_row(self.bom_combo_vheader_spacer, self.bom_combo_inner)
        )

        self.bom_table = QtWidgets.QTableView()
        self.bom_table.setAlternatingRowColors(True)
        self.bom_model = SortableTableModel(pd.DataFrame(), editable=True)
        self.bom_model.set_undo_stack(
            self._bom_undo_stack,
            table_id="bom",
            audit_callback=self._on_table_audit_log,
        )
        self.bom_table.setModel(self.bom_model)
        self.bom_table.horizontalHeader().setMinimumSectionSize(48)
        self._apply_compact_preview_chrome(self.bom_table)
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
        self._connect_mapping_table_signals(self.bom_table, "_bom")
        bom_pv.addWidget(self.bom_table, 1)
        layout.addWidget(self.bom_preview_stack, 1)

        # Bottom config row
        config = QtWidgets.QFrame()
        config_layout = QtWidgets.QHBoxLayout(config)

        self.lbl_bom_separator = QtWidgets.QLabel(self.ui_tr("bom.separator"))
        config_layout.addWidget(self.lbl_bom_separator)
        self.bom_separator = QtWidgets.QComboBox()
        self.bom_separator.addItems(["auto", ",", ";", "\\t", "space"])
        self.bom_separator.setCurrentText("auto")
        self.bom_separator.setMinimumWidth(70)
        config_layout.addWidget(self.bom_separator)

        self.lbl_bom_first = QtWidgets.QLabel(self.ui_tr("bom.row_range_first"))
        self.lbl_bom_first.setToolTip(self.ui_tr("bom.row_range_tip"))
        config_layout.addWidget(self.lbl_bom_first)
        self.bom_first_row = QtWidgets.QLineEdit("1")
        self.bom_first_row.setMaximumWidth(52)
        self.bom_first_row.setToolTip(self.ui_tr("bom.row_range_tip"))
        config_layout.addWidget(self.bom_first_row)

        self.lbl_bom_last = QtWidgets.QLabel(self.ui_tr("bom.row_range_last"))
        self.lbl_bom_last.setToolTip(self.ui_tr("bom.row_range_tip"))
        config_layout.addWidget(self.lbl_bom_last)
        self.bom_last_row = QtWidgets.QLineEdit("")
        self.bom_last_row.setMaximumWidth(52)
        self.bom_last_row.setToolTip(self.ui_tr("bom.row_range_tip"))
        config_layout.addWidget(self.bom_last_row)

        btn_reload_bom = QtWidgets.QPushButton(self.ui_tr("bom.reload"))
        btn_reload_bom.clicked.connect(self._reload_bom)
        config_layout.addWidget(btn_reload_bom)

        self.btn_bom_undo = QtWidgets.QPushButton(self.ui_tr("bom.undo"))
        self.btn_bom_redo = QtWidgets.QPushButton(self.ui_tr("bom.redo"))
        self.btn_bom_undo.setEnabled(False)
        self.btn_bom_redo.setEnabled(False)
        self._bom_undo_stack.canUndoChanged.connect(self.btn_bom_undo.setEnabled)
        self._bom_undo_stack.canRedoChanged.connect(self.btn_bom_redo.setEnabled)
        self.btn_bom_undo.clicked.connect(self._bom_undo_stack.undo)
        self.btn_bom_redo.clicked.connect(self._bom_undo_stack.redo)
        config_layout.addWidget(self.btn_bom_undo)
        config_layout.addWidget(self.btn_bom_redo)

        config_layout.addStretch()
        btn_find = QtWidgets.QPushButton(self.ui_tr("bom.find_replace"))
        btn_find.clicked.connect(lambda: self._find_replace_table("bom"))
        config_layout.addWidget(btn_find)

        self.btn_clear_bom = QtWidgets.QPushButton(self.ui_tr("bom.clear_workspace"))
        self.btn_clear_bom.setObjectName("dangerClearBtn")
        self.btn_clear_bom.setStyleSheet(_DANGER_CLEAR_BTN_STYLE)
        self.btn_clear_bom.setToolTip(self.ui_tr("bom.clear_workspace_tip"))
        self.btn_clear_bom.clicked.connect(self._confirm_clear_bom_workspace)
        config_layout.addWidget(self.btn_clear_bom)

        layout.addWidget(config)

        self.bom_separator.currentTextChanged.connect(
            lambda *_: self._schedule_save_bom_tab_settings()
        )
        self.bom_first_row.textChanged.connect(self._on_bom_first_last_row_changed)
        self.bom_last_row.textChanged.connect(self._on_bom_first_last_row_changed)
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
        while self.bom_combos_layout.count():
            item = self.bom_combos_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.bom_col_combos = []
        configure_path_label(
            self.bom_path_label, "", empty_text=self.ui_tr("project.no_file")
        )
        self._refresh_active_row_highlight("bom")
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
            for i, role in enumerate(pm):
                if isinstance(role, str):
                    self._set_mapping_combo_role(self.bom_col_combos[i], role)
        finally:
            self._bom_ui_restoring = False
        self._profile_restore_bom_mappings = None
