"""Hidden Scan tab: the reel barcode → component → T-OLP feeder position."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Optional

from PySide6 import QtCore, QtWidgets

from parsers.tolp_export import TolpExport, TolpExportError, load_tolp_export
from services.scan_match import (
    STATE_OK,
    STATE_PART_MISSING,
    STATE_UNKNOWN_CODE,
    ScanResult,
    build_code_index,
    normalize_code,
    resolve_scan,
)
from ui.chrome import action_button, switch_checkbox

_FONT_MIN = 25
_FONT_MAX = 72
_FONT_DEFAULT = 48
_HISTORY_MAX = 20
_CUSTOM_PREFIX = "Custom "


def _custom_sort_key(name: str) -> tuple[int, str]:
    suffix = name[len(_CUSTOM_PREFIX) :]
    return (int(suffix) if suffix.isdigit() else 999, name)


class ScanTab(QtWidgets.QWidget):
    """Operator screen opened from Merge; not present in the tab bar."""

    def __init__(
        self,
        host: QtWidgets.QWidget,
        *,
        settings: Optional[QtCore.QSettings] = None,
    ) -> None:
        super().__init__(host)
        self._host = host
        self._settings = settings
        self._export: Optional[TolpExport] = None
        self._index: dict[str, tuple] = {}
        self._export_dir = ""
        self._places_error = False

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 10)
        root.setSpacing(8)

        source_row = QtWidgets.QHBoxLayout()
        source_row.setSpacing(6)
        self.folder_label = QtWidgets.QLabel(self._tr("scan.folder"))
        source_row.addWidget(self.folder_label)
        self.folder_edit = QtWidgets.QLineEdit()
        self.folder_edit.setReadOnly(True)
        self.folder_edit.setPlaceholderText("C:\\PCB")
        source_row.addWidget(self.folder_edit, 1)
        self.btn_browse = action_button(self._tr("scan.browse"))
        self.btn_browse.clicked.connect(self._browse_folder)
        source_row.addWidget(self.btn_browse)
        self.btn_reload = action_button(self._tr("scan.reload"))
        self.btn_reload.clicked.connect(self._reload_export)
        source_row.addWidget(self.btn_reload)
        root.addLayout(source_row)

        options = QtWidgets.QHBoxLayout()
        options.setSpacing(8)
        self.custom_label = QtWidgets.QLabel(self._tr("scan.custom"))
        options.addWidget(self.custom_label)
        self.custom_combo = QtWidgets.QComboBox()
        self.custom_combo.setMinimumWidth(150)
        self.custom_combo.currentIndexChanged.connect(self._on_custom_changed)
        options.addWidget(self.custom_combo)
        options.addSpacing(12)
        self.font_label = QtWidgets.QLabel(self._tr("scan.font"))
        options.addWidget(self.font_label)
        self.font_spin = QtWidgets.QSpinBox()
        self.font_spin.setRange(_FONT_MIN, _FONT_MAX)
        self.font_spin.setValue(_FONT_DEFAULT)
        self.font_spin.setSuffix(" px")
        self.font_spin.valueChanged.connect(self._on_font_changed)
        options.addWidget(self.font_spin)
        self.swap_check = switch_checkbox(self._tr("scan.swap"))
        self.swap_check.toggled.connect(self._on_swap_changed)
        options.addWidget(self.swap_check)
        options.addStretch(1)
        self.source_status = QtWidgets.QLabel("")
        options.addWidget(self.source_status)
        root.addLayout(options)

        input_row = QtWidgets.QHBoxLayout()
        input_row.setSpacing(6)
        self.scan_edit = QtWidgets.QLineEdit()
        self.scan_edit.setPlaceholderText(self._tr("scan.input"))
        self.scan_edit.setClearButtonEnabled(True)
        self.scan_edit.returnPressed.connect(self._on_scan)
        font = self.scan_edit.font()
        font.setPixelSize(24)
        self.scan_edit.setFont(font)
        input_row.addWidget(self.scan_edit, 1)
        self.btn_show = action_button(self._tr("scan.show"))
        self.btn_show.clicked.connect(self._on_scan)
        input_row.addWidget(self.btn_show)
        root.addLayout(input_row)

        body = QtWidgets.QHBoxLayout()
        body.setSpacing(12)
        display = QtWidgets.QFrame()
        display.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        display_l = QtWidgets.QVBoxLayout(display)
        display_l.setContentsMargins(12, 12, 12, 12)
        self.code_label = QtWidgets.QLabel("")
        code_font = self.code_label.font()
        code_font.setPixelSize(18)
        self.code_label.setFont(code_font)
        self.code_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        display_l.addWidget(self.code_label)
        self.part_label = QtWidgets.QLabel("")
        part_font = self.part_label.font()
        part_font.setPixelSize(22)
        part_font.setBold(True)
        self.part_label.setFont(part_font)
        self.part_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.part_label.setWordWrap(True)
        display_l.addWidget(self.part_label)
        display_l.addStretch(1)
        self.places_label = QtWidgets.QLabel("")
        self.places_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.places_label.setWordWrap(True)
        self.places_label.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )
        display_l.addWidget(self.places_label)
        self.hint_label = QtWidgets.QLabel("")
        self.hint_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.hint_label.setWordWrap(True)
        display_l.addWidget(self.hint_label)
        display_l.addStretch(1)
        body.addWidget(display, 3)

        history_box = QtWidgets.QGroupBox(self._tr("scan.history"))
        history_l = QtWidgets.QVBoxLayout(history_box)
        self.history_list = QtWidgets.QListWidget()
        self.history_list.setAlternatingRowColors(True)
        history_l.addWidget(self.history_list, 1)
        self.btn_clear_history = action_button(self._tr("scan.clear"))
        self.btn_clear_history.clicked.connect(self.history_list.clear)
        history_l.addWidget(self.btn_clear_history)
        body.addWidget(history_box, 1)
        root.addLayout(body, 1)

        self._restore_settings()
        self._apply_font()

    # ------------------------------------------------------------------ host
    def _host_attr(self, name: str) -> Any:
        return getattr(self._host, name, None)

    def _tr(self, key: str, **kwargs: Any) -> str:
        fn = getattr(self._host, "ui_tr", None)
        if callable(fn):
            try:
                return str(fn(key, **kwargs))
            except Exception:
                pass
        return key

    # -------------------------------------------------------------- settings
    def _restore_settings(self) -> None:
        if self._settings is None:
            self._export_dir = ""
            return
        self._export_dir = str(self._settings.value("scan/export_dir", "") or "")
        self.folder_edit.setText(self._export_dir)
        try:
            self.font_spin.setValue(
                int(self._settings.value("scan/font_px", _FONT_DEFAULT))
            )
        except (TypeError, ValueError):
            self.font_spin.setValue(_FONT_DEFAULT)
        self.swap_check.blockSignals(True)
        self.swap_check.setChecked(
            bool(self._settings.value("scan/swap_sides", False, type=bool))
        )
        self.swap_check.blockSignals(False)

    def _save(self, key: str, value: object) -> None:
        if self._settings is not None:
            self._settings.setValue(key, value)

    # ------------------------------------------------------------------- font
    def _apply_font(self) -> None:
        self._style_places()

    def _style_places(self, error: Optional[bool] = None) -> None:
        """Big text via QSS: ``setFont`` is dropped when the stylesheet is reset."""
        if error is not None:
            self._places_error = error
        px = max(_FONT_MIN, min(_FONT_MAX, int(self.font_spin.value())))
        color = "color: #c62828;" if getattr(self, "_places_error", False) else ""
        self.places_label.setStyleSheet(
            f"font-size: {px}px; font-weight: 700; {color}".strip()
        )

    def _on_font_changed(self, value: int) -> None:
        self._apply_font()
        self._save("scan/font_px", int(value))

    def _on_swap_changed(self, checked: bool) -> None:
        self._save("scan/swap_sides", bool(checked))
        if self._export_dir and self._export is not None:
            self._load_export(self._export_dir, keep_index=True)

    # ----------------------------------------------------------------- export
    def _browse_folder(self) -> None:
        start = self._export_dir or str(Path.home())
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self, self._tr("scan.folder"), start
        )
        if not path:
            return
        self._set_export_dir(path)
        self._load_export(path)

    def _set_export_dir(self, path: str) -> None:
        self._export_dir = path
        self.folder_edit.setText(path)
        self._save("scan/export_dir", path)

    def _reload_export(self) -> None:
        if not self._export_dir:
            self._browse_folder()
            return
        self._load_export(self._export_dir)

    def _load_export(self, path: str, *, keep_index: bool = False) -> None:
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        try:
            export = load_tolp_export(
                path, front_is_one=not self.swap_check.isChecked()
            )
        except TolpExportError as exc:
            self._export = None
            self.export_status_error(str(exc))
            return
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        self._export = export
        self._set_export_dir(str(export.folder))
        self._render_export_status(export)
        if not keep_index:
            self._refresh_sources()
        self.scan_edit.setFocus(QtCore.Qt.FocusReason.OtherFocusReason)

    def _render_export_status(self, export: TolpExport) -> None:
        machines = len(export.machines)
        text = self._tr(
            "scan.export_loaded", feeders=len(export.feeders), machines=machines
        )
        if export.source:
            text += f" · {export.source.upper()}"
        if export.warnings:
            text += f" · {len(export.warnings)} warning(s)"
            self.source_status.setToolTip("\n".join(export.warnings[:10]))
        self.source_status.setStyleSheet("")
        self.source_status.setText(text)

    def export_status_error(self, message: str) -> None:
        self.source_status.setStyleSheet("color: #c62828;")
        self.source_status.setText(message)
        self.source_status.setToolTip(message)

    # ------------------------------------------------------------------ index
    def _merge_df(self):
        sync = self._host_attr("_sync_merge_df_from_model")
        if callable(sync):
            try:
                sync()
            except Exception:
                pass
        return self._host_attr("_last_merge_df")

    def _bom_roles(self) -> tuple[Any, list[tuple[Any, str]]]:
        """``(bom_df, [(column, role)])`` from the BOM tab combos."""
        df = self._host_attr("_bom_df")
        combos = self._host_attr("bom_col_combos") or []
        role_of = self._host_attr("_mapping_combo_role")
        if df is None or getattr(df, "empty", True) or not combos:
            return None, []
        out: list[tuple[Any, str]] = []
        for i, combo in enumerate(combos):
            if i >= len(df.columns):
                break
            role = str(role_of(combo)) if callable(role_of) else "-"
            out.append((df.columns[i], role))
        return df, out

    def _refresh_sources(self) -> None:
        """Build the scanned-code index from Merge, falling back to the BOM."""
        merge_df = self._merge_df()
        if merge_df is not None and not getattr(merge_df, "empty", True):
            columns = [str(c) for c in merge_df.columns]
            custom = sorted(
                (c for c in columns if c.startswith(_CUSTOM_PREFIX)),
                key=_custom_sort_key,
            )
            if "Ref" in columns and "Value" in columns and custom:
                self._set_index(merge_df, custom, ["Value"], "Ref")
                self._fill_custom_combo(custom)
                return

        df, roles = self._bom_roles()
        if df is None:
            self._index = {}
            self.source_status.setText(self._tr("scan.no_source"))
            return
        custom = [col for col, role in roles if role == "Custom"]
        if not custom:
            self._index = {}
            self.source_status.setText(self._tr("scan.no_custom"))
            return
        names = []
        for n, (col, role) in enumerate(roles):
            if role == "Custom":
                names.append(f"{_CUSTOM_PREFIX}{len(names) + 1}")
        part_cols = [col for col, role in roles if role == "Comment"]
        part_cols += [col for col, role in roles if role == "PnJoin"]
        ref_col = next((col for col, role in roles if role == "REF"), None)
        if not part_cols:
            self._index = {}
            self.source_status.setText(self._tr("scan.no_source"))
            return
        key_columns = [str(c) for c in custom]
        self._set_index(df, key_columns, part_cols, ref_col)
        self._fill_custom_combo(key_columns, labels=names)

    def _set_index(
        self,
        df,
        code_columns: Iterable[str],
        part_columns: Iterable[str],
        ref_column: Any,
    ) -> None:
        self._code_columns = list(code_columns)
        self._part_columns = list(part_columns)
        self._ref_column = ref_column
        selected = self._selected_code_column()
        if not selected and self._code_columns:
            selected = self._code_columns[0]
        self._rebuild_index_for(selected)

    def _selected_code_column(self) -> str:
        data = self.custom_combo.currentData()
        return str(data) if data is not None else ""

    def _fill_custom_combo(
        self, columns: list[str], *, labels: Optional[list[str]] = None
    ) -> None:
        current = self._selected_code_column()
        self.custom_combo.blockSignals(True)
        self.custom_combo.clear()
        for i, col in enumerate(columns):
            label = labels[i] if labels and i < len(labels) else col
            self.custom_combo.addItem(label, col)
        idx = self.custom_combo.findData(current) if current else -1
        if idx < 0:
            saved = (
                str(self._settings.value("scan/custom_column", "") or "")
                if self._settings is not None
                else ""
            )
            idx = self.custom_combo.findData(saved)
        self.custom_combo.setCurrentIndex(max(0, idx))
        self.custom_combo.blockSignals(False)
        self._rebuild_index_for(self._selected_code_column())

    def _rebuild_index_for(self, code_column: str) -> None:
        df = self._merge_df()
        if df is None or getattr(df, "empty", True):
            df, _roles = self._bom_roles()
        column = code_column
        if df is None or column not in [str(c) for c in df.columns]:
            self._index = {}
            return
        # The dataframe column labels may not be strings; resolve the real label.
        real = next((c for c in df.columns if str(c) == column), column)
        rows = df.to_dict("records")
        self._index = build_code_index(
            rows,
            real,
            [c for c in self._part_columns if c in df.columns],
            ref_key=self._ref_column if self._ref_column in df.columns else "Ref",
        )

    def _on_custom_changed(self, _idx: int) -> None:
        column = self._selected_code_column()
        if not column:
            return
        self._save("scan/custom_column", column)
        self._rebuild_index_for(column)

    # ------------------------------------------------------------------- scan
    def on_shown(self) -> None:
        """Called by Merge when the button opens this screen."""
        if not self._export_dir:
            saved = ""
            if self._settings is not None:
                saved = str(self._settings.value("scan/export_dir", "") or "")
            self._export_dir = saved
            self.folder_edit.setText(saved)
        if self._export is None and self._export_dir:
            self._load_export(self._export_dir)
        else:
            self._refresh_sources()
        self.focus_scan()

    def focus_scan(self) -> None:
        self.scan_edit.setFocus(QtCore.Qt.FocusReason.OtherFocusReason)
        self.scan_edit.selectAll()

    def _on_scan(self) -> None:
        code = normalize_code(self.scan_edit.text())
        self.scan_edit.clear()
        self.scan_edit.setFocus(QtCore.Qt.FocusReason.OtherFocusReason)
        if not code:
            return
        if not self._index:
            self._render_message(self._tr("scan.no_source"))
            return
        result = resolve_scan(code, self._index, self._export)
        if result.state != STATE_OK and self._export is None:
            self._render_message(self._tr("scan.no_export"))
            return
        self._render_result(result)
        self._push_history(result)

    def _render_result(self, result: ScanResult) -> None:
        self.code_label.setText(result.code)
        parts = []
        for entry in result.entries:
            if entry.part not in parts:
                parts.append(entry.part)
        self.part_label.setText(" / ".join(parts))
        if result.state == STATE_UNKNOWN_CODE:
            self._set_places(self._tr("scan.unknown_code"), error=True)
            self.hint_label.setText("")
            return
        if result.state == STATE_PART_MISSING:
            self._set_places(self._tr("scan.part_missing"), error=True)
            self.hint_label.setText("")
            return
        lines = []
        for feeder in result.feeders:
            if feeder.model:
                lines.append(
                    f"{feeder.machine} · {feeder.model} · {feeder.side} · {feeder.slot}"
                )
            else:
                lines.append(f"{feeder.machine} · {feeder.side} · {feeder.slot}")
        self._set_places("\n".join(lines), error=False)
        refs = ", ".join(r for e in result.entries for r in e.refs)
        self.hint_label.setText(refs)

    def _render_message(self, message: str) -> None:
        self.code_label.setText("")
        self.part_label.setText("")
        self._set_places(message, error=True)
        self.hint_label.setText("")

    def _set_places(self, text: str, *, error: bool) -> None:
        self._style_places(error=error)
        self.places_label.setText(text)

    def _push_history(self, result: ScanResult) -> None:
        if result.state == STATE_OK:
            first = result.feeders[0]
            detail = f"{first.machine} {first.side} {first.slot}"
            if len(result.feeders) > 1:
                detail += f" +{len(result.feeders) - 1}"
            tooltip = "\n".join(
                f"{f.machine} · {f.model} · {f.side} · {f.slot}"
                if f.model
                else f"{f.machine} · {f.side} · {f.slot}"
                for f in result.feeders
            )
        elif result.state == STATE_UNKNOWN_CODE:
            detail = self._tr("scan.unknown_code")
            tooltip = detail
        else:
            detail = self._tr("scan.part_missing")
            tooltip = detail
        item = QtWidgets.QListWidgetItem(f"{result.code} → {detail}")
        item.setToolTip(tooltip)
        self.history_list.insertItem(0, item)
        while self.history_list.count() > _HISTORY_MAX:
            self.history_list.takeItem(self.history_list.count() - 1)
