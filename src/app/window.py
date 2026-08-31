"""Main application window (mixins + shell)."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from PySide6 import QtCore, QtGui, QtWidgets

import logger
from app.constants import SETTINGS_APP, SETTINGS_ORG
from app.prefs import _prefs_profile_bool
from app.workers import CrossCheckThread
from app_paths import autosave_root
from debug_settings_dialog import DebugSettingsDialog
from machine_library_tab import MachineLibraryTab
from smt_processor import ProcessorConfig, SMTDataProcessor
from themes.colour_prefs import (
    DEFAULT_TABLE_COLOURS,
    DEFAULT_UI_COLOURS,
    merge_table_colours,
    merge_ui_colours,
)
from themes.fonts_loader import apply_app_font, build_mono_font
from themes.stylesheet import apply_composed_stylesheet
from ui.bom_tab import BomTabMixin
from ui.clean_tab import CleanTabMixin
from ui.files import FilesMixin
from ui.mapping import MappingMixin
from ui.merge_tab import MergeTabMixin
from ui.pnp_tab import PnpTabMixin
from ui.profiles import ProfilesMixin
from ui.project_tab import configure_path_label, setup_project_tab
from ui.report_tab import ReportTabMixin
from ui.session import SessionMixin
from ui.table_actions import TableActionsMixin
from ui_i18n import SUPPORTED_UI_LOCALES, UiI18n
from valvetpack import OPEN_FILTER, SAVE_FILTER, VALVETPACK_EXT

_TAB_GROUP_KEY = {
    "project": "data",
    "bom": "data",
    "pnp": "data",
    "package": "data",
    "clean_bom": "transform",
    "merge": "transform",
    "report": "output",
    "pcb_preview": "view",
    "step_3d": "view",
    "machine_lib": "view",
}


class MainWindow(
    MappingMixin,
    TableActionsMixin,
    FilesMixin,
    BomTabMixin,
    PnpTabMixin,
    CleanTabMixin,
    MergeTabMixin,
    ReportTabMixin,
    ProfilesMixin,
    SessionMixin,
    QtWidgets.QMainWindow,
):
    """Main application window."""

    log_message = QtCore.Signal(str, str)  # message, level

    def __init__(self, *, settings: QtCore.QSettings | None = None, debug: bool = False):
        super().__init__()
        self.setMinimumSize(900, 600)
        self.resize(1400, 900)
        self._cli_debug = bool(debug)

        # Data processor
        self.processor = SMTDataProcessor(ProcessorConfig())

        # Current data
        self._bom_df: Optional[pd.DataFrame] = None
        self._pnp_df: Optional[pd.DataFrame] = None
        self._result_df: Optional[pd.DataFrame] = None

        # Recent files (up to 10)
        self._recent_bom: list[str] = []
        self._recent_pnp: list[str] = []
        self._last_report_html: str = ""
        self._last_merge_df: Optional[pd.DataFrame] = None
        self._restoring_settings: bool = False
        self._settings = settings or QtCore.QSettings(SETTINGS_ORG, SETTINGS_APP)
        self._autosave_dir = str(autosave_root())
        self._cc_thread: Optional[CrossCheckThread] = None
        self._bom_source_path: str = ""
        self._pnp_source_path: str = ""
        self._pnp_secondary_path: str = ""
        self._pnp_primary_row_count: int = 0
        self._pnp_layer_reload_timer = QtCore.QTimer(self)
        self._pnp_layer_reload_timer.setSingleShot(True)
        self._pnp_layer_reload_timer.timeout.connect(self._on_pnp_layer_reload_timer)
        self._bom_dirty: bool = False
        self._pnp_dirty: bool = False
        self._loading_working_copy: bool = False
        self._autosave_timer = QtCore.QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.timeout.connect(self._autosave_dirty_working_copies)
        self._bom_ui_restoring = False
        self._pnp_ui_restoring = False
        self._syncing_pnp_xy_units = False
        self._bom_tab_settings_timer = QtCore.QTimer(self)
        self._bom_tab_settings_timer.setSingleShot(True)
        self._bom_tab_settings_timer.timeout.connect(
            self._save_bom_tab_settings_to_disk
        )
        self._pnp_tab_settings_timer = QtCore.QTimer(self)
        self._pnp_tab_settings_timer.setSingleShot(True)
        self._pnp_tab_settings_timer.timeout.connect(
            self._save_pnp_tab_settings_to_disk
        )

        self._profile_restore_bom_mappings: Optional[list[str]] = None
        self._profile_restore_pnp_mappings: Optional[list[str]] = None

        self._session_bom_to_pnp: dict[str, set[str]] = defaultdict(set)
        self._session_pnp_to_bom: dict[str, set[str]] = defaultdict(set)
        self._bom_undo_stack = QtGui.QUndoStack(self)
        self._pnp_undo_stack = QtGui.QUndoStack(self)
        self._bom_mapping_highlight: int = -1
        self._pnp_mapping_highlight: int = -1
        self.bom_col_combos: list = []
        self.pnp_col_combos: list = []

        self._clean_preview_stale: bool = False

        self._ui_colours: dict[str, str] = dict(DEFAULT_UI_COLOURS)
        self._table_colours: dict[str, str] = dict(DEFAULT_TABLE_COLOURS)

        _raw_lang = self._settings.value("ui/language", "en")
        _lang = str(_raw_lang) if _raw_lang is not None else "en"
        self._i18n = UiI18n(_lang if _lang in SUPPORTED_UI_LOCALES else "en")
        self.setWindowTitle(self.ui_tr("app.window_title"))

        self._setup_ui()
        self._load_settings()
        if self._cli_debug or logger.env_debug_enabled():
            self.chk_colorful.setChecked(True)
        self._sync_file_debug_logger()
        self._session_geometry_restored = False
        self._log(self.ui_tr("msg.app_ready"), "info")

    def ui_tr(self, key: str, **kwargs: Any) -> str:
        """UI string from current language catalog."""
        return self._i18n.tr(key, **kwargs)

    def _setup_ui(self):
        """Build main UI."""
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)

        main_layout = QtWidgets.QVBoxLayout(central)

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.tabBar().setExpanding(True)
        main_layout.addWidget(self.tabs)
        self._tab_keys_in_order = []

        exp_step = _prefs_profile_bool(
            self._settings.value("experimental/enable_step_3d", False), False
        )

        # Tabs (titles via ui_tr in _register_main_tab)
        self._create_project_tab()
        self._create_bom_tab()
        self._create_pnp_tab()
        self._create_package_tab()
        self._create_clean_tab()
        self._create_merge_tab()
        self._create_report_tab()
        self._create_pcb_preview_tab()
        if exp_step:
            self._create_step_3d_tab()
        self._create_machine_library_tab()

        self.tabs.currentChanged.connect(self._on_main_tab_changed)

        self._sync_tab_titles_i18n()
        self.apply_ui_font_from_settings()

        self._create_menus()
        self._install_edit_shortcuts()

        self._refresh_shell_status()

    def _sync_tab_titles_i18n(self) -> None:
        for i, key in enumerate(self._tab_keys_in_order):
            group = _TAB_GROUP_KEY.get(key, "")
            title = self.ui_tr(f"tab.{key}")
            if group:
                g = self.ui_tr(f"tab.group.{group}")
                title = f"{g} · {title}"
            self.tabs.setTabText(i, title.upper())

    def _refresh_shell_status(self) -> None:
        bom = Path(self._bom_source_path).name if self._bom_source_path else self.ui_tr(
            "status.no_bom"
        )
        comment = self.ui_tr("status.comment_unmapped")
        if hasattr(self, "_get_bom_comment_column_names"):
            try:
                cols = self._get_bom_comment_column_names()
            except Exception:
                cols = []
            if cols:
                comment = ", ".join(str(c) for c in cols)
        rows = self.ui_tr("status.rows_all")
        stale = (
            self.ui_tr("status.clean_stale")
            if getattr(self, "_clean_preview_stale", False)
            else ""
        )
        self.statusBar().showMessage(
            self.ui_tr(
                "status.shell",
                bom=bom,
                comment=comment,
                rows=rows,
                stale=stale,
            )
        )
        if hasattr(self, "_refresh_clean_context_chip"):
            self._refresh_clean_context_chip()

    def _refresh_static_ui_texts(self) -> None:
        """Re-apply translated strings (after language change)."""
        self.setWindowTitle(self.ui_tr("app.window_title"))
        self._sync_tab_titles_i18n()
        self._refresh_project_tab_static_texts()
        if hasattr(self, "_refresh_clean_tab_static_texts"):
            self._refresh_clean_tab_static_texts()
        if hasattr(self, "_pcb_tab") and hasattr(self._pcb_tab, "refresh_static_texts"):
            self._pcb_tab.refresh_static_texts()
        if hasattr(self, "_step_3d_tab"):
            self._step_3d_tab.refresh_static_texts()
        self._refresh_shell_status()

    def apply_ui_font_from_settings(self) -> None:
        """Apply UI font from QSettings (Debug Fonts tab and startup)."""
        apply_app_font(self._settings)
        if hasattr(self, "console"):
            self.console.setFont(build_mono_font(self._settings))

    def _refresh_application_stylesheet(self) -> None:
        """Recompose qdarkstyle + tokens + profile UI/table colours; then re-apply fonts."""
        apply_composed_stylesheet(
            self._ui_colours,
            self._table_colours,
            apply_fonts=self.apply_ui_font_from_settings,
        )

    def apply_debug_colours(self, ui: dict[str, Any], table: dict[str, Any]) -> None:
        """Merge colour dicts from Debug dialog, refresh QSS, persist active profile."""
        self._ui_colours = merge_ui_colours(ui)
        self._table_colours = merge_table_colours(table)
        self._refresh_application_stylesheet()
        self._save_full_profile_snapshot()
        self._log(self.ui_tr("debug.colours_saved_profile"), "info")

    def _refresh_project_tab_static_texts(self) -> None:
        if not hasattr(self, "project_bom_group"):
            return
        self.project_load_group.setTitle(self.ui_tr("project.load_files"))
        self.project_bom_group.setTitle(self.ui_tr("project.bom_file"))
        self.project_pnp_group.setTitle(self.ui_tr("project.pnp_file"))
        self.project_settings_group.setTitle(self.ui_tr("project.settings"))
        self.project_console_group.setTitle(self.ui_tr("project.console"))
        self.btn_browse_bom.setText(self.ui_tr("project.browse_bom"))
        self.btn_browse_pnp.setText(self.ui_tr("project.browse_pnp"))
        self.profile_label.setText(self.ui_tr("project.profile"))
        self.btn_profile_clone.setText(self.ui_tr("project.profile_clone"))
        self.btn_profile_delete.setText(self.ui_tr("project.profile_delete"))
        self.chk_colorful.setText(self.ui_tr("project.debug_logs"))
        self.chk_colorful.setToolTip(self.ui_tr("project.debug_logs_hint"))
        self.lang_label.setText(self.ui_tr("project.language"))
        if self._bom_source_path:
            configure_path_label(
                self.bom_path_label,
                self._bom_source_path,
                empty_text=self.ui_tr("project.no_file"),
            )
        else:
            configure_path_label(
                self.bom_path_label, "", empty_text=self.ui_tr("project.no_file")
            )
        if self._pnp_source_path:
            configure_path_label(
                self.pnp_path_label,
                self._pnp_source_path,
                empty_text=self.ui_tr("project.no_file"),
            )
        else:
            configure_path_label(
                self.pnp_path_label, "", empty_text=self.ui_tr("project.no_file")
            )
        if self._pnp_secondary_path:
            configure_path_label(
                self.pnp_path2_label,
                self._pnp_secondary_path,
                empty_text=self.ui_tr("project.no_file"),
            )
        else:
            configure_path_label(
                self.pnp_path2_label, "", empty_text=self.ui_tr("project.no_file")
            )
        if hasattr(self, "btn_browse_pnp2"):
            self.btn_browse_pnp2.setText(self.ui_tr("project.browse_pnp2"))
        if hasattr(self, "btn_clear_pnp_optional"):
            self.btn_clear_pnp_optional.setText(
                self.ui_tr("project.pnp_clear_optional")
            )
        if hasattr(self, "chk_pnp_layer_override"):
            self.chk_pnp_layer_override.setText(
                self.ui_tr("project.pnp_layer_override")
            )
            self.chk_pnp_layer_override.setToolTip(
                self.ui_tr("project.pnp_layer_override_tip")
            )
            self.edit_pnp_layer_tokens.setPlaceholderText(
                self.ui_tr("project.pnp_layer_tokens_placeholder")
            )
            self.edit_pnp_layer_tokens.setToolTip(
                self.ui_tr("project.pnp_layer_override_tip")
            )
        if hasattr(self, "lbl_pnp_topbot_help"):
            self.lbl_pnp_topbot_help.setText(self.ui_tr("project.pnp_topbot_help"))
        if hasattr(self, "btn_bom_undo"):
            self.btn_bom_undo.setText(self.ui_tr("bom.undo"))
            self.btn_bom_redo.setText(self.ui_tr("bom.redo"))
        if hasattr(self, "gb_bom_file"):
            self.gb_bom_file.setTitle(self.ui_tr("bom.group_file"))
            self.gb_bom_edit.setTitle(self.ui_tr("bom.group_edit"))
            self.gb_bom_workspace.setTitle(self.ui_tr("bom.group_workspace"))
            self.btn_reload_bom.setText(self.ui_tr("bom.reload"))
            self.btn_bom_find.setText(self.ui_tr("bom.find_replace"))
            self.btn_clear_bom.setText(self.ui_tr("bom.clear_workspace"))
        if hasattr(self, "gb_pnp_file"):
            self.gb_pnp_file.setTitle(self.ui_tr("pnp.group_file"))
            self.gb_pnp_coords.setTitle(self.ui_tr("pnp.group_coords"))
            self.gb_pnp_edit.setTitle(self.ui_tr("pnp.group_edit"))
            self.gb_pnp_workspace.setTitle(self.ui_tr("pnp.group_workspace"))
            self.btn_reload_pnp.setText(self.ui_tr("pnp.reload"))
            self.btn_pnp_find.setText(self.ui_tr("pnp.find_replace"))
            self.btn_clear_pnp.setText(self.ui_tr("pnp.clear_workspace"))
            self.btn_pnp_help.setToolTip(self.ui_tr("pnp.help_title"))
        if hasattr(self, "btn_bom_pn_join_help"):
            self.btn_bom_pn_join_help.setToolTip(
                self.ui_tr("mapping.pn_join_help_title")
            )
        if hasattr(self, "btn_find_package"):
            self.btn_find_package.setText(self.ui_tr("package.find"))
            self.btn_find_package.setToolTip(self.ui_tr("package.find_tip"))
        if hasattr(self, "btn_apply_package_table"):
            self.btn_apply_package_table.setText(self.ui_tr("package.apply_table"))
            self.btn_apply_package_table.setToolTip(
                self.ui_tr("package.apply_table_tip")
            )
        if hasattr(self, "btn_pnp_undo"):
            self.btn_pnp_undo.setText(self.ui_tr("pnp.undo"))
            self.btn_pnp_redo.setText(self.ui_tr("pnp.redo"))
        if hasattr(self, "btn_project_debug"):
            self.btn_project_debug.setText(self.ui_tr("project.advanced"))
            self.btn_project_save_pack.setText(self.ui_tr("project.save_session"))
            self.btn_project_load_pack.setText(self.ui_tr("project.load_session"))

    def _on_ui_language_changed(self) -> None:
        if getattr(self, "_restoring_settings", False):
            return
        lang = self.lang_combo.currentData()
        if not lang:
            return
        lang_s = str(lang)
        if lang_s not in SUPPORTED_UI_LOCALES:
            return
        self._apply_ui_language(lang_s, save=True)

    def _apply_ui_language(self, lang: str, *, save: bool = True) -> None:
        if lang not in SUPPORTED_UI_LOCALES:
            lang = "en"
        self._i18n.set_locale(lang)
        if save:
            self._settings.setValue("ui/language", lang)
        self.lang_combo.blockSignals(True)
        idx = self.lang_combo.findData(lang)
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)
        self.lang_combo.blockSignals(False)
        self._refresh_static_ui_texts()

    def _register_main_tab(self, key: str, widget: QtWidgets.QWidget) -> None:
        """Append a main-window tab and record its logical key (i18n titles, ``_tab_index``)."""
        self.tabs.addTab(widget, self.ui_tr(f"tab.{key}"))
        self._tab_keys_in_order.append(key)

    def _create_project_tab(self):
        """Project tab — file selection, settings (profile, language), console."""
        tab = QtWidgets.QWidget()
        self._register_main_tab("project", tab)

        layout = QtWidgets.QVBoxLayout(tab)
        setup_project_tab(self, layout)

    def _create_pcb_preview_tab(self) -> None:
        from pcb_preview_tab import PcbPreviewTab

        self._pcb_tab = PcbPreviewTab(self, settings=self._settings)
        self._pcb_tab.pnp_xy_unit_mm_selected.connect(self._on_user_pnp_xy_unit_choice)
        self._pcb_tab.sync_pnp_xy_units_ui(mm=self._pnp_xy_stored_in_mm())
        self._register_main_tab("pcb_preview", self._pcb_tab)

    def _create_step_3d_tab(self) -> None:
        from step_3d import Step3DTabWidget

        self._step_3d_tab = Step3DTabWidget(
            self, settings=self._settings, ui_tr=self.ui_tr
        )
        self._register_main_tab("step_3d", self._step_3d_tab)

    def _create_package_tab(self) -> None:
        from ui.package_tab import PackageTab

        self._package_tab = PackageTab(self, settings=self._settings)
        self._register_main_tab("package", self._package_tab)

    def _create_machine_library_tab(self) -> None:
        self._machine_library_tab = MachineLibraryTab(self, settings=self._settings)
        self._register_main_tab("machine_lib", self._machine_library_tab)

    def _on_main_tab_changed(self, idx: int) -> None:
        if (
            not getattr(self, "_restoring_settings", False)
            and hasattr(self, "_settings")
            and hasattr(self, "tabs")
        ):
            self._settings.setValue("ui/main_tab_index", idx)
        self._refresh_shell_status()
        if (
            0 <= idx < len(self._tab_keys_in_order)
            and self._tab_keys_in_order[idx] == "pcb_preview"
        ):
            self._refresh_pcb_preview_from_ui(force=False)

    def _pcb_preview_bridge_kwargs(self) -> Optional[dict]:
        self._sync_pnp_df_from_model()
        if (
            self._pnp_df is None
            or not hasattr(self, "pnp_col_combos")
            or not self.pnp_col_combos
        ):
            return None
        cols = list(self._pnp_df.columns)
        m: dict[str, object] = {}
        for i, combo in enumerate(self.pnp_col_combos):
            label = combo.currentText()
            if label != "-":
                m[label] = cols[i]
        ref = m.get("REF")
        xc = m.get("X")
        yc = m.get("Y")
        if not ref or not xc or not yc:
            return None
        return {
            "designator_col": ref,
            "x_col": xc,
            "y_col": yc,
            "rot_col": m.get("Rotation"),
            "layer_col": m.get("Layer"),
            "footprint_col": m.get("Footprint"),
            "value_col": m.get("Value"),
            "comment_col": m.get("Comment"),
            "coord_unit_mm": self._pnp_xy_stored_in_mm(),
        }

    def _refresh_pcb_preview_from_ui(self, *, force: bool = True) -> None:
        kwargs = self._pcb_preview_bridge_kwargs()
        if kwargs is None:
            return
        if hasattr(self, "_pcb_tab"):
            self._pcb_tab.set_placements_from_dataframe(
                self._pnp_df, force=force, **kwargs
            )

    def _create_menus(self) -> None:
        # File menu removed — same actions live as buttons on the Project tab (right of Settings).
        self.setMenuBar(None)

    def _menu_save_boomerpack(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            self.ui_tr("project.save_session"),
            str(Path.home() / "session.valvetpack"),
            SAVE_FILTER,
        )
        if path:
            if not path.lower().endswith(VALVETPACK_EXT):
                path += VALVETPACK_EXT
            self._debug_save_boomerpack(path)

    def _menu_load_boomerpack(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            self.ui_tr("project.load_session"),
            str(Path.home()),
            OPEN_FILTER,
        )
        if path:
            self._debug_load_boomerpack(path)

    def _open_debug_settings(self) -> None:
        from shiboken6 import isValid

        dlg = getattr(self, "_debug_settings_dialog", None)
        if dlg is not None and isValid(dlg):
            dlg.show()
            dlg.raise_()
            dlg.activateWindow()
            return
        dlg = DebugSettingsDialog(self, self)
        self._debug_settings_dialog = dlg
        dlg.destroyed.connect(lambda *_: setattr(self, "_debug_settings_dialog", None))
        dlg.show()

    def _install_edit_shortcuts(self) -> None:
        u = QtGui.QShortcut(QtGui.QKeySequence.StandardKey.Undo, self)
        u.setContext(QtCore.Qt.ShortcutContext.ApplicationShortcut)
        u.activated.connect(self._shortcut_undo)
        r = QtGui.QShortcut(QtGui.QKeySequence.StandardKey.Redo, self)
        r.setContext(QtCore.Qt.ShortcutContext.ApplicationShortcut)
        r.activated.connect(self._shortcut_redo)

    def _tab_index(self, key: str) -> int:
        try:
            return self._tab_keys_in_order.index(key)
        except ValueError:
            return -1

    def _shortcut_undo(self) -> None:
        i = self.tabs.currentIndex()
        if i == self._tab_index("bom"):
            self._bom_undo_stack.undo()
        elif i == self._tab_index("pnp"):
            self._pnp_undo_stack.undo()

    def _shortcut_redo(self) -> None:
        i = self.tabs.currentIndex()
        if i == self._tab_index("bom"):
            self._bom_undo_stack.redo()
        elif i == self._tab_index("pnp"):
            self._pnp_undo_stack.redo()

    def _on_table_audit_log(self, payload: dict[str, Any]) -> None:
        ev = payload.get("event", "")
        tbl = payload.get("table", "")
        r = payload.get("row", "")
        c = payload.get("col", "")
        coln = payload.get("column", "")
        self._log(f"Table audit [{tbl}] {ev} row={r} col={c} ({coln})", "debug")

    def _on_colorful_logs_toggled(self, *_args) -> None:
        if self._restoring_settings or not hasattr(self, "_settings"):
            return
        self._settings.setValue("ui/colorful_logs", self.chk_colorful.isChecked())
        self._sync_file_debug_logger()

    def _sync_file_debug_logger(self) -> None:
        """Project 'Debug logs' checkbox is the same switch as ``--debug``."""
        if not hasattr(self, "chk_colorful"):
            return
        logger.set_debug_mode(self.chk_colorful.isChecked())

    def _load_settings(self) -> None:
        self._restoring_settings = True
        s = self._settings
        try:
            self._load_profile_combo_from_storage()
            pid = self._current_profile_id()
            blob = str(s.value(f"profiles/{pid}/state_json", "") or "").strip()
            loaded = False
            if blob:
                try:
                    self._apply_profile_payload(json.loads(blob))
                    loaded = True
                except (json.JSONDecodeError, TypeError, ValueError) as e:
                    logger.warning(
                        "Profile state invalid (%s); using legacy flat keys", e
                    )
            if not loaded:
                self._load_legacy_settings_flat(s)
        finally:
            self._restoring_settings = False
        self._restore_main_tab_from_settings()
        self._refresh_application_stylesheet()

    def _restore_main_tab_from_settings(self) -> None:
        """Restore tab index after tabs and settings exist."""
        if not hasattr(self, "tabs") or self.tabs.count() <= 0:
            return
        s = self._settings
        idx = int(s.value("ui/main_tab_index", 0) or 0)
        idx = max(0, min(idx, self.tabs.count() - 1))
        self.tabs.blockSignals(True)
        self.tabs.setCurrentIndex(idx)
        self.tabs.blockSignals(False)
        self._on_main_tab_changed(idx)

    def _save_window_layout_settings(self) -> None:
        """Persist window geometry and active tab (global layout, not profile JSON)."""
        if not hasattr(self, "_settings"):
            return
        self._settings.setValue("ui/main_window_geometry", self.saveGeometry())
        if hasattr(self, "tabs"):
            self._settings.setValue("ui/main_tab_index", self.tabs.currentIndex())

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        super().showEvent(event)
        if getattr(self, "_session_geometry_restored", False):
            return
        self._session_geometry_restored = True
        raw = self._settings.value("ui/main_window_geometry")
        if raw is None:
            return
        ba = (
            raw if isinstance(raw, QtCore.QByteArray) else QtCore.QByteArray(bytes(raw))
        )
        if ba.isEmpty():
            return
        self.restoreGeometry(ba)
        self._clamp_window_to_screen()

    def _clamp_window_to_screen(self) -> None:
        screen = self.screen()
        if screen is None:
            screen = QtWidgets.QApplication.primaryScreen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        geo = self.geometry()
        w = min(max(geo.width(), self.minimumWidth()), avail.width())
        h = min(max(geo.height(), self.minimumHeight()), avail.height())
        x = max(avail.left(), min(geo.x(), avail.right() - w + 1))
        y = max(avail.top(), min(geo.y(), avail.bottom() - h + 1))
        self.setGeometry(x, y, w, h)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Persist active profile snapshot (widgets only; no BOM/PnP file paths)."""
        try:
            self._save_window_layout_settings()
            if hasattr(self, "_save_full_profile_snapshot"):
                self._save_full_profile_snapshot()
            if hasattr(self, "_settings"):
                self._settings.sync()
        finally:
            super().closeEvent(event)

    # =========================================================================
    # Logging
    # =========================================================================

    def _log(self, message: str, level: str = "info"):
        self.log_message.emit(message, level)

    def _on_log_message(self, message: str, level: str):
        color = {
            "error": "#ff6b6b",
            "warning": "#ffa94d",
            "info": "#d8dee9",
            "debug": "#9aa7b5",
        }.get(level, "#d8dee9")

        if level == "debug":
            if not getattr(self, "chk_colorful", None) or not self.chk_colorful.isChecked():
                return

        self.console.append(f'<span style="color:{color}">{message}</span>')
