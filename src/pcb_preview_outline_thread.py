"""Resolve package outlines off the GUI thread."""

from __future__ import annotations

from typing import Optional

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
    ) -> None:
        super().__init__(parent)
        self._names = list(names)
        self._epoch = int(epoch)

    def run(self) -> None:
        if self.isInterruptionRequested():
            return
        packed = resolve_named_outlines(
            self._names, should_stop=self.isInterruptionRequested
        )
        if not self.isInterruptionRequested():
            self.result_ready.emit((self._epoch, packed))
