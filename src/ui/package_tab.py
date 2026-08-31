"""DATA · Package tab: VSPD catalog, aliases, Machine Lib–style outline canvas."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd
from PySide6 import QtCore, QtWidgets

from app_paths import package_vspd_dir
from package_vspd.import_machine import import_machine_packages
from package_vspd.kicad_mod import parse_kicad_mod_file
from package_vspd.outline import build_result_for_package, outline_to_json
from package_vspd.parse import apply_preset, parse_package
from package_vspd.store import PackageStore
from qt_models import SortableTableModel
from ui.chrome import action_button, apply_equal_widths, left_rail_widget
from ui.machine_lib.footprint_preview import FootprintPreviewWidget


class PackageTab(QtWidgets.QWidget):
    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
        *,
        settings: Optional[QtCore.QSettings] = None,
        db_path: Optional[Path] = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        pid = "default"
        if settings is not None:
            from app.constants import PROFILE_LAST_ACTIVE_KEY

            pid = str(settings.value(PROFILE_LAST_ACTIVE_KEY, "default") or "default")
        store_path = db_path if db_path is not None else package_vspd_dir(pid) / "vspd.sqlite"
        self._store = PackageStore(store_path)

        root = QtWidgets.QHBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)

        left = left_rail_widget()
        left_l = QtWidgets.QVBoxLayout(left)
        left_l.setContentsMargins(0, 0, 8, 0)
        self._status = QtWidgets.QLabel("")
        self._status.setWordWrap(True)
        left_l.addWidget(self._status)

        self.btn_import_machine = action_button("Import machine lib")
        self.btn_import_machine.setToolTip(
            "Import unique part groups (packages), not every PARTNAME. "
            "SOT23 / SOT_23 / SOT-23 collapse to one alias. Copies Hanwha UPD outlines when present."
        )
        self.btn_import_machine.clicked.connect(self._import_machine)
        left_l.addWidget(self.btn_import_machine)
        self.btn_import_kicad = action_button("Import .kicad_mod…")
        self.btn_import_kicad.clicked.connect(self._import_kicad)
        left_l.addWidget(self.btn_import_kicad)
        self.btn_add = action_button("Add VSPD…")
        self.btn_add.clicked.connect(self._add_vspd)
        left_l.addWidget(self.btn_add)
        self.btn_rename = action_button("Rename VSPD…")
        self.btn_rename.clicked.connect(self._rename_selected)
        left_l.addWidget(self.btn_rename)
        self._filter = QtWidgets.QLineEdit()
        self._filter.setPlaceholderText("Filter VSPD / class / family")
        self._filter.textChanged.connect(self._reload_table)
        left_l.addWidget(self._filter)
        self._preset = QtWidgets.QComboBox()
        self._preset.addItems(["IPC→VSPD", "Hanwha PARTGROUP→VSPD", "KiCad KLC→VSPD"])
        left_l.addWidget(self._preset)
        self.btn_preset = action_button("Apply preset")
        self.btn_preset.clicked.connect(self._apply_preset_selected)
        left_l.addWidget(self.btn_preset)
        apply_equal_widths(
            (
                self.btn_import_machine,
                self.btn_import_kicad,
                self.btn_add,
                self.btn_rename,
                self.btn_preset,
            )
        )
        left_l.addStretch(1)
        root.addWidget(left, 0)

        mid = QtWidgets.QWidget()
        mid_l = QtWidgets.QVBoxLayout(mid)
        mid_l.setContentsMargins(0, 0, 0, 0)
        self._table = QtWidgets.QTableView()
        self._table.setAlternatingRowColors(True)
        self._model = SortableTableModel(pd.DataFrame())
        self._table.setModel(self._model)
        self._table.setSortingEnabled(True)
        self._table.selectionModel().currentChanged.connect(self._on_row_changed)
        mid_l.addWidget(self._table, 3)
        self._detail = QtWidgets.QPlainTextEdit()
        self._detail.setReadOnly(True)
        self._detail.setMaximumHeight(140)
        mid_l.addWidget(self._detail, 1)

        self._fp_preview = FootprintPreviewWidget(self)
        self._fp_debounce = QtCore.QTimer(self)
        self._fp_debounce.setSingleShot(True)
        self._fp_debounce.setInterval(150)
        self._fp_debounce.timeout.connect(self._load_selected_outline)

        split = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        split.addWidget(mid)
        split.addWidget(self._fp_preview)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        split.setChildrenCollapsible(False)
        root.addWidget(split, 1)

        self._reload_table()
        self._refresh_import_enabled()

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        self._refresh_import_enabled()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._store.close()
        super().closeEvent(event)

    def _profile_id(self) -> str:
        if self._settings is None:
            return "default"
        from app.constants import PROFILE_LAST_ACTIVE_KEY

        return str(
            self._settings.value(PROFILE_LAST_ACTIVE_KEY, "default") or "default"
        )

    def _reload_table(self) -> None:
        needle = (self._filter.text() if hasattr(self, "_filter") else "").strip().lower()
        rows = []
        for r in self._store.list_packages():
            if needle:
                blob = f"{r['vspd_id']} {r['class']} {r['family']}".lower()
                if needle not in blob:
                    continue
            rows.append(
                {
                    "VSPD": r["vspd_id"],
                    "Class": r["class"],
                    "Family": r["family"],
                    "Aliases": int(r["alias_n"]),
                    "Links": int(r["link_n"]),
                }
            )
        df = pd.DataFrame(rows) if rows else pd.DataFrame(
            columns=["VSPD", "Class", "Family", "Aliases", "Links"]
        )
        self._model.update_dataframe(df)

    def _selected_vspd(self) -> str:
        idx = self._table.currentIndex()
        if not idx.isValid():
            return ""
        row = self._model.get_row_values(idx.row())
        return str(row.get("VSPD") or "").strip()

    def _on_row_changed(self, *_a: object) -> None:
        self._fp_debounce.start()
        vid = self._selected_vspd()
        if not vid:
            self._detail.setPlainText("")
            return
        als = [str(a["raw"]) for a in self._store.aliases_for(vid)]
        lks = [f"{lk['kind']}: {lk['value']}" for lk in self._store.links_for(vid)]
        self._detail.setPlainText(
            "Aliases:\n" + "\n".join(als[:80]) + "\n\nLinks:\n" + "\n".join(lks[:80])
        )

    def _load_selected_outline(self) -> None:
        vid = self._selected_vspd()
        if not vid:
            self._fp_preview.set_idle("Select a package")
            return
        pkg = self._store.get_package(vid)
        oj = None
        fam = ""
        notes = ""
        if pkg is not None:
            oj = pkg["outline_json"]
            fam = str(pkg["family"] or "")
            notes = str(pkg["notes"] or "")
        result = build_result_for_package(
            vid, outline_json=oj, family=fam, notes=notes
        )
        if result.outline.source in ("none", "vspd_heuristic") and not oj:
            live = self._hanwha_outline_for(vid)
            if live is not None:
                result = build_result_for_package(
                    vid,
                    outline_json=outline_to_json(live),
                    family=fam,
                    notes=notes,
                )
        self._fp_preview.show_result(result, title=vid)

    def _hanwha_outline_for(self, vid: str):
        win = self.window()
        ml = getattr(win, "_machine_library_tab", None)
        if ml is None:
            return None
        cache = str(getattr(ml, "_hanwha_cache_dir", "") or "")
        gmap = self._group_to_profile(ml)
        if not cache or not gmap:
            return None
        try:
            from machine_library.hanwha_sqlite_cache import build_outline_from_sqlite
        except ImportError:
            return None
        from package_vspd.parse import parse_package as _parse

        for group, prof in gmap.items():
            if _parse(group).vspd_id != vid:
                continue
            try:
                built = build_outline_from_sqlite(cache, prof)
            except (OSError, ValueError, TypeError):
                continue
            if (
                built.error
                or built.outline.source in ("none", "")
                or not (built.outline.lines or built.outline.pads)
            ):
                continue
            return built.outline
        return None

    @staticmethod
    def _group_to_profile(ml) -> dict[str, str]:
        df = getattr(ml, "_hanwha_df", None)
        out: dict[str, str] = {}
        if df is None or getattr(df, "empty", True):
            return out
        if "UPDPARTGROUPNAME" not in df.columns:
            return out
        cols = ["UPDPARTGROUPNAME"]
        if "PROFILENAME" in df.columns:
            cols.append("PROFILENAME")
        sub = df.loc[:, cols].drop_duplicates(subset=["UPDPARTGROUPNAME"], keep="first")
        for rec in sub.itertuples(index=False):
            group = str(rec[0] or "").strip()
            if not group:
                continue
            prof = str(rec[1] or "").strip() if len(rec) > 1 else ""
            out[group] = prof
        return out

    @staticmethod
    def _unique_partdesc(ml) -> list[str]:
        df = getattr(ml, "_hanwha_df", None)
        if df is None or getattr(df, "empty", True) or "PARTDESC" not in df.columns:
            return []
        seen: set[str] = set()
        out: list[str] = []
        for raw in df["PARTDESC"].astype(str).tolist():
            s = str(raw).strip()
            if not s or s.lower() in {"nan", "none"}:
                continue
            key = s.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(s)
        return out

    def _refresh_import_enabled(self) -> None:
        win = self.window()
        ml = getattr(win, "_machine_library_tab", None)
        gmap = self._group_to_profile(ml) if ml is not None else {}
        n_y = len(ml.yamaha_partname_set()) if ml is not None else 0
        n_parts = len(ml.hanwha_partname_set()) if ml is not None else 0
        n_g = len(gmap)
        self.btn_import_machine.setEnabled(n_g + n_y + n_parts > 0)
        if n_g + n_y + n_parts == 0:
            self._status.setText(
                "Load a library on VIEW · Machine lib to import unique packages."
            )
        else:
            self._status.setText(
                f"{n_g} unique part groups, {n_y} Yamaha names "
                f"({n_parts} part SKUs — SKUs are not imported)."
            )

    def _import_machine(self) -> None:
        win = self.window()
        ml = getattr(win, "_machine_library_tab", None)
        if ml is None:
            QtWidgets.QMessageBox.information(
                self, "Package", "Machine lib tab is not available."
            )
            return
        gmap = self._group_to_profile(ml)
        yamaha = ml.yamaha_partname_set()
        descs = self._unique_partdesc(ml)
        if not gmap and not yamaha and not descs:
            QtWidgets.QMessageBox.information(
                self,
                "Package",
                "No part groups loaded. Open a Hanwha library or Yamaha files on VIEW · Machine lib.",
            )
            return
        cache = str(getattr(ml, "_hanwha_cache_dir", "") or "")
        stats = import_machine_packages(
            self._store,
            part_groups=gmap.keys(),
            yamaha_names=yamaha,
            extra_tokens=descs,
            group_to_profile=gmap,
            cache_dir=cache,
        )
        self._status.setText(
            f"Imported {stats.mapped} unique packages "
            f"({stats.skipped} unmatched groups skipped, {stats.outlines} outlines)."
        )
        self._reload_table()
        self._on_row_changed()
        self._load_selected_outline()

    def _import_kicad(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select .kicad_mod",
            "",
            "KiCad footprint (*.kicad_mod);;All (*.*)",
        )
        if not path:
            folder = QtWidgets.QFileDialog.getExistingDirectory(
                self, "Or select a folder of .kicad_mod files"
            )
            paths = []
            if folder:
                paths = list(Path(folder).glob("*.kicad_mod"))
        else:
            paths = [Path(path)]
        if not paths:
            return
        n = 0
        for p in paths:
            try:
                imp = parse_kicad_mod_file(p)
            except (OSError, ValueError) as e:
                QtWidgets.QMessageBox.warning(self, "Package", f"{p.name}: {e}")
                continue
            vid = imp.vspd_id or "OTHER"
            self._store.add_alias(imp.name or p.stem, vid, "kicad_mod")
            self._store.add_alias(str(p), vid, "kicad_mod")
            self._store.set_outline_json(vid, outline_to_json(imp.outline))
            n += 1
        self._status.setText(f"Imported {n} .kicad_mod file(s).")
        self._reload_table()

    def _add_vspd(self) -> None:
        new, ok = QtWidgets.QInputDialog.getText(self, "Add VSPD", "New VSPD id:")
        if ok and new.strip():
            self._store.ensure_package(new.strip())
            self._reload_table()

    def _rename_selected(self) -> None:
        vid = self._selected_vspd()
        if not vid:
            return
        new, ok = QtWidgets.QInputDialog.getText(
            self, "Rename VSPD", "New VSPD id:", text=vid
        )
        if ok and new.strip():
            self._store.rename_package(vid, new.strip())
            self._reload_table()

    def _apply_preset_selected(self) -> None:
        vid = self._selected_vspd()
        if not vid:
            return
        preset = self._preset.currentText()
        for a in self._store.aliases_for(vid):
            rewritten = apply_preset(str(a["raw"]), preset)
            hit = parse_package(rewritten)
            if hit.vspd_id and hit.vspd_id != "OTHER":
                self._store.add_alias(str(a["raw"]), hit.vspd_id, str(a["standard"]))
        self._reload_table()
        self._on_row_changed()
