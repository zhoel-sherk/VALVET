from typing import Optional

from PySide6 import QtCore

from smt_processor import SMTDataProcessor, SMTProcessorError
from machine_library.hanwha_mdbtools import (
    HanwhaMdbToolsError,
    load_hanwha_machine_lib_dataframe,
)


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


class HanwhaPartDetLoadThread(QtCore.QThread):
    """Load PART_Det off the GUI thread (ACE/ODBC or mdbtools can block for minutes)."""

    result_ready = QtCore.Signal(object, str)  # DataFrame or None, error
    progress = QtCore.Signal(int, str)  # 0–100, stage label

    def __init__(self, mdb_path: str, parent: Optional[QtCore.QObject] = None):
        super().__init__(parent)
        self._mdb_path = mdb_path
        self.load_gen = 0

    def run(self) -> None:
        try:
            from machine_library.access_odbc import ensure_com_sta

            ensure_com_sta()
            df = load_hanwha_machine_lib_dataframe(
                self._mdb_path, progress=self.progress.emit
            )
        except HanwhaMdbToolsError as e:
            self.result_ready.emit(None, str(e))
        except Exception as e:
            self.result_ready.emit(None, str(e))
        else:
            self.result_ready.emit(df, "")
