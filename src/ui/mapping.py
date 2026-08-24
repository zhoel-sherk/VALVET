"""Column mapping strip and combo helpers (MainWindow mixin)."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtWidgets

from app.constants import (
    _BOM_MAPPING_ROLES,
    _MAPPING_COMBO_HIGHLIGHT_STYLE,
    _MAPPING_COMBO_MAX_HEIGHT,
    _MAPPING_I18N_KEY,
    _PNP_MAPPING_ROLES,
    _PREVIEW_TABLE_HDR_HEIGHT,
    _TABLE_COL_MAX_WIDTH,
)


class MappingMixin:
    def _build_mapping_row_widgets(
        self,
    ) -> tuple[QtWidgets.QWidget, QtWidgets.QWidget, QtWidgets.QHBoxLayout]:
        """Spacer (row-number column) + plain widget with combo row. No QScrollArea — it hid combos on some styles."""
        spacer = QtWidgets.QWidget()
        inner = QtWidgets.QWidget()
        inner.setMinimumHeight(26)
        inner.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Fixed
        )
        lay = QtWidgets.QHBoxLayout(inner)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        return spacer, inner, lay
    def _wrap_mapping_row(
        self, spacer: QtWidgets.QWidget, inner: QtWidgets.QWidget
    ) -> QtWidgets.QWidget:
        class _MappingScroll(QtWidgets.QScrollArea):
            def sizeHint(self) -> QtCore.QSize:  # type: ignore[override]
                sh = super().sizeHint()
                return QtCore.QSize(160, sh.height())

            def minimumSizeHint(self) -> QtCore.QSize:  # type: ignore[override]
                sh = super().minimumSizeHint()
                return QtCore.QSize(0, sh.height())

        scroll = _MappingScroll()
        scroll.setWidgetResizable(False)
        scroll.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        scroll.setVerticalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setWidget(inner)
        scroll.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        scroll.setMinimumWidth(0)
        scroll.setMinimumHeight(28)
        scroll.setMaximumHeight(36)
        inner.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Minimum,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )

        row = QtWidgets.QWidget()
        row.setMinimumHeight(28)
        h = QtWidgets.QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        h.addWidget(spacer)
        h.addWidget(scroll, 1)
        return row
    def _apply_compact_preview_chrome(self, table: QtWidgets.QTableView) -> None:
        """Short horizontal header (labels are only 0,1,… in preview); mapping row sits flush above."""
        hh = table.horizontalHeader()
        hh.setFixedHeight(_PREVIEW_TABLE_HDR_HEIGHT)
    def _style_mapping_combo(self, combo: QtWidgets.QComboBox) -> None:
        combo.setMaximumHeight(_MAPPING_COMBO_MAX_HEIGHT)
        combo.setObjectName("boomerMappingCombo")
        combo.setIconSize(QtCore.QSize(0, 0))
    def _style_clean_template_combo(self, combo: QtWidgets.QComboBox) -> None:
        """Tighter label + popup (qdarkstyle leaves a wide left gutter on small combos)."""
        combo.setObjectName("boomerCleanTemplateCombo")
        combo.setIconSize(QtCore.QSize(0, 0))
    def _connect_mapping_table_signals(
        self, table: QtWidgets.QTableView, which: str
    ) -> None:
        vh = table.verticalHeader()
        vh.sectionResized.connect(
            lambda *args, w=which: self._update_mapping_margins(w)
        )
        vh.geometriesChanged.connect(lambda w=which: self._update_mapping_margins(w))
    def _update_mapping_margins(self, which: Optional[str] = None) -> None:
        if which in (None, "_bom") and hasattr(self, "bom_combo_vheader_spacer"):
            self.bom_combo_vheader_spacer.setFixedWidth(
                self.bom_table.verticalHeader().width()
            )
            self._refresh_bom_mapping_strip()
        if which in (None, "_pnp") and hasattr(self, "pnp_combo_vheader_spacer"):
            self.pnp_combo_vheader_spacer.setFixedWidth(
                self.pnp_table.verticalHeader().width()
            )
            self._refresh_pnp_mapping_strip()
    def _strip_column_width(self, table: QtWidgets.QTableView, col: int) -> int:
        """Column width for mapping strip. columnWidth is often 0 before first layout; use size hint."""
        w = table.columnWidth(col)
        if w <= 0:
            w = table.sizeHintForColumn(col)
        return min(max(50, w), _TABLE_COL_MAX_WIDTH)
    def _refresh_pnp_mapping_strip(self) -> None:
        if (
            not hasattr(self, "pnp_col_combos")
            or not self.pnp_col_combos
            or not hasattr(self, "pnp_combo_inner")
        ):
            return
        n = self.pnp_model.columnCount()
        if n <= 0:
            return
        total = sum(self._strip_column_width(self.pnp_table, i) for i in range(n))
        self.pnp_combo_inner.setMinimumWidth(max(total, len(self.pnp_col_combos) * 50))
    def _refresh_bom_mapping_strip(self) -> None:
        if (
            not hasattr(self, "bom_col_combos")
            or not self.bom_col_combos
            or not hasattr(self, "bom_combo_inner")
        ):
            return
        n = self.bom_model.columnCount()
        if n <= 0:
            return
        total = sum(self._strip_column_width(self.bom_table, i) for i in range(n))
        self.bom_combo_inner.setMinimumWidth(max(total, len(self.bom_col_combos) * 60))
    def _on_bom_section_resized(self, idx: int, _old: int, new: int) -> None:
        self._sync_bom_combo_width(idx, new)
        self._refresh_bom_mapping_strip()
    def _on_pnp_section_resized(self, idx: int, _old: int, new: int) -> None:
        self._sync_pnp_combo_width(idx, new)
        self._refresh_pnp_mapping_strip()
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
    def _mapping_role_label(self, role: str) -> str:
        key = _MAPPING_I18N_KEY.get(role, "mapping.none")
        return self.ui_tr(key)
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
    def _fill_bom_combos(self, *, preserved_roles: list[str] | None = None):
        """Create per-column role dropdowns above the BOM table."""
        if self._bom_df is None:
            return

        # Clear existing combos
        while self.bom_combos_layout.count():
            item = self.bom_combos_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        cols = list(self._bom_df.columns)
        self.bom_col_combos = []

        for i, col_name in enumerate(cols):
            combo = QtWidgets.QComboBox()
            self._populate_mapping_combo(combo, _BOM_MAPPING_ROLES)
            combo.setMinimumWidth(60)
            self._style_mapping_combo(combo)

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

            self.bom_col_combos.append(combo)
            combo.currentIndexChanged.connect(
                lambda *_a, c=combo, idx=i: self._on_bom_col_mapping_changed(
                    idx, self._mapping_combo_role(c)
                )
            )
            self.bom_combos_layout.addWidget(combo)

        QtCore.QTimer.singleShot(0, self._update_mapping_margins)
        # Sync widths after table is shown
        QtCore.QTimer.singleShot(50, self._sync_bom_all_combos_width)
        self._apply_pending_profile_bom_mappings()
    def _sync_bom_combo_width(self, col_idx, new_width):
        """Match one BOM mapping combo width to its table column."""
        if hasattr(self, "bom_col_combos") and col_idx < len(self.bom_col_combos):
            w = (
                new_width
                if new_width > 0
                else self.bom_table.sizeHintForColumn(col_idx)
            )
            self.bom_col_combos[col_idx].setFixedWidth(max(60, w))
    def _sync_bom_all_combos_width(self):
        """Resize all BOM role dropdowns to match column widths."""
        if not hasattr(self, "bom_col_combos"):
            return
        header = self.bom_table.horizontalHeader()
        for i, combo in enumerate(self.bom_col_combos):
            w = self.bom_table.columnWidth(i) if header.count() > i else 60
            if w <= 0:
                w = self.bom_table.sizeHintForColumn(i)
            combo.setFixedWidth(max(60, w))
        self._update_mapping_margins("_bom")
        self._refresh_bom_mapping_strip()
    def _fill_pnp_combos(self, *, preserved_roles: list[str] | None = None):
        """Create per-column role dropdowns above the PnP table."""
        if self._pnp_df is None:
            return

        # Clear existing combos
        while self.pnp_combos_layout.count():
            item = self.pnp_combos_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        cols = list(self._pnp_df.columns)
        self.pnp_col_combos = []

        for i, col_name in enumerate(cols):
            combo = QtWidgets.QComboBox()
            self._populate_mapping_combo(combo, _PNP_MAPPING_ROLES)
            combo.setMinimumWidth(50)
            self._style_mapping_combo(combo)

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

            self.pnp_col_combos.append(combo)
            combo.currentIndexChanged.connect(
                lambda *_a, c=combo, idx=i: self._on_pnp_col_mapping_changed(
                    idx, self._mapping_combo_role(c)
                )
            )
            self.pnp_combos_layout.addWidget(combo)

        QtCore.QTimer.singleShot(0, lambda: self._update_mapping_margins("_pnp"))
        QtCore.QTimer.singleShot(50, self._sync_pnp_all_combos_width)
        self._apply_pending_profile_pnp_mappings()
    def _sync_pnp_combo_width(self, col_idx, new_width):
        """Match one PnP mapping combo width to its table column."""
        if hasattr(self, "pnp_col_combos") and col_idx < len(self.pnp_col_combos):
            w = (
                new_width
                if new_width > 0
                else self.pnp_table.sizeHintForColumn(col_idx)
            )
            self.pnp_col_combos[col_idx].setFixedWidth(max(50, w))
    def _sync_pnp_all_combos_width(self):
        """Resize all PnP role dropdowns to match column widths."""
        if not hasattr(self, "pnp_col_combos"):
            return
        header = self.pnp_table.horizontalHeader()
        for i, combo in enumerate(self.pnp_col_combos):
            w = self.pnp_table.columnWidth(i) if header.count() > i else 50
            if w <= 0:
                w = self.pnp_table.sizeHintForColumn(i)
            combo.setFixedWidth(max(50, w))
        self._update_mapping_margins("_pnp")
        self._refresh_pnp_mapping_strip()
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
