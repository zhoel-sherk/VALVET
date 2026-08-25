"""Machine library tab: Hanwha UPD ``.mdb`` (PART_Det) and Yamaha ``.tou`` / ``Ver500`` ``.lib``."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Set

import pandas as pd
from PySide6 import QtCore, QtWidgets

from hanwha_mdb_edit.gui import open_hanwha_mdb_editor

from machine_library.hanwha_mdbtools import (
    HanwhaMdbToolsError,
    list_mdb_tables,
    load_part_det_from_mdb,
    part_det_rows_to_dataframe,
)
from machine_library.yamaha_devlib import load_devlib_items
from machine_library.yamaha_tou import load_tou_items
from qt_models import SortableTableModel

if TYPE_CHECKING:
    from PySide6.QtCore import QSettings

# T-OLP ST column / PART_Det.CONFIDENCE_LEVEL — known tiers (see doc/hanwha_UPD_mdb_schema.md).
HANWHA_CONFIDENCE_KNOWN_LEVELS: frozenset[int] = frozenset((0, 10, 20, 40))


class MachineLibraryTab(QtWidgets.QWidget):
    """Browse Hanwha-style ``.mdb`` or Yamaha ``.tou`` / ``.Lib``; preview part names."""

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
        *,
        settings: Optional["QSettings"] = None,
    ):
        super().__init__(parent)
        self._settings = settings
        self._mdb_path: str = ""
        self._yam_tou_path: str = ""
        self._yam_lib_path: str = ""
        self._yamaha_partnames: Set[str] = set()
        self._hanwha_df = part_det_rows_to_dataframe([])
        self._table_model = SortableTableModel(self._hanwha_df)

        layout = QtWidgets.QVBoxLayout(self)

        self._vendor_combo = QtWidgets.QComboBox()
        self._vendor_combo.addItem("Hanwha / Samsung (.mdb)", 0)
        self._vendor_combo.addItem("Yamaha (.tou / .lib)", 1)
        self._vendor_combo.currentIndexChanged.connect(self._on_vendor_changed)
        layout.addWidget(self._vendor_combo)

        self._stack = QtWidgets.QStackedWidget()

        # --- Hanwha page ---
        hw = QtWidgets.QWidget()
        hw_layout = QtWidgets.QVBoxLayout(hw)
        if sys.platform == "win32":
            hint_hw = QtWidgets.QLabel(
                "Hanwha/Samsung UPD library (<b>.mdb</b>): on Windows, VALVET reads via "
                "<b>pyodbc</b> and the <b>Microsoft Access Database Engine (ACE)</b> ODBC driver "
                "(install the redistributable if opening the library fails). "
                "Table <b>PART_Det</b> → column <b>PARTNAME</b> for Clean BOM matching. "
                "Developers with <b>mdbtools</b> on PATH may use it as a fallback when not running a frozen build."
            )
        else:
            hint_hw = QtWidgets.QLabel(
                "Hanwha/Samsung UPD library (<b>.mdb</b>): requires <b>mdbtools</b> "
                "(<code>mdb-tables</code>, <code>mdb-export</code>) on PATH. "
                "Machine component names are in table <b>PART_Det</b> → column <b>PARTNAME</b>."
            )
        hint_hw.setWordWrap(True)
        hint_hw.setTextFormat(QtCore.Qt.TextFormat.RichText)
        hw_layout.addWidget(hint_hw)

        row_hw = QtWidgets.QHBoxLayout()
        self._path_label = QtWidgets.QLabel("<no .mdb loaded>")
        self._path_label.setWordWrap(True)
        row_hw.addWidget(self._path_label, 1)
        browse = QtWidgets.QPushButton("Open .mdb…")
        browse.clicked.connect(self._browse_mdb)
        row_hw.addWidget(browse)
        reload_btn = QtWidgets.QPushButton("Reload PART_Det")
        reload_btn.clicked.connect(self._reload_part_det)
        row_hw.addWidget(reload_btn)
        edit_btn = QtWidgets.QPushButton("EDIT HANWHA MDB")
        edit_btn.setToolTip("Edit PART_Det in a separate window (Hanwha UPD library)")
        edit_btn.clicked.connect(self._open_hanwha_editor)
        row_hw.addWidget(edit_btn)
        if sys.platform == "win32":
            ace_btn = QtWidgets.QPushButton("Access ODBC (ACE)…")
            ace_btn.setToolTip(
                "Check for the Microsoft Access ODBC driver; open the ACE redistributable download page"
            )
            ace_btn.clicked.connect(self._show_access_odbc_driver_help)
            row_hw.addWidget(ace_btn)
        hw_layout.addLayout(row_hw)

        self._tables_label = QtWidgets.QLabel("")
        self._tables_label.setWordWrap(True)
        hw_layout.addWidget(self._tables_label)

        conf_box = QtWidgets.QGroupBox(
            "Clean BOM — include PARTNAME by CONFIDENCE_LEVEL (T-OLP column ST)"
        )
        conf_layout = QtWidgets.QVBoxLayout(conf_box)
        conf_hint = QtWidgets.QLabel(
            "Rows with levels you turn off are excluded from «From machine library» matching in Clean BOM. "
            "Unknown numeric levels (not 0/10/20/40) are still included until mapped."
        )
        conf_hint.setWordWrap(True)
        conf_layout.addWidget(conf_hint)
        row_cb = QtWidgets.QHBoxLayout()
        self._cb_conf_0 = QtWidgets.QCheckBox("0 — not placement-ready (copy only)")
        self._cb_conf_0.setToolTip(
            "Templates / not placement-ready (often _New* rows). Not MASTER/STANDART and not S-library."
        )
        self._cb_conf_10 = QtWidgets.QCheckBox("10 — newly created")
        self._cb_conf_10.setToolTip("Just created in user/working library.")
        self._cb_conf_20 = QtWidgets.QCheckBox("20 — partially proven on line")
        self._cb_conf_20.setToolTip("Some placement history; not fully verified.")
        self._cb_conf_40 = QtWidgets.QCheckBox("40 — production ready (100%)")
        self._cb_conf_40.setToolTip(
            "Machines have placed this part successfully; strongest confidence for Clean matching."
        )
        for w in (
            self._cb_conf_0,
            self._cb_conf_10,
            self._cb_conf_20,
            self._cb_conf_40,
        ):
            w.stateChanged.connect(self._save_confidence_filters)
            row_cb.addWidget(w)
        row_cb.addStretch(1)
        conf_layout.addLayout(row_cb)
        hw_layout.addWidget(conf_box)
        self._load_confidence_filters()

        hw_layout.addStretch(0)
        self._stack.addWidget(hw)

        # --- Yamaha page ---
        ym = QtWidgets.QWidget()
        ym_layout = QtWidgets.QVBoxLayout(ym)
        hint_ym = QtWidgets.QLabel(
            "Yamaha machine libraries: <b>.Tou</b> (320-byte records, 40-byte names) and "
            "<b>DevLibEd / DevLibEd2</b> <b>.Lib</b> files with <code>Ver500</code> header. "
            "Preview fills <b>PARTNAME</b> for the same Clean BOM matching as Hanwha."
        )
        hint_ym.setWordWrap(True)
        hint_ym.setTextFormat(QtCore.Qt.TextFormat.RichText)
        ym_layout.addWidget(hint_ym)

        row_tou = QtWidgets.QHBoxLayout()
        self._yam_tou_label = QtWidgets.QLabel("<no .tou>")
        self._yam_tou_label.setWordWrap(True)
        row_tou.addWidget(self._yam_tou_label, 1)
        tou_btn = QtWidgets.QPushButton("Open .tou…")
        tou_btn.clicked.connect(self._browse_yamaha_tou)
        row_tou.addWidget(tou_btn)
        ym_layout.addLayout(row_tou)

        row_lib = QtWidgets.QHBoxLayout()
        self._yam_lib_label = QtWidgets.QLabel("<no .lib>")
        self._yam_lib_label.setWordWrap(True)
        row_lib.addWidget(self._yam_lib_label, 1)
        lib_btn = QtWidgets.QPushButton("Open .lib…")
        lib_btn.clicked.connect(self._browse_yamaha_lib)
        row_lib.addWidget(lib_btn)
        ym_layout.addLayout(row_lib)

        row_yam_act = QtWidgets.QHBoxLayout()
        yam_reload = QtWidgets.QPushButton("Reload preview")
        yam_reload.clicked.connect(self._reload_yamaha_preview)
        row_yam_act.addWidget(yam_reload)
        row_yam_act.addStretch(1)
        ym_layout.addLayout(row_yam_act)
        ym_layout.addStretch(0)
        self._stack.addWidget(ym)

        layout.addWidget(self._stack)

        self._hanwha_editor_window: Optional[QtWidgets.QMainWindow] = None

        self._table = QtWidgets.QTableView()
        self._table.setAlternatingRowColors(True)
        self._table.setModel(self._table_model)
        layout.addWidget(self._table, 1)

    def loaded_mdb_path(self) -> str:
        """Absolute path of the Hanwha library opened on this tab, or empty."""
        return self._mdb_path or ""

    def hanwha_partname_set(self) -> Set[str]:
        """PARTNAME values from the last loaded Hanwha PART_Det (not the on-screen table in Yamaha mode)."""
        from machine_library.hanwha_partnames import partnames_for_clean

        df = self._hanwha_df
        if df is None or df.empty or "PARTNAME" not in df.columns:
            return set()
        return partnames_for_clean(df, enabled_confidence_levels=self._enabled_confidence_levels())

    def _enabled_confidence_levels(self) -> Set[int]:
        s: Set[int] = set()
        if self._cb_conf_0.isChecked():
            s.add(0)
        if self._cb_conf_10.isChecked():
            s.add(10)
        if self._cb_conf_20.isChecked():
            s.add(20)
        if self._cb_conf_40.isChecked():
            s.add(40)
        return s

    def _load_confidence_filters(self) -> None:
        """Default: all tiers included (same as no filter)."""
        default_on = {0, 10, 20, 40}
        loaded: Set[int] = set()
        if self._settings is not None:
            raw = str(
                self._settings.value("machine_lib/hanwha_confidence_levels", "") or ""
            ).strip()
            if raw:
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, list):
                        for x in parsed:
                            try:
                                xi = int(x)
                                if xi in HANWHA_CONFIDENCE_KNOWN_LEVELS:
                                    loaded.add(xi)
                            except (TypeError, ValueError):
                                pass
                except (json.JSONDecodeError, TypeError):
                    pass
        active = loaded if loaded else default_on
        for w in (
            self._cb_conf_0,
            self._cb_conf_10,
            self._cb_conf_20,
            self._cb_conf_40,
        ):
            w.blockSignals(True)
        try:
            self._cb_conf_0.setChecked(0 in active)
            self._cb_conf_10.setChecked(10 in active)
            self._cb_conf_20.setChecked(20 in active)
            self._cb_conf_40.setChecked(40 in active)
        finally:
            for w in (
                self._cb_conf_0,
                self._cb_conf_10,
                self._cb_conf_20,
                self._cb_conf_40,
            ):
                w.blockSignals(False)

    def _save_confidence_filters(self) -> None:
        if self._settings is None:
            return
        levels = sorted(self._enabled_confidence_levels())
        self._settings.setValue(
            "machine_lib/hanwha_confidence_levels", json.dumps(levels)
        )

    def yamaha_partname_set(self) -> Set[str]:
        """Component names last loaded from Yamaha ``.tou`` / ``.lib`` paths."""
        return set(self._yamaha_partnames)

    def machine_partname_set(self) -> Set[str]:
        """Union of Hanwha PART_Det and Yamaha names (for Clean BOM machine-library match)."""
        return self.hanwha_partname_set() | self.yamaha_partname_set()

    def _on_vendor_changed(self, _idx: int) -> None:
        mode = self._vendor_combo.currentData()
        self._stack.setCurrentIndex(0 if mode == 0 else 1)
        if mode == 0:
            if self._mdb_path:
                self._reload_tables_and_parts()
            else:
                self._hanwha_df = part_det_rows_to_dataframe([])
                self._table_model.update_dataframe(self._hanwha_df)
        else:
            self._reload_yamaha_preview()

    def _browse_mdb(self) -> None:
        start = os.path.expanduser("~")
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select Hanwha UPD library (.mdb)",
            start,
            "Access database (*.mdb *.MDB);;All (*.*)",
        )
        if path:
            self._mdb_path = path
            self._path_label.setText(path)
            self._reload_tables_and_parts()

    def _browse_yamaha_tou(self) -> None:
        start = os.path.expanduser("~")
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select Yamaha .tou",
            start,
            "Yamaha Tou (*.tou *.TOU);;All (*.*)",
        )
        if path:
            self._yam_tou_path = path
            self._yam_tou_label.setText(path)
            self._reload_yamaha_preview()

    def _browse_yamaha_lib(self) -> None:
        start = os.path.expanduser("~")
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select Yamaha DevLib .lib",
            start,
            "Yamaha Lib (*.lib *.LIB);;All (*.*)",
        )
        if path:
            self._yam_lib_path = path
            self._yam_lib_label.setText(path)
            self._reload_yamaha_preview()

    def _reload_tables_and_parts(self) -> None:
        if not self._mdb_path:
            return
        p = Path(self._mdb_path)
        try:
            tables = list_mdb_tables(p)
        except HanwhaMdbToolsError as e:
            self._tables_label.setText(f"mdb-tables: {e}")
            return
        preview = ", ".join(tables[:12])
        if len(tables) > 12:
            preview += f" … (+{len(tables) - 12} more)"
        self._tables_label.setText(f"{len(tables)} tables: {preview}")
        self._reload_part_det()

    def _reload_part_det(self) -> None:
        if not self._mdb_path:
            QtWidgets.QMessageBox.information(
                self, "Machine library", "Select an .mdb file first."
            )
            return
        try:
            rows = load_part_det_from_mdb(self._mdb_path)
        except HanwhaMdbToolsError as e:
            QtWidgets.QMessageBox.warning(self, "Machine library", str(e))
            return
        df = part_det_rows_to_dataframe(rows)
        self._hanwha_df = df
        self._table_model.update_dataframe(df)

    def _reload_yamaha_preview(self) -> None:
        rows: list[dict[str, str]] = []
        names: Set[str] = set()
        try:
            if self._yam_tou_path:
                p = Path(self._yam_tou_path)
                base = p.name
                for _k, variants in load_tou_items(p).items():
                    for nm in variants:
                        names.add(nm)
                        rows.append({"PARTNAME": nm, "Kind": "Tou", "File": base})
            if self._yam_lib_path:
                p = Path(self._yam_lib_path)
                base = p.name
                for _k, variants in load_devlib_items(p).items():
                    for nm in variants:
                        names.add(nm)
                        rows.append({"PARTNAME": nm, "Kind": "Lib", "File": base})
        except OSError as e:
            QtWidgets.QMessageBox.warning(
                self, "Machine library", f"Cannot read Yamaha file: {e}"
            )
            self._yamaha_partnames = set()
            self._table_model.update_dataframe(
                pd.DataFrame(columns=["PARTNAME", "Kind", "File"])
            )
            return
        self._yamaha_partnames = names
        df = (
            pd.DataFrame(rows)
            if rows
            else pd.DataFrame(columns=["PARTNAME", "Kind", "File"])
        )
        self._table_model.update_dataframe(df)

    def _open_hanwha_editor(self) -> None:
        def _sync_path_chosen(p: str) -> None:
            self._mdb_path = p
            self._path_label.setText(p)
            self._reload_tables_and_parts()

        win = open_hanwha_mdb_editor(
            self,
            self._mdb_path or None,
            on_saved=self._reload_part_det,
            on_path_chosen=_sync_path_chosen,
        )
        if win is not None:
            self._hanwha_editor_window = win

    def _show_access_odbc_driver_help(self) -> None:
        """Windows: show ACE/ODBC driver status and optionally open the redistributable page."""
        from PySide6.QtGui import QDesktopServices

        from machine_library.access_odbc import (
            ACCESS_ENGINE_2016_REDIST_URL,
            driver_status_message,
            pick_access_odbc_driver,
        )

        drv = pick_access_odbc_driver()
        msg = driver_status_message(drv)
        if drv:
            QtWidgets.QMessageBox.information(
                self, "Hanwha .mdb — Access ODBC", msg
            )
            return
        r = QtWidgets.QMessageBox.question(
            self,
            "Hanwha .mdb — Access ODBC",
            msg + "\n\nOpen the Microsoft Access Database Engine download page?",
            QtWidgets.QMessageBox.StandardButton.Yes
            | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.Yes,
        )
        if r == QtWidgets.QMessageBox.StandardButton.Yes:
            QDesktopServices.openUrl(QtCore.QUrl(ACCESS_ENGINE_2016_REDIST_URL))
