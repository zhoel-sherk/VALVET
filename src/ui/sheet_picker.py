"""Worksheet picker combo shared by the BOM and PnP tabs (MainWindow mixin).

Excel workbooks often carry auxiliary sheets that are hidden (ECN logs,
production notes) or sit after the real data sheet. The reader picks the first
*visible* sheet; this mixin exposes that choice to the user and persists it
alongside the separator setting.
"""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtWidgets

from smt_processor import default_sheet_name, list_sheets

# Sentinel combo entry meaning "let the reader decide" (first visible sheet).
# Persisted instead of a sheet name so the default follows later edits.
SHEET_AUTO = "(auto)"

_SPREADSHEET_SUFFIXES = (".xlsx", ".xls", ".ods", ".xlsm")


def is_spreadsheet_path(path: str) -> bool:
    return Path(path).suffix.lower() in _SPREADSHEET_SUFFIXES


class SheetPickerMixin:
    """Adds a sheet combo + row-count hint to a tab's File group.

    The host owns ``self.{prefix}_sheet`` (combo) and ``self.{prefix}_sheet_rows``
    (hint label); ``self._log(msg, level)`` is used for console warnings.
    """

    def _create_sheet_picker(
        self,
        prefix: str,
        *,
        tr_key: str,
    ) -> QtWidgets.QHBoxLayout:
        """Build a 'Sheet:' label + combo row (populated later, per file)."""
        row = QtWidgets.QHBoxLayout()
        label = QtWidgets.QLabel(self.ui_tr(tr_key))
        setattr(self, f"lbl_{prefix}_sheet", label)
        row.addWidget(label)
        combo = QtWidgets.QComboBox()
        combo.setMinimumWidth(70)
        combo.setToolTip(self.ui_tr(f"{prefix}.sheet_tip"))
        combo.addItem(SHEET_AUTO)
        combo.setEnabled(False)
        row.addWidget(combo, 1)
        setattr(self, f"{prefix}_sheet", combo)
        hint = QtWidgets.QLabel("")
        hint.setObjectName(f"{prefix}SheetRowsHint")
        # Sheet names can be long; the full name is also on the tooltip.
        hint.setWordWrap(False)
        setattr(self, f"{prefix}_sheet_rows", hint)
        combo.currentTextChanged.connect(lambda *_: self._on_sheet_changed(prefix))
        return row

    def _on_sheet_changed(self, prefix: str) -> None:
        """Reload the tab when the user picks a different sheet.

        Persist the choice first so a reload that restores per-file settings sees
        the new sheet and does not snap back to the old one.
        """
        if getattr(self, "_sheets_updating", False):
            return
        path = getattr(self, f"_{prefix}_source_path", "") or ""
        combo: QtWidgets.QComboBox = getattr(self, f"{prefix}_sheet")
        if not path or not combo.isEnabled():
            return
        if prefix == "bom":
            self._schedule_save_bom_tab_settings()
            self._reload_bom()
        else:
            self._schedule_save_pnp_tab_settings()
            self._reload_pnp()

    def _populate_sheet_combo(
        self,
        prefix: str,
        path: str,
        saved_sheet: str | None = None,
    ) -> None:
        """Fill the combo for ``path``, honouring ``saved_sheet`` when still valid.

        A saved sheet that vanished (the file was replaced) warns and falls back
        to auto instead of failing the load.
        """
        if saved_sheet is None:
            saved_sheet = getattr(self, f"_{prefix}_saved_sheet", None)
        combo: QtWidgets.QComboBox = getattr(self, f"{prefix}_sheet")
        # A live selection wins over the stored setting: changing the sheet
        # reloads the tab, which repopulates this combo from scratch. Without this
        # the reload would snap back to the stored/default sheet. It only applies
        # to the same file, so another workbook starts from its own default.
        prev_path = getattr(self, "_sheet_paths", {}).get(prefix)
        if prev_path == path:
            current = combo.currentData()
            if current and combo.currentText() != SHEET_AUTO:
                saved_sheet = str(current)
        self._sheets_updating = True
        try:
            combo.blockSignals(True)
            combo.clear()
            sheets = list_sheets(path) if path and is_spreadsheet_path(path) else []
            if not sheets:
                combo.addItem(SHEET_AUTO)
                combo.setEnabled(False)
                getattr(self, "_sheet_paths", {}).pop(prefix, None)
                self._set_sheet_hint(prefix, "", None)
                return
            combo.setEnabled(True)
            combo.addItem(SHEET_AUTO)
            for sheet in sheets:
                combo.addItem(sheet.label, sheet.name)
            default = default_sheet_name(sheets)
            names = {s.name for s in sheets}
            target = default
            if saved_sheet and saved_sheet in names:
                target = saved_sheet
            elif saved_sheet:
                self._log(
                    f"{prefix.upper()} sheet '{saved_sheet}' is no longer in "
                    f"{Path(path).name}; using '{target}' instead.",
                    "warning",
                )
            idx = self._combo_index_for_sheet(combo, target)
            combo.setCurrentIndex(idx if idx >= 0 else 0)
            if not hasattr(self, "_sheet_paths"):
                self._sheet_paths = {}
            self._sheet_paths[prefix] = path
        finally:
            combo.blockSignals(False)
            self._sheets_updating = False

    @staticmethod
    def _combo_index_for_sheet(
        combo: QtWidgets.QComboBox, sheet_name: str | None
    ) -> int:
        """Index of the entry whose stored data equals ``sheet_name``.

        Matching on userData, not text: hidden sheets display as 'Name (hidden)'.
        """
        if not sheet_name:
            return 0
        for i in range(combo.count()):
            if combo.itemData(i) == sheet_name:
                return i
        return -1

    def _selected_sheet(self, prefix: str) -> str | None:
        """Current sheet name to pass to ``read_file``; None means auto."""
        combo: QtWidgets.QComboBox = getattr(self, f"{prefix}_sheet")
        if not combo.isEnabled() or combo.currentText() == SHEET_AUTO:
            return None
        data = combo.currentData()
        return str(data) if data else None

    def _set_sheet_hint(self, prefix: str, sheet_name: str, rows: int | None) -> None:
        """Show the chosen sheet name and its row count under the combo."""
        hint: QtWidgets.QLabel = getattr(self, f"{prefix}_sheet_rows")
        if not sheet_name:
            hint.setText("")
            hint.setToolTip("")
            return
        if rows is None:
            hint.setText(sheet_name)
        else:
            hint.setText(
                self.ui_tr(f"{prefix}.sheet_rows", sheet=sheet_name, rows=rows)
            )
        hint.setToolTip(sheet_name)

    def _clear_sheet_picker(self, prefix: str) -> None:
        """Reset to auto when the tab workspace is cleared."""
        combo: QtWidgets.QComboBox = getattr(self, f"{prefix}_sheet")
        self._sheets_updating = True
        try:
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(SHEET_AUTO)
            combo.setEnabled(False)
        finally:
            combo.blockSignals(False)
            self._sheets_updating = False
        self._set_sheet_hint(prefix, "", None)
