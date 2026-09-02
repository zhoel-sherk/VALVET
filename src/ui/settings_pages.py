"""Settings tab pages (snapshots, cache, .valvetpack, fonts, colours, experimental)."""

from __future__ import annotations

import shutil
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6 import QtCore, QtWidgets

from themes.color_picker import pick_hex_color
from themes.colour_prefs import DEFAULT_TABLE_COLOURS, DEFAULT_UI_COLOURS
from themes.fonts_loader import (
    FONT_BOLD_SETTINGS_KEY,
    FONT_POINT_SETTINGS_KEY,
    FONT_TABLE_FAMILY_KEY,
    FONT_TABLE_POINT_KEY,
    FONT_TABLE_STYLE_KEY,
    FONT_UI_FAMILY_KEY,
    FONT_UI_STYLE_KEY,
    STYLE_BOLD,
    STYLE_BOLDITALIC,
    STYLE_ITALIC,
    STYLE_REGULAR,
    TABLE_FAMILY_INTER,
    TABLE_FAMILY_JETBRAINS,
    TABLE_FAMILY_SYSTEM,
    UI_FAMILY_INTER,
    UI_FAMILY_SYSTEM,
    build_table_font,
    build_ui_font,
    font_point_size_for_editor,
    font_table_point_size_for_editor,
    read_table_family,
    read_table_style,
    read_ui_family,
    read_ui_style,
)
from ui.chrome import switch_checkbox
from valvetpack import OPEN_FILTER, SAVE_FILTER, VALVETPACK_EXT
from working_copy import SnapshotIndex, delete_snapshot_pair, list_snapshot_indices

if TYPE_CHECKING:
    from app.window import MainWindow


def _prefs_profile_bool(val: object, default: bool = False) -> bool:
    """Same coercion as ``app_pyside6._prefs_profile_bool`` (avoid circular import)."""
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return bool(val)
    if isinstance(val, str):
        v = val.strip().lower()
        if v in ("0", "false", "no", "off", ""):
            return False
        if v in ("1", "true", "yes", "on"):
            return True
    return default


