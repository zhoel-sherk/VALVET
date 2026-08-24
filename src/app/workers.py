from typing import Optional

from PySide6 import QtCore

from smt_processor import SMTDataProcessor, SMTProcessorError


class CrossCheckThread(QtCore.QThread):
    """Runs SMTDataProcessor.cross_check() off the GUI thread."""

    result_ready = QtCore.Signal(
        object, str
    )  # DataFrame or None, error message (empty if ok)

    def __init__(self, proc: SMTDataProcessor, parent: Optional[QtCore.QObject] = None):
        super().__init__(parent)
        self._proc = proc

    def run(self) -> None:
        try:
            r = self._proc.cross_check()
        except SMTProcessorError as e:
            self.result_ready.emit(None, str(e))
        except Exception as e:
            self.result_ready.emit(None, str(e))
        else:
            self.result_ready.emit(r, "")
