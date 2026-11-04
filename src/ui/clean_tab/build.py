"""Widget construction for the Clean BOM tab."""

from __future__ import annotations

from typing import Optional

import pandas as pd
from PySide6 import QtCore, QtWidgets

from qt_models import CleanPreviewTableModel
from ui.chrome import (
    CLEAN_PRIMARY_BTN_MIN_H,
    CLEAN_PRIMARY_BTN_MIN_W,
    WidePopupComboBox,
)


class CleanBuildMixin:
    def _create_clean_tab(self):
        """Clean BOM tab — normalization via clean_component and optional pn_original."""
        tab = QtWidgets.QWidget()
        self._register_main_tab("clean_bom", tab)
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        options = QtWidgets.QFrame()
        options.setObjectName("cleanRulesContent")
        grid = QtWidgets.QGridLayout(options)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        grid.setColumnStretch(0, 1)

        group_parser = QtWidgets.QGroupBox()
        self.gb_clean_parser = group_parser
        group_parser.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.Maximum,
        )
        parser_grid = QtWidgets.QGridLayout(group_parser)
        parser_grid.setHorizontalSpacing(8)
        parser_grid.setVerticalSpacing(6)
        parser_grid.setColumnStretch(0, 1)
        parser_grid.setColumnStretch(1, 1)
        self.clean_rules_grid = parser_grid

        group_global = QtWidgets.QGroupBox()
        group_global.setTitle("")
        self.gb_clean_everyday = group_global
        group_global.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.Maximum,
        )
        glb = QtWidgets.QGridLayout(group_global)
        glb.setHorizontalSpacing(8)
        glb.setVerticalSpacing(4)
        self.lbl_clean_spacer = QtWidgets.QLabel()
        self.clean_spacer_combo = QtWidgets.QComboBox()
        self.clean_spacer_combo.setSizeAdjustPolicy(
            QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.clean_spacer_combo.setMinimumContentsLength(16)
        self.clean_spacer_combo.addItem('Underscore "_"', "_")
        self.clean_spacer_combo.addItem('Hyphen "-"', "-")
        self.clean_spacer_combo.addItem("Space", " ")
        self.clean_spacer_combo.addItem("Tab", "\t")
        self.clean_spacer_combo.addItem("Custom…", "cust")
        self.clean_spacer_cust = QtWidgets.QLineEdit()
        self.clean_spacer_cust.setPlaceholderText("Custom separator (any string)")
        self.clean_spacer_cust.setEnabled(False)
        self.clean_spacer_cust.setMaximumWidth(220)
        glb.addWidget(self.lbl_clean_spacer, 0, 0)
        glb.addWidget(self.clean_spacer_combo, 0, 1)
        glb.addWidget(self.clean_spacer_cust, 0, 2)
        glb.setColumnStretch(2, 1)

        self.clean_from_db = QtWidgets.QCheckBox()
        self.clean_from_db.setChecked(True)
        self.clean_from_hanwha_mdb = QtWidgets.QCheckBox()
        self.clean_from_hanwha_mdb.setChecked(False)
        glb.addWidget(self.clean_from_db, 1, 0, 1, 2)
        glb.addWidget(self.clean_from_hanwha_mdb, 1, 2)

        self.gb_clean_pn = QtWidgets.QCheckBox()
        self.gb_clean_pn.setChecked(True)
        self.clean_use_vendor = QtWidgets.QCheckBox()
        self.clean_use_vendor.setChecked(False)
        glb.addWidget(self.gb_clean_pn, 2, 0, 1, 2)
        glb.addWidget(self.clean_use_vendor, 2, 2)

        self.lbl_clean_preset = QtWidgets.QLabel()
        self.clean_format_preset = QtWidgets.QComboBox()
        self.clean_format_preset.addItem("", "smt")
        self.clean_format_preset.addItem("", "compact")
        self.clean_format_preset.addItem("", "custom")
        glb.addWidget(self.lbl_clean_preset, 3, 0)
        glb.addWidget(self.clean_format_preset, 3, 1)
        glb.setColumnStretch(3, 1)

        rcl_host = QtWidgets.QWidget()
        rcl_v = QtWidgets.QVBoxLayout(rcl_host)
        rcl_v.setContentsMargins(0, 4, 0, 0)
        rcl_v.setSpacing(2)
        self._build_clean_rcl_grid(rcl_v)
        self.clean_rcl_host = rcl_host

        group_advanced = QtWidgets.QGroupBox()
        self.gb_clean_advanced = group_advanced
        group_advanced.setTitle("")
        group_advanced.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.Maximum,
        )
        adv = QtWidgets.QGridLayout(group_advanced)
        adv.setHorizontalSpacing(8)
        adv.setVerticalSpacing(2)
        self.clean_prefix_use_separator = QtWidgets.QCheckBox()
        self.clean_prefix_use_separator.setChecked(True)
        adv.addWidget(self.clean_prefix_use_separator, 0, 0, 1, 2)
        self.lbl_clean_double_join = QtWidgets.QLabel()
        self.clean_combine_inputs = QtWidgets.QCheckBox()
        self.clean_combine_inputs.setToolTip(self.ui_tr("clean.combine_inputs_tip"))
        self.btn_clean_pn_join_help = QtWidgets.QToolButton()
        self.btn_clean_pn_join_help.setText("?")
        self.btn_clean_pn_join_help.setAutoRaise(True)
        self.btn_clean_pn_join_help.clicked.connect(self._show_pn_join_help)
        self.btn_clean_debug = QtWidgets.QPushButton()
        self.btn_clean_debug.clicked.connect(self._open_clean_pipeline_debug)
        adv.addWidget(self.lbl_clean_double_join, 1, 0)
        adv.addWidget(self.clean_combine_inputs, 1, 1)
        adv.addWidget(self.btn_clean_pn_join_help, 1, 2)
        adv.addWidget(self.btn_clean_debug, 1, 3)
        adv.setColumnStretch(3, 1)
        self.clean_hanwha_partial_match = QtWidgets.QCheckBox()
        self.clean_hanwha_partial_match.setChecked(False)
        adv.addWidget(self.clean_hanwha_partial_match, 2, 0, 1, 2)
        self.clean_regex_master = QtWidgets.QCheckBox()
        self.clean_regex_master.setChecked(False)
        self.clean_regex_master_scores = QtWidgets.QCheckBox()
        self.clean_regex_master_scores.setChecked(False)
        self.clean_regex_master_scores.setEnabled(False)
        self.clean_regex_master.toggled.connect(self._on_clean_regex_master_toggled)
        adv.addWidget(self.clean_regex_master, 3, 0, 1, 2)
        adv.addWidget(self.clean_regex_master_scores, 4, 0, 1, 2)
        parser_grid.addWidget(group_global, 0, 0)
        parser_grid.addWidget(group_advanced, 0, 1)
        parser_grid.addWidget(rcl_host, 1, 0, 1, 2)
        parser_grid.setRowStretch(0, 0)
        parser_grid.setRowStretch(1, 0)
        grid.addWidget(group_parser, 0, 0)

        group_mpn_www = QtWidgets.QGroupBox()
        self.gb_clean_mpn = group_mpn_www
        mpn_w = QtWidgets.QHBoxLayout(group_mpn_www)
        self.lbl_clean_mpn_search = QtWidgets.QLabel()
        mpn_w.addWidget(self.lbl_clean_mpn_search)
        self.clean_mpn_search_provider = QtWidgets.QComboBox()
        self.clean_mpn_search_provider.addItem("Digi-Key", "digikey")
        self.clean_mpn_search_provider.addItem("Mouser", "mouser")
        self.clean_mpn_search_provider.addItem("Octopart (search page)", "octopart")
        mpn_w.addWidget(self.clean_mpn_search_provider)
        self.lbl_clean_octopart_key = QtWidgets.QLabel()
        self.lbl_clean_octopart_key.hide()
        mpn_w.addWidget(self.lbl_clean_octopart_key)
        self.clean_octopart_api_key = QtWidgets.QLineEdit()
        self.clean_octopart_api_key.setEchoMode(
            QtWidgets.QLineEdit.EchoMode.PasswordEchoOnEdit
        )
        self.clean_octopart_api_key.hide()
        mpn_w.addWidget(self.clean_octopart_api_key, 0)
        self.btn_mpn_open_search = QtWidgets.QPushButton()
        self.btn_mpn_open_search.clicked.connect(self._open_mpn_search_browser)
        mpn_w.addWidget(self.btn_mpn_open_search)
        mpn_w.addStretch(1)
        group_mpn_www.hide()

        self.clean_options_scroll = QtWidgets.QScrollArea()
        self.clean_options_scroll.setObjectName("cleanRulesScroll")
        self.clean_options_scroll.setWidgetResizable(True)
        self.clean_options_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.clean_options_scroll.setWidget(options)
        self.clean_options_panel = self.clean_options_scroll
        self.clean_options_scroll.viewport().installEventFilter(self)

        for w in (
            *self.clean_res_template_combos,
            *self.clean_cap_template_combos,
            *self.clean_ind_template_combos,
        ):
            w.currentIndexChanged.connect(self._save_clean_settings)
        for w in (
            self.clean_cap_nf,
            self.clean_cap_uf_micro,
            self.clean_use_vendor,
            self.clean_from_db,
            self.clean_from_hanwha_mdb,
            self.clean_hanwha_partial_match,
            self.clean_combine_inputs,
        ):
            w.stateChanged.connect(self._save_clean_settings)
        self.clean_regex_master_scores.stateChanged.connect(self._save_clean_settings)
        self.gb_clean_pn.toggled.connect(self._on_gb_clean_pn_toggled)
        self.chk_clean_res.toggled.connect(self._on_gb_clean_res_toggled)
        self.chk_clean_cap.toggled.connect(self._on_gb_clean_cap_toggled)
        self.chk_clean_ind.toggled.connect(self._on_gb_clean_ind_toggled)
        self._on_gb_clean_res_toggled(self.chk_clean_res.isChecked())
        self._on_gb_clean_cap_toggled(self.chk_clean_cap.isChecked())
        self._on_gb_clean_ind_toggled(self.chk_clean_ind.isChecked())
        self._on_gb_clean_pn_toggled(self.gb_clean_pn.isChecked())
        self.clean_spacer_combo.currentIndexChanged.connect(
            self._on_clean_spacer_changed
        )
        self.clean_spacer_cust.textChanged.connect(self._save_clean_settings)
        self.clean_prefix_use_separator.stateChanged.connect(self._save_clean_settings)
        self.clean_res_prefix.textChanged.connect(self._save_clean_settings)
        self.clean_res_ohm_r.stateChanged.connect(self._save_clean_settings)
        self.clean_res_watt_from_pack.stateChanged.connect(self._save_clean_settings)
        self.clean_cap_prefix.textChanged.connect(self._save_clean_settings)
        self.clean_ind_prefix.textChanged.connect(self._save_clean_settings)
        for sig in (
            self.clean_spacer_combo.currentIndexChanged,
            self.clean_prefix_use_separator.stateChanged,
            self.clean_res_prefix.textChanged,
            self.clean_cap_prefix.textChanged,
            self.clean_ind_prefix.textChanged,
        ):
            sig.connect(self._update_clean_rcl_examples)
        for w in (
            *self.clean_res_template_combos,
            *self.clean_cap_template_combos,
            *self.clean_ind_template_combos,
        ):
            w.currentIndexChanged.connect(self._update_clean_rcl_examples)
        self._update_clean_rcl_examples()
        self.clean_mpn_search_provider.currentIndexChanged.connect(
            self._save_clean_mpn_lookup_settings
        )
        self.clean_octopart_api_key.editingFinished.connect(
            self._save_clean_mpn_lookup_settings
        )
        self.clean_format_preset.currentIndexChanged.connect(
            self._on_clean_preset_changed
        )
        for combo in (
            *self.clean_res_template_combos,
            *self.clean_cap_template_combos,
            *self.clean_ind_template_combos,
        ):
            combo.currentIndexChanged.connect(self._on_clean_preview_setting_changed)
        for combo in (self.clean_spacer_combo, self.clean_format_preset):
            combo.currentIndexChanged.connect(self._on_clean_preview_setting_changed)
        for edit in (
            self.clean_spacer_cust,
            self.clean_res_prefix,
            self.clean_cap_prefix,
            self.clean_ind_prefix,
        ):
            edit.textChanged.connect(self._on_clean_preview_setting_changed)
        for chk in (
            self.clean_cap_nf,
            self.clean_cap_uf_micro,
            self.clean_use_vendor,
            self.clean_from_db,
            self.clean_from_hanwha_mdb,
            self.clean_hanwha_partial_match,
            self.clean_combine_inputs,
            self.clean_regex_master,
            self.clean_regex_master_scores,
            self.clean_prefix_use_separator,
            self.clean_res_ohm_r,
            self.clean_res_watt_from_pack,
            self.chk_clean_res,
            self.chk_clean_cap,
            self.chk_clean_ind,
            self.gb_clean_pn,
        ):
            chk.stateChanged.connect(self._on_clean_preview_setting_changed)

        buttons = QtWidgets.QHBoxLayout()
        buttons.setSpacing(8)
        self.btn_clean_import = QtWidgets.QPushButton()
        self.btn_clean_import.setObjectName("cleanPrimaryImport")
        self.btn_clean_import.clicked.connect(self._clean_import)
        self.btn_clean_convert = QtWidgets.QPushButton()
        self.btn_clean_convert.setObjectName("cleanPrimaryConvert")
        self.btn_clean_convert.setEnabled(False)
        self.btn_clean_convert.clicked.connect(self._run_clean_preview)
        self.btn_clean_apply = QtWidgets.QPushButton()
        self.btn_clean_apply.setObjectName("cleanPrimaryApply")
        self.btn_clean_apply.setEnabled(False)
        self.btn_clean_apply.clicked.connect(self._clean_apply)
        self.btn_clean_learn_other = QtWidgets.QPushButton()
        self.btn_clean_learn_other.setObjectName("cleanSecondaryAction")
        self.btn_clean_learn_other.setEnabled(False)
        self.btn_clean_learn_other.clicked.connect(self._learn_selected_other)
        self.btn_clean_save = QtWidgets.QPushButton()
        self.btn_clean_save.setObjectName("cleanSecondaryAction")
        self.btn_clean_save.clicked.connect(self._clean_save_excel)
        for b in (
            self.btn_clean_import,
            self.btn_clean_convert,
            self.btn_clean_apply,
        ):
            f = b.font()
            f.setBold(True)
            b.setFont(f)
            b.setAutoDefault(False)
            b.setDefault(False)
            b.setMinimumHeight(CLEAN_PRIMARY_BTN_MIN_H)
            b.setMinimumWidth(CLEAN_PRIMARY_BTN_MIN_W)
            b.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Minimum,
                QtWidgets.QSizePolicy.Policy.Fixed,
            )
            buttons.addWidget(b)
        buttons.addStretch(1)
        for b in (self.btn_clean_learn_other, self.btn_clean_save):
            f = b.font()
            f.setBold(True)
            b.setFont(f)
            b.setAutoDefault(False)
            b.setDefault(False)
            b.setMinimumHeight(CLEAN_PRIMARY_BTN_MIN_H)
            b.setMinimumWidth(CLEAN_PRIMARY_BTN_MIN_W)
            b.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Minimum,
                QtWidgets.QSizePolicy.Policy.Fixed,
            )
            buttons.addWidget(b)
        layout.addLayout(buttons)

        self.clean_apply_ok_banner = QtWidgets.QFrame()
        self.clean_apply_ok_banner.setObjectName("cleanApplyOkBanner")
        self.clean_apply_ok_banner.setVisible(False)
        self.clean_apply_ok_banner.setStyleSheet(
            "QFrame#cleanApplyOkBanner { background-color: rgba(46, 125, 50, 0.22); "
            "border: 1px solid #43a047; border-radius: 4px; padding: 6px 8px; }"
        )
        clean_ok_lay = QtWidgets.QHBoxLayout(self.clean_apply_ok_banner)
        clean_ok_lay.setContentsMargins(8, 4, 8, 4)
        self.clean_apply_ok_label = QtWidgets.QLabel()
        self.clean_apply_ok_label.setStyleSheet(
            "color: #c8e6c9; font-weight: bold; border: none; background: transparent;"
        )
        self.btn_clean_go_bom = QtWidgets.QPushButton()
        self.btn_clean_go_bom.clicked.connect(
            lambda: self.tabs.setCurrentIndex(self._tab_index("bom"))
        )
        clean_ok_lay.addWidget(self.clean_apply_ok_label, 1)
        clean_ok_lay.addWidget(self.btn_clean_go_bom)
        layout.addWidget(self.clean_apply_ok_banner)

        self.clean_alert_frame = QtWidgets.QFrame()
        self.clean_alert_frame.setObjectName("cleanErrorStrip")
        self.clean_alert_frame.setVisible(False)
        alert_lay = QtWidgets.QHBoxLayout(self.clean_alert_frame)
        alert_lay.setContentsMargins(8, 4, 8, 4)
        alert_lay.setSpacing(8)
        self.lbl_clean_alert_icon = QtWidgets.QLabel("⚠")
        self.lbl_clean_alert_icon.setObjectName("cleanAlertIcon")
        self.lbl_clean_alert = QtWidgets.QLabel()
        self.lbl_clean_alert.setWordWrap(True)
        self.lbl_clean_alert.setObjectName("cleanAlertText")
        self.btn_clean_alert_details = QtWidgets.QPushButton()
        self.btn_clean_alert_details.clicked.connect(self._show_project_console)
        self.btn_clean_alert_dismiss = QtWidgets.QToolButton()
        self.btn_clean_alert_dismiss.setText("✕")
        self.btn_clean_alert_dismiss.setAutoRaise(True)
        self.btn_clean_alert_dismiss.clicked.connect(self._clear_clean_alert)
        alert_lay.addWidget(self.lbl_clean_alert_icon)
        alert_lay.addWidget(self.lbl_clean_alert, 1)
        alert_lay.addWidget(self.btn_clean_alert_details)
        alert_lay.addWidget(self.btn_clean_alert_dismiss)
        self._clean_alert_key = ""
        self._clean_alert_args: dict[str, object] = {}
        layout.addWidget(self.clean_alert_frame)

        self.lbl_clean_source = QtWidgets.QLabel()
        self.lbl_clean_source.setWordWrap(True)
        self.lbl_clean_source.setObjectName("cleanSummary")
        self.lbl_clean_stale = QtWidgets.QLabel()
        self.lbl_clean_stale.setObjectName("cleanStaleBadge")
        self.lbl_clean_stale.setVisible(False)
        self.btn_clean_help = QtWidgets.QToolButton()
        self.btn_clean_help.setText("?")
        self.btn_clean_help.setAutoRaise(True)
        self.btn_clean_help.clicked.connect(self._show_clean_help)
        summary_row = QtWidgets.QHBoxLayout()
        summary_row.setContentsMargins(0, 0, 0, 0)
        summary_row.setSpacing(8)
        summary_row.addWidget(self.lbl_clean_source, 1)
        summary_row.addWidget(self.lbl_clean_stale)
        summary_row.addWidget(self.btn_clean_help)
        layout.addLayout(summary_row)

        self._clean_imported_comments: list[str] = []
        self._clean_last_preview: list = []
        self._clean_source_column: Optional[str] = None
        self._clean_source_indices: list[int] = []
        self._clean_applied = False
        self._clean_applying = False

        self.clean_preview_table = QtWidgets.QTableView()
        self.clean_preview_table.setAlternatingRowColors(True)
        self.clean_preview_table.setContextMenuPolicy(
            QtCore.Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.clean_preview_table.customContextMenuRequested.connect(
            self._clean_preview_context_menu
        )
        self.clean_preview_table.verticalHeader().setVisible(False)
        self.clean_preview_table.horizontalHeader().setStretchLastSection(False)
        self.clean_preview_table.horizontalHeader().setMinimumSectionSize(28)
        self.clean_preview_table.horizontalHeader().setMaximumSectionSize(
            max(240, self.fontMetrics().horizontalAdvance("M") * 42)
        )
        self.clean_preview_model = CleanPreviewTableModel(
            pd.DataFrame(columns=["#", "Original", "Cleaned", "Type", "Source"])
        )
        self.clean_preview_table.setModel(self.clean_preview_model)

        self.clean_preview_empty = QtWidgets.QFrame()
        self.clean_preview_empty.setObjectName("cleanEmptyState")
        empty_lay = QtWidgets.QVBoxLayout(self.clean_preview_empty)
        empty_lay.setContentsMargins(16, 16, 16, 16)
        empty_lay.setSpacing(8)
        empty_lay.addStretch(1)
        self.lbl_clean_empty_title = QtWidgets.QLabel()
        self.lbl_clean_empty_title.setObjectName("cleanEmptyTitle")
        self.lbl_clean_empty_title.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)
        self.lbl_clean_empty_hint = QtWidgets.QLabel()
        self.lbl_clean_empty_hint.setWordWrap(True)
        self.lbl_clean_empty_hint.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)
        self.btn_clean_empty_bom = QtWidgets.QPushButton()
        self.btn_clean_empty_bom.clicked.connect(self._clean_empty_go_bom)
        empty_lay.addWidget(self.lbl_clean_empty_title)
        empty_lay.addWidget(self.lbl_clean_empty_hint)
        empty_row = QtWidgets.QHBoxLayout()
        empty_row.addStretch(1)
        empty_row.addWidget(self.btn_clean_empty_bom)
        empty_row.addStretch(1)
        empty_lay.addLayout(empty_row)
        empty_lay.addStretch(2)

        self.clean_preview_stack = QtWidgets.QStackedWidget()
        self.clean_preview_stack.addWidget(self.clean_preview_table)
        self.clean_preview_stack.addWidget(self.clean_preview_empty)
        self.clean_preview_stack.setCurrentWidget(self.clean_preview_empty)

        self.clean_rules_host = QtWidgets.QWidget()
        rules_lay = QtWidgets.QVBoxLayout(self.clean_rules_host)
        rules_lay.setContentsMargins(0, 0, 0, 0)
        rules_lay.setSpacing(4)
        toggle_row = QtWidgets.QHBoxLayout()
        self.btn_clean_options_toggle = QtWidgets.QToolButton()
        self.btn_clean_options_toggle.setCheckable(True)
        self.btn_clean_options_toggle.setToolButtonStyle(
            QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self.btn_clean_options_toggle.setArrowType(QtCore.Qt.ArrowType.RightArrow)
        _rules_font = self.btn_clean_options_toggle.font()
        _rules_font.setBold(True)
        self.btn_clean_options_toggle.setFont(_rules_font)
        self.btn_clean_options_toggle.toggled.connect(self._on_clean_options_toggled)
        toggle_row.addWidget(self.btn_clean_options_toggle)
        toggle_row.addStretch(1)
        rules_lay.addLayout(toggle_row)
        self.lbl_clean_rules_summary = QtWidgets.QLabel()
        self.lbl_clean_rules_summary.setWordWrap(False)
        self.lbl_clean_rules_summary.setObjectName("cleanRulesSummary")
        self.lbl_clean_rules_summary.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        self.lbl_clean_rules_summary.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )
        rules_lay.addWidget(self.lbl_clean_rules_summary)
        rules_lay.addWidget(self.clean_options_panel, 1)

        self.clean_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.clean_splitter.setObjectName("cleanSplitter")
        self.clean_splitter.setChildrenCollapsible(False)
        self.clean_splitter.addWidget(self.clean_preview_stack)
        self.clean_splitter.addWidget(self.clean_rules_host)
        self.clean_splitter.setStretchFactor(0, 1)
        self.clean_splitter.setStretchFactor(1, 0)
        self.clean_splitter.splitterMoved.connect(self._on_clean_splitter_moved)
        layout.addWidget(self.clean_splitter, 1)
        expanded = False
        if hasattr(self, "_settings"):
            expanded = bool(
                self._settings.value("clean/options_expanded", False, type=bool)
            )
        self.btn_clean_options_toggle.blockSignals(True)
        self.btn_clean_options_toggle.setChecked(expanded)
        self.btn_clean_options_toggle.blockSignals(False)
        self._apply_clean_options_visibility(expanded)
        self._restore_clean_splitter_sizes()

        for w in (
            *self.clean_res_template_combos,
            *self.clean_cap_template_combos,
            *self.clean_ind_template_combos,
        ):
            w.currentIndexChanged.connect(self._sync_clean_preset_from_combos)
        self._refresh_clean_tab_static_texts()
        self._sync_clean_preset_from_combos()
        self._sync_clean_preview_view()
        self._sync_clean_primary_buttons()
        self._sync_clean_parser_grid_sizes()
        self._update_clean_preview_min_height()
        self._layout_clean_rules_groups()
        QtCore.QTimer.singleShot(0, self._apply_default_clean_splitter_sizes)

    def _make_clean_slot_combo(
        self, options: list[tuple[str, str]], default: str
    ) -> QtWidgets.QComboBox:
        combo = WidePopupComboBox()
        for label, data in options:
            combo.addItem("—" if data == "none" else label, data)
        combo.setCurrentIndex(combo.findData(default))
        self._style_clean_template_combo(combo)
        return combo

    def _build_clean_rcl_grid(self, stack: QtWidgets.QVBoxLayout) -> None:
        """Stacked rows that share column minimum widths (type | 1–5 | prefix | extras | example)."""
        slot_n = 5
        self._clean_rcl_inner_grids: list[QtWidgets.QGridLayout] = []
        self._clean_rcl_slot_headers = []
        self._clean_rcl_slot_spacers = []

        def _new_grid(parent: QtWidgets.QWidget) -> QtWidgets.QGridLayout:
            g = QtWidgets.QGridLayout(parent)
            g.setContentsMargins(6, 4, 6, 4)
            g.setHorizontalSpacing(8)
            g.setVerticalSpacing(0)
            self._clean_rcl_inner_grids.append(g)
            return g

        hdr = QtWidgets.QWidget()
        self._clean_rcl_header = hdr
        hg = _new_grid(hdr)
        self.lbl_clean_rcl_type_hdr = QtWidgets.QLabel()
        self.lbl_clean_rcl_type_hdr.setObjectName("cleanRclTypeHeader")
        hg.addWidget(self.lbl_clean_rcl_type_hdr, 0, 0)
        for i in range(slot_n):
            h = QtWidgets.QLabel(str(i + 1))
            h.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self._clean_rcl_slot_headers.append(h)
            hg.addWidget(h, 0, 1 + i)
        self.lbl_clean_rcl_prefix_hdr = QtWidgets.QLabel()
        hg.addWidget(self.lbl_clean_rcl_prefix_hdr, 0, 6, 1, 2)
        hg.setColumnStretch(9, 1)
        stack.addWidget(hdr)

        res_options = [
            ("nom", "nom"),
            ("pack", "pack"),
            ("watt", "watt"),
            ("%", "%"),
            ("none", "none"),
        ]
        cap_options = [
            ("nom", "nom"),
            ("pack", "pack"),
            ("film", "film"),
            ("%", "%"),
            ("V (volt)", "V"),
            ("none", "none"),
        ]
        ind_options = [
            ("pack", "pack"),
            ("nom", "nom"),
            ("%", "%"),
            ("Imax", "Imax"),
            ("DCR", "DCR"),
            ("none", "none"),
        ]

        def _family_row(
            *,
            frame_attr: str,
            chk: QtWidgets.QCheckBox,
            defaults: tuple[str, ...],
            options: list[tuple[str, str]],
            combos_attr: str,
            labels_attr: str,
            prefix_lbl: QtWidgets.QLabel,
            prefix_edit: QtWidgets.QLineEdit,
            extras: list[QtWidgets.QWidget],
            example: QtWidgets.QLabel,
        ) -> None:
            frame = QtWidgets.QFrame()
            frame.setObjectName("cleanRclRow")
            frame.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
            frame.setFrameShadow(QtWidgets.QFrame.Shadow.Plain)
            setattr(self, frame_attr, frame)
            inner = _new_grid(frame)
            inner.addWidget(chk, 0, 0)
            combos: list[QtWidgets.QComboBox] = []
            for i in range(slot_n):
                if i < len(defaults):
                    combo = self._make_clean_slot_combo(options, defaults[i])
                    combos.append(combo)
                    inner.addWidget(combo, 0, 1 + i)
                else:
                    spacer = QtWidgets.QWidget()
                    self._clean_rcl_slot_spacers.append(spacer)
                    inner.addWidget(spacer, 0, 1 + i)
            setattr(self, combos_attr, combos)
            setattr(self, labels_attr, [])
            prefix_lbl.setAlignment(
                QtCore.Qt.AlignmentFlag.AlignRight
                | QtCore.Qt.AlignmentFlag.AlignVCenter
            )
            inner.addWidget(prefix_lbl, 0, 6)
            inner.addWidget(prefix_edit, 0, 7)
            extra_wrap = QtWidgets.QWidget()
            extra_l = QtWidgets.QHBoxLayout(extra_wrap)
            extra_l.setContentsMargins(0, 0, 0, 0)
            extra_l.setSpacing(8)
            for w in extras:
                extra_l.addWidget(w)
            extra_l.addStretch(1)
            inner.addWidget(extra_wrap, 0, 8)
            example.setStyleSheet(
                "color: #9e9e9e; font-style: italic; background: transparent;"
            )
            example.setAlignment(
                QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
            )
            inner.addWidget(example, 0, 9)
            inner.setColumnStretch(9, 1)
            stack.addWidget(frame)

        self.chk_clean_res = QtWidgets.QCheckBox()
        self.chk_clean_res.setChecked(True)
        self.lbl_clean_res_prefix = QtWidgets.QLabel()
        self.clean_res_prefix = QtWidgets.QLineEdit()
        self.clean_res_prefix.setPlaceholderText("R")
        self.clean_res_ohm_r = QtWidgets.QCheckBox()
        self.clean_res_ohm_r.setChecked(True)
        self.clean_res_watt_from_pack = QtWidgets.QCheckBox()
        self.clean_res_watt_from_pack.setChecked(False)
        self.lbl_clean_res_example = QtWidgets.QLabel()
        _family_row(
            frame_attr="clean_res_frame",
            chk=self.chk_clean_res,
            defaults=("nom", "pack", "watt", "%"),
            options=res_options,
            combos_attr="clean_res_template_combos",
            labels_attr="_clean_res_slot_labels",
            prefix_lbl=self.lbl_clean_res_prefix,
            prefix_edit=self.clean_res_prefix,
            extras=[self.clean_res_ohm_r, self.clean_res_watt_from_pack],
            example=self.lbl_clean_res_example,
        )

        self.chk_clean_cap = QtWidgets.QCheckBox()
        self.chk_clean_cap.setChecked(True)
        self.lbl_clean_cap_prefix = QtWidgets.QLabel()
        self.clean_cap_prefix = QtWidgets.QLineEdit()
        self.clean_cap_prefix.setPlaceholderText("C")
        self.clean_cap_nf = QtWidgets.QCheckBox()
        self.clean_cap_nf.setChecked(False)
        self.clean_cap_uf_micro = QtWidgets.QCheckBox()
        self.clean_cap_uf_micro.setChecked(False)
        self.lbl_clean_cap_example = QtWidgets.QLabel()
        _family_row(
            frame_attr="clean_cap_frame",
            chk=self.chk_clean_cap,
            defaults=("nom", "pack", "film", "%", "V"),
            options=cap_options,
            combos_attr="clean_cap_template_combos",
            labels_attr="_clean_cap_slot_labels",
            prefix_lbl=self.lbl_clean_cap_prefix,
            prefix_edit=self.clean_cap_prefix,
            extras=[self.clean_cap_nf, self.clean_cap_uf_micro],
            example=self.lbl_clean_cap_example,
        )

        self.chk_clean_ind = QtWidgets.QCheckBox()
        self.chk_clean_ind.setChecked(True)
        self.lbl_clean_ind_prefix = QtWidgets.QLabel()
        self.clean_ind_prefix = QtWidgets.QLineEdit()
        self.clean_ind_prefix.setPlaceholderText("L")
        self.lbl_clean_ind_example = QtWidgets.QLabel()
        _family_row(
            frame_attr="clean_ind_frame",
            chk=self.chk_clean_ind,
            defaults=("pack", "nom", "%", "Imax", "DCR"),
            options=ind_options,
            combos_attr="clean_ind_template_combos",
            labels_attr="_clean_ind_slot_labels",
            prefix_lbl=self.lbl_clean_ind_prefix,
            prefix_edit=self.clean_ind_prefix,
            extras=[],
            example=self.lbl_clean_ind_example,
        )

    def _sync_clean_parser_grid_sizes(self) -> None:
        if not getattr(self, "_clean_rcl_inner_grids", None):
            return
        combos = [
            *self.clean_res_template_combos,
            *self.clean_cap_template_combos,
            *self.clean_ind_template_combos,
        ]
        slot_w = 104
        for c in combos:
            slot_w = max(slot_w, int(c.sizeHint().width()))
        type_w = 96
        for chk in (self.chk_clean_res, self.chk_clean_cap, self.chk_clean_ind):
            type_w = max(type_w, int(chk.sizeHint().width()))
        prefix_lbl_w = 56
        for lbl in (
            self.lbl_clean_res_prefix,
            self.lbl_clean_cap_prefix,
            self.lbl_clean_ind_prefix,
            getattr(self, "lbl_clean_rcl_prefix_hdr", None),
        ):
            if lbl is not None:
                prefix_lbl_w = max(prefix_lbl_w, int(lbl.sizeHint().width()))
        prefix_edit_w = 48
        for ed in (
            self.clean_res_prefix,
            self.clean_cap_prefix,
            self.clean_ind_prefix,
        ):
            ed.setMinimumWidth(prefix_edit_w)
            ed.setMaximumWidth(72)
        extras_w = 160
        extras_w = max(
            extras_w,
            int(self.clean_res_ohm_r.sizeHint().width())
            + int(self.clean_res_watt_from_pack.sizeHint().width())
            + 8,
            int(self.clean_cap_nf.sizeHint().width())
            + int(self.clean_cap_uf_micro.sizeHint().width())
            + 8,
        )
        show_slots = bool(getattr(self, "_clean_custom_slots_visible", False))
        for g in self._clean_rcl_inner_grids:
            g.setColumnMinimumWidth(0, type_w)
            for i in range(5):
                g.setColumnMinimumWidth(1 + i, slot_w if show_slots else 0)
            g.setColumnMinimumWidth(6, prefix_lbl_w)
            g.setColumnMinimumWidth(7, 72)
            g.setColumnMinimumWidth(8, extras_w)
        for c in combos:
            c.setMinimumWidth(slot_w)
        for chk in (self.chk_clean_res, self.chk_clean_cap, self.chk_clean_ind):
            chk.setMinimumWidth(type_w)
        for sp in getattr(self, "_clean_rcl_slot_spacers", []):
            sp.setMinimumWidth(slot_w)
        if hasattr(self, "clean_options_scroll"):
            self._layout_clean_rules_groups()

    def _set_clean_custom_slots_visible(self, visible: bool) -> None:
        self._clean_custom_slots_visible = visible
        for combos in (
            self.clean_res_template_combos,
            self.clean_cap_template_combos,
            self.clean_ind_template_combos,
        ):
            for w in combos:
                w.setVisible(visible)
        # The slot numbers and Type header describe the visible row below, even
        # when the empty default slots are not part of a custom preset.
        hdr = getattr(self, "_clean_rcl_header", None)
        if hdr is not None:
            hdr.setVisible(True)
        for h in getattr(self, "_clean_rcl_slot_headers", []):
            h.setVisible(True)
        for sp in getattr(self, "_clean_rcl_slot_spacers", []):
            sp.setVisible(visible)
        self._sync_clean_parser_grid_sizes()

    def _layout_clean_rules_groups(self) -> None:
        """Side-by-side Parser/Advanced on wide windows, stacked when narrow."""
        if not hasattr(self, "clean_rules_grid"):
            return
        available = self.clean_options_scroll.viewport().width()
        need = (
            self.gb_clean_everyday.minimumSizeHint().width()
            + self.gb_clean_advanced.minimumSizeHint().width()
            + self.clean_rules_grid.horizontalSpacing()
            + 16
        )
        mode = "side" if available >= need else "stack"
        if getattr(self, "_clean_rules_layout_mode", "") == mode:
            return
        self._clean_rules_layout_mode = mode
        grid = self.clean_rules_grid
        for widget in (
            self.gb_clean_everyday,
            self.gb_clean_advanced,
            self.clean_rcl_host,
        ):
            grid.removeWidget(widget)
        if mode == "side":
            grid.addWidget(self.gb_clean_everyday, 0, 0)
            grid.addWidget(self.gb_clean_advanced, 0, 1)
            grid.addWidget(self.clean_rcl_host, 1, 0, 1, 2)
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 1)
        else:
            grid.addWidget(self.gb_clean_everyday, 0, 0, 1, 2)
            grid.addWidget(self.gb_clean_advanced, 1, 0, 1, 2)
            grid.addWidget(self.clean_rcl_host, 2, 0, 1, 2)
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 0)
        grid.setRowStretch(0, 0)
        grid.setRowStretch(1, 0)
        grid.setRowStretch(2, 0)
