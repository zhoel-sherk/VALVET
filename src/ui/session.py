"""Session links, valvetpack debug, snapshot recovery (MainWindow mixin)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pandas as pd
from PySide6 import QtWidgets

from facades.session_links import apply_session_links_payload, session_links_to_pairs
from valvetpack import (
    ValvetpackError,
    load_valvetpack,
    save_valvetpack,
)
from working_copy import find_snapshot
from working_copy_ui import prompt_recover_snapshot


class SessionMixin:
    @staticmethod
    def _norm_session_bom_path(p: str) -> str:
        if not p or not os.path.isfile(p):
            return ""
        return os.path.normcase(os.path.abspath(os.path.expanduser(p)))

    def _bom_session_key(self) -> str:
        return self._norm_session_bom_path(self._bom_source_path or "")

    def _register_session_link(self) -> None:
        """Remember that the current BOM and PnP were active together."""
        bk = self._bom_session_key()
        pnp_id = (self._pnp_snapshot_identity_path() or "").strip()
        if not bk or not pnp_id:
            return
        self._session_bom_to_pnp[bk].add(pnp_id)
        self._session_pnp_to_bom[pnp_id].add(bk)

    def _prune_session_links_for_bom(self, bom_key: str) -> None:
        if not bom_key:
            return
        for pid in list(self._session_bom_to_pnp.pop(bom_key, ())):
            s = self._session_pnp_to_bom.get(pid)
            if not s:
                continue
            s.discard(bom_key)
            if not s:
                del self._session_pnp_to_bom[pid]

    def _prune_session_links_for_pnp_identity(self, pnp_id: str) -> None:
        if not pnp_id:
            return
        for bk in list(self._session_pnp_to_bom.pop(pnp_id, ())):
            s = self._session_bom_to_pnp.get(bk)
            if not s:
                continue
            s.discard(pnp_id)
            if not s:
                del self._session_bom_to_pnp[bk]

    def _session_links_to_payload(self) -> list[dict[str, str]]:
        return session_links_to_pairs(self._session_bom_to_pnp)

    def _apply_session_links_payload(self, raw: Any) -> None:
        b2p, p2b = apply_session_links_payload(raw)
        self._session_bom_to_pnp.clear()
        self._session_pnp_to_bom.clear()
        for k, vs in b2p.items():
            self._session_bom_to_pnp[k].update(vs)
        for k, vs in p2b.items():
            self._session_pnp_to_bom[k].update(vs)

    def _collect_related_snapshot_nodes(self) -> list[tuple[str, str]]:
        """(kind, identity_path) for BOM and PnP linked in this session."""
        seen: set[tuple[str, str]] = set()
        stack: list[tuple[str, str]] = []
        if (self._bom_source_path or "").strip() and os.path.isfile(
            self._bom_source_path
        ):
            stack.append(("bom", self._bom_source_path))
        pid = (self._pnp_snapshot_identity_path() or "").strip()
        if pid:
            stack.append(("pnp", pid))
        while stack:
            kind, ident = stack.pop()
            key = (kind, ident)
            if key in seen:
                continue
            seen.add(key)
            if kind == "bom":
                bk = self._norm_session_bom_path(ident)
                if not bk:
                    continue
                for pnp_id in self._session_bom_to_pnp.get(bk, ()):
                    stack.append(("pnp", pnp_id))
            else:
                for bk in self._session_pnp_to_bom.get(ident, ()):
                    stack.append(("bom", bk))
        return list(seen)

    def _debug_recover_all_dirty_snapshots(self) -> None:
        nodes = self._collect_related_snapshot_nodes()
        dirty: list[tuple[str, str, Any]] = []
        for kind, ident in nodes:
            snap = find_snapshot(ident, kind, self._autosave_dir)
            if snap is not None and bool(snap.meta.get("dirty", False)):
                dirty.append((kind, ident, snap))
        if not dirty:
            QtWidgets.QMessageBox.information(
                self,
                self.ui_tr("debug.window_title"),
                self.ui_tr("debug.recover_none"),
            )
            return
        if (
            QtWidgets.QMessageBox.question(
                self,
                self.ui_tr("debug.recover_confirm_title"),
                self.ui_tr("debug.recover_confirm_body", n=len(dirty)),
            )
            != QtWidgets.QMessageBox.StandardButton.Yes
        ):
            return
        for kind, ident, snap in dirty:
            if kind == "bom" and self._norm_session_bom_path(
                self._bom_source_path or ""
            ) == self._norm_session_bom_path(ident):
                self._bom_df = snap.dataframe.copy()
                self._loading_working_copy = True
                self.bom_model.update_dataframe(self._bom_df)
                self._loading_working_copy = False
                self._bom_dirty = True
                self._log(self.ui_tr("debug.recovered_bom"), "info")
            elif kind == "pnp" and (self._pnp_snapshot_identity_path() == ident):
                self._pnp_df = snap.dataframe.copy()
                self._loading_working_copy = True
                self.pnp_model.update_dataframe(self._pnp_df)
                self._loading_working_copy = False
                self._pnp_dirty = True
                self._log(self.ui_tr("debug.recovered_pnp"), "info")
        self._refresh_pcb_preview_from_ui()
        self._hide_merge_cross_check_ok_banner()

    def _debug_gather_mappings_lists(self) -> tuple[list[str], list[str]]:
        bom_maps: list[str] = []
        if getattr(self, "bom_col_combos", None):
            bom_maps = self._mapping_roles_from_combos(self.bom_col_combos)
        pnp_maps: list[str] = []
        if getattr(self, "pnp_col_combos", None):
            pnp_maps = self._mapping_roles_from_combos(self.pnp_col_combos)
        return bom_maps, pnp_maps

    def _pack_include_flags(self) -> dict[str, bool]:
        from valvetpack import PACK_INCLUDE_DEFAULTS, PACK_INCLUDE_KEYS

        flags = dict(PACK_INCLUDE_DEFAULTS)
        pages = getattr(self, "_settings_pages", None)
        boxes = getattr(pages, "_pack_include", None) if pages is not None else None
        if isinstance(boxes, dict):
            for key in PACK_INCLUDE_KEYS:
                chk = boxes.get(key)
                if chk is not None:
                    flags[key] = bool(chk.isChecked())
        return flags

    def _pack_add_file(
        self, extras: dict[str, bytes], arc: str, path: str | None
    ) -> None:
        if not path:
            return
        p = Path(path)
        if not p.is_file():
            return
        extras[arc.replace("\\", "/")] = p.read_bytes()

    def _pack_gather_extra_members(self, flags: dict[str, bool]) -> dict[str, bytes]:
        extras: dict[str, bytes] = {}
        ml = getattr(self, "_machine_library_tab", None)
        pid = (
            self._current_profile_id()
            if hasattr(self, "_current_profile_id")
            else "default"
        )
        if flags.get("mdb") and ml is not None:
            self._pack_add_file(
                extras,
                "files/mdb/" + Path(ml.loaded_mdb_path()).name,
                ml.loaded_mdb_path(),
            )
        if ml is not None:
            cache = Path(ml.hanwha_cache_dir()) if ml.hanwha_cache_dir() else None
            if cache is not None and cache.is_dir():
                from machine_library.hanwha_sqlite_cache import (
                    mdb_copy_path,
                    meta_path,
                    sqlite_path,
                )

                if flags.get("sql_cache"):
                    self._pack_add_file(
                        extras, "files/sql_cache/vision.sqlite", str(sqlite_path(cache))
                    )
                    self._pack_add_file(
                        extras, "files/sql_cache/meta.json", str(meta_path(cache))
                    )
                if flags.get("sql_db"):
                    self._pack_add_file(
                        extras, "files/sql_db/library.mdb", str(mdb_copy_path(cache))
                    )
        if flags.get("sql_db"):
            from app_paths import package_vspd_dir

            self._pack_add_file(
                extras,
                "files/sql_db/vspd.sqlite",
                str(package_vspd_dir(pid) / "vspd.sqlite"),
            )
        excel_suf = {".xlsx", ".xls", ".xlsm", ".ods"}
        if flags.get("excel"):
            for label, src in (
                ("bom", getattr(self, "_bom_source_path", "") or ""),
                ("pnp", getattr(self, "_pnp_source_path", "") or ""),
                ("pnp2", getattr(self, "_pnp_secondary_path", "") or ""),
            ):
                if Path(src).suffix.lower() in excel_suf:
                    self._pack_add_file(
                        extras, f"files/excel/{label}_{Path(src).name}", src
                    )
        if flags.get("gerber"):
            pcb = getattr(self, "_pcb_tab", None)
            layers = getattr(pcb, "_layers", None) if pcb is not None else None
            if layers:
                for i, row in enumerate(layers):
                    gp = str(getattr(row, "path", "") or "")
                    if gp:
                        self._pack_add_file(
                            extras, f"files/gerber/{i:02d}_{Path(gp).name}", gp
                        )
        if flags.get("yamaha") and ml is not None:
            self._pack_add_file(
                extras,
                "files/yamaha/" + Path(ml.loaded_yamaha_tou_path()).name,
                ml.loaded_yamaha_tou_path(),
            )
            self._pack_add_file(
                extras,
                "files/yamaha/" + Path(ml.loaded_yamaha_lib_path()).name,
                ml.loaded_yamaha_lib_path(),
            )
        return extras

    def _pack_restore_extra_members(self, extra: dict[str, bytes]) -> None:
        if not extra:
            return
        from app_paths import hanwha_lib_cache_dir, package_vspd_dir
        from machine_library.hanwha_sqlite_cache import (
            MDB_COPY_NAME,
            META_NAME,
            SQLITE_NAME,
        )

        pid = (
            self._current_profile_id()
            if hasattr(self, "_current_profile_id")
            else "default"
        )
        cache = hanwha_lib_cache_dir(pid)
        restore_root = Path(self._autosave_dir) / "valvetpack_restore"
        restore_root.mkdir(parents=True, exist_ok=True)
        gerber_paths: list[str] = []
        mdb_restore = ""
        wrote_sql = False
        for arc, blob in extra.items():
            name = Path(arc).name
            if arc.startswith("files/sql_cache/"):
                if name == SQLITE_NAME:
                    (cache / SQLITE_NAME).write_bytes(blob)
                    wrote_sql = True
                elif name == META_NAME:
                    (cache / META_NAME).write_bytes(blob)
                    wrote_sql = True
            elif arc.startswith("files/sql_db/"):
                if name == MDB_COPY_NAME:
                    (cache / MDB_COPY_NAME).write_bytes(blob)
                    wrote_sql = True
                elif name == "vspd.sqlite":
                    dest = package_vspd_dir(pid) / "vspd.sqlite"
                    dest.write_bytes(blob)
            elif arc.startswith("files/mdb/"):
                dest = restore_root / "mdb" / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(blob)
                mdb_restore = str(dest)
            elif arc.startswith("files/excel/"):
                dest = restore_root / "excel" / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(blob)
            elif arc.startswith("files/gerber/"):
                dest = restore_root / "gerber" / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(blob)
                gerber_paths.append(str(dest))
            elif arc.startswith("files/yamaha/"):
                dest = restore_root / "yamaha" / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(blob)
                ml = getattr(self, "_machine_library_tab", None)
                if ml is not None:
                    low = name.lower()
                    if low.endswith(".tou"):
                        ml.open_yamaha_tou(str(dest))
                    elif low.endswith(".lib"):
                        ml.open_yamaha_lib(str(dest))
        ml = getattr(self, "_machine_library_tab", None)
        if ml is not None and wrote_sql:
            ml.apply_restored_hanwha_cache(str(cache), mdb_path=mdb_restore)
        elif ml is not None and mdb_restore:
            ml.open_mdb(mdb_restore)
        pcb = getattr(self, "_pcb_tab", None)
        if pcb is not None and gerber_paths:
            load = getattr(pcb, "load_gerber_paths", None)
            if callable(load):
                load(gerber_paths)

    def _debug_save_boomerpack(self, path: str) -> None:
        self._sync_bom_df_from_model()
        self._sync_pnp_df_from_model()
        flags = self._pack_include_flags()
        bom_maps, pnp_maps = self._debug_gather_mappings_lists()
        meta = {
            "bom_path": self._bom_source_path or "",
            "pnp_identity": self._pnp_snapshot_identity_path(),
            "pnp_secondary": self._pnp_secondary_path or "",
            "profile": self._current_profile_id(),
            "bom_mappings": bom_maps,
            "pnp_mappings": pnp_maps,
            "include": flags,
        }
        bom_df = self._bom_df if flags.get("tables") else None
        pnp_df = self._pnp_df if flags.get("tables") else None
        merge_df = self._last_merge_df if flags.get("tables") else None
        profile = None
        if flags.get("profile") and hasattr(self, "_gather_profile_payload"):
            profile = self._gather_profile_payload()
        extras = self._pack_gather_extra_members(flags)
        try:
            save_valvetpack(
                path,
                bom_df=bom_df,
                pnp_df=pnp_df,
                merge_df=merge_df,
                meta=meta,
                profile=profile,
                extra_members=extras,
            )
        except Exception as e:
            self._log(f"Save .valvetpack failed: {e}", "error")
            QtWidgets.QMessageBox.critical(
                self, self.ui_tr("debug.window_title"), str(e)
            )
            return
        self._log(self.ui_tr("debug.saved_boomerpack", path=path), "info")

    def _debug_load_boomerpack(self, path: str) -> None:
        try:
            data = load_valvetpack(path)
        except ValvetpackError as e:
            self._log(str(e), "error")
            QtWidgets.QMessageBox.critical(
                self, self.ui_tr("debug.window_title"), str(e)
            )
            return
        except Exception as e:
            self._log(f"Load .valvetpack failed: {e}", "error")
            QtWidgets.QMessageBox.critical(
                self, self.ui_tr("debug.window_title"), str(e)
            )
            return
        prof = data.get("profile")
        if isinstance(prof, dict) and prof and hasattr(self, "_apply_profile_payload"):
            try:
                self._restoring_settings = True
                self._apply_profile_payload(prof)
            finally:
                self._restoring_settings = False
            self._refresh_application_stylesheet()
            if hasattr(self, "_save_full_profile_snapshot"):
                self._save_full_profile_snapshot()
        meta = data.get("meta") or {}
        bom_df = data.get("bom_df")
        pnp_df = data.get("pnp_df")
        merge_df = data.get("merge_df")
        if bom_df is not None and isinstance(bom_df, pd.DataFrame):
            self._bom_df = bom_df
            self._loading_working_copy = True
            self.bom_model.update_dataframe(self._bom_df)
            self._loading_working_copy = False
            self._bom_dirty = True
            bm = meta.get("bom_mappings")
            if isinstance(bm, list):
                self._profile_restore_bom_mappings = [str(x) for x in bm]
            self._fill_bom_combos()
            self._apply_pending_profile_bom_mappings()
        if pnp_df is not None and isinstance(pnp_df, pd.DataFrame):
            self._pnp_df = pnp_df
            self._loading_working_copy = True
            self.pnp_model.update_dataframe(self._pnp_df)
            self._loading_working_copy = False
            self._pnp_dirty = True
            pm = meta.get("pnp_mappings")
            if isinstance(pm, list):
                self._profile_restore_pnp_mappings = [str(x) for x in pm]
            self._fill_pnp_combos()
            self._apply_pending_profile_pnp_mappings()
        if (
            merge_df is not None
            and isinstance(merge_df, pd.DataFrame)
            and hasattr(self, "merge_model")
        ):
            self._last_merge_df = merge_df
            self.merge_model.update_dataframe(merge_df)
            self._update_merge_layer_export_controls()
        extra = data.get("extra_members") or {}
        if extra:
            self._pack_restore_extra_members(extra)
        self._refresh_pcb_preview_from_ui()
        self._log(self.ui_tr("debug.loaded_boomerpack", path=path), "info")

    def _recover_snapshot_choice(
        self, path: str, kind: str
    ) -> pd.DataFrame | None | str:
        return prompt_recover_snapshot(self, path, kind, self._autosave_dir)
