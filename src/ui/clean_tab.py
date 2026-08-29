"""Clean BOM tab UI mixin (extracted from MainWindow)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

import pandas as pd
from PySide6 import QtCore, QtGui, QtWidgets

import logger
from app.constants import _RCL_ROW_DISABLED_STYLE
from app.prefs import _prefs_profile_bool
from clean_component import CleanConfig, clean_preview
from clean_debug_dialog import (
    CleanPipelineDebugDialog,
    load_pipeline_from_settings,
)
from component_library import append_component, default_components_path
from parsers.formatting import (
    format_cap_fields,
    format_inductor_fields,
    format_resistor_fields,
)
from pn_original import normalize_mpn_bare
from qt_models import CleanPreviewTableModel
from services.clean_apply import apply_clean_preview_to_bom
from services.clean_config import build_clean_config
from services.clean_import import import_bom_comments_for_clean
from ui.chrome import WidePopupComboBox

_CLEAN_PRESET_SMT = {
    "res": ("nom", "pack", "watt", "%"),
    "cap": ("nom", "pack", "film", "%", "V"),
    "ind": ("pack", "nom", "%", "Imax", "DCR"),
}
_CLEAN_PRESET_COMPACT = {
    "res": ("nom", "pack", "none", "none"),
    "cap": ("nom", "pack", "none", "none", "none"),
    "ind": ("pack", "nom", "none", "none", "none"),
}


class CleanTabMixin:
    def _create_clean_tab(self):
        """Clean BOM tab — normalization via clean_component and optional pn_original."""
        tab = QtWidgets.QWidget()
        self._register_main_tab("clean_bom", tab)
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        chip_row = QtWidgets.QHBoxLayout()
        self.lbl_clean_context = QtWidgets.QLabel()
        self.lbl_clean_context.setObjectName("cleanContextChip")
        self.lbl_clean_context.setWordWrap(False)
        chip_row.addWidget(self.lbl_clean_context, 1)
        self.btn_clean_help = QtWidgets.QToolButton()
        self.btn_clean_help.setText("?")
        self.btn_clean_help.setAutoRaise(True)
        self.btn_clean_help.clicked.connect(self._show_clean_help)
        chip_row.addWidget(self.btn_clean_help)
        layout.addLayout(chip_row)

        options = QtWidgets.QFrame()
        grid = QtWidgets.QGridLayout(options)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)

        group_global = QtWidgets.QGroupBox()
        self.gb_clean_everyday = group_global
        glb_outer = QtWidgets.QVBoxLayout(group_global)
        row_sp = QtWidgets.QHBoxLayout()
        self.lbl_clean_spacer = QtWidgets.QLabel()
        row_sp.addWidget(self.lbl_clean_spacer)
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
        row_sp.addWidget(self.clean_spacer_combo, 0)
        row_sp.addWidget(self.clean_spacer_cust, 1)
        row_sp.addStretch(1)
        glb_outer.addLayout(row_sp)

        row_lib = QtWidgets.QHBoxLayout()
        self.clean_from_db = QtWidgets.QCheckBox()
        self.clean_from_db.setChecked(True)
        row_lib.addWidget(self.clean_from_db)
        self.clean_from_hanwha_mdb = QtWidgets.QCheckBox()
        self.clean_from_hanwha_mdb.setChecked(False)
        row_lib.addWidget(self.clean_from_hanwha_mdb)
        row_lib.addStretch(1)
        glb_outer.addLayout(row_lib)

        pn_row = QtWidgets.QHBoxLayout()
        self.gb_clean_pn = QtWidgets.QCheckBox()
        self.gb_clean_pn.setChecked(True)
        pn_row.addWidget(self.gb_clean_pn)
        self.clean_use_vendor = QtWidgets.QCheckBox()
        self.clean_use_vendor.setChecked(False)
        pn_row.addWidget(self.clean_use_vendor)
        pn_row.addStretch(1)
        glb_outer.addLayout(pn_row)

        preset_row = QtWidgets.QHBoxLayout()
        self.lbl_clean_preset = QtWidgets.QLabel()
        self.clean_format_preset = QtWidgets.QComboBox()
        self.clean_format_preset.addItem("", "smt")
        self.clean_format_preset.addItem("", "compact")
        self.clean_format_preset.addItem("", "custom")
        preset_row.addWidget(self.lbl_clean_preset)
        preset_row.addWidget(self.clean_format_preset)
        preset_row.addStretch(1)
        glb_outer.addLayout(preset_row)

        rcl_host = QtWidgets.QWidget()
        rcl_v = QtWidgets.QVBoxLayout(rcl_host)
        rcl_v.setContentsMargins(0, 4, 0, 0)
        rcl_v.setSpacing(6)
        self._build_clean_rcl_grid(rcl_v)
        glb_outer.addWidget(rcl_host)

        grid.addWidget(group_global, 0, 0, 1, 3)

        group_advanced = QtWidgets.QGroupBox()
        self.gb_clean_advanced = group_advanced
        adv = QtWidgets.QVBoxLayout(group_advanced)
        row_sp_adv = QtWidgets.QHBoxLayout()
        self.clean_prefix_use_separator = QtWidgets.QCheckBox()
        self.clean_prefix_use_separator.setChecked(True)
        row_sp_adv.addWidget(self.clean_prefix_use_separator)
        row_sp_adv.addStretch(1)
        adv.addLayout(row_sp_adv)
        row_dbg = QtWidgets.QHBoxLayout()
        self.clean_double_comment_import = QtWidgets.QCheckBox()
        self.clean_double_comment_import.hide()
        row_dbg.addWidget(self.clean_double_comment_import)
        self.lbl_clean_double_join = QtWidgets.QLabel()
        row_dbg.addWidget(self.lbl_clean_double_join)
        self.clean_double_comment_sep = QtWidgets.QLineEdit()
        self.clean_double_comment_sep.setPlaceholderText(" | ")
        self.clean_double_comment_sep.setMaximumWidth(96)
        self.clean_double_comment_sep.setText(" | ")
        row_dbg.addWidget(self.clean_double_comment_sep)
        self.btn_clean_pn_join_help = QtWidgets.QToolButton()
        self.btn_clean_pn_join_help.setText("?")
        self.btn_clean_pn_join_help.setAutoRaise(True)
        self.btn_clean_pn_join_help.clicked.connect(self._show_pn_join_help)
        row_dbg.addWidget(self.btn_clean_pn_join_help)
        row_dbg.addStretch(1)
        self.btn_clean_debug = QtWidgets.QPushButton()
        self.btn_clean_debug.clicked.connect(self._open_clean_pipeline_debug)
        row_dbg.addWidget(self.btn_clean_debug)
        adv.addLayout(row_dbg)
        row_fuzzy = QtWidgets.QHBoxLayout()
        self.clean_hanwha_partial_match = QtWidgets.QCheckBox()
        self.clean_hanwha_partial_match.setChecked(False)
        row_fuzzy.addWidget(self.clean_hanwha_partial_match)
        row_fuzzy.addStretch(1)
        adv.addLayout(row_fuzzy)
        self.clean_regex_master = QtWidgets.QCheckBox()
        self.clean_regex_master.setChecked(False)
        self.clean_regex_master_scores = QtWidgets.QCheckBox()
        self.clean_regex_master_scores.setChecked(False)
        self.clean_regex_master_scores.setEnabled(False)
        self.clean_regex_master.toggled.connect(self._on_clean_regex_master_toggled)
        adv.addWidget(self.clean_regex_master)
        adv.addWidget(self.clean_regex_master_scores)
        grid.addWidget(group_advanced, 1, 0, 1, 3)

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

        self.clean_options_panel = options

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
            self.clean_double_comment_import,
        ):
            w.stateChanged.connect(self._save_clean_settings)
        self.clean_regex_master_scores.stateChanged.connect(self._save_clean_settings)
        self.clean_double_comment_sep.textChanged.connect(self._save_clean_settings)
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
        self.clean_format_preset.currentIndexChanged.connect(self._on_clean_preset_changed)

        buttons = QtWidgets.QHBoxLayout()
        self.btn_clean_import = QtWidgets.QPushButton()
        self.btn_clean_import.clicked.connect(self._clean_import)
        self.btn_clean_convert = QtWidgets.QPushButton()
        self.btn_clean_convert.setEnabled(False)
        self.btn_clean_convert.clicked.connect(self._run_clean_preview)
        self.btn_clean_apply = QtWidgets.QPushButton()
        self.btn_clean_apply.setEnabled(False)
        self.btn_clean_apply.clicked.connect(self._clean_apply)
        self.clean_apply_replace = QtWidgets.QCheckBox()
        self.clean_apply_replace.stateChanged.connect(self._save_clean_settings)
        self.btn_clean_learn_other = QtWidgets.QPushButton()
        self.btn_clean_learn_other.setEnabled(False)
        self.btn_clean_learn_other.clicked.connect(self._learn_selected_other)
        self.btn_clean_save = QtWidgets.QPushButton()
        self.btn_clean_save.clicked.connect(self._clean_save_excel)
        for b in (
            self.btn_clean_import,
            self.btn_clean_convert,
            self.btn_clean_apply,
        ):
            buttons.addWidget(b)
        buttons.addWidget(self.clean_apply_replace)
        buttons.addStretch()
        buttons.addWidget(self.btn_clean_learn_other)
        buttons.addWidget(self.btn_clean_save)
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

        self.lbl_clean_source = QtWidgets.QLabel()
        self.lbl_clean_source.setWordWrap(True)
        layout.addWidget(self.lbl_clean_source)

        self._clean_imported_comments: list[str] = []
        self._clean_last_preview: list = []
        self._clean_source_column: Optional[str] = None
        self._clean_source_indices: list[int] = []

        self.clean_preview_table = QtWidgets.QTableView()
        self.clean_preview_table.setAlternatingRowColors(True)
        self.clean_preview_table.setContextMenuPolicy(
            QtCore.Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.clean_preview_table.customContextMenuRequested.connect(
            self._clean_preview_context_menu
        )
        self.clean_preview_model = CleanPreviewTableModel(
            pd.DataFrame(columns=["#", "Original", "Cleaned", "Type", "Source"])
        )
        self.clean_preview_table.setModel(self.clean_preview_model)
        self.clean_preview_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.clean_preview_table, 1)

        self.btn_clean_options_toggle = QtWidgets.QToolButton()
        self.btn_clean_options_toggle.setCheckable(True)
        self.btn_clean_options_toggle.setToolButtonStyle(
            QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self.btn_clean_options_toggle.setArrowType(QtCore.Qt.ArrowType.RightArrow)
        self.btn_clean_options_toggle.toggled.connect(self._on_clean_options_toggled)
        layout.addWidget(self.btn_clean_options_toggle)
        layout.addWidget(self.clean_options_panel)
        expanded = False
        if hasattr(self, "_settings"):
            expanded = bool(self._settings.value("clean/options_expanded", False, type=bool))
        self.btn_clean_options_toggle.blockSignals(True)
        self.btn_clean_options_toggle.setChecked(expanded)
        self.btn_clean_options_toggle.blockSignals(False)
        self.clean_options_panel.setVisible(expanded)
        self.btn_clean_options_toggle.setArrowType(
            QtCore.Qt.ArrowType.DownArrow if expanded else QtCore.Qt.ArrowType.RightArrow
        )

        for w in (
            *self.clean_res_template_combos,
            *self.clean_cap_template_combos,
            *self.clean_ind_template_combos,
        ):
            w.currentIndexChanged.connect(self._sync_clean_preset_from_combos)
        self._refresh_clean_tab_static_texts()
        self._sync_clean_preset_from_combos()
        self._sync_clean_primary_buttons()
        self._refresh_clean_context_chip()
        self._sync_clean_parser_grid_sizes()

    def _make_clean_slot_combo(
        self, options: list[tuple[str, str]], default: str
    ) -> QtWidgets.QComboBox:
        combo = WidePopupComboBox()
        for label, data in options:
            combo.addItem(label, data)
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
        hg.addWidget(QtWidgets.QLabel(), 0, 0)
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
            example.setStyleSheet("color: #9e9e9e; font-style: italic;")
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
        slot_w = 112
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
        for g in self._clean_rcl_inner_grids:
            g.setColumnMinimumWidth(0, type_w)
            for i in range(5):
                g.setColumnMinimumWidth(1 + i, slot_w)
            g.setColumnMinimumWidth(6, prefix_lbl_w)
            g.setColumnMinimumWidth(7, 72)
            g.setColumnMinimumWidth(8, extras_w)
        for c in combos:
            c.setMinimumWidth(slot_w)
        for chk in (self.chk_clean_res, self.chk_clean_cap, self.chk_clean_ind):
            chk.setMinimumWidth(type_w)
        for sp in getattr(self, "_clean_rcl_slot_spacers", []):
            sp.setMinimumWidth(slot_w)

    def _show_clean_help(self) -> None:
        QtWidgets.QMessageBox.information(
            self,
            self.ui_tr("clean.help_title"),
            self.ui_tr("clean.help_body"),
        )

    def _on_clean_options_toggled(self, expanded: bool) -> None:
        self.clean_options_panel.setVisible(expanded)
        self.btn_clean_options_toggle.setArrowType(
            QtCore.Qt.ArrowType.DownArrow if expanded else QtCore.Qt.ArrowType.RightArrow
        )
        if hasattr(self, "_settings") and not getattr(self, "_restoring_settings", False):
            self._settings.setValue("clean/options_expanded", expanded)

    def _mark_clean_preview_stale(self) -> None:
        if getattr(self, "_clean_last_preview", None):
            self._clean_preview_stale = True
        if hasattr(self, "_refresh_shell_status"):
            self._refresh_shell_status()
        else:
            self._refresh_clean_context_chip()

    def _refresh_clean_context_chip(self) -> None:
        if not hasattr(self, "lbl_clean_context"):
            return
        bom = (
            Path(self._bom_source_path).name
            if getattr(self, "_bom_source_path", "")
            else self.ui_tr("status.no_bom")
        )
        comment = self.ui_tr("status.comment_unmapped")
        try:
            cols = self._get_bom_comment_column_names()
        except Exception:
            cols = []
        if cols:
            comment = ", ".join(str(c) for c in cols)
        rows = self.ui_tr("status.rows_all")
        self.lbl_clean_context.setText(
            self.ui_tr("clean.context_chip", file=bom, cols=comment, rows=rows)
        )

    def _sync_clean_primary_buttons(self) -> None:
        if not hasattr(self, "btn_clean_convert"):
            return
        conv = self.btn_clean_convert.isEnabled()
        apply_on = self.btn_clean_apply.isEnabled()
        self.btn_clean_import.setDefault(not conv and not apply_on)
        self.btn_clean_convert.setDefault(conv and not apply_on)
        self.btn_clean_apply.setDefault(apply_on)

    def _set_clean_custom_slots_visible(self, visible: bool) -> None:
        for combos in (
            self.clean_res_template_combos,
            self.clean_cap_template_combos,
            self.clean_ind_template_combos,
        ):
            for w in combos:
                w.setVisible(visible)
        hdr = getattr(self, "_clean_rcl_header", None)
        if hdr is not None:
            hdr.setVisible(visible)
        for h in getattr(self, "_clean_rcl_slot_headers", []):
            h.setVisible(visible)
        for sp in getattr(self, "_clean_rcl_slot_spacers", []):
            sp.setVisible(visible)

    def _clean_template_tuple(self, combos: list) -> tuple[str, ...]:
        return tuple(self._template_from_combos(combos))

    def _sync_clean_preset_from_combos(self) -> None:
        if getattr(self, "_applying_clean_preset", False):
            return
        if not hasattr(self, "clean_format_preset"):
            return
        res = self._clean_template_tuple(self.clean_res_template_combos)
        cap = self._clean_template_tuple(self.clean_cap_template_combos)
        ind = self._clean_template_tuple(self.clean_ind_template_combos)
        if (
            res == _CLEAN_PRESET_SMT["res"]
            and cap == _CLEAN_PRESET_SMT["cap"]
            and ind == _CLEAN_PRESET_SMT["ind"]
        ):
            key = "smt"
        elif (
            res == _CLEAN_PRESET_COMPACT["res"]
            and cap == _CLEAN_PRESET_COMPACT["cap"]
            and ind == _CLEAN_PRESET_COMPACT["ind"]
        ):
            key = "compact"
        else:
            key = "custom"
        idx = self.clean_format_preset.findData(key)
        self.clean_format_preset.blockSignals(True)
        if idx >= 0:
            self.clean_format_preset.setCurrentIndex(idx)
        self.clean_format_preset.blockSignals(False)
        self._set_clean_custom_slots_visible(key == "custom")

    def _on_clean_preset_changed(self, *_args) -> None:
        if getattr(self, "_applying_clean_preset", False):
            return
        if not hasattr(self, "clean_res_template_combos"):
            return
        key = self.clean_format_preset.currentData()
        if key == "custom":
            self._set_clean_custom_slots_visible(True)
            return
        preset = _CLEAN_PRESET_SMT if key == "smt" else _CLEAN_PRESET_COMPACT
        self._applying_clean_preset = True
        try:
            self._set_template_combos(
                self.clean_res_template_combos, ",".join(preset["res"]), preset["res"]
            )
            self._set_template_combos(
                self.clean_cap_template_combos, ",".join(preset["cap"]), preset["cap"]
            )
            self._set_template_combos(
                self.clean_ind_template_combos, ",".join(preset["ind"]), preset["ind"]
            )
        finally:
            self._applying_clean_preset = False
        self._set_clean_custom_slots_visible(False)
        self._update_clean_rcl_examples()
        self._save_clean_settings()

    def _clean_preview_context_menu(self, pos) -> None:
        idx = self.clean_preview_table.indexAt(pos)
        if idx.isValid():
            self.clean_preview_table.setCurrentIndex(idx)
        menu = QtWidgets.QMenu(self.clean_preview_table)
        act = menu.addAction(self.ui_tr("clean.mpn_search"))
        chosen = menu.exec(self.clean_preview_table.viewport().mapToGlobal(pos))
        if chosen is act:
            self._open_mpn_search_browser()

    def _refresh_clean_tab_static_texts(self) -> None:
        if not hasattr(self, "btn_clean_import"):
            return
        self.btn_clean_help.setToolTip(self.ui_tr("clean.help_title"))
        self.gb_clean_everyday.setTitle(self.ui_tr("clean.everyday"))
        self.gb_clean_advanced.setTitle(self.ui_tr("clean.advanced"))
        self.lbl_clean_spacer.setText(self.ui_tr("clean.spacer"))
        self.clean_spacer_cust.setPlaceholderText(self.ui_tr("clean.spacer_custom"))
        _si = self.clean_spacer_combo.currentIndex()
        self.clean_spacer_combo.blockSignals(True)
        for i, key in enumerate(
            (
                "clean.spacer_underscore",
                "clean.spacer_hyphen",
                "clean.spacer_space",
                "clean.spacer_tab",
                "clean.spacer_custom_item",
            )
        ):
            if i < self.clean_spacer_combo.count():
                self.clean_spacer_combo.setItemText(i, self.ui_tr(key))
        self.clean_spacer_combo.setCurrentIndex(_si)
        self.clean_spacer_combo.blockSignals(False)
        self.clean_from_db.setText(self.ui_tr("clean.from_db"))
        self.clean_from_db.setToolTip(self.ui_tr("clean.from_db_tip"))
        self.clean_from_hanwha_mdb.setText(self.ui_tr("clean.from_machine"))
        self.clean_from_hanwha_mdb.setToolTip(self.ui_tr("clean.from_machine_tip"))
        self.gb_clean_pn.setText(self.ui_tr("clean.pn"))
        self.gb_clean_pn.setToolTip(self.ui_tr("clean.pn_tip"))
        self.clean_use_vendor.setText(self.ui_tr("clean.pn_vendor_label"))
        self.clean_use_vendor.setToolTip(self.ui_tr("clean.pn_vendor_tip"))
        self.lbl_clean_preset.setText(self.ui_tr("clean.preset"))
        self.clean_format_preset.blockSignals(True)
        self.clean_format_preset.setItemText(0, self.ui_tr("clean.preset_smt"))
        self.clean_format_preset.setItemText(1, self.ui_tr("clean.preset_compact"))
        self.clean_format_preset.setItemText(2, self.ui_tr("clean.preset_custom"))
        self.clean_format_preset.blockSignals(False)
        self.clean_prefix_use_separator.setText(self.ui_tr("clean.prefix_spacer"))
        self.clean_prefix_use_separator.setToolTip(self.ui_tr("clean.prefix_spacer_tip"))
        self.clean_double_comment_import.setText(self.ui_tr("clean.double_comment"))
        self.clean_double_comment_import.setToolTip(self.ui_tr("clean.double_comment_tip"))
        self.lbl_clean_double_join.setText(self.ui_tr("clean.double_join"))
        if hasattr(self, "btn_clean_pn_join_help"):
            self.btn_clean_pn_join_help.setToolTip(
                self.ui_tr("mapping.pn_join_help_title")
            )
        self.btn_clean_debug.setText(self.ui_tr("clean.advanced_debug"))
        self.btn_clean_debug.setToolTip(self.ui_tr("clean.advanced_debug_tip"))
        self.clean_hanwha_partial_match.setText(self.ui_tr("clean.partial_match"))
        self.clean_hanwha_partial_match.setToolTip(self.ui_tr("clean.partial_match_tip"))
        self.clean_regex_master.setText(self.ui_tr("clean.regex_master"))
        self.clean_regex_master.setToolTip(self.ui_tr("clean.regex_master_tip"))
        self.clean_regex_master_scores.setText(self.ui_tr("clean.regex_master_scores"))
        self.clean_regex_master_scores.setToolTip(
            self.ui_tr("clean.regex_master_scores_tip")
        )
        self.chk_clean_res.setText(self.ui_tr("clean.resistor"))
        self.chk_clean_res.setToolTip(self.ui_tr("clean.resistor_tip"))
        self.chk_clean_cap.setText(self.ui_tr("clean.capacitor"))
        self.chk_clean_cap.setToolTip(self.ui_tr("clean.capacitor_tip"))
        self.chk_clean_ind.setText(self.ui_tr("clean.inductor"))
        self.chk_clean_ind.setToolTip(self.ui_tr("clean.inductor_tip"))
        self.lbl_clean_res_prefix.setText(self.ui_tr("clean.prefix"))
        self.lbl_clean_cap_prefix.setText(self.ui_tr("clean.prefix"))
        self.lbl_clean_ind_prefix.setText(self.ui_tr("clean.prefix"))
        if hasattr(self, "lbl_clean_rcl_prefix_hdr"):
            self.lbl_clean_rcl_prefix_hdr.setText(self.ui_tr("clean.prefix"))
        self.clean_res_ohm_r.setText(self.ui_tr("clean.ohm_r"))
        self.clean_res_ohm_r.setToolTip(self.ui_tr("clean.ohm_r_tip"))
        self.clean_res_watt_from_pack.setText(self.ui_tr("clean.watt_from_pack"))
        self.clean_res_watt_from_pack.setToolTip(self.ui_tr("clean.watt_from_pack_tip"))
        self.clean_cap_nf.setText(self.ui_tr("clean.cap_nf"))
        self.clean_cap_uf_micro.setText(self.ui_tr("clean.cap_uf_micro"))
        self.clean_cap_uf_micro.setToolTip(self.ui_tr("clean.cap_uf_micro_tip"))
        self.gb_clean_mpn.setTitle(self.ui_tr("clean.mpn_group"))
        self.lbl_clean_mpn_search.setText(self.ui_tr("clean.mpn_search_label"))
        self.btn_mpn_open_search.setText(self.ui_tr("clean.mpn_open"))
        self.btn_clean_import.setText(self.ui_tr("clean.btn_import"))
        self.btn_clean_import.setToolTip(self.ui_tr("clean.btn_import_tip"))
        self.btn_clean_convert.setText(self.ui_tr("clean.btn_convert"))
        self.btn_clean_convert.setToolTip(self.ui_tr("clean.btn_convert_tip"))
        self.btn_clean_apply.setText(self.ui_tr("clean.btn_apply"))
        self.btn_clean_apply.setToolTip(self.ui_tr("clean.btn_apply_tip"))
        self.clean_apply_replace.setText(self.ui_tr("clean.replace_source"))
        self.clean_apply_replace.setToolTip(self.ui_tr("clean.replace_source_tip"))
        self.btn_clean_learn_other.setText(self.ui_tr("clean.btn_learn"))
        self.btn_clean_learn_other.setToolTip(self.ui_tr("clean.btn_learn_tip"))
        self.btn_clean_save.setText(self.ui_tr("clean.btn_save"))
        self.btn_clean_go_bom.setText(self.ui_tr("clean.go_to_bom"))
        self.btn_clean_options_toggle.setText(self.ui_tr("clean.options_toggle"))
        if not self._clean_imported_comments and not self._clean_last_preview:
            self.lbl_clean_source.setText(self.ui_tr("clean.source_hint"))
        self._refresh_clean_context_chip()
        self._sync_clean_parser_grid_sizes()

    def _get_bom_comment_column_names(
        self, df: pd.DataFrame | None = None
    ) -> list[Any]:
        """BOM columns mapped to PN name or PN join (table order).

        Returns **actual** column labels from ``df`` (same types as ``df.columns``), not
        stringified names — otherwise ``col in df.columns`` fails for integer/RangeIndex
        headers (e.g. ``1`` vs ``"1"``).
        """
        if df is None:
            self._sync_bom_df_from_model()
            df = self._bom_df
        if df is None or df.empty:
            return []
        cols: list[Any] = []
        if hasattr(self, "bom_col_combos") and self.bom_col_combos:
            for i, combo in enumerate(self.bom_col_combos):
                if i >= len(df.columns):
                    break
                if self._mapping_combo_role(combo) in ("Comment", "PnJoin"):
                    cols.append(df.columns[i])
        if cols:
            return cols
        for col in df.columns:
            u = str(col).upper()
            if "COMMENT" in u or u == "VALUE" or "NAME" in u:
                return [col]
        return [df.columns[0]]

    def _get_bom_comment_column_name(self) -> Any | None:
        names = self._get_bom_comment_column_names()
        return names[0] if names else None

    def _merge_clean_comment_cells(self, parts: list[object]) -> str:
        from parsers.bom_text_utils import merge_clean_comment_cell_parts

        raw = (
            self.clean_double_comment_sep.text()
            if hasattr(self, "clean_double_comment_sep")
            else ""
        )
        return merge_clean_comment_cell_parts(parts, raw)

    def _open_clean_pipeline_debug(self) -> None:
        if not hasattr(self, "_settings"):
            return
        dlg = CleanPipelineDebugDialog(self, self._settings)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._log("Clean BOM: debug pipeline / components.txt path saved", "info")

    def _clean_output_separator(self) -> str:
        d = self.clean_spacer_combo.currentData()
        if d == "cust":
            return self.clean_spacer_cust.text()
        if isinstance(d, str):
            return d
        return "_"

    def _on_clean_spacer_changed(self) -> None:
        d = self.clean_spacer_combo.currentData()
        if d == "cust":
            self.clean_spacer_cust.setEnabled(True)
        else:
            self.clean_spacer_cust.setEnabled(False)
            self.clean_spacer_cust.clear()
        self._save_clean_settings()

    def _apply_clean_spacer_to_ui(self, sep: str) -> None:
        """Set combo and optional custom line from a saved output_separator string."""
        for i in range(self.clean_spacer_combo.count()):
            data = self.clean_spacer_combo.itemData(i)
            if data == "cust" or data is None:
                continue
            if data == sep:
                self.clean_spacer_combo.setCurrentIndex(i)
                self.clean_spacer_cust.setEnabled(False)
                self.clean_spacer_cust.clear()
                return
        idx = self.clean_spacer_combo.findData("cust")
        if idx < 0:
            return
        self.clean_spacer_combo.setCurrentIndex(idx)
        self.clean_spacer_cust.setText(sep)
        self.clean_spacer_cust.setEnabled(True)

    def _on_gb_clean_res_toggled(self, on: bool) -> None:
        for w in (
            *self.clean_res_template_combos,
            self.clean_res_prefix,
            self.clean_res_ohm_r,
            self.clean_res_watt_from_pack,
        ):
            w.setEnabled(on)
        self.clean_res_frame.setProperty("rclDisabled", not on)
        self.clean_res_frame.setStyleSheet(_RCL_ROW_DISABLED_STYLE if not on else "")
        self.clean_res_frame.style().unpolish(self.clean_res_frame)
        self.clean_res_frame.style().polish(self.clean_res_frame)
        self._update_clean_rcl_examples()
        self._save_clean_settings()

    def _on_clean_regex_master_toggled(self, on: bool) -> None:
        self.clean_regex_master_scores.setEnabled(on)
        if not on:
            self.clean_regex_master_scores.setChecked(False)
        self._save_clean_settings()

    def _on_gb_clean_cap_toggled(self, on: bool) -> None:
        for w in (
            *self.clean_cap_template_combos,
            self.clean_cap_nf,
            self.clean_cap_uf_micro,
            self.clean_cap_prefix,
        ):
            w.setEnabled(on)
        self.clean_cap_frame.setProperty("rclDisabled", not on)
        self.clean_cap_frame.setStyleSheet(_RCL_ROW_DISABLED_STYLE if not on else "")
        self.clean_cap_frame.style().unpolish(self.clean_cap_frame)
        self.clean_cap_frame.style().polish(self.clean_cap_frame)
        self._update_clean_rcl_examples()
        self._save_clean_settings()

    def _on_gb_clean_ind_toggled(self, on: bool) -> None:
        for w in (*self.clean_ind_template_combos, self.clean_ind_prefix):
            w.setEnabled(on)
        self.clean_ind_frame.setProperty("rclDisabled", not on)
        self.clean_ind_frame.setStyleSheet(_RCL_ROW_DISABLED_STYLE if not on else "")
        self.clean_ind_frame.style().unpolish(self.clean_ind_frame)
        self.clean_ind_frame.style().polish(self.clean_ind_frame)
        self._update_clean_rcl_examples()
        self._save_clean_settings()

    def _on_gb_clean_pn_toggled(self, on: bool) -> None:
        self.clean_use_vendor.setEnabled(on)
        self._save_clean_settings()

    def _save_clean_mpn_lookup_settings(self) -> None:
        if getattr(self, "_restoring_settings", False) or not hasattr(
            self, "_settings"
        ):
            return
        s = self._settings
        prov = self.clean_mpn_search_provider.currentData()
        s.setValue("clean/mpn_search_provider", prov if prov else "digikey")
        s.setValue("clean/octopart_api_key", self.clean_octopart_api_key.text())

    def _open_mpn_search_browser(self) -> None:
        idx = self.clean_preview_table.currentIndex()
        if not idx.isValid():
            self._log("Clean BOM: select a row in the preview table first", "warning")
            return
        row = idx.row()
        df = self.clean_preview_model.get_dataframe()
        if df is None or df.empty or row < 0 or row >= len(df):
            self._log("Clean BOM: no preview data", "warning")
            return
        if "Original" not in df.columns:
            self._log("Clean BOM: preview has no Original column", "error")
            return
        orig = str(df.iloc[row]["Original"])
        mpn = normalize_mpn_bare(orig)
        if not mpn:
            self._log("Clean BOM: empty MPN after normalize", "warning")
            return
        prov = self.clean_mpn_search_provider.currentData() or "digikey"
        q = quote(mpn, safe="")
        if prov == "digikey":
            url = f"https://www.digikey.com/en/products/result?keywords={q}"
        elif prov == "mouser":
            url = f"https://www.mouser.com/c/?q={q}"
        else:
            url = f"https://octopart.com/search?q={q}"
        if not QtGui.QDesktopServices.openUrl(QtCore.QUrl(url)):
            self._log("Could not open default browser for MPN search", "error")
        else:
            self._log(f"MPN search opened for {mpn!r} ({prov})", "info")

    def _template_from_combos(
        self, combos: list[QtWidgets.QComboBox]
    ) -> tuple[str, ...]:
        values: list[str] = []
        for combo in combos:
            data = combo.currentData()
            key = str(data) if data is not None else "none"
            values.append(key)
        return tuple(values)

    def _set_template_combos(
        self, combos: list[QtWidgets.QComboBox], raw: object, default: tuple[str, ...]
    ) -> None:
        if isinstance(raw, str) and raw.strip():
            values = [x.strip() for x in raw.split(",")]
        else:
            values = list(default)
        for i, combo in enumerate(combos):
            key = values[i] if i < len(values) else "none"
            if key == "W":
                key = "V"
            # Legacy: cap voltage combo used addItem("V", "V (volt)") — userData was wrong.
            if key == "V (volt)":
                key = "V"
            idx = combo.findData(key)
            if idx < 0:
                idx = combo.findData("none")
            if idx >= 0:
                combo.setCurrentIndex(idx)

    def _clean_config_from_ui(self) -> CleanConfig:
        res_template = self._template_from_combos(self.clean_res_template_combos)
        cap_template = self._template_from_combos(self.clean_cap_template_combos)
        ind_template = self._template_from_combos(self.clean_ind_template_combos)
        hanwha_names = None
        if self.clean_from_hanwha_mdb.isChecked() and hasattr(
            self, "_machine_library_tab"
        ):
            hs = self._machine_library_tab.machine_partname_set()
            hanwha_names = hs if hs else None
        pipe_order, pipe_disabled = load_pipeline_from_settings(self._settings)
        regex_master_enabled = self.clean_regex_master.isChecked()
        regex_master_preview_scores = (
            regex_master_enabled and self.clean_regex_master_scores.isChecked()
        )
        return build_clean_config(
            res_template=res_template,
            cap_template=cap_template,
            ind_template=ind_template,
            cap_nf_to_uf=self.clean_cap_nf.isChecked(),
            cap_uf_micro_sign=self.clean_cap_uf_micro.isChecked(),
            res_ohm_r_suffix=self.clean_res_ohm_r.isChecked(),
            infer_resistor_watt_from_package=self.clean_res_watt_from_pack.isChecked(),
            use_pn_codecs=self.gb_clean_pn.isChecked(),
            use_vendor_pn=self.gb_clean_pn.isChecked()
            and self.clean_use_vendor.isChecked(),
            parse_resistors=self.chk_clean_res.isChecked(),
            parse_capacitors=self.chk_clean_cap.isChecked(),
            parse_inductors=self.chk_clean_ind.isChecked(),
            output_separator=self._clean_output_separator(),
            res_prefix=self.clean_res_prefix.text().strip(),
            cap_prefix=self.clean_cap_prefix.text().strip(),
            ind_prefix=self.clean_ind_prefix.text().strip(),
            prefix_use_separator=self.clean_prefix_use_separator.isChecked(),
            use_component_library=self.clean_from_db.isChecked(),
            use_hanwha_mdb=self.clean_from_hanwha_mdb.isChecked(),
            hanwha_partial_match=self.clean_hanwha_partial_match.isChecked(),
            hanwha_partnames=hanwha_names,
            clean_pipeline_order=pipe_order,
            clean_pipeline_disabled=pipe_disabled,
            component_library_path=None,
            regex_master_enabled=regex_master_enabled,
            regex_master_preview_scores=regex_master_preview_scores,
            settings_getter=lambda k, d: str(self._settings.value(k, d) or ""),
        )

    def _save_clean_settings(self) -> None:
        if getattr(self, "_restoring_settings", False) or not hasattr(
            self, "_settings"
        ):
            return
        s = self._settings
        s.setValue(
            "clean/res_template",
            ",".join(self._template_from_combos(self.clean_res_template_combos)),
        )
        s.setValue(
            "clean/cap_template",
            ",".join(self._template_from_combos(self.clean_cap_template_combos)),
        )
        s.setValue(
            "clean/ind_template",
            ",".join(self._template_from_combos(self.clean_ind_template_combos)),
        )
        s.setValue("clean/cap_nf", self.clean_cap_nf.isChecked())
        s.setValue("clean/cap_uf_micro", self.clean_cap_uf_micro.isChecked())
        s.setValue("clean/res_ohm_r_suffix", self.clean_res_ohm_r.isChecked())
        s.setValue(
            "clean/infer_resistor_watt_from_package",
            self.clean_res_watt_from_pack.isChecked(),
        )
        s.setValue("clean/use_vendor", self.clean_use_vendor.isChecked())
        s.setValue("clean/group_res", self.chk_clean_res.isChecked())
        s.setValue("clean/group_cap", self.chk_clean_cap.isChecked())
        s.setValue("clean/group_ind", self.chk_clean_ind.isChecked())
        s.setValue("clean/group_pn", self.gb_clean_pn.isChecked())
        s.setValue("clean/output_separator", self._clean_output_separator())
        s.setValue("clean/res_prefix", self.clean_res_prefix.text().strip())
        s.setValue("clean/cap_prefix", self.clean_cap_prefix.text().strip())
        s.setValue("clean/ind_prefix", self.clean_ind_prefix.text().strip())
        s.setValue(
            "clean/prefix_use_separator", self.clean_prefix_use_separator.isChecked()
        )
        if hasattr(self, "clean_from_db"):
            s.setValue("clean/from_db", self.clean_from_db.isChecked())
        if hasattr(self, "clean_from_hanwha_mdb"):
            s.setValue("clean/from_hanwha_mdb", self.clean_from_hanwha_mdb.isChecked())
        if hasattr(self, "clean_hanwha_partial_match"):
            s.setValue(
                "clean/hanwha_partial_match",
                self.clean_hanwha_partial_match.isChecked(),
            )
        if hasattr(self, "clean_regex_master"):
            s.setValue(
                "clean/regex_master_enabled",
                self.clean_regex_master.isChecked(),
            )
            s.setValue(
                "clean/regex_master_preview_scores",
                self.clean_regex_master_scores.isChecked(),
            )
        if hasattr(self, "clean_apply_replace"):
            s.setValue("clean/apply_replace", self.clean_apply_replace.isChecked())
        if hasattr(self, "clean_double_comment_import"):
            s.setValue(
                "clean/double_comment_import",
                self.clean_double_comment_import.isChecked(),
            )
        if hasattr(self, "clean_double_comment_sep"):
            s.setValue(
                "clean/double_comment_sep",
                self.clean_double_comment_sep.text(),
            )
        if hasattr(self, "btn_clean_options_toggle"):
            s.setValue(
                "clean/options_expanded",
                self.btn_clean_options_toggle.isChecked(),
            )

    def _clean_import(self) -> None:
        self._sync_bom_df_from_model()
        df = (
            self.bom_model.get_dataframe()
            if hasattr(self, "bom_model")
            else self._bom_df
        )
        if df is not None and not df.empty:
            self._bom_df = df
        if df is None or df.empty:
            self._log("Clean BOM: load BOM on BOM tab first", "warning")
            logger.warning("Clean BOM: no BOM loaded")
            return
        comment_cols = self._get_bom_comment_column_names(df)
        if not comment_cols:
            self._log(
                "Clean BOM: map PN name and/or PN join on the BOM tab",
                "warning",
            )
            logger.error("Clean BOM: BOM PN column not configured")
            return
        for col in comment_cols:
            if col not in df.columns:
                self._log(f"Clean BOM: column «{col}» missing from BOM", "warning")
                return
        primary_col = comment_cols[0]
        self._clean_source_column = primary_col
        self._clean_source_indices = list(range(len(df)))
        if not self._clean_source_indices:
            self._log("Clean BOM: BOM table is empty", "warning")
            return

        self._clean_imported_comments = import_bom_comments_for_clean(
            df,
            comment_cols,
            self._clean_source_indices,
            double_comment_separator=str(
                self.clean_double_comment_sep.text()
                if hasattr(self, "clean_double_comment_sep")
                else " "
            ),
        )
        n = len(self._clean_imported_comments)
        joined = "», «".join(str(c) for c in comment_cols)
        col_desc = (
            "«" + joined + "» (merged)"
            if len(comment_cols) > 1
            else f"«{primary_col}»"
        )
        logger.info("Imported %d comments from BOM columns %s", n, comment_cols)
        self._log(
            f"Clean BOM: imported {n} row(s) from column(s) {col_desc} using active BOM range",
            "info",
        )
        for i, c in enumerate(self._clean_imported_comments[:5], start=1):
            one = c.replace("\n", " ")
            if len(one) > 72:
                one = one[:70] + ".."
            self._log(f"  sample row {i}: {one}", "info")
        if n > 5:
            self._log(
                f"  … plus {n - 5} more rows (see Original column in the table)", "info"
            )
        self.btn_clean_convert.setEnabled(True)
        self.btn_clean_apply.setEnabled(False)
        self.btn_clean_learn_other.setEnabled(False)
        self._clean_last_preview = []
        self._clean_preview_stale = False
        self._sync_clean_primary_buttons()
        if hasattr(self, "_refresh_shell_status"):
            self._refresh_shell_status()
        pending = "\u2014"
        raw_df = pd.DataFrame(
            {
                "#": list(range(1, n + 1)),
                "Original": self._clean_imported_comments,
                "Cleaned": [pending] * n,
                "Type": [pending] * n,
                "Source": [pending] * n,
            }
        )
        self.clean_preview_model.update_dataframe(raw_df)
        range_note = self._clean_source_range_label(n)
        self.lbl_clean_source.setText(
            self.ui_tr(
                "clean.import_done",
                columns=col_desc,
                count=n,
                range=range_note,
            )
        )

    def _run_clean_preview(self) -> None:
        if not self._clean_imported_comments:
            self._log("Clean BOM: run Import from BOM first, then Convert!", "warning")
            logger.error("Clean BOM: no comments imported")
            return
        n = len(self._clean_imported_comments)
        logger.info("Generating clean preview for %d components…", n)
        self._log(f"Clean BOM: generating clean preview for {n} component(s)…", "info")
        cfg = self._clean_config_from_ui()
        try:
            rows = clean_preview(self._clean_imported_comments, cfg)
        except Exception as e:
            self._log(f"Clean BOM: Convert! error: {e}", "error")
            logger.error("Clean BOM clean_preview failed: %s", e)
            return
        self._clean_last_preview = rows
        self._clean_preview_stale = False
        if rows and len(rows[0]) == 8:
            df = pd.DataFrame(
                rows,
                columns=[
                    "#",
                    "Original",
                    "Cleaned",
                    "Type",
                    "Source",
                    "Arbiter",
                    "Win%",
                    "Alert",
                ],
            )
        elif rows and len(rows[0]) == 7:
            df = pd.DataFrame(
                rows,
                columns=[
                    "#",
                    "Original",
                    "Cleaned",
                    "Type",
                    "Source",
                    "Arbiter",
                    "Win%",
                ],
            )
        elif rows and len(rows[0]) == 6:
            df = pd.DataFrame(
                rows, columns=["#", "Original", "Cleaned", "Type", "Source", "Alert"]
            )
        else:
            df = pd.DataFrame(
                rows, columns=["#", "Original", "Cleaned", "Type", "Source"]
            )
        use_hl = cfg.regex_master_enabled and cfg.regex_master_preview_scores
        if isinstance(self.clean_preview_model, CleanPreviewTableModel):
            self.clean_preview_model.set_arbiter_score_highlight(use_hl)
        self.clean_preview_model.update_dataframe(df)
        logger.info("Clean preview generated: %d rows", len(rows))
        self._log(
            f"Clean BOM: Convert! done — {len(rows)} row(s) (check Cleaned / Type / Source)",
            "info",
        )
        if self._clean_source_column:
            range_note = self._clean_source_range_label(len(rows))
            self.lbl_clean_source.setText(
                self.ui_tr(
                    "clean.convert_done",
                    column=str(self._clean_source_column),
                    count=len(rows),
                    range=range_note,
                )
            )
        self.btn_clean_apply.setEnabled(bool(rows))
        self.btn_clean_learn_other.setEnabled(bool(rows))
        self._sync_clean_primary_buttons()
        if hasattr(self, "_refresh_shell_status"):
            self._refresh_shell_status()

    def _footprint_for_clean_row(self, one_based_row: int) -> str:
        self._sync_bom_df_from_model()
        if self._bom_df is None or self._bom_df.empty:
            return ""
        preview_idx = one_based_row - 1
        if 0 <= preview_idx < len(self._clean_source_indices):
            idx = self._clean_source_indices[preview_idx]
        else:
            idx = preview_idx
        if idx < 0 or idx >= len(self._bom_df):
            return ""
        for col in self._bom_df.columns:
            if "FOOTPRINT" in str(col).upper():
                val = self._bom_df.iloc[idx].get(col, "")
                return "" if pd.isna(val) else str(val).strip()
        return ""

    def _learn_selected_other(self) -> None:
        idx = self.clean_preview_table.currentIndex()
        if not idx.isValid():
            self._log("Clean BOM: select an OTHER row first", "warning")
            return
        df = self.clean_preview_model.get_dataframe()
        if df is None or df.empty or idx.row() >= len(df):
            self._log("Clean BOM: preview table is empty", "warning")
            return
        row = df.iloc[idx.row()]
        typ = str(row.get("Type", "")).upper()
        if typ != "OTHER":
            self._log("Clean BOM: selected row is not OTHER", "warning")
            return
        original = str(row.get("Original", "")).strip()
        cleaned = str(row.get("Cleaned", "")).strip()
        try:
            one_based = int(row.get("#", idx.row() + 1))
        except (TypeError, ValueError):
            one_based = idx.row() + 1
        footprint = self._footprint_for_clean_row(one_based)

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Learn OTHER component")
        form = QtWidgets.QFormLayout(dlg)
        raw_edit = QtWidgets.QLineEdit(original)
        raw_edit.setReadOnly(True)
        clean_edit = QtWidgets.QLineEdit(cleaned or original)
        type_combo = QtWidgets.QComboBox()
        for label in ("OTHER", "CAP", "RES", "IND"):
            type_combo.addItem(label, label)
        fp_edit = QtWidgets.QLineEdit(footprint)
        form.addRow("Original", raw_edit)
        form.addRow("Canonical name", clean_edit)
        form.addRow("Type", type_combo)
        form.addRow("Footprint", fp_edit)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Save
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)
        if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        lib_path = (
            str(self._settings.value("clean/components_txt_path", "") or "").strip()
            if hasattr(self, "_settings")
            else ""
        )
        ok = append_component(
            raw_edit.text(),
            clean_edit.text(),
            type_combo.currentData() or "OTHER",
            fp_edit.text(),
            path=lib_path if lib_path else None,
        )
        path = Path(lib_path) if lib_path else default_components_path()
        if ok:
            self._log(f"Learned component saved to {path}", "info")
        else:
            self._log("Component already exists in user library", "warning")

    def _clean_apply(self) -> None:
        self._sync_bom_df_from_model()
        if self._bom_df is None or self._bom_df.empty:
            logger.warning("Clean BOM apply: no BOM data")
            return
        col = self._clean_source_column or self._get_bom_comment_column_name()
        if not col or col not in self._bom_df.columns:
            self._log("Clean BOM: no Comment column", "warning")
            logger.error("Clean BOM apply: comment column missing")
            return
        if not self._clean_last_preview:
            self._log("Clean BOM: run Convert! before Apply", "warning")
            return

        replace = self.clean_apply_replace.isChecked()
        logger.info(
            "Applying clean preview to BOM (%d preview rows, replace=%s)…",
            len(self._clean_last_preview),
            replace,
        )

        preserved_roles = (
            self._mapping_roles_from_combos(self.bom_col_combos)
            if getattr(self, "bom_col_combos", None)
            else []
        )
        self._bom_df = apply_clean_preview_to_bom(
            self._bom_df,
            self._clean_last_preview,
            self._clean_source_indices,
            col,
            replace_source=replace,
        )
        after_cols = list(self._bom_df.columns)
        self.bom_model.update_dataframe(self._bom_df)
        from services.column_mapping import roles_after_clean_apply

        comment_target = col if replace else "comment"
        if comment_target not in after_cols and "comment" in after_cols:
            comment_target = "comment"
        if comment_target in after_cols:
            roles = roles_after_clean_apply(
                preserved_roles, after_cols, comment_column=comment_target
            )
            self._fill_bom_combos(preserved_roles=roles)
        if replace:
            msg = self.ui_tr(
                "clean.apply_replaced",
                count=len(self._clean_last_preview),
                column=str(col),
            )
        else:
            msg = self.ui_tr(
                "clean.apply_added",
                count=len(self._clean_last_preview),
            )
        self._log(msg, "info")
        logger.info("Applied clean to BOM: %s", msg)
        self._mark_working_dirty("bom")
        self._show_clean_apply_banner(self.ui_tr("clean.apply_ok_banner"))

    def _clean_save_excel(self) -> None:
        self._sync_bom_df_from_model()
        if self._bom_df is None or self._bom_df.empty:
            self._log("Clean BOM: no BOM to save", "warning")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save cleaned BOM as Excel", "", "Excel (*.xlsx);;All (*.*)"
        )
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        try:
            self._bom_df.to_excel(path, index=False)
            self._log(f"Clean BOM: saved {path}", "info")
            logger.info("Clean BOM saved Excel: %s", path)
        except Exception as e:
            self._log(f"Save Excel error: {e}", "error")
            logger.error("Clean BOM save Excel failed: %s", e)
            QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def _gather_clean_prefs_payload(self) -> dict[str, Any]:
        if not hasattr(self, "clean_res_template_combos"):
            return {}
        prov = "digikey"
        if hasattr(self, "clean_mpn_search_provider"):
            prov = self.clean_mpn_search_provider.currentData() or "digikey"
        key = str(prov) if prov is not None else "digikey"
        return {
            "res_template": ",".join(
                self._template_from_combos(self.clean_res_template_combos)
            ),
            "cap_template": ",".join(
                self._template_from_combos(self.clean_cap_template_combos)
            ),
            "ind_template": ",".join(
                self._template_from_combos(self.clean_ind_template_combos)
            ),
            "cap_nf": self.clean_cap_nf.isChecked(),
            "cap_uf_micro": self.clean_cap_uf_micro.isChecked(),
            "res_ohm_r_suffix": self.clean_res_ohm_r.isChecked(),
            "infer_resistor_watt_from_package": self.clean_res_watt_from_pack.isChecked(),
            "use_vendor": self.clean_use_vendor.isChecked(),
            "from_db": self.clean_from_db.isChecked(),
            "from_hanwha_mdb": self.clean_from_hanwha_mdb.isChecked(),
            "hanwha_partial_match": self.clean_hanwha_partial_match.isChecked(),
            "regex_master_enabled": self.clean_regex_master.isChecked(),
            "regex_master_preview_scores": self.clean_regex_master_scores.isChecked(),
            "prefix_use_separator": self.clean_prefix_use_separator.isChecked(),
            "res_prefix": self.clean_res_prefix.text(),
            "cap_prefix": self.clean_cap_prefix.text(),
            "ind_prefix": self.clean_ind_prefix.text(),
            "apply_replace": self.clean_apply_replace.isChecked(),
            "group_res": self.chk_clean_res.isChecked(),
            "group_cap": self.chk_clean_cap.isChecked(),
            "group_ind": self.chk_clean_ind.isChecked(),
            "group_pn": self.gb_clean_pn.isChecked(),
            "double_comment_import": self.clean_double_comment_import.isChecked()
            if hasattr(self, "clean_double_comment_import")
            else False,
            "double_comment_sep": self.clean_double_comment_sep.text()
            if hasattr(self, "clean_double_comment_sep")
            else " | ",
            "output_separator": self._clean_output_separator(),
            "mpn_search_provider": key,
            "octopart_api_key": self.clean_octopart_api_key.text()
            if hasattr(self, "clean_octopart_api_key")
            else "",
            "options_expanded": self.btn_clean_options_toggle.isChecked()
            if hasattr(self, "btn_clean_options_toggle")
            else False,
        }

    def _apply_clean_prefs_dict(self, c: dict[str, Any]) -> None:
        if not hasattr(self, "clean_res_template_combos"):
            return
        if hasattr(self, "chk_clean_res"):
            for gb in (
                self.chk_clean_res,
                self.chk_clean_cap,
                self.chk_clean_ind,
                self.gb_clean_pn,
            ):
                gb.blockSignals(True)
        for w in (
            *self.clean_res_template_combos,
            *self.clean_cap_template_combos,
            *self.clean_ind_template_combos,
            self.clean_cap_nf,
            self.clean_cap_uf_micro,
            self.clean_use_vendor,
            self.clean_from_db,
            self.clean_from_hanwha_mdb,
            self.clean_hanwha_partial_match,
            self.clean_prefix_use_separator,
            self.clean_res_prefix,
            self.clean_res_ohm_r,
            self.clean_res_watt_from_pack,
            self.clean_cap_prefix,
            self.clean_ind_prefix,
            self.clean_apply_replace,
            self.clean_double_comment_import,
        ):
            w.blockSignals(True)
        if hasattr(self, "clean_double_comment_sep"):
            self.clean_double_comment_sep.blockSignals(True)
        self._set_template_combos(
            self.clean_res_template_combos,
            str(c.get("res_template", "nom,pack,watt,%")),
            ("nom", "pack", "watt", "%"),
        )
        self._set_template_combos(
            self.clean_cap_template_combos,
            str(c.get("cap_template", "nom,pack,film,%,V")),
            ("nom", "pack", "film", "%", "V"),
        )
        self._set_template_combos(
            self.clean_ind_template_combos,
            str(c.get("ind_template", "pack,nom,%,Imax,DCR")),
            ("pack", "nom", "%", "Imax", "DCR"),
        )
        self.clean_cap_nf.setChecked(_prefs_profile_bool(c.get("cap_nf"), False))
        self.clean_cap_uf_micro.setChecked(
            _prefs_profile_bool(c.get("cap_uf_micro"), False)
        )
        self.clean_res_ohm_r.setChecked(
            _prefs_profile_bool(c.get("res_ohm_r_suffix"), True)
        )
        self.clean_res_watt_from_pack.setChecked(
            _prefs_profile_bool(c.get("infer_resistor_watt_from_package"), False)
        )
        self.clean_use_vendor.setChecked(
            _prefs_profile_bool(c.get("use_vendor"), False)
        )
        self.clean_from_db.setChecked(_prefs_profile_bool(c.get("from_db"), True))
        self.clean_from_hanwha_mdb.setChecked(
            _prefs_profile_bool(c.get("from_hanwha_mdb"), False)
        )
        self.clean_hanwha_partial_match.setChecked(
            _prefs_profile_bool(c.get("hanwha_partial_match"), False)
        )
        if hasattr(self, "clean_regex_master"):
            rm = _prefs_profile_bool(c.get("regex_master_enabled"), False)
            self.clean_regex_master.blockSignals(True)
            self.clean_regex_master.setChecked(rm)
            self.clean_regex_master.blockSignals(False)
            self.clean_regex_master_scores.setEnabled(rm)
            self.clean_regex_master_scores.blockSignals(True)
            self.clean_regex_master_scores.setChecked(
                rm and _prefs_profile_bool(c.get("regex_master_preview_scores"), False)
            )
            self.clean_regex_master_scores.blockSignals(False)
        self.clean_prefix_use_separator.setChecked(
            _prefs_profile_bool(c.get("prefix_use_separator"), True)
        )
        self.clean_res_prefix.setText(str(c.get("res_prefix", "")))
        self.clean_cap_prefix.setText(str(c.get("cap_prefix", "")))
        self.clean_ind_prefix.setText(str(c.get("ind_prefix", "")))
        self.clean_apply_replace.setChecked(
            _prefs_profile_bool(c.get("apply_replace"), False)
        )
        if hasattr(self, "chk_clean_res"):
            self.chk_clean_res.setChecked(_prefs_profile_bool(c.get("group_res"), True))
            self.chk_clean_cap.setChecked(_prefs_profile_bool(c.get("group_cap"), True))
            self.chk_clean_ind.setChecked(_prefs_profile_bool(c.get("group_ind"), True))
            self.gb_clean_pn.setChecked(_prefs_profile_bool(c.get("group_pn"), True))
        if hasattr(self, "clean_double_comment_import"):
            self.clean_double_comment_import.setChecked(
                _prefs_profile_bool(c.get("double_comment_import"), False)
            )
        if hasattr(self, "clean_double_comment_sep"):
            self.clean_double_comment_sep.setText(
                str(c.get("double_comment_sep", " | "))
            )
        self.clean_spacer_combo.blockSignals(True)
        self.clean_spacer_cust.blockSignals(True)
        self._apply_clean_spacer_to_ui(str(c.get("output_separator", "_")))
        self.clean_spacer_combo.blockSignals(False)
        self.clean_spacer_cust.blockSignals(False)
        for w in (
            *self.clean_res_template_combos,
            *self.clean_cap_template_combos,
            *self.clean_ind_template_combos,
            self.clean_cap_nf,
            self.clean_cap_uf_micro,
            self.clean_use_vendor,
            self.clean_from_db,
            self.clean_from_hanwha_mdb,
            self.clean_hanwha_partial_match,
            self.clean_prefix_use_separator,
            self.clean_res_prefix,
            self.clean_res_ohm_r,
            self.clean_res_watt_from_pack,
            self.clean_cap_prefix,
            self.clean_ind_prefix,
            self.clean_apply_replace,
            self.clean_double_comment_import,
        ):
            w.blockSignals(False)
        if hasattr(self, "clean_double_comment_sep"):
            self.clean_double_comment_sep.blockSignals(False)
        if hasattr(self, "clean_mpn_search_provider"):
            self.clean_mpn_search_provider.blockSignals(True)
            self.clean_octopart_api_key.blockSignals(True)
            prov = str(c.get("mpn_search_provider", "digikey"))
            for i in range(self.clean_mpn_search_provider.count()):
                if self.clean_mpn_search_provider.itemData(i) == prov:
                    self.clean_mpn_search_provider.setCurrentIndex(i)
                    break
            self.clean_octopart_api_key.setText(str(c.get("octopart_api_key", "")))
            self.clean_mpn_search_provider.blockSignals(False)
            self.clean_octopart_api_key.blockSignals(False)
        if hasattr(self, "chk_clean_res"):
            for gb in (
                self.chk_clean_res,
                self.chk_clean_cap,
                self.chk_clean_ind,
                self.gb_clean_pn,
            ):
                gb.blockSignals(False)
            self._on_gb_clean_res_toggled(self.chk_clean_res.isChecked())
            self._on_gb_clean_cap_toggled(self.chk_clean_cap.isChecked())
            self._on_gb_clean_ind_toggled(self.chk_clean_ind.isChecked())
            self._on_gb_clean_pn_toggled(self.gb_clean_pn.isChecked())
        if hasattr(self, "btn_clean_options_toggle"):
            expanded = _prefs_profile_bool(c.get("options_expanded"), False)
            self.btn_clean_options_toggle.blockSignals(True)
            self.btn_clean_options_toggle.setChecked(expanded)
            self.btn_clean_options_toggle.blockSignals(False)
            self.clean_options_panel.setVisible(expanded)
            self.btn_clean_options_toggle.setArrowType(
                QtCore.Qt.ArrowType.DownArrow
                if expanded
                else QtCore.Qt.ArrowType.RightArrow
            )
        self._sync_clean_preset_from_combos()

    def _update_clean_rcl_examples(self) -> None:
        if not hasattr(self, "lbl_clean_res_example"):
            return
        cfg = self._clean_config_from_ui()
        raw_res = "0402 12K 1%"
        raw_cap = "0402 12pF 5%"
        raw_ind = "4.7uH 0805"
        try:
            res_out = format_resistor_fields(
                {"pack": "0402", "nom": "12K", "%": "1%"}, cfg
            )
            cap_out = format_cap_fields(
                {"pack": "0402", "nom": "12pF", "%": "5%"}, cfg
            )
            ind_out = format_inductor_fields(
                {"pack": "0805", "nom": "4.7uH"}, cfg
            )
        except Exception:
            res_out = cap_out = ind_out = ""
        self.lbl_clean_res_example.setText(
            self.ui_tr("clean.example_res", raw=raw_res, out=res_out or "—")
        )
        self.lbl_clean_cap_example.setText(
            self.ui_tr("clean.example_cap", raw=raw_cap, out=cap_out or "—")
        )
        self.lbl_clean_ind_example.setText(
            self.ui_tr("clean.example_ind", raw=raw_ind, out=ind_out or "—")
        )

    def _clean_source_range_label(self, n_rows: int) -> str:
        return self.ui_tr("clean.source_range", count=n_rows)

    def _show_clean_apply_banner(self, message: str) -> None:
        if not hasattr(self, "clean_apply_ok_banner"):
            return
        self.clean_apply_ok_label.setText(message)
        self.clean_apply_ok_banner.setVisible(True)
