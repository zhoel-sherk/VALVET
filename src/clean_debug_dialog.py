"""Clean BOM debug dialog: parser pipeline order and component library path."""

from __future__ import annotations

import json
import os
from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import QSettings

from clean_pipeline_settings import load_clean_debug_extras, load_pipeline_from_settings
from clean_types import DEFAULT_CLEAN_PIPELINE, canonical_pipeline_order
from parsers.registry import ensure_discovered, loaded_parser_catalog_text

__all__ = [
    "CleanPipelineDebugDialog",
    "load_clean_debug_extras",
    "load_pipeline_from_settings",
]


def _read_bool_setting(settings: QSettings, key: str, default: bool = False) -> bool:
    v = settings.value(key, default)
    if isinstance(v, bool):
        return v
    sl = str(v).strip().lower()
    if sl in ("true", "1", "yes", "on"):
        return True
    if sl in ("false", "0", "no", "off", ""):
        return False
    return default


STEP_LABELS = {
    "inferit": "INFERIT / BOM regex presets",
    "vendor": "Vendor MPN decoders (pn_original)",
    "library": "Component library (components.txt)",
    "hanwha": "Machine library PARTNAME match (Hanwha / Yamaha)",
    "regex": "Family regex cleaners (R/C/L)",
}


class CleanPipelineDebugDialog(QtWidgets.QDialog):
    """Reorder pipeline steps, toggle steps off, override components.txt path."""

    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        settings: QSettings,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self.setWindowTitle("Clean BOM — debug settings")
        self.resize(560, 520)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(
            QtWidgets.QLabel(
                "Pipeline runs top → bottom. Disabled steps are skipped. "
                "If «Vendor» is above «Regex», a successful MPN decode prevents resistor/cap regex."
            )
        )
        hint_lib = QtWidgets.QLabel(
            "Recommended: keep «Component library» above «Machine library PARTNAME (Hanwha)» "
            "when both are enabled. Machine libraries are hand-maintained; substring matches "
            "can false-trigger on short PARTNAME tokens (e.g. R0603 inside a long comment). "
            "Putting Hanwha above library should be a deliberate exception."
        )
        hint_lib.setWordWrap(True)
        layout.addWidget(hint_lib)

        ensure_discovered()
        catalog = QtWidgets.QPlainTextEdit()
        catalog.setReadOnly(True)
        catalog.setPlaceholderText("Loaded parser modules…")
        catalog.setPlainText(loaded_parser_catalog_text())
        catalog.setMinimumHeight(140)
        catalog.setToolTip(
            "Built-in parsers ship under src/parsers/. User scripts: set VALVET_USER_PARSERS_DIR "
            "or use the per-user folder from app_paths.user_parsers_dir() (see doc/info/PACKAGING_WINDOWS.md); "
            "restart the app after changes."
        )
        layout.addWidget(QtWidgets.QLabel("Loaded BOM parsers (GUI / CLI names):"))
        layout.addWidget(catalog)

        self._list = QtWidgets.QListWidget()
        self._list.setDragDropMode(
            QtWidgets.QAbstractItemView.DragDropMode.InternalMove
        )
        self._list.setDefaultDropAction(QtCore.Qt.DropAction.MoveAction)
        layout.addWidget(self._list, 1)

        order, disabled = self._load_pipeline()
        for sid in order:
            item = QtWidgets.QListWidgetItem(STEP_LABELS.get(sid, sid))
            item.setData(QtCore.Qt.ItemDataRole.UserRole, sid)
            item.setFlags(
                item.flags()
                | QtCore.Qt.ItemFlag.ItemIsUserCheckable
                | QtCore.Qt.ItemFlag.ItemIsDragEnabled
                | QtCore.Qt.ItemFlag.ItemIsDropEnabled
            )
            item.setCheckState(
                QtCore.Qt.CheckState.Unchecked
                if sid in disabled
                else QtCore.Qt.CheckState.Checked
            )
            self._list.addItem(item)

        rx_box = QtWidgets.QGroupBox("Regex master (experimental)")
        rx_lay = QtWidgets.QVBoxLayout(rx_box)
        self._cb_regex_master = QtWidgets.QCheckBox(
            "Enable parser arbiter (INFERIT / vendor PN / token-regex compete by slot score)"
        )
        self._cb_regex_master.setToolTip(
            "When on, Clean BOM picks among inferit, pn_original, and family regex using "
            "filled template slots (cap 90%% for regex-class paths). Library and Hanwha steps "
            "still win immediately when they match."
        )
        self._cb_preview_scores = QtWidgets.QCheckBox(
            "Show arbiter detail + Win%% in Clean preview; tint Cleaned cells by score"
        )
        self._cb_preview_scores.setToolTip(
            "Requires parser arbiter enabled. Adds Arbiter and Win%% columns and soft row tint."
        )
        rm_init = _read_bool_setting(
            self._settings, "clean/regex_master_enabled", False
        )
        pv_init = _read_bool_setting(
            self._settings, "clean/regex_master_preview_scores", False
        )
        self._cb_regex_master.setChecked(rm_init)
        self._cb_preview_scores.setChecked(pv_init and rm_init)
        self._cb_regex_master.toggled.connect(self._on_regex_master_toggled)
        self._on_regex_master_toggled(rm_init)
        rx_lay.addWidget(self._cb_regex_master)
        rx_lay.addWidget(self._cb_preview_scores)
        layout.addWidget(rx_box)

        lib_row = QtWidgets.QHBoxLayout()
        lib_row.addWidget(QtWidgets.QLabel("components.txt override:"))
        self._path_edit = QtWidgets.QLineEdit()
        raw_p = str(settings.value("clean/components_txt_path", "") or "")
        self._path_edit.setPlaceholderText(
            "(empty — use BOOMER_COMPONENTS_TXT or repo components.txt)"
        )
        self._path_edit.setText(raw_p)
        lib_row.addWidget(self._path_edit, 1)
        btn_browse = QtWidgets.QPushButton("Browse…")
        btn_browse.clicked.connect(self._browse_components_txt)
        lib_row.addWidget(btn_browse)
        layout.addLayout(lib_row)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
            | QtWidgets.QDialogButtonBox.StandardButton.RestoreDefaults
        )
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        btns.button(
            QtWidgets.QDialogButtonBox.StandardButton.RestoreDefaults
        ).clicked.connect(self._restore_defaults)
        layout.addWidget(btns)

    def _on_regex_master_toggled(self, on: bool) -> None:
        self._cb_preview_scores.setEnabled(on)
        if not on:
            self._cb_preview_scores.setChecked(False)

    def _browse_components_txt(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Component library text file",
            self._path_edit.text() or os.path.expanduser("~"),
            "Text (*.txt);;All (*.*)",
        )
        if path:
            self._path_edit.setText(path)

    def _load_pipeline(self) -> tuple[list[str], set[str]]:
        raw_o = str(self._settings.value("clean/pipeline_order", "") or "").strip()
        raw_d = str(self._settings.value("clean/pipeline_disabled", "") or "").strip()
        order: list[str] = []
        if raw_o:
            try:
                parsed = json.loads(raw_o)
                if isinstance(parsed, list):
                    order = canonical_pipeline_order([str(x) for x in parsed])
            except (json.JSONDecodeError, TypeError):
                order = list(DEFAULT_CLEAN_PIPELINE)
        if not order:
            order = list(DEFAULT_CLEAN_PIPELINE)
        disabled: set[str] = set()
        if raw_d:
            try:
                parsed = json.loads(raw_d)
                if isinstance(parsed, list):
                    disabled = {str(x).strip().lower() for x in parsed}
            except (json.JSONDecodeError, TypeError):
                pass
        return order, disabled

    def _restore_defaults(self) -> None:
        self._path_edit.clear()
        self._list.clear()
        for sid in DEFAULT_CLEAN_PIPELINE:
            item = QtWidgets.QListWidgetItem(STEP_LABELS.get(sid, sid))
            item.setData(QtCore.Qt.ItemDataRole.UserRole, sid)
            item.setFlags(
                item.flags()
                | QtCore.Qt.ItemFlag.ItemIsUserCheckable
                | QtCore.Qt.ItemFlag.ItemIsDragEnabled
                | QtCore.Qt.ItemFlag.ItemIsDropEnabled
            )
            item.setCheckState(QtCore.Qt.CheckState.Checked)
            self._list.addItem(item)
        self._cb_regex_master.setChecked(False)
        self._cb_preview_scores.setChecked(False)
        self._on_regex_master_toggled(False)

    def _on_accept(self) -> None:
        order: list[str] = []
        disabled: list[str] = []
        for i in range(self._list.count()):
            it = self._list.item(i)
            sid = str(it.data(QtCore.Qt.ItemDataRole.UserRole) or "").strip().lower()
            if sid:
                order.append(sid)
            if it.checkState() != QtCore.Qt.CheckState.Checked and sid:
                disabled.append(sid)
        order = list(canonical_pipeline_order(order))
        self._settings.setValue("clean/pipeline_order", json.dumps(order))
        self._settings.setValue("clean/pipeline_disabled", json.dumps(disabled))
        p = self._path_edit.text().strip()
        if p:
            self._settings.setValue("clean/components_txt_path", p)
        else:
            self._settings.remove("clean/components_txt_path")
        self._settings.setValue(
            "clean/regex_master_enabled",
            bool(self._cb_regex_master.isChecked()),
        )
        self._settings.setValue(
            "clean/regex_master_preview_scores",
            bool(self._cb_preview_scores.isChecked()),
        )
        self.accept()
