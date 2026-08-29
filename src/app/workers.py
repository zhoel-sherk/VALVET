import os
from typing import Optional

from PySide6 import QtCore

import logger
import machine_library.hanwha_mdbtools as mdbtools
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
            logger.error("cross_check failed: %s", e)
            self.result_ready.emit(None, str(e))
        except Exception as e:
            logger.error("cross_check failed: %s", e)
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
        if not self._mdb_path or not os.path.isfile(self._mdb_path):
            msg = f"Not a file: {self._mdb_path}"
            logger.error("Hanwha PART_Det load failed: %s", msg)
            self.result_ready.emit(None, msg)
            return
        try:
            from machine_library.access_odbc import ensure_com_sta

            ensure_com_sta()
            df = mdbtools.load_hanwha_machine_lib_dataframe(
                self._mdb_path, progress=self.progress.emit
            )
        except mdbtools.HanwhaMdbToolsError as e:
            logger.error("Hanwha PART_Det load failed: %s", e)
            self.result_ready.emit(None, str(e))
        except Exception as e:
            logger.error("Hanwha PART_Det load failed: %s", e)
            self.result_ready.emit(None, str(e))
        else:
            self.result_ready.emit(df, "")


class HanwhaSqliteImportThread(QtCore.QThread):
    """Copy .mdb into the VALVET profile cache and dump vision tables to SQLite."""

    result_ready = QtCore.Signal(object, str)  # DataFrame or None, error
    progress = QtCore.Signal(int, str)

    def __init__(
        self,
        mdb_path: str,
        cache_dir: str,
        parent: Optional[QtCore.QObject] = None,
        *,
        force: bool = False,
    ) -> None:
        super().__init__(parent)
        self._mdb_path = mdb_path
        self._cache_dir = cache_dir
        self._force = force
        self.load_gen = 0

    def run(self) -> None:
        if not self._mdb_path or not os.path.isfile(self._mdb_path):
            msg = f"Not a file: {self._mdb_path}"
            logger.error("Hanwha SQLite import failed: %s", msg)
            self.result_ready.emit(None, msg)
            return
        try:
            import machine_library.hanwha_sqlite_cache as hanwha_cache
            from machine_library.access_odbc import ensure_com_sta

            ensure_com_sta()
            hanwha_cache.import_mdb_to_cache(
                self._mdb_path,
                self._cache_dir,
                progress=self.progress.emit,
                force=self._force,
            )
            df = hanwha_cache.load_preview_dataframe_from_sqlite(self._cache_dir)
        except Exception as e:
            logger.error("Hanwha SQLite import failed: %s", e)
            self.result_ready.emit(None, str(e))
        else:
            self.result_ready.emit(df, "")


class HanwhaFootprintBuildThread(QtCore.QThread):
    """Load one UPD profile geometry from the SQLite cache (no ODBC)."""

    result_ready = QtCore.Signal(object, str)  # FootprintBuildResult or None, error

    def __init__(
        self,
        cache_dir: str,
        profilename: str,
        *,
        partdesc: str = "",
        parent: Optional[QtCore.QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._cache_dir = cache_dir
        self._profilename = profilename
        self._partdesc = partdesc
        self.load_gen = 0

    def run(self) -> None:
        try:
            import machine_library.hanwha_sqlite_cache as hanwha_cache

            result = hanwha_cache.build_outline_from_sqlite(
                self._cache_dir, self._profilename, partdesc=self._partdesc
            )
        except Exception as e:
            logger.error(
                "Hanwha footprint build failed for %s: %s", self._profilename, e
            )
            self.result_ready.emit(None, str(e))
        else:
            self.result_ready.emit(result, "")
