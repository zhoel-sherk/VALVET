"""Background STEP tessellation (pythonocc). Qt allowed here; OCC work stays in occ_load."""

from __future__ import annotations

import threading
from typing import Optional

from PySide6 import QtCore

from step_3d.occ_load import StepLoadResult, load_step_file


class StepLoadThread(QtCore.QThread):
    progress = QtCore.Signal(int, int, str)
    result_ready = QtCore.Signal(object)

    def __init__(
        self,
        path: str,
        lin_deflection: float,
        parent: Optional[QtCore.QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._path = path
        self._lin_deflection = lin_deflection
        self._cancel = threading.Event()

    def request_cancel(self) -> None:
        self._cancel.set()

    def run(self) -> None:
        def progress(done: int, total: int, msg: str) -> None:
            self.progress.emit(int(done), int(total), str(msg))

        result: StepLoadResult = load_step_file(
            self._path,
            lin_deflection=self._lin_deflection,
            should_stop=self._cancel.is_set,
            progress=progress,
        )
        self.result_ready.emit(result)