class SettingsPages(QtCore.QObject):
    """Six settings panes plus handlers (owned by the Settings tab)."""

    def __init__(self, main: "MainWindow"):
        super().__init__(main)
        self._main = main

        # --- Snapshots tab ---
        snap_w = QtWidgets.QWidget()
        snap_l = QtWidgets.QVBoxLayout(snap_w)
        self._snap_list = QtWidgets.QListWidget()
        self._snap_list.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection
        )
        snap_l.addWidget(self._snap_list, 1)
        self._snap_detail = QtWidgets.QPlainTextEdit()
        self._snap_detail.setReadOnly(True)
        self._snap_detail.setMaximumBlockCount(2000)
        snap_l.addWidget(self._snap_detail, 0)
        row = QtWidgets.QHBoxLayout()
        self._btn_refresh = QtWidgets.QPushButton(main.ui_tr("debug.refresh_snapshots"))
        self._btn_delete = QtWidgets.QPushButton(main.ui_tr("debug.delete_selected"))
        self._btn_copy_dir = QtWidgets.QPushButton(main.ui_tr("debug.copy_to_folder"))
        self._btn_export_zip = QtWidgets.QPushButton(main.ui_tr("debug.export_zip"))
        self._btn_recover_all = QtWidgets.QPushButton(
            main.ui_tr("debug.recover_all_dirty")
        )
        self._btn_refresh.clicked.connect(self._reload_list)
        self._btn_delete.clicked.connect(self._delete_selected)
        self._btn_copy_dir.clicked.connect(self._copy_to_folder)
        self._btn_export_zip.clicked.connect(self._export_zip)
        self._btn_recover_all.clicked.connect(self._recover_all_dirty)
        for b in (
            self._btn_refresh,
            self._btn_delete,
            self._btn_copy_dir,
            self._btn_export_zip,
            self._btn_recover_all,
        ):
            row.addWidget(b)
        row.addStretch(1)
        snap_l.addLayout(row)
        self._snap_list.currentItemChanged.connect(self._on_snap_selection)
        self.page_snapshots = snap_w

        # --- Cache tab ---
        cache_w = QtWidgets.QWidget()
        cache_l = QtWidgets.QVBoxLayout(cache_w)
        self._cache_info = QtWidgets.QLabel()
        cache_l.addWidget(self._cache_info)
        self._btn_clear_autosave = QtWidgets.QPushButton(
            main.ui_tr("debug.clear_autosave_dir")
        )
        self._btn_clear_autosave.clicked.connect(self._clear_autosave)
        cache_l.addWidget(self._btn_clear_autosave)
        cache_l.addStretch(1)
        self.page_cache = cache_w

        # --- Session (.valvetpack) ---
        bundle_w = QtWidgets.QWidget()
        bundle_l = QtWidgets.QVBoxLayout(bundle_w)
        self._session_note = QtWidgets.QLabel(main.ui_tr("settings.session_note"))
        self._session_note.setWordWrap(True)
        bundle_l.addWidget(self._session_note)
        self._session_include_cap = QtWidgets.QLabel(
            main.ui_tr("settings.session_include")
        )
        bundle_l.addWidget(self._session_include_cap)
        from valvetpack import PACK_INCLUDE_DEFAULTS, PACK_INCLUDE_KEYS

        self._pack_include: dict[str, QtWidgets.QCheckBox] = {}
        s = main._settings
        for key in PACK_INCLUDE_KEYS:
            chk = switch_checkbox(main.ui_tr(f"settings.pack_{key}"))
            default = PACK_INCLUDE_DEFAULTS[key]
            chk.setChecked(
                _prefs_profile_bool(
                    s.value(f"session_pack/include_{key}", default), default
                )
            )
            chk.toggled.connect(
                lambda on, k=key: main._settings.setValue(
                    f"session_pack/include_{k}", bool(on)
                )
            )
            bundle_l.addWidget(chk)
            self._pack_include[key] = chk
        row_b = QtWidgets.QHBoxLayout()
        self._btn_save_pack = QtWidgets.QPushButton(main.ui_tr("debug.save_boomerpack"))
        self._btn_load_pack = QtWidgets.QPushButton(main.ui_tr("debug.load_boomerpack"))
        self._btn_save_pack.clicked.connect(self._save_boomerpack)
        self._btn_load_pack.clicked.connect(self._load_boomerpack)
        row_b.addWidget(self._btn_save_pack)
        row_b.addWidget(self._btn_load_pack)
        row_b.addStretch(1)
        bundle_l.addLayout(row_b)
        bundle_l.addStretch(1)
        self.page_session = bundle_w

        # --- Fonts tab ---
        fonts_w = QtWidgets.QWidget()
        fonts_l = QtWidgets.QVBoxLayout(fonts_w)
        self._fonts_note = QtWidgets.QLabel(main.ui_tr("debug.fonts_note"))
        self._fonts_note.setWordWrap(True)
        fonts_l.addWidget(self._fonts_note)

        def _add_row(
            layout: QtWidgets.QGridLayout,
            row: int,
            label_key: str,
            widget: QtWidgets.QWidget,
        ) -> None:
            layout.addWidget(QtWidgets.QLabel(main.ui_tr(label_key)), row, 0)
            layout.addWidget(widget, row, 1)

        # --- Main UI ---
        grp_ui = QtWidgets.QGroupBox(main.ui_tr("debug.fonts_group_ui"))
        grid_ui = QtWidgets.QGridLayout(grp_ui)
        self._font_ui_family = QtWidgets.QComboBox()
        self._font_ui_family.addItem(
            main.ui_tr("debug.fonts_opt_inter"), UI_FAMILY_INTER
        )
        self._font_ui_family.addItem(
            main.ui_tr("debug.fonts_opt_system"), UI_FAMILY_SYSTEM
        )
        _add_row(grid_ui, 0, "debug.fonts_family_label", self._font_ui_family)
        self._font_ui_pt = QtWidgets.QSpinBox()
        self._font_ui_pt.setRange(7, 24)
        _add_row(grid_ui, 1, "debug.fonts_point_label", self._font_ui_pt)
        self._font_ui_style = QtWidgets.QComboBox()
        for key, st in (
            ("debug.fonts_style_regular", STYLE_REGULAR),
            ("debug.fonts_style_bold", STYLE_BOLD),
            ("debug.fonts_style_italic", STYLE_ITALIC),
            ("debug.fonts_style_bolditalic", STYLE_BOLDITALIC),
        ):
            self._font_ui_style.addItem(main.ui_tr(key), st)
        _add_row(grid_ui, 2, "debug.fonts_style_label", self._font_ui_style)
        fonts_l.addWidget(grp_ui)
        self._fonts_preview_ui_cap = QtWidgets.QLabel(
            main.ui_tr("debug.fonts_preview_ui")
        )
        fonts_l.addWidget(self._fonts_preview_ui_cap)
        self._font_preview_ui = QtWidgets.QPlainTextEdit()
        self._font_preview_ui.setReadOnly(True)
        self._font_preview_ui.setMaximumHeight(72)
        self._font_preview_ui.setPlainText("Aa Bb 0123456789 — VALVET")
        fonts_l.addWidget(self._font_preview_ui)

        # --- Data tables ---
        grp_tbl = QtWidgets.QGroupBox(main.ui_tr("debug.fonts_group_table"))
        grid_tbl = QtWidgets.QGridLayout(grp_tbl)
        self._font_table_family = QtWidgets.QComboBox()
        self._font_table_family.addItem(
            main.ui_tr("debug.fonts_opt_jetbrains"), TABLE_FAMILY_JETBRAINS
        )
        self._font_table_family.addItem(
            main.ui_tr("debug.fonts_opt_inter"), TABLE_FAMILY_INTER
        )
        self._font_table_family.addItem(
            main.ui_tr("debug.fonts_opt_system"), TABLE_FAMILY_SYSTEM
        )
        _add_row(grid_tbl, 0, "debug.fonts_family_label", self._font_table_family)
        self._font_table_pt = QtWidgets.QSpinBox()
        self._font_table_pt.setRange(7, 24)
        _add_row(grid_tbl, 1, "debug.fonts_point_label", self._font_table_pt)
        self._font_table_style = QtWidgets.QComboBox()
        for key, st in (
            ("debug.fonts_style_regular", STYLE_REGULAR),
            ("debug.fonts_style_bold", STYLE_BOLD),
            ("debug.fonts_style_italic", STYLE_ITALIC),
            ("debug.fonts_style_bolditalic", STYLE_BOLDITALIC),
        ):
            self._font_table_style.addItem(main.ui_tr(key), st)
        _add_row(grid_tbl, 2, "debug.fonts_style_label", self._font_table_style)
        fonts_l.addWidget(grp_tbl)
        self._fonts_preview_table_cap = QtWidgets.QLabel(
            main.ui_tr("debug.fonts_preview_table")
        )
        fonts_l.addWidget(self._fonts_preview_table_cap)
        self._font_preview_table = QtWidgets.QTableWidget(2, 3)
        self._font_preview_table.setHorizontalHeaderLabels(
            [
                main.ui_tr("debug.fonts_table_col_a"),
                main.ui_tr("debug.fonts_table_col_b"),
                main.ui_tr("debug.fonts_table_col_c"),
            ]
        )
        self._font_preview_table.verticalHeader().setVisible(False)
        self._font_preview_table.setMaximumHeight(140)
        for r in range(2):
            for c in range(3):
                it = QtWidgets.QTableWidgetItem(f"R{r + 1}C{c + 1}")
                self._font_preview_table.setItem(r, c, it)
        fonts_l.addWidget(self._font_preview_table)

        self._btn_font_apply = QtWidgets.QPushButton(main.ui_tr("debug.fonts_apply"))
        self._btn_font_apply.clicked.connect(self._on_font_apply_clicked)
        fonts_l.addWidget(self._btn_font_apply)
        for w in (
            self._font_ui_family,
            self._font_ui_style,
            self._font_table_family,
            self._font_table_style,
        ):
            w.currentIndexChanged.connect(lambda *_: self._refresh_font_preview())
        self._font_ui_pt.valueChanged.connect(lambda *_: self._refresh_font_preview())
        self._font_table_pt.valueChanged.connect(
            lambda *_: self._refresh_font_preview()
        )
        fonts_l.addStretch(1)
        self.page_fonts = fonts_w
        self._fonts_group_ui = grp_ui
        self._fonts_group_table = grp_tbl

        # --- Colours tab (saved in active profile JSON) ---
        colours_w = QtWidgets.QWidget()
        colours_outer = QtWidgets.QVBoxLayout(colours_w)
        self._colours_note = QtWidgets.QLabel(main.ui_tr("debug.colours_note"))
        self._colours_note.setWordWrap(True)
        colours_outer.addWidget(self._colours_note)
        scroll_c = QtWidgets.QScrollArea()
        scroll_c.setWidgetResizable(True)
        scroll_c.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        inner_c = QtWidgets.QWidget()
        scroll_c.setWidget(inner_c)
        colours_inner = QtWidgets.QVBoxLayout(inner_c)
        colours_outer.addWidget(scroll_c, 1)

        self._colour_edits_ui: dict[str, QtWidgets.QLineEdit] = {}
        self._colour_edits_table: dict[str, QtWidgets.QLineEdit] = {}

        def _add_colour_group(
            title_key: str,
            keys: tuple[str, ...],
            prefix: str,
            dest: dict[str, QtWidgets.QLineEdit],
        ) -> None:
            g = QtWidgets.QGroupBox(main.ui_tr(title_key))
            grid = QtWidgets.QGridLayout(g)
            for i, key in enumerate(keys):
                tr_key = (
                    f"debug.colours.ui.{key}"
                    if prefix == "ui"
                    else f"debug.colours.table.{key}"
                )
                lbl = QtWidgets.QLabel(main.ui_tr(tr_key))
                edit = QtWidgets.QLineEdit()
                edit.setMaxLength(7)
                edit.setMaximumWidth(100)
                dest[key] = edit
                pick = QtWidgets.QPushButton(main.ui_tr("debug.colours_pick"))
                pick.setMaximumWidth(90)
                pick.clicked.connect(partial(self._on_pick_colour_clicked, prefix, key))
                grid.addWidget(lbl, i, 0)
                row_h = QtWidgets.QHBoxLayout()
                row_h.addWidget(edit)
                row_h.addWidget(pick)
                row_h.addStretch(1)
                wrap = QtWidgets.QWidget()
                wrap.setLayout(row_h)
                grid.addWidget(wrap, i, 1)
            colours_inner.addWidget(g)

        _add_colour_group(
            "debug.colours_group_ui",
            (
                "window_bg",
                "window_fg",
                "panel_bg",
                "panel_fg",
                "control_bg",
                "control_fg",
            ),
            "ui",
            self._colour_edits_ui,
        )
        _add_colour_group(
            "debug.colours_group_table",
            (
                "bg",
                "alt_bg",
                "text",
                "header_bg",
                "header_fg",
                "selection_bg",
                "selection_fg",
                "grid",
            ),
            "table",
            self._colour_edits_table,
        )
        row_cb = QtWidgets.QHBoxLayout()
        self._btn_colour_reset_ui = QtWidgets.QPushButton(
            main.ui_tr("debug.colours_reset_ui")
        )
        self._btn_colour_reset_table = QtWidgets.QPushButton(
            main.ui_tr("debug.colours_reset_table")
        )
        self._btn_colour_apply = QtWidgets.QPushButton(
            main.ui_tr("debug.colours_apply")
        )
        self._btn_colour_reset_ui.clicked.connect(self._on_colours_reset_ui_clicked)
        self._btn_colour_reset_table.clicked.connect(
            self._on_colours_reset_table_clicked
        )
        self._btn_colour_apply.clicked.connect(self._on_colours_apply_clicked)
        row_cb.addWidget(self._btn_colour_reset_ui)
        row_cb.addWidget(self._btn_colour_reset_table)
        row_cb.addStretch(1)
        row_cb.addWidget(self._btn_colour_apply)
        colours_inner.addLayout(row_cb)
        colours_inner.addStretch(1)
        self.page_colours = colours_w

        # --- Experimental: optional Step 3D tab (restart required) ---
        exp_w = QtWidgets.QWidget()
        exp_l = QtWidgets.QVBoxLayout(exp_w)
        exp_note = QtWidgets.QLabel(main.ui_tr("debug.experimental_note"))
        exp_note.setWordWrap(True)
        exp_l.addWidget(exp_note)
        s = main._settings
        self._cb_exp_step = QtWidgets.QCheckBox(main.ui_tr("tab.step_3d"))
        self._cb_exp_step.setChecked(
            _prefs_profile_bool(s.value("experimental/enable_step_3d", False), False)
        )
        self._cb_exp_step.toggled.connect(
            lambda on: self._on_experimental_toggled("step_3d", on)
        )
        exp_l.addWidget(self._cb_exp_step)
        exp_l.addStretch(1)
        self.page_experimental = exp_w
        self._exp_note = exp_note

        self.pages = (
            snap_w,
            cache_w,
            bundle_w,
            fonts_w,
            colours_w,
            exp_w,
        )

        self._reload_list()
        self._update_cache_label()
        self._load_fonts_tab_state()
        self._refresh_font_preview()
        self._load_colours_tab_state()

    def on_shown(self) -> None:
        self._load_fonts_tab_state()
        self._refresh_font_preview()
        self._load_colours_tab_state()
        self._reload_experimental_tab_state()
        self._reload_list()
        self._update_cache_label()

    def refresh_static_texts(self) -> None:
        tr = self._main.ui_tr
        self._btn_refresh.setText(tr("debug.refresh_snapshots"))
        self._btn_delete.setText(tr("debug.delete_selected"))
        self._btn_copy_dir.setText(tr("debug.copy_to_folder"))
        self._btn_export_zip.setText(tr("debug.export_zip"))
        self._btn_recover_all.setText(tr("debug.recover_all_dirty"))
        self._btn_clear_autosave.setText(tr("debug.clear_autosave_dir"))
        self._session_note.setText(tr("settings.session_note"))
        if hasattr(self, "_session_include_cap"):
            self._session_include_cap.setText(tr("settings.session_include"))
        for key, chk in getattr(self, "_pack_include", {}).items():
            chk.setText(tr(f"settings.pack_{key}"))
        self._btn_save_pack.setText(tr("debug.save_boomerpack"))
        self._btn_load_pack.setText(tr("debug.load_boomerpack"))
        self._fonts_note.setText(tr("debug.fonts_note"))
        self._fonts_group_ui.setTitle(tr("debug.fonts_group_ui"))
        self._fonts_group_table.setTitle(tr("debug.fonts_group_table"))
        self._fonts_preview_ui_cap.setText(tr("debug.fonts_preview_ui"))
        self._fonts_preview_table_cap.setText(tr("debug.fonts_preview_table"))
        self._btn_font_apply.setText(tr("debug.fonts_apply"))
        self._colours_note.setText(tr("debug.colours_note"))
        self._btn_colour_reset_ui.setText(tr("debug.colours_reset_ui"))
        self._btn_colour_reset_table.setText(tr("debug.colours_reset_table"))
        self._btn_colour_apply.setText(tr("debug.colours_apply"))
        self._exp_note.setText(tr("debug.experimental_note"))
        self._cb_exp_step.setText(tr("tab.step_3d"))
        self._update_cache_label()

    @staticmethod
    def _set_combo_user_data(cb: QtWidgets.QComboBox, data: object) -> None:
        for i in range(cb.count()):
            if cb.itemData(i, QtCore.Qt.ItemDataRole.UserRole) == data:
                cb.setCurrentIndex(i)
                return
        cb.setCurrentIndex(0)

    def _load_fonts_tab_state(self) -> None:
        s = self._main._settings
        self._set_combo_user_data(self._font_ui_family, read_ui_family(s))
        self._font_ui_pt.setValue(font_point_size_for_editor(s))
        self._set_combo_user_data(self._font_ui_style, read_ui_style(s))
        self._set_combo_user_data(self._font_table_family, read_table_family(s))
        self._font_table_pt.setValue(font_table_point_size_for_editor(s))
        self._set_combo_user_data(self._font_table_style, read_table_style(s))

    def _refresh_font_preview(self) -> None:
        ui_fam = self._font_ui_family.currentData(QtCore.Qt.ItemDataRole.UserRole)
        ui_st = self._font_ui_style.currentData(QtCore.Qt.ItemDataRole.UserRole)
        tbl_fam = self._font_table_family.currentData(QtCore.Qt.ItemDataRole.UserRole)
        tbl_st = self._font_table_style.currentData(QtCore.Qt.ItemDataRole.UserRole)
        f_ui = build_ui_font(
            self._main._settings,
            override_point=int(self._font_ui_pt.value()),
            override_family=str(ui_fam) if ui_fam is not None else None,
            override_style=str(ui_st) if ui_st is not None else None,
        )
        self._font_preview_ui.setFont(f_ui)
        f_tbl = build_table_font(
            self._main._settings,
            override_point=int(self._font_table_pt.value()),
            override_family=str(tbl_fam) if tbl_fam is not None else None,
            override_style=str(tbl_st) if tbl_st is not None else None,
        )
        self._font_preview_table.setFont(f_tbl)
        hdr = self._font_preview_table.horizontalHeader()
        hdr.setFont(f_tbl)

    def _on_font_apply_clicked(self) -> None:
        s = self._main._settings
        ui_fam = self._font_ui_family.currentData(QtCore.Qt.ItemDataRole.UserRole)
        ui_st = self._font_ui_style.currentData(QtCore.Qt.ItemDataRole.UserRole)
        tbl_fam = self._font_table_family.currentData(QtCore.Qt.ItemDataRole.UserRole)
        tbl_st = self._font_table_style.currentData(QtCore.Qt.ItemDataRole.UserRole)
        s.setValue(FONT_UI_FAMILY_KEY, str(ui_fam))
        s.setValue(FONT_POINT_SETTINGS_KEY, int(self._font_ui_pt.value()))
        s.setValue(FONT_UI_STYLE_KEY, str(ui_st))
        s.setValue(FONT_TABLE_FAMILY_KEY, str(tbl_fam))
        s.setValue(FONT_TABLE_POINT_KEY, int(self._font_table_pt.value()))
        s.setValue(FONT_TABLE_STYLE_KEY, str(tbl_st))
        s.setValue(FONT_BOLD_SETTINGS_KEY, str(ui_st) in (STYLE_BOLD, STYLE_BOLDITALIC))
        self._main.apply_ui_font_from_settings()
        self._refresh_font_preview()

    def _load_colours_tab_state(self) -> None:
        for k, ed in self._colour_edits_ui.items():
            ed.setText(self._main._ui_colours.get(k, DEFAULT_UI_COLOURS[k]))
        for k, ed in self._colour_edits_table.items():
            ed.setText(self._main._table_colours.get(k, DEFAULT_TABLE_COLOURS[k]))

    def _on_pick_colour_clicked(self, prefix: str, key: str) -> None:
        edits = self._colour_edits_ui if prefix == "ui" else self._colour_edits_table
        edit = edits[key]
        raw = edit.text().strip()
        name = pick_hex_color(self._main, raw, self._main.ui_tr("debug.colours_pick"))
        if name:
            edit.setText(name)

    def _on_colours_reset_ui_clicked(self) -> None:
        for k, ed in self._colour_edits_ui.items():
            ed.setText(DEFAULT_UI_COLOURS[k])

    def _on_colours_reset_table_clicked(self) -> None:
        for k, ed in self._colour_edits_table.items():
            ed.setText(DEFAULT_TABLE_COLOURS[k])

    def _on_colours_apply_clicked(self) -> None:
        ui_raw = {k: ed.text().strip() for k, ed in self._colour_edits_ui.items()}
        tbl_raw = {k: ed.text().strip() for k, ed in self._colour_edits_table.items()}
        self._main.apply_debug_colours(ui_raw, tbl_raw)

    def _on_experimental_toggled(self, key: str, on: bool) -> None:
        self._main._settings.setValue(f"experimental/enable_{key}", bool(on))

    def _reload_experimental_tab_state(self) -> None:
        s = self._main._settings
        for cb, key, default in ((self._cb_exp_step, "step_3d", False),):
            cb.blockSignals(True)
            cb.setChecked(
                _prefs_profile_bool(
                    s.value(f"experimental/enable_{key}", default), default
                )
            )
            cb.blockSignals(False)

    def _autosave_dir(self) -> Path:
        return Path(self._main._autosave_dir)

    def _reload_list(self) -> None:
        self._snap_list.clear()
        base = self._autosave_dir()
        for si in list_snapshot_indices(base):
            kind = str(si.meta.get("kind", "?"))
            src = (si.meta.get("source") or {}).get("name", "?")
            dirty = si.meta.get("dirty", False)
            saved = si.meta.get("saved_at", "")
            label = f"[{kind}] {src}  dirty={dirty}  {saved}"
            item = QtWidgets.QListWidgetItem(label)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, str(si.meta_path))
            self._snap_list.addItem(item)
        self._snap_detail.clear()

    def _current_indices(self) -> list[SnapshotIndex]:
        base = self._autosave_dir()
        all_si = {str(si.meta_path): si for si in list_snapshot_indices(base)}
        out: list[SnapshotIndex] = []
        for it in self._snap_list.selectedItems():
            mp = it.data(QtCore.Qt.ItemDataRole.UserRole)
            if mp and mp in all_si:
                out.append(all_si[mp])
        return out

    def _on_snap_selection(
        self, cur: QtWidgets.QListWidgetItem | None, _prev: Any
    ) -> None:
        if cur is None:
            self._snap_detail.clear()
            return
        mp = cur.data(QtCore.Qt.ItemDataRole.UserRole)
        if not mp:
            return
        try:
            text = Path(mp).read_text(encoding="utf-8")
        except OSError:
            text = ""
        self._snap_detail.setPlainText(text)

    def _delete_selected(self) -> None:
        sel = self._current_indices()
        if not sel:
            QtWidgets.QMessageBox.information(
                self._main,
                self._main.ui_tr("debug.window_title"),
                self._main.ui_tr("debug.none_selected"),
            )
            return
        if (
            QtWidgets.QMessageBox.question(
                self._main,
                self._main.ui_tr("debug.confirm_delete_title"),
                self._main.ui_tr("debug.confirm_delete_body", n=len(sel)),
            )
            != QtWidgets.QMessageBox.StandardButton.Yes
        ):
            return
        for si in sel:
            delete_snapshot_pair(si.meta_path)
        self._main._log(self._main.ui_tr("debug.deleted_n", n=len(sel)), "info")
        self._reload_list()
        self._update_cache_label()

    def _copy_to_folder(self) -> None:
        sel = self._current_indices()
        if not sel:
            QtWidgets.QMessageBox.information(
                self._main,
                self._main.ui_tr("debug.window_title"),
                self._main.ui_tr("debug.none_selected"),
            )
            return
        d = QtWidgets.QFileDialog.getExistingDirectory(
            self._main, self._main.ui_tr("debug.pick_folder")
        )
        if not d:
            return
        dest = Path(d)
        for si in sel:
            shutil.copy2(si.meta_path, dest / si.meta_path.name)
            shutil.copy2(si.pkl_path, dest / si.pkl_path.name)
        self._main._log(self._main.ui_tr("debug.copied_n", n=len(sel), dir=d), "info")

    def _export_zip(self) -> None:
        sel = self._current_indices()
        if not sel:
            QtWidgets.QMessageBox.information(
                self._main,
                self._main.ui_tr("debug.window_title"),
                self._main.ui_tr("debug.none_selected"),
            )
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self._main,
            self._main.ui_tr("debug.export_zip_save_title"),
            str(Path.home() / "valvet_snapshots_export.zip"),
            "ZIP (*.zip);;All (*)",
        )
        if not path:
            return
        import zipfile

        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for si in sel:
                zf.write(si.meta_path, arcname=f"{si.meta_path.stem}.json")
                zf.write(si.pkl_path, arcname=f"{si.meta_path.stem}.pkl")
        self._main._log(self._main.ui_tr("debug.exported_zip", path=path), "info")

    def _recover_all_dirty(self) -> None:
        self._main._debug_recover_all_dirty_snapshots()
        self._reload_list()

    def _clear_autosave(self) -> None:
        if (
            QtWidgets.QMessageBox.question(
                self._main,
                self._main.ui_tr("debug.clear_autosave_title"),
                self._main.ui_tr(
                    "debug.clear_autosave_body", path=str(self._autosave_dir())
                ),
            )
            != QtWidgets.QMessageBox.StandardButton.Yes
        ):
            return
        base = self._autosave_dir()
        n = 0
        if base.is_dir():
            for p in base.iterdir():
                if p.suffix in (".json", ".pkl", ".tmp"):
                    try:
                        p.unlink()
                        n += 1
                    except OSError:
                        pass
        self._main._log(self._main.ui_tr("debug.cleared_files", n=n), "info")
        self._reload_list()
        self._update_cache_label()

    def _update_cache_label(self) -> None:
        base = self._autosave_dir()
        n = 0
        if base.is_dir():
            n = sum(1 for _ in base.iterdir())
        self._cache_info.setText(
            self._main.ui_tr("debug.cache_dir_label", path=str(base), n=n)
        )

    def _save_boomerpack(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self._main,
            self._main.ui_tr("debug.save_boomerpack"),
            str(Path.home() / "session.valvetpack"),
            SAVE_FILTER,
        )
        if not path:
            return
        if not path.lower().endswith(VALVETPACK_EXT):
            path += VALVETPACK_EXT
        self._main._debug_save_boomerpack(path)

    def _load_boomerpack(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self._main,
            self._main.ui_tr("debug.load_boomerpack"),
            str(Path.home()),
            OPEN_FILTER,
        )
        if not path:
            return
        self._main._debug_load_boomerpack(path)
