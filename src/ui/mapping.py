"""Column mapping combo helpers (MainWindow mixin)."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from app.constants import (
    _BOM_MAPPING_ROLES,
    _MAPPING_COMBO_HIGHLIGHT_STYLE,
    _MAPPING_COMBO_MAX_HEIGHT,
    _MAPPING_I18N_KEY,
    _PNP_MAPPING_ROLES,
    _TABLE_COL_MAX_WIDTH,
)
from ui.mapping_header import MappingComboBox, MappingHeaderView


class MappingMixin:
    def _install_mapping_header(self, table: QtWidgets.QTableView) -> MappingHeaderView:
        hh = MappingHeaderView(QtCore.Qt.Orientation.Horizontal, table)
        table.setHorizontalHeader(hh)
        hh.setMinimumSectionSize(48)
        hh.attach_table(table)
        return hh

    def _mapping_header(self, table: QtWidgets.QTableView) -> MappingHeaderView | None:
        hh = table.horizontalHeader()
        return hh if isinstance(hh, MappingHeaderView) else None

    def _style_mapping_combo(self, combo: QtWidgets.QComboBox) -> None:
        combo.setMaximumHeight(_MAPPING_COMBO_MAX_HEIGHT)
        combo.setObjectName("valvetMappingCombo")
        combo.setIconSize(QtCore.QSize(0, 0))

    def _style_clean_template_combo(self, combo: QtWidgets.QComboBox) -> None:
        """Tighter label + popup (qdarkstyle leaves a wide left gutter on small combos)."""
        combo.setObjectName("valvetCleanTemplateCombo")
        combo.setIconSize(QtCore.QSize(0, 0))

    def _relayout_mapping_header(self, table: QtWidgets.QTableView) -> None:
        hh = self._mapping_header(table)
        if hh is not None:
            hh.relayout_combos()

    def _on_bom_section_resized(self, _idx: int, _old: int, _new: int) -> None:
        self._relayout_mapping_header(self.bom_table)

    def _on_pnp_section_resized(self, _idx: int, _old: int, _new: int) -> None:
        self._relayout_mapping_header(self.pnp_table)

    def _autoresize_bom_columns(self) -> None:
        if not hasattr(self, "bom_table") or self.bom_model.columnCount() <= 0:
            return
        for c in range(self.bom_model.columnCount()):
            self.bom_table.resizeColumnToContents(c)
            w = self.bom_table.columnWidth(c)
            self.bom_table.setColumnWidth(c, min(max(w, 48), _TABLE_COL_MAX_WIDTH))
        self._sync_bom_all_combos_width()

    def _autoresize_pnp_columns(self) -> None:
        if not hasattr(self, "pnp_table") or self.pnp_model.columnCount() <= 0:
            return
        for c in range(self.pnp_model.columnCount()):
            self.pnp_table.resizeColumnToContents(c)
            w = self.pnp_table.columnWidth(c)
            self.pnp_table.setColumnWidth(c, min(max(w, 48), _TABLE_COL_MAX_WIDTH))
        self._sync_pnp_all_combos_width()

    def _sync_bom_all_combos_width(self) -> None:
        self._relayout_mapping_header(self.bom_table)

    def _sync_pnp_all_combos_width(self) -> None:
        self._relayout_mapping_header(self.pnp_table)

    def _mapping_role_label(self, role: str) -> str:
        key = _MAPPING_I18N_KEY.get(role, "mapping.none")
        return self.ui_tr(key)

    def _mapping_column_tooltip(self, index: int) -> str:
        return self.ui_tr("mapping.column_tooltip", n=index)

    def _populate_mapping_combo(
        self, combo: QtWidgets.QComboBox, roles: tuple[str, ...]
    ) -> None:
        combo.clear()
        for role in roles:
            combo.addItem(self._mapping_role_label(role), role)

    def _mapping_combo_role(self, combo: QtWidgets.QComboBox) -> str:
        data = combo.currentData()
        if data is not None:
            return str(data)
        text = combo.currentText()
        for role in _PNP_MAPPING_ROLES:
            if text == role or text == self._mapping_role_label(role):
                return role
        return "-"

    def _set_mapping_combo_role(
        self, combo: QtWidgets.QComboBox, role: str
    ) -> None:
        idx = combo.findData(role)
        if idx < 0 and role in _PNP_MAPPING_ROLES:
            idx = combo.findText(self._mapping_role_label(role))
        if idx < 0:
            idx = combo.findData("-")
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _mapping_roles_from_combos(
        self, combos: list[QtWidgets.QComboBox]
    ) -> list[str]:
        return [self._mapping_combo_role(c) for c in combos]

    def _restore_mapping_roles_to_combos(
        self, combos: list[QtWidgets.QComboBox], roles: list[str]
    ) -> None:
        for i, role in enumerate(roles):
            if i < len(combos):
                self._set_mapping_combo_role(combos[i], role)

    def _highlight_mapping_combo(self, kind: str, section: int) -> None:
        combos = (
            self.bom_col_combos
            if kind == "bom"
            else self.pnp_col_combos
            if kind == "pnp"
            else []
        )
        if not combos or section < 0 or section >= len(combos):
            return
        attr = "_bom_mapping_highlight" if kind == "bom" else "_pnp_mapping_highlight"
        setattr(self, attr, section)
        for i, combo in enumerate(combos):
            if i == section:
                combo.setStyleSheet(_MAPPING_COMBO_HIGHLIGHT_STYLE)
            else:
                combo.setStyleSheet("")

    def _make_mapping_combo(
        self, index: int, roles: tuple[str, ...]
    ) -> MappingComboBox:
        combo = MappingComboBox()
        self._populate_mapping_combo(combo, roles)
        self._style_mapping_combo(combo)
        combo.setToolTip(self._mapping_column_tooltip(index))
        return combo

    def _fill_bom_combos(self, *, preserved_roles: list[str] | None = None):
        """Create per-column role dropdowns in the BOM header."""
        if self._bom_df is None:
            return
        hh = self._mapping_header(self.bom_table)
        if hh is None:
            return

        cols = list(self._bom_df.columns)
        combos: list[QtWidgets.QComboBox] = []

        for i, col_name in enumerate(cols):
            combo = self._make_mapping_combo(i, _BOM_MAPPING_ROLES)
            role = "-"
            if preserved_roles and i < len(preserved_roles):
                role = preserved_roles[i]
            else:
                col_name_str = str(col_name) if col_name else ""
                col_upper = col_name_str.upper()
                if "DESIGNATOR" in col_upper or "REF" in col_upper:
                    role = "REF"
                elif (
                    "COMMENT" in col_upper
                    or "VALUE" in col_upper
                    or "NAME" in col_upper
                ):
                    role = "Comment"
            self._set_mapping_combo_role(combo, role)
            combo.currentIndexChanged.connect(
                lambda *_a, c=combo, idx=i: self._on_bom_col_mapping_changed(
                    idx, self._mapping_combo_role(c)
                )
            )
            combos.append(combo)

        self.bom_col_combos = combos
        hh.set_mapping_combos(combos)
        QtCore.QTimer.singleShot(0, self._sync_bom_all_combos_width)
        self._apply_pending_profile_bom_mappings()

    def _fill_pnp_combos(self, *, preserved_roles: list[str] | None = None):
        """Create per-column role dropdowns in the PnP header."""
        if self._pnp_df is None:
            return
        hh = self._mapping_header(self.pnp_table)
        if hh is None:
            return

        cols = list(self._pnp_df.columns)
        combos: list[QtWidgets.QComboBox] = []

        for i, col_name in enumerate(cols):
            combo = self._make_mapping_combo(i, _PNP_MAPPING_ROLES)
            role = "-"
            if preserved_roles and i < len(preserved_roles):
                role = preserved_roles[i]
            else:
                col_name_str = str(col_name) if col_name else ""
                col_upper = col_name_str.upper()
                compact = col_upper.replace(" ", "")
                if "DESIGNATOR" in col_upper or "REFDES" in compact:
                    role = "REF"
                elif "POS-X" in compact and "MIL" not in col_upper:
                    role = "X"
                elif "POS-Y" in compact and "MIL" not in col_upper:
                    role = "Y"
                elif "MID-X" in col_upper or "MID-Y" in col_upper:
                    role = "-"
                elif (
                    "FOOTPRINT" in col_upper
                    or "PATTERN" in col_upper
                    or "PACKAGE" in col_upper
                ):
                    role = "Footprint"
                elif "COMMENT" in col_upper and "VALUE" not in col_name_str:
                    role = "-"
                elif "VALUE" in col_upper and "POS" not in col_upper:
                    role = "-"
                elif "CENTER-X" in col_upper and "MID" not in col_upper:
                    role = "X"
                elif "CENTER-Y" in col_upper and "MID" not in col_upper:
                    role = "Y"
                elif (
                    col_upper.strip() == "X"
                    and "MIL" not in col_upper
                    and "PAD" not in col_upper
                    and "MID" not in col_upper
                ):
                    role = "X"
                elif (
                    col_upper.strip() == "Y"
                    and "MIL" not in col_upper
                    and "PAD" not in col_upper
                    and "MID" not in col_upper
                ):
                    role = "Y"
                elif "ROTATION" in col_upper:
                    role = "Rotation"
                elif (
                    "LAYER" in col_upper
                    or "SIDE" in col_upper
                    or "MIRROR" in col_upper
                ):
                    role = "Layer"
            self._set_mapping_combo_role(combo, role)
            combo.currentIndexChanged.connect(
                lambda *_a, c=combo, idx=i: self._on_pnp_col_mapping_changed(
                    idx, self._mapping_combo_role(c)
                )
            )
            combos.append(combo)

        self.pnp_col_combos = combos
        hh.set_mapping_combos(combos)
        QtCore.QTimer.singleShot(0, self._sync_pnp_all_combos_width)
        self._apply_pending_profile_pnp_mappings()

    def _on_bom_column_changed(self, text):
        """Legacy single-combo BOM column handler (logging only)."""
        self._log(
            f"BOM cols: REF={self.bom_ref_combo.currentText() if hasattr(self, 'bom_ref_combo') else 'N/A'}, Comment={self.bom_comment_combo.currentText() if hasattr(self, 'bom_comment_combo') else 'N/A'}",
            "debug",
        )
    def _on_pnp_column_changed(self, text):
        """Legacy single-combo PnP column handler (logging only)."""
        self._log(
            f"PnP cols: REF={self.pnp_ref_combo.currentText() if hasattr(self, 'pnp_ref_combo') else 'N/A'}, Comment={self.pnp_comment_combo.currentText() if hasattr(self, 'pnp_comment_combo') else 'N/A'}",
            "debug",
        )
    def _on_bom_col_mapping_changed(self, col_idx, mapping):
        """Per-column BOM role dropdown changed."""
        self._log(f"BOM col {col_idx} -> {mapping}", "debug")
        self._schedule_save_bom_tab_settings()
        if hasattr(self, "_mark_clean_preview_stale"):
            self._mark_clean_preview_stale()
    def _on_pnp_col_mapping_changed(self, col_idx, mapping):
        """Per-column PnP role dropdown changed."""
        self._log(f"PnP col {col_idx} -> {mapping}", "debug")
        self._schedule_save_pnp_tab_settings()
    def _on_bom_header_click(self, section: int):
        """Highlight the mapping combo for the clicked BOM column."""
        self._highlight_mapping_combo("bom", section)
    def _on_pnp_header_click(self, section: int):
        """Highlight the mapping combo for the clicked PnP column."""
        self._highlight_mapping_combo("pnp", section)
    def _pnp_mappings_from_combos(self) -> dict[str, object]:
        self._sync_pnp_df_from_model()
        out: dict[str, object] = {}
        if self._pnp_df is None or not getattr(self, "pnp_col_combos", None):
            return out
        colnames = list(self._pnp_df.columns)
        for i, combo in enumerate(self.pnp_col_combos):
            m = self._mapping_combo_role(combo)
            if m != "-" and i < len(colnames):
                out[m] = colnames[i]
        return out
