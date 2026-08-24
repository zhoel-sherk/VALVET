"""Clean BOM tab UI mixin (extracted from MainWindow)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

import pandas as pd
from PySide6 import QtWidgets
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from app.constants import _RCL_ROW_DISABLED_STYLE
from app.prefs import _prefs_profile_bool
from clean_component import CleanConfig, clean_preview
from clean_debug_dialog import (
    CleanPipelineDebugDialog,
    load_clean_debug_extras,
    load_pipeline_from_settings,
)
from component_library import append_component, default_components_path
from parsers.formatting import (
    format_cap_fields,
    format_inductor_fields,
    format_resistor_fields,
)
from pn_original import normalize_mpn_bare
from services.clean_apply import apply_clean_preview_to_bom
from services.clean_config import build_clean_config
from services.clean_import import import_bom_comments_for_clean

from qt_models import CleanPreviewTableModel

import logger


class CleanTabMixin:
    def _create_clean_tab(self):
        """Clean BOM tab — normalization via clean_component and optional pn_original."""
        tab = QtWidgets.QWidget()
        self._register_main_tab("clean_bom", tab)
        layout = QtWidgets.QVBoxLayout(tab)

        clean_intro = QtWidgets.QLabel(
            "Uses the BOM column mapped to «Comment» on the BOM tab. "
            "Import fills the table with raw Comment; Convert! runs classifiers and regex; "
            "Apply adds _cleaned / clean_* columns. "
            "Global settings: From DB, From Hanwha MDB (PARTNAME from Machine lib .mdb), Part numbers (vendor MPN)."
        )
        clean_intro.setToolTip(
            "External hand-made BOMs may prefix THT parts with «DIP_» to mean off-line or "
            "through-hole; that is not the same as this tab’s cleaned Comment from PnP."
        )
        layout.addWidget(clean_intro)

        options = QtWidgets.QFrame()
        grid = QtWidgets.QGridLayout(options)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)

        group_global = QtWidgets.QGroupBox("Global settings")
        glb_outer = QtWidgets.QVBoxLayout(group_global)
        row_sp = QtWidgets.QHBoxLayout()
        row_sp.addWidget(QtWidgets.QLabel("Spacer (join segments):"))
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
        self.clean_prefix_use_separator = QtWidgets.QCheckBox("Use spacer after Prefix")
        self.clean_prefix_use_separator.setChecked(True)
        self.clean_prefix_use_separator.setToolTip(
            "On: Prefix C + spacer '-' + 0402-12PF -> C-0402-12PF. Off: C0402-12PF."
        )
        row_sp.addWidget(self.clean_prefix_use_separator)
        row_sp.addStretch(1)
        glb_outer.addLayout(row_sp)

        row_lib = QtWidgets.QHBoxLayout()
        self.clean_from_db = QtWidgets.QCheckBox("From DB")
        self.clean_from_db.setChecked(True)
        _db_path = default_components_path()
        self.clean_from_db.setToolTip(
            "On: lookup learned components from components.txt "
            f"(default file: {_db_path}). "
            "Set BOOMER_COMPONENTS_TXT or use Debug settings to override the path. "
            "Off: skip library lookup."
        )
        row_lib.addWidget(self.clean_from_db)
        self.clean_from_hanwha_mdb = QtWidgets.QCheckBox("From machine library tab")
        self.clean_from_hanwha_mdb.setChecked(False)
        self.clean_from_hanwha_mdb.setToolTip(
            "Match BOM text to names from the Machine lib tab: Hanwha PART_Det PARTNAME "
            "and/or Yamaha .tou / Ver500 .lib (longest substring wins). "
            "Load a library on that tab first; no match falls through to other rules."
        )
        row_lib.addWidget(self.clean_from_hanwha_mdb)
        self.clean_hanwha_partial_match = QtWidgets.QCheckBox(
            "Partial match (fuzzy fallback)"
        )
        self.clean_hanwha_partial_match.setChecked(False)
        self.clean_hanwha_partial_match.setToolTip(
            "When «From machine library tab» is on: primary match is still the longest "
            "PARTNAME key contained in the BOM key (spacer-stripped). If that misses, "
            "try a fuzzy alignment (rapidfuzz partial_ratio) on those keys so small typos "
            "or OCR noise can still match. Source shows PARTIAL hanwha_mdb. "
            "Tune cutoff via CleanConfig (defaults: cutoff 88, min query length 5)."
        )
        row_lib.addWidget(self.clean_hanwha_partial_match)
        row_lib.addStretch(1)
        glb_outer.addLayout(row_lib)

        row_dbg = QtWidgets.QHBoxLayout()
        self.clean_double_comment_import = QtWidgets.QCheckBox("Double Comment import")
        self.clean_double_comment_import.setToolTip(
            "Merge every BOM column mapped to «Comment» into one line for Import / Convert! "
            "(joined with the separator on the right). Needs two or more Comment mappings."
        )
        row_dbg.addWidget(self.clean_double_comment_import)
        row_dbg.addWidget(QtWidgets.QLabel("Join:"))
        self.clean_double_comment_sep = QtWidgets.QLineEdit()
        self.clean_double_comment_sep.setPlaceholderText(" | ")
        self.clean_double_comment_sep.setMaximumWidth(96)
        self.clean_double_comment_sep.setText(" | ")
        row_dbg.addWidget(self.clean_double_comment_sep)
        row_dbg.addStretch(1)
        btn_clean_debug = QtWidgets.QPushButton("Debug settings…")
        btn_clean_debug.setToolTip(
            "Pipeline order (inferit / vendor / library / Hanwha / regex), "
            "toggle steps, and override components.txt path."
        )
        btn_clean_debug.clicked.connect(self._open_clean_pipeline_debug)
        row_dbg.addWidget(btn_clean_debug)
        glb_outer.addLayout(row_dbg)

        pn_row = QtWidgets.QHBoxLayout()
        self.gb_clean_pn = QtWidgets.QCheckBox("Part numbers (vendor MPN)")
        self.gb_clean_pn.setChecked(True)
        self.gb_clean_pn.setToolTip(
            "Off: no pn_original MPN decoders (TAI RM/WR, Yageo, Murata, …); pipeline can still "
            "use regex if enabled in Debug settings. "
            "On: vendor step may run pn_original (order vs regex is set in Debug settings). "
            "The inner checkbox only changes Source: «vendor» vs «pn»."
        )
        pn_row.addWidget(self.gb_clean_pn)
        self.clean_use_vendor = QtWidgets.QCheckBox(
            "Label as «vendor» in Source (not «pn»)"
        )
        self.clean_use_vendor.setToolTip(
            "When Part numbers is on, MPN decoders (pn_original) participate in the pipeline. "
            "This only controls the Source column: «vendor» vs «pn» for decoded lines."
        )
        self.clean_use_vendor.setChecked(False)
        pn_row.addWidget(self.clean_use_vendor)
        pn_row.addStretch(1)
        glb_outer.addLayout(pn_row)

        grid.addWidget(group_global, 0, 0, 1, 3)

        self.clean_res_frame = QtWidgets.QFrame()
        self.clean_res_frame.setObjectName("cleanRclRow")
        self.clean_res_frame.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        self.clean_res_frame.setFrameShadow(QtWidgets.QFrame.Shadow.Plain)
        self.chk_clean_res = QtWidgets.QCheckBox("Resistor")
        self.chk_clean_res.setChecked(True)
        self.chk_clean_res.setToolTip(
            "Off: resistor regex is disabled (row stays original after classification)."
        )
        gl = QtWidgets.QHBoxLayout(self.clean_res_frame)
        gl.setContentsMargins(6, 4, 6, 4)
        gl.setSpacing(6)
        gl.addWidget(self.chk_clean_res)
        self.clean_res_template_combos: list[QtWidgets.QComboBox] = []
        res_options = [
            ("nom", "nom"),
            ("pack", "pack"),
            ("watt", "watt"),
            ("%", "%"),
            ("none", "none"),
        ]
        for i, default in enumerate(("nom", "pack", "watt", "%")):
            gl.addWidget(QtWidgets.QLabel(str(i + 1)))
            combo = QtWidgets.QComboBox()
            for label, data in res_options:
                combo.addItem(label, data)
            combo.setCurrentIndex(combo.findData(default))
            combo.setMaximumWidth(86)
            self._style_clean_template_combo(combo)
            self.clean_res_template_combos.append(combo)
            gl.addWidget(combo)
        gl.addWidget(QtWidgets.QLabel("Prefix:"))
        self.clean_res_prefix = QtWidgets.QLineEdit()
        self.clean_res_prefix.setPlaceholderText("R")
        self.clean_res_prefix.setMaximumWidth(54)
        gl.addWidget(self.clean_res_prefix)
        self.clean_res_ohm_r = QtWidgets.QCheckBox("R (Ω)")
        self.clean_res_ohm_r.setChecked(True)
        self.clean_res_ohm_r.setToolTip(
            "When on, plain ohm magnitudes keep a trailing «R» (e.g. 12.5R). "
            "When off, that suffix is dropped (12.5R→12.5). Does not change K/M "
            "(e.g. 12.5K stays 12.5K)."
        )
        gl.addWidget(self.clean_res_ohm_r)
        self.lbl_clean_res_example = QtWidgets.QLabel()
        self.lbl_clean_res_example.setStyleSheet("color: #9e9e9e; font-style: italic;")
        gl.addWidget(self.lbl_clean_res_example)
        gl.addStretch(1)
        grid.addWidget(self.clean_res_frame, 1, 0)

        self.clean_cap_frame = QtWidgets.QFrame()
        self.clean_cap_frame.setObjectName("cleanRclRow")
        self.clean_cap_frame.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        self.clean_cap_frame.setFrameShadow(QtWidgets.QFrame.Shadow.Plain)
        self.chk_clean_cap = QtWidgets.QCheckBox("Capacitor")
        self.chk_clean_cap.setChecked(True)
        self.chk_clean_cap.setToolTip(
            "Off: capacitor regex/MLCC helper is disabled (row stays original when typed as cap)."
        )
        cgrid = QtWidgets.QHBoxLayout(self.clean_cap_frame)
        cgrid.setContentsMargins(6, 4, 6, 4)
        cgrid.setSpacing(6)
        cgrid.addWidget(self.chk_clean_cap)
        self.clean_cap_template_combos: list[QtWidgets.QComboBox] = []
        cap_options = [
            ("nom", "nom"),
            ("pack", "pack"),
            ("film", "film"),
            ("%", "%"),
            # QComboBox.addItem(text, userData): second arg is stored in cap_template.
            ("V (volt)", "V"),
            ("none", "none"),
        ]
        for i, default in enumerate(("nom", "pack", "film", "%", "V")):
            cgrid.addWidget(QtWidgets.QLabel(str(i + 1)))
            combo = QtWidgets.QComboBox()
            for label, data in cap_options:
                combo.addItem(label, data)
            combo.setCurrentIndex(combo.findData(default))
            combo.setMaximumWidth(82)
            self._style_clean_template_combo(combo)
            self.clean_cap_template_combos.append(combo)
            cgrid.addWidget(combo)
        self.clean_cap_nf = QtWidgets.QCheckBox("Convert nF → µF (simple)")
        self.clean_cap_nf.setChecked(False)
        cgrid.addWidget(self.clean_cap_nf)
        self.clean_cap_uf_micro = QtWidgets.QCheckBox("µ in uF")
        self.clean_cap_uf_micro.setChecked(False)
        self.clean_cap_uf_micro.setToolTip(
            "Show microfarads with the Unicode micro sign (µF) instead of ASCII «uF»."
        )
        cgrid.addWidget(self.clean_cap_uf_micro)
        cgrid.addWidget(QtWidgets.QLabel("Prefix:"))
        self.clean_cap_prefix = QtWidgets.QLineEdit()
        self.clean_cap_prefix.setPlaceholderText("C")
        self.clean_cap_prefix.setMaximumWidth(54)
        cgrid.addWidget(self.clean_cap_prefix)
        self.lbl_clean_cap_example = QtWidgets.QLabel()
        self.lbl_clean_cap_example.setStyleSheet("color: #9e9e9e; font-style: italic;")
        cgrid.addWidget(self.lbl_clean_cap_example)
        cgrid.addStretch(1)
        grid.addWidget(self.clean_cap_frame, 1, 1)

        self.clean_ind_frame = QtWidgets.QFrame()
        self.clean_ind_frame.setObjectName("cleanRclRow")
        self.clean_ind_frame.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        self.clean_ind_frame.setFrameShadow(QtWidgets.QFrame.Shadow.Plain)
        self.chk_clean_ind = QtWidgets.QCheckBox("Inductor")
        self.chk_clean_ind.setChecked(True)
        self.chk_clean_ind.setToolTip(
            "Off: inductor-specific regex is disabled; classified inductor lines use the same path as "
            "OTHER (vendor MPN for passives, From DB, From Hanwha MDB, then general OTHER regex)."
        )
        ind_row = QtWidgets.QHBoxLayout(self.clean_ind_frame)
        ind_row.setContentsMargins(6, 4, 6, 4)
        ind_row.setSpacing(6)
        ind_row.addWidget(self.chk_clean_ind)
        self.clean_ind_template_combos: list[QtWidgets.QComboBox] = []
        ind_options = [
            ("pack", "pack"),
            ("nom", "nom"),
            ("%", "%"),
            ("Imax", "Imax"),
            ("DCR", "DCR"),
            ("none", "none"),
        ]
        for i, default in enumerate(("pack", "nom", "%", "Imax", "DCR")):
            ind_row.addWidget(QtWidgets.QLabel(str(i + 1)))
            combo = QtWidgets.QComboBox()
            for label, data in ind_options:
                combo.addItem(label, data)
            combo.setCurrentIndex(combo.findData(default))
            combo.setMaximumWidth(82)
            self._style_clean_template_combo(combo)
            self.clean_ind_template_combos.append(combo)
            ind_row.addWidget(combo)
        ind_row.addWidget(QtWidgets.QLabel("Prefix:"))
        self.clean_ind_prefix = QtWidgets.QLineEdit()
        self.clean_ind_prefix.setPlaceholderText("L")
        self.clean_ind_prefix.setMaximumWidth(54)
        ind_row.addWidget(self.clean_ind_prefix)
        self.lbl_clean_ind_example = QtWidgets.QLabel()
        self.lbl_clean_ind_example.setStyleSheet("color: #9e9e9e; font-style: italic;")
        ind_row.addWidget(self.lbl_clean_ind_example)
        ind_row.addStretch(1)
        grid.addWidget(self.clean_ind_frame, 1, 2)

        group_mpn_www = QtWidgets.QGroupBox("MPN web lookup")
        mpn_w = QtWidgets.QHBoxLayout(group_mpn_www)
        mpn_w.addWidget(QtWidgets.QLabel("Search:"))
        self.clean_mpn_search_provider = QtWidgets.QComboBox()
        self.clean_mpn_search_provider.addItem("Digi-Key", "digikey")
        self.clean_mpn_search_provider.addItem("Mouser", "mouser")
        self.clean_mpn_search_provider.addItem("Octopart (search page)", "octopart")
        mpn_w.addWidget(self.clean_mpn_search_provider)
        mpn_w.addWidget(QtWidgets.QLabel("API key (optional, reserved):"))
        self.clean_octopart_api_key = QtWidgets.QLineEdit()
        self.clean_octopart_api_key.setEchoMode(
            QtWidgets.QLineEdit.EchoMode.PasswordEchoOnEdit
        )
        self.clean_octopart_api_key.setPlaceholderText(
            "Octopart / Nexar — not used in UI yet"
        )
        self.clean_octopart_api_key.setMaximumWidth(280)
        mpn_w.addWidget(self.clean_octopart_api_key, 0)
        self.btn_mpn_open_search = QtWidgets.QPushButton("Open search for selected row")
        self.btn_mpn_open_search.setToolTip(
            "Uses «Original» from the table below (VENDOR/MPN normalized to bare MPN). "
            "Select a cell in the Clean BOM preview, then click."
        )
        self.btn_mpn_open_search.clicked.connect(self._open_mpn_search_browser)
        mpn_w.addWidget(self.btn_mpn_open_search)
        mpn_w.addStretch(1)
        grid.addWidget(group_mpn_www, 3, 0, 1, 3)

        layout.addWidget(options)

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

        buttons = QtWidgets.QHBoxLayout()
        self.btn_clean_import = QtWidgets.QPushButton("Import from BOM")
        self.btn_clean_import.setToolTip(
            "Reads the BOM column mapped to «Comment»; fills the preview with raw values."
        )
        self.btn_clean_import.clicked.connect(self._clean_import)
        self.btn_clean_convert = QtWidgets.QPushButton("Convert!")
        self.btn_clean_convert.setToolTip(
            "Runs classifiers, clean_component regex, and optional vendor MPN (pn_original)."
        )
        self.btn_clean_convert.setEnabled(False)
        self.btn_clean_convert.clicked.connect(self._run_clean_preview)
        self.btn_clean_apply = QtWidgets.QPushButton("Apply to BOM (add columns)")
        self.btn_clean_apply.setToolTip(
            "Adds Comment_cleaned, clean_type, clean_part_code, clean_vendor (drops prior clean_* if re-run)"
        )
        self.btn_clean_apply.setEnabled(False)
        self.btn_clean_apply.clicked.connect(self._clean_apply)
        self.clean_apply_replace = QtWidgets.QCheckBox("Replace source column")
        self.clean_apply_replace.setToolTip(
            "On: write Cleaned back into the source Comment column. "
            "Off: update/add the *_cleaned and clean_* columns."
        )
        self.clean_apply_replace.stateChanged.connect(self._save_clean_settings)
        self.btn_clean_learn_other = QtWidgets.QPushButton("Learn selected OTHER")
        self.btn_clean_learn_other.setToolTip(
            "Approve and append the selected OTHER row to components.txt for future imports."
        )
        self.btn_clean_learn_other.setEnabled(False)
        self.btn_clean_learn_other.clicked.connect(self._learn_selected_other)
        self.btn_clean_save = QtWidgets.QPushButton("Save Excel…")
        self.btn_clean_save.clicked.connect(self._clean_save_excel)
        for b in (
            self.btn_clean_import,
            self.btn_clean_convert,
            self.btn_clean_apply,
            self.btn_clean_learn_other,
            self.btn_clean_save,
        ):
            buttons.addWidget(b)
        buttons.addWidget(self.clean_apply_replace)
        buttons.addStretch()
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
        self.btn_clean_go_bom = QtWidgets.QPushButton(self.ui_tr("clean.go_to_bom"))
        self.btn_clean_go_bom.clicked.connect(
            lambda: self.tabs.setCurrentIndex(self._tab_index("bom"))
        )
        clean_ok_lay.addWidget(self.clean_apply_ok_label, 1)
        clean_ok_lay.addWidget(self.btn_clean_go_bom)
        layout.addWidget(self.clean_apply_ok_banner)

        self.lbl_clean_source = QtWidgets.QLabel(
            self.ui_tr("clean.source_hint")
        )
        self.lbl_clean_source.setWordWrap(True)
        layout.addWidget(self.lbl_clean_source)

        self._clean_imported_comments: list[str] = []
        self._clean_last_preview: list = []
        self._clean_source_column: Optional[str] = None
        self._clean_source_indices: list[int] = []

        self.clean_preview_table = QtWidgets.QTableView()
        self.clean_preview_table.setAlternatingRowColors(True)
        self.clean_preview_model = CleanPreviewTableModel(
            pd.DataFrame(columns=["#", "Original", "Cleaned", "Type", "Source"])
        )
        self.clean_preview_table.setModel(self.clean_preview_model)
        self.clean_preview_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.clean_preview_table, 1)

    def _get_bom_comment_column_names(
        self, df: pd.DataFrame | None = None
    ) -> list[Any]:
        """All BOM columns mapped to «Comment» (column picker order).

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
                if self._mapping_combo_role(combo) == "Comment":
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
        ):
            w.setEnabled(on)
        self.clean_res_frame.setProperty("rclDisabled", not on)
        self.clean_res_frame.setStyleSheet(_RCL_ROW_DISABLED_STYLE if not on else "")
        self.clean_res_frame.style().unpolish(self.clean_res_frame)
        self.clean_res_frame.style().polish(self.clean_res_frame)
        self._update_clean_rcl_examples()
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
        if not QDesktopServices.openUrl(QUrl(url)):
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
        regex_master_enabled, regex_master_preview_scores = load_clean_debug_extras(
            self._settings
        )
        return build_clean_config(
            res_template=res_template,
            cap_template=cap_template,
            ind_template=ind_template,
            cap_nf_to_uf=self.clean_cap_nf.isChecked(),
            cap_uf_micro_sign=self.clean_cap_uf_micro.isChecked(),
            res_ohm_r_suffix=self.clean_res_ohm_r.isChecked(),
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
            self._log("Clean BOM: map a column to «Comment» on the BOM tab", "warning")
            logger.error("Clean BOM: BOM comment column not configured")
            return
        double_on = (
            self.clean_double_comment_import.isChecked()
            if hasattr(self, "clean_double_comment_import")
            else False
        )
        if double_on and len(comment_cols) < 2:
            self._log(
                "Clean BOM: Double Comment import needs ≥2 columns mapped to «Comment»",
                "warning",
            )
            return
        if double_on:
            use_cols = comment_cols
        else:
            use_cols = [comment_cols[0]]
        for col in use_cols:
            if col not in df.columns:
                self._log(f"Clean BOM: column «{col}» missing from BOM", "warning")
                return
        primary_col = comment_cols[0]
        self._clean_source_column = primary_col
        self._clean_source_indices = self._active_row_indices(
            len(df), self.bom_first_row, self.bom_last_row
        )
        if not self._clean_source_indices:
            self._log("Clean BOM: selected BOM row range is empty", "warning")
            return

        self._clean_imported_comments = import_bom_comments_for_clean(
            df,
            comment_cols,
            self._clean_source_indices,
            double_comment_enabled=double_on,
            double_comment_separator=str(
                self.clean_double_comment_sep.text()
                if hasattr(self, "clean_double_comment_sep")
                else " "
            ),
        )
        n = len(self._clean_imported_comments)
        joined = "», «".join(str(c) for c in use_cols)
        col_desc = (
            "«" + joined + "» (merged)"
            if double_on and len(use_cols) > 1
            else f"«{primary_col}»"
        )
        logger.info("Imported %d comments from BOM columns %s", n, use_cols)
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

        before_cols = list(self._bom_df.columns)
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
        self._refresh_active_row_highlight("bom")
        if not replace and after_cols != before_cols:
            roles = list(preserved_roles)
            while len(roles) < len(after_cols):
                roles.append("-")
            if "comment" in after_cols:
                roles[after_cols.index("comment")] = "Comment"
            self._fill_bom_combos(preserved_roles=roles)
        elif not replace and "comment" in after_cols and getattr(
            self, "bom_col_combos", None
        ):
            tidx = after_cols.index("comment")
            if tidx < len(self.bom_col_combos):
                self._set_mapping_combo_role(self.bom_col_combos[tidx], "Comment")
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
            "use_vendor": self.clean_use_vendor.isChecked(),
            "from_db": self.clean_from_db.isChecked(),
            "from_hanwha_mdb": self.clean_from_hanwha_mdb.isChecked(),
            "hanwha_partial_match": self.clean_hanwha_partial_match.isChecked(),
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
        first, last = self._active_row_numbers(
            self.bom_model.rowCount() if hasattr(self, "bom_model") else 0,
            self.bom_first_row,
            self.bom_last_row,
        )
        if first is None or last is None:
            return ""
        return self.ui_tr(
            "clean.source_range",
            first=first,
            last=last,
            count=n_rows,
        )

    def _show_clean_apply_banner(self, message: str) -> None:
        if not hasattr(self, "clean_apply_ok_banner"):
            return
        self.clean_apply_ok_label.setText(message)
        self.clean_apply_ok_banner.setVisible(True)
