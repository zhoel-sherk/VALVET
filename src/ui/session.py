"""Session links, valvetpack debug, snapshot recovery (MainWindow mixin)."""

from __future__ import annotations

import os
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

    def _debug_save_boomerpack(self, path: str) -> None:
        self._sync_bom_df_from_model()
        self._sync_pnp_df_from_model()
        bom_maps, pnp_maps = self._debug_gather_mappings_lists()
        meta = {
            "saved_at": "",
            "bom_path": self._bom_source_path or "",
            "pnp_identity": self._pnp_snapshot_identity_path(),
            "pnp_secondary": self._pnp_secondary_path or "",
            "profile": self._current_profile_id(),
            "bom_mappings": bom_maps,
            "pnp_mappings": pnp_maps,
        }
        try:
            save_valvetpack(
                path,
                bom_df=self._bom_df,
                pnp_df=self._pnp_df,
                merge_df=self._last_merge_df,
                meta=meta,
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
        self._refresh_pcb_preview_from_ui()
        self._log(self.ui_tr("debug.loaded_boomerpack", path=path), "info")

    def _recover_snapshot_choice(
        self, path: str, kind: str
    ) -> pd.DataFrame | None | str:
        return prompt_recover_snapshot(self, path, kind, self._autosave_dir)
