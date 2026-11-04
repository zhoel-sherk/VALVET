"""Runtime view state: stepper, banners, summary, splitter."""

from __future__ import annotations

import pandas as pd
from PySide6 import QtCore, QtGui, QtWidgets

from ui.chrome import apply_equal_widths
from ui.clean_tab.helpers import _clean_int_list


class CleanViewStateMixin:
    def _show_clean_help(self) -> None:
        QtWidgets.QMessageBox.information(
            self,
            self.ui_tr("clean.help_title"),
            self.ui_tr("clean.help_body"),
        )

    def _on_clean_options_toggled(self, expanded: bool) -> None:
        self._apply_clean_options_visibility(expanded)
        if hasattr(self, "_settings") and not getattr(
            self, "_restoring_settings", False
        ):
            self._settings.setValue("clean/options_expanded", expanded)

    def _apply_clean_options_visibility(self, expanded: bool) -> None:
        self.clean_options_panel.setVisible(expanded)
        self.btn_clean_options_toggle.setArrowType(
            QtCore.Qt.ArrowType.DownArrow
            if expanded
            else QtCore.Qt.ArrowType.RightArrow
        )
        if expanded:
            self._restore_clean_splitter_sizes()
            QtCore.QTimer.singleShot(0, self._apply_default_clean_splitter_sizes)
        else:
            self._collapse_clean_splitter()

    def _on_clean_splitter_moved(self, *_args) -> None:
        self._save_clean_splitter_sizes()

    def eventFilter(self, obj, event):
        if (
            hasattr(self, "clean_options_scroll")
            and obj is self.clean_options_scroll.viewport()
            and event.type() == QtCore.QEvent.Type.Resize
        ):
            self._layout_clean_rules_groups()
        return super().eventFilter(obj, event)

    def _save_clean_splitter_sizes(self) -> None:
        if not hasattr(self, "clean_splitter") or not hasattr(self, "_settings"):
            return
        if not self.btn_clean_options_toggle.isChecked():
            return
        sizes = [int(x) for x in self.clean_splitter.sizes()]
        if len(sizes) != 2 or not sizes[0]:
            return
        self._settings.setValue("clean/splitter_sizes", sizes)

    def _stored_clean_splitter_sizes(self) -> list[int]:
        raw = (
            self._settings.value("clean/splitter_sizes")
            if hasattr(self, "_settings")
            else None
        )
        return _clean_int_list(raw)

    def _collapse_clean_splitter(self) -> None:
        if not hasattr(self, "clean_splitter"):
            return
        total = sum(self.clean_splitter.sizes()) or 600
        handle = self.clean_splitter.handleWidth()
        lay = self.clean_rules_host.layout()
        margins = lay.contentsMargins()
        collapsed = (
            self.btn_clean_options_toggle.sizeHint().height()
            + self.lbl_clean_rules_summary.sizeHint().height()
            + lay.spacing()
            + margins.top()
            + margins.bottom()
            + handle
            + 4
        )
        collapsed = max(56, collapsed)
        self.clean_rules_host.setMaximumHeight(collapsed)
        self.clean_splitter.setSizes([max(120, total - collapsed), collapsed])

    def _apply_default_clean_splitter_sizes(self) -> None:
        """Give an expanded Rules pane a usable 55/45 split after layout.

        ``QSplitter.setSizes`` before the window is shown is rebalanced from
        size hints, so the first real geometry is applied on the next event-loop
        turn. A stored user split always wins.
        """
        if not hasattr(self, "clean_splitter"):
            return
        if not self.btn_clean_options_toggle.isChecked():
            return
        if self._stored_clean_splitter_sizes():
            return
        total = self.clean_splitter.height()
        if total <= 0:
            total = sum(self.clean_splitter.sizes())
        if total <= 0:
            return
        table = max(self.clean_preview_stack.minimumHeight(), int(total * 0.35))
        rules = max(120, total - table)
        if table + rules > total:
            table = max(120, total - rules)
        self.clean_splitter.setSizes([table, rules])

    def _restore_clean_splitter_sizes(self) -> None:
        if not hasattr(self, "clean_splitter"):
            return
        if not self.btn_clean_options_toggle.isChecked():
            self._collapse_clean_splitter()
            return
        self.clean_rules_host.setMaximumHeight(16777215)
        sizes = self._stored_clean_splitter_sizes()
        if len(sizes) == 2 and sizes[0] > 0 and sizes[1] >= 120:
            self.clean_splitter.setSizes(sizes)
            return
        total = sum(self.clean_splitter.sizes()) or 600
        self.clean_splitter.setSizes([int(total * 0.35), int(total * 0.65)])

    def _update_clean_preview_min_height(self) -> None:
        if not hasattr(self, "clean_preview_stack"):
            return
        row_h = int(self.clean_preview_table.verticalHeader().defaultSectionSize())
        if row_h <= 0:
            row_h = self.fontMetrics().height() + 12
        header_h = int(self.clean_preview_table.horizontalHeader().sizeHint().height())
        self.clean_preview_stack.setMinimumHeight(row_h * 6 + header_h + 10)

    def _mark_clean_preview_stale(self) -> None:
        if getattr(self, "_clean_applying", False):
            # Apply rewrites BOM mapping combos; that is not a preview change.
            return
        if getattr(self, "_clean_last_preview", None):
            self._clean_preview_stale = True
        self._hide_clean_apply_banner()
        self._refresh_clean_stale_badge()
        self._sync_clean_primary_buttons()
        if hasattr(self, "_refresh_shell_status"):
            self._refresh_shell_status()

    def _on_clean_preview_setting_changed(self, *_args) -> None:
        self._hide_clean_apply_banner()
        if getattr(self, "_clean_last_preview", None):
            self._clean_preview_stale = True
        self._refresh_clean_stale_badge()
        self._sync_clean_primary_buttons()
        self._update_clean_rules_summary()
        if hasattr(self, "_refresh_shell_status"):
            self._refresh_shell_status()

    def _hide_clean_apply_banner(self) -> None:
        if hasattr(self, "clean_apply_ok_banner"):
            self.clean_apply_ok_banner.setVisible(False)

    def _refresh_clean_stale_badge(self) -> None:
        if not hasattr(self, "lbl_clean_stale"):
            return
        stale = bool(getattr(self, "_clean_preview_stale", False)) and bool(
            getattr(self, "_clean_last_preview", None)
        )
        self.lbl_clean_stale.setText(self.ui_tr("clean.stale_badge"))
        self.lbl_clean_stale.setVisible(stale)

    def _clean_preview_dataframe(self) -> pd.DataFrame | None:
        if not hasattr(self, "clean_preview_model"):
            return None
        return self.clean_preview_model.get_dataframe()

    @staticmethod
    def _clean_counts(df: pd.DataFrame | None) -> dict[str, int]:
        rows = 0 if df is None else len(df)
        clean = partial = other = errors = 0
        if rows:
            for _i, row in df.iterrows():
                cleaned = str(row.get("Cleaned", "")).strip()
                if cleaned and cleaned != "—":
                    clean += 1
                if "PARTIAL" in str(row.get("Source", "")).upper():
                    partial += 1
                if str(row.get("Type", "")).strip().upper() == "OTHER":
                    other += 1
                if str(row.get("Alert", "")).strip():
                    errors += 1
        return {
            "rows": rows,
            "clean": clean,
            "partial": partial,
            "other": other,
            "errors": errors,
        }

    def _refresh_clean_summary(self) -> None:
        if not hasattr(self, "lbl_clean_source"):
            return
        df = self._clean_preview_dataframe()
        counts = self._clean_counts(df)
        if counts["rows"]:
            self.lbl_clean_source.setText(
                self.ui_tr(
                    "clean.summary_counts",
                    rows=counts["rows"],
                    clean=counts["clean"],
                    partial=counts["partial"],
                    other=counts["other"],
                    errors=counts["errors"],
                )
            )
        elif self._clean_imported_comments:
            self.lbl_clean_source.setText(
                self.ui_tr(
                    "clean.summary_imported", rows=len(self._clean_imported_comments)
                )
            )
        else:
            self.lbl_clean_source.setText(self.ui_tr("clean.summary_empty"))
        self.lbl_clean_source.setToolTip(self.ui_tr("clean.summary_tip"))

    def _sync_clean_learn_button(self) -> None:
        if not hasattr(self, "btn_clean_learn_other"):
            return
        counts = self._clean_counts(self._clean_preview_dataframe())
        has_preview = bool(getattr(self, "_clean_last_preview", None))
        self.btn_clean_learn_other.setText(
            self.ui_tr("clean.btn_learn_count", count=counts["other"])
            if has_preview
            else self.ui_tr("clean.btn_learn")
        )
        self.btn_clean_learn_other.setEnabled(has_preview and counts["other"] > 0)
        self.btn_clean_learn_other.setToolTip(
            self.ui_tr("clean.btn_learn_zero_tip")
            if counts["other"] == 0
            else self.ui_tr("clean.btn_learn_tip")
        )

    def _sync_clean_preview_view(self) -> None:
        if not hasattr(self, "clean_preview_stack"):
            return
        df = self._clean_preview_dataframe()
        has_rows = df is not None and not df.empty
        self.clean_preview_stack.setCurrentWidget(
            self.clean_preview_table if has_rows else self.clean_preview_empty
        )
        header = self.clean_preview_table.horizontalHeader()
        mode = QtWidgets.QHeaderView.ResizeMode
        alert_index = -1
        if df is not None:
            for col, raw_name in enumerate(df.columns):
                name = str(raw_name)
                if name == "#":
                    header.setSectionResizeMode(col, mode.ResizeToContents)
                elif name.startswith("Original") or name == "Cleaned":
                    header.setSectionResizeMode(col, mode.Stretch)
                elif name == "Alert":
                    header.setSectionResizeMode(col, mode.Interactive)
                else:
                    header.setSectionResizeMode(col, mode.ResizeToContents)
                if name == "Alert":
                    alert_index = col
        if alert_index >= 0 and df is not None:
            has_alert = any(str(v).strip() for v in df["Alert"].tolist())
            self.clean_preview_table.setColumnHidden(alert_index, not has_alert)
            if has_alert:
                fm = self.clean_preview_table.fontMetrics()
                widths = [
                    fm.horizontalAdvance(str(v))
                    for v in df["Alert"].tolist()
                    if str(v).strip()
                ]
                # Normal UI text gets the warning marker plus the whole alert;
                # at large fonts the column stays bounded and the tooltip holds
                # the full text so the name columns keep their width.
                large_text = fm.height() > 22
                budget = 0 if large_text else 40
                cap = 260 if large_text else 320
                self.clean_preview_table.setColumnWidth(
                    alert_index, max(150, min(cap, max(widths) + budget))
                )
        self._refresh_clean_header_metadata()
        self._refresh_clean_summary()
        self._refresh_clean_stale_badge()
        self._sync_clean_learn_button()

    def _refresh_clean_header_metadata(self) -> None:
        if not hasattr(self, "clean_preview_model"):
            return
        tips = {
            "#": self.ui_tr("clean.header_tip_hash"),
            "Original": self.ui_tr("clean.header_tip_original"),
            "Cleaned": self.ui_tr("clean.header_tip_cleaned"),
            "Type": self.ui_tr("clean.header_tip_type"),
            "Source": self.ui_tr("clean.header_tip_source"),
            "Input": self.ui_tr("clean.header_tip_input"),
            "Arbiter": self.ui_tr("clean.header_tip_arbiter"),
            "Win%": self.ui_tr("clean.header_tip_win"),
            "Alert": self.ui_tr("clean.header_tip_alert"),
        }
        df = self._clean_preview_dataframe()
        tooltips: dict[str, str] = {}
        if df is not None:
            for raw_name in df.columns:
                name = str(raw_name)
                if name.startswith("Original"):
                    tooltips[name] = self.ui_tr("clean.header_tip_original")
                elif name in tips:
                    tooltips[name] = tips[name]
        self.clean_preview_model.set_column_header_metadata({}, tooltips)

    def _clean_empty_go_bom(self) -> None:
        idx = self._tab_index("bom")
        if idx >= 0:
            self.tabs.setCurrentIndex(idx)

    def _show_clean_alert(
        self, key: str, *, severity: str = "warning", **kwargs: object
    ) -> None:
        if not hasattr(self, "clean_alert_frame"):
            return
        self._clean_alert_key = key
        self._clean_alert_args = dict(kwargs)
        self.clean_alert_frame.setProperty("severity", severity)
        self._render_clean_alert()
        self.clean_alert_frame.setVisible(True)
        style = self.clean_alert_frame.style()
        style.unpolish(self.clean_alert_frame)
        style.polish(self.clean_alert_frame)

    def _render_clean_alert(self) -> None:
        if not getattr(self, "_clean_alert_key", ""):
            return
        self.lbl_clean_alert.setText(
            self.ui_tr(self._clean_alert_key, **self._clean_alert_args)
        )
        self.btn_clean_alert_details.setText(self.ui_tr("clean.err_details"))
        self.btn_clean_alert_dismiss.setAccessibleName(self.ui_tr("clean.err_dismiss"))

    def _clear_clean_alert(self) -> None:
        self._clean_alert_key = ""
        self._clean_alert_args = {}
        if hasattr(self, "clean_alert_frame"):
            self.clean_alert_frame.setVisible(False)

    def _update_clean_rules_summary(self) -> None:
        if not hasattr(self, "lbl_clean_rules_summary"):
            return

        def slots(combos: list[QtWidgets.QComboBox]) -> str:
            values = [
                "—"
                if str(c.currentData()) in ("none", "None")
                else str(c.currentData())
                for c in combos
            ]
            return "·".join(values)

        families = []
        for chk, combos, short_key in (
            (
                self.chk_clean_res,
                self.clean_res_template_combos,
                "clean.rules_short_res",
            ),
            (
                self.chk_clean_cap,
                self.clean_cap_template_combos,
                "clean.rules_short_cap",
            ),
            (
                self.chk_clean_ind,
                self.clean_ind_template_combos,
                "clean.rules_short_ind",
            ),
        ):
            if chk.isChecked():
                families.append(
                    self.ui_tr(
                        "clean.rules_family",
                        name=self.ui_tr(short_key),
                        slots=slots(combos),
                    )
                )
        sources = []
        if self.clean_from_db.isChecked():
            sources.append(self.ui_tr("clean.from_db"))
        if self.clean_from_hanwha_mdb.isChecked():
            sources.append(self.ui_tr("clean.from_machine"))
        if self.gb_clean_pn.isChecked():
            sources.append(self.ui_tr("clean.pn"))
        join_data = self.clean_spacer_combo.currentData()
        if join_data == " ":
            join = self.ui_tr("clean.spacer_space")
        elif join_data == "\t":
            join = self.ui_tr("clean.spacer_tab")
        elif self.clean_spacer_combo.currentData() == "cust":
            join = (
                self.clean_spacer_cust.text() or self.clean_spacer_combo.currentText()
            )
        else:
            join = str(join_data)
        self._clean_rules_summary_full = self.ui_tr(
            "clean.rules_summary",
            families=" · ".join(families) or self.ui_tr("clean.rules_none"),
            join=join,
            sources=", ".join(sources) or self.ui_tr("clean.rules_sources_none"),
            combine=self.ui_tr(
                "clean.rules_combine_on"
                if self.clean_combine_inputs.isChecked()
                else "clean.rules_combine_off"
            ),
        )
        self._apply_clean_rules_summary_elide()
        self.lbl_clean_rules_summary.setAccessibleDescription(
            self.ui_tr("clean.rules_summary_tip")
        )
        QtCore.QTimer.singleShot(0, self._apply_clean_rules_summary_elide)

    def _apply_clean_rules_summary_elide(self) -> None:
        if not hasattr(self, "lbl_clean_rules_summary"):
            return
        full = getattr(self, "_clean_rules_summary_full", "")
        if not full:
            return
        label = self.lbl_clean_rules_summary
        width = label.width() - 2
        label.setText(
            label.fontMetrics().elidedText(
                full, QtCore.Qt.TextElideMode.ElideRight, width
            )
            if width > 20
            else full
        )
        label.setToolTip(full)

    def _sync_clean_primary_buttons(self) -> None:
        if not hasattr(self, "btn_clean_convert"):
            return
        imported = bool(getattr(self, "_clean_imported_comments", None))
        has_preview = bool(getattr(self, "_clean_last_preview", None))
        stale = bool(getattr(self, "_clean_preview_stale", False)) and has_preview
        applied = bool(getattr(self, "_clean_applied", False)) and has_preview
        # ``cleanStep`` keeps the original enabled-state contract (QSS/tests use it);
        # ``cleanStepState`` adds the done/next/stale distinction on top.
        conv_enabled = self.btn_clean_convert.isEnabled()
        apply_enabled = self.btn_clean_apply.isEnabled()
        import_active = not conv_enabled and not apply_enabled
        convert_active = conv_enabled and not apply_enabled
        apply_active = apply_enabled
        if not conv_enabled:
            next_key = "apply" if apply_enabled else "import"
        elif not apply_enabled:
            next_key = "convert"
        else:
            next_key = "apply"
        states = {
            "import": "done" if imported else ("next" if import_active else "idle"),
            "convert": (
                "stale"
                if stale
                else (
                    "done"
                    if has_preview and not stale
                    else ("next" if next_key == "convert" else "idle")
                )
            ),
            "apply": (
                "done"
                if applied
                else ("next" if next_key == "apply" and apply_enabled else "idle")
            ),
        }
        active_flags = {
            "import": import_active,
            "convert": convert_active,
            "apply": apply_active,
        }
        markers = {"done": "✓ ", "next": "▶ ", "stale": "⟳ ", "idle": ""}
        button_keys = {
            "import": "clean.btn_import",
            "convert": "clean.btn_convert",
            "apply": "clean.btn_apply",
        }
        for btn, key in (
            (self.btn_clean_import, "import"),
            (self.btn_clean_convert, "convert"),
            (self.btn_clean_apply, "apply"),
        ):
            state = states[key]
            btn.setProperty("cleanStep", "active" if active_flags[key] else "idle")
            btn.setProperty("cleanStepState", state)
            btn.setText(markers[state] + self.ui_tr(button_keys[key]))
            btn.setIcon(QtGui.QIcon())
            sty = btn.style()
            sty.unpolish(btn)
            sty.polish(btn)
            btn.update()
        if self.btn_clean_convert.isEnabled():
            self.btn_clean_convert.setToolTip(self.ui_tr("clean.btn_convert_tip"))
        else:
            self.btn_clean_convert.setToolTip(
                self.ui_tr(
                    "clean.btn_convert_disabled_import"
                    if not imported
                    else "clean.btn_convert_disabled_map"
                )
            )
        if not self.btn_clean_apply.isEnabled():
            if not has_preview:
                self.btn_clean_apply.setToolTip(
                    self.ui_tr("clean.btn_apply_disabled_convert")
                )
            elif stale:
                self.btn_clean_apply.setToolTip(
                    self.ui_tr("clean.btn_apply_disabled_stale")
                )
            else:
                self.btn_clean_apply.setToolTip(
                    self.ui_tr("clean.btn_apply_disabled_none")
                )
        elif stale:
            self.btn_clean_apply.setToolTip(
                self.ui_tr("clean.btn_apply_disabled_stale")
            )
        else:
            self.btn_clean_apply.setToolTip(self.ui_tr("clean.btn_apply_tip"))
        apply_equal_widths(
            (
                self.btn_clean_import,
                self.btn_clean_convert,
                self.btn_clean_apply,
                self.btn_clean_learn_other,
                self.btn_clean_save,
            )
        )

    def _show_clean_apply_banner(self, message: str) -> None:
        if not hasattr(self, "clean_apply_ok_banner"):
            return
        self.clean_apply_ok_label.setText(message)
        self.clean_apply_ok_banner.setVisible(True)
