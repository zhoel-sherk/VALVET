"""Resolve package outlines off the GUI thread."""

from __future__ import annotations

from typing import Mapping, Optional

from PySide6 import QtCore

from pcb_preview.outline_resolve import resolve_named_outlines


class PackageOutlineThread(QtCore.QThread):
    """Batch-resolve unique footprint names to FootprintOutlineMM."""

    result_ready = QtCore.Signal(object)

    def __init__(
        self,
        names: list[str],
        epoch: int,
        parent: Optional[QtCore.QObject] = None,
        *,
        mdb_cache_dir: str = "",
        group_to_profile: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(parent)
        self._names = list(names)
        self._epoch = int(epoch)
        self._mdb_cache_dir = (mdb_cache_dir or "").strip()
        self._group_to_profile = dict(group_to_profile or {})

    def run(self) -> None:
        if self.isInterruptionRequested():
            return
        packed = resolve_named_outlines(
            self._names,
            should_stop=self.isInterruptionRequested,
            mdb_cache_dir=self._mdb_cache_dir or None,
            group_to_profile=self._group_to_profile,
        )
        if not self.isInterruptionRequested():
            self.result_ready.emit((self._epoch, packed))
