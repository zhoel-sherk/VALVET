"""Machine library tab: Hanwha UPD ``.mdb`` (PART_Det) and Yamaha ``.tou`` / ``Ver500`` ``.lib``."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Set

import pandas as pd
from PySide6 import QtCore, QtGui, QtWidgets

import logger

from hanwha_mdb_edit.core.column_labels import build_column_header_metadata
from hanwha_mdb_edit.gui import open_hanwha_mdb_editor

from app.workers import HanwhaFootprintBuildThread, HanwhaSqliteImportThread
from machine_library.hanwha_mdbtools import part_det_rows_to_dataframe
from machine_library.hanwha_preview import machine_lib_preview_frame
from machine_library.yamaha_devlib import load_devlib_items
from machine_library.yamaha_tou import load_tou_items
from qt_models import SortableTableModel

if TYPE_CHECKING:
    from PySide6.QtCore import QSettings

# T-OLP ST column / PART_Det.CONFIDENCE_LEVEL — known tiers (see doc/hanwha_UPD_mdb_schema.md).
HANWHA_CONFIDENCE_KNOWN_LEVELS: frozenset[int] = frozenset((0, 10, 20, 40))

from ui.chrome import left_rail_widget
from ui.machine_lib.footprint_preview import FootprintPreviewWidget

_HANWHA_HELP = (
    "Hanwha/Samsung UPD library (.mdb).\n\n"
    "On Windows VALVET copies the .mdb into the VALVET profile cache and dumps "
    "vision tables to SQLite (one ACE/ODBC pass). Row clicks read SQLite only. "
    "Install the Access Database Engine redistributable (same bitness as VALVET) "
    "if import fails. Linux uses mdbtools on PATH.\n\n"
    "Preview columns:\n"
    "• Part name (PARTNAME) — Clean BOM match key\n"
    "• Description (PARTDESC)\n"
    "• Level (CONFIDENCE_LEVEL, T-OLP ST: 0 / 10 / 20 / 40). "
    "0 is templates / not placement-ready — not MASTER/STANDART.\n"
    "• Type (PARTGROUP_Map.UPDPARTGROUPNAME) — Chip-Tantal, CHIP-Circle, "
    "Chip-R0201, … This is the component class. It is not PARENTPROFILE "
    "(parent profile template used in the MDB editor bulk action).\n\n"
    "Level checkboxes only change «From machine library» matching in Clean BOM; "
    "they do not hide rows in this table."
)

_YAMAHA_HELP = (
    "Yamaha machine libraries: .Tou (320-byte records, 40-byte names) and "
    "DevLibEd / DevLibEd2 .Lib files with a Ver500 header.\n\n"
    "Preview columns are PARTNAME, Kind (Tou/Lib), and File. Names feed the "
    "same Clean BOM matching as Hanwha PARTNAME."
)


def _help_button(slot: object) -> QtWidgets.QToolButton:
    btn = QtWidgets.QToolButton()
    btn.setText("?")
    btn.setAutoRaise(True)
    btn.setToolTip("Help")
    btn.clicked.connect(slot)
    return btn


def _elide_label(label: QtWidgets.QLabel, full: str) -> None:
    label.setToolTip(full)
    w = max(60, label.width() - 8)
    label.setText(
        label.fontMetrics().elidedText(full, QtCore.Qt.TextElideMode.ElideMiddle, w)
    )


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

        root = QtWidgets.QHBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)

        left = left_rail_widget()
        left_l = QtWidgets.QVBoxLayout(left)
        left_l.setContentsMargins(0, 0, 8, 0)

        vendor_row = QtWidgets.QHBoxLayout()
        self._vendor_combo = QtWidgets.QComboBox()
        self._vendor_combo.addItem("Hanwha / Samsung (.mdb)", 0)
        self._vendor_combo.addItem("Yamaha (.tou / .lib)", 1)
        self._vendor_combo.currentIndexChanged.connect(self._on_vendor_changed)
        vendor_row.addWidget(self._vendor_combo, 1)
        self._btn_help = _help_button(self._show_vendor_help)
        vendor_row.addWidget(self._btn_help)
        left_l.addLayout(vendor_row)

        self._stack = QtWidgets.QStackedWidget()
        self._stack.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.Maximum,
        )

        hw = QtWidgets.QWidget()
        hw_layout = QtWidgets.QVBoxLayout(hw)
        hw_layout.setContentsMargins(0, 0, 0, 0)

        self._path_label = QtWidgets.QLabel("<no .mdb loaded>")
        self._path_label.setWordWrap(False)
        hw_layout.addWidget(self._path_label)

        browse = QtWidgets.QPushButton("Open .mdb…")
        browse.clicked.connect(self._browse_mdb)
        self._btn_open_mdb = browse
        hw_layout.addWidget(browse)
        reload_btn = QtWidgets.QPushButton("Reload")
        reload_btn.setToolTip(
            "Re-import the .mdb into the profile SQLite cache (PART_Det + vision tables)"
        )
        reload_btn.clicked.connect(self._reload_part_det)
        self._btn_reload_mdb = reload_btn
        hw_layout.addWidget(reload_btn)
        edit_btn = QtWidgets.QPushButton("Edit Hanwha MDB")
        edit_btn.setToolTip("Edit PART_Det in a separate window (Hanwha UPD library)")
        edit_btn.clicked.connect(self._open_hanwha_editor)
        hw_layout.addWidget(edit_btn)
        if sys.platform == "win32":
            ace_btn = QtWidgets.QPushButton("Access ODBC (ACE)…")
            ace_btn.setToolTip(
                "Check for the Microsoft Access ODBC driver; open the ACE redistributable download page"
            )
            ace_btn.clicked.connect(self._show_access_odbc_driver_help)
            hw_layout.addWidget(ace_btn)

        self._tables_label = QtWidgets.QLabel("")
        self._tables_label.setWordWrap(True)
        hw_layout.addWidget(self._tables_label)
        self._mdb_progress = QtWidgets.QProgressBar()
        self._mdb_progress.setMaximumHeight(14)
        self._mdb_progress.setTextVisible(False)
        self._mdb_progress.hide()
        hw_layout.addWidget(self._mdb_progress)

        conf_box = QtWidgets.QGroupBox("Clean BOM — Level")
        conf_layout = QtWidgets.QVBoxLayout(conf_box)
        conf_head = QtWidgets.QHBoxLayout()
        conf_head.addWidget(QtWidgets.QLabel("Include in matching"))
        conf_head.addWidget(_help_button(self._show_level_help), 0)
        conf_head.addStretch(1)
        conf_layout.addLayout(conf_head)
        self._cb_conf_0 = QtWidgets.QCheckBox("0 — not placement-ready")
        self._cb_conf_0.setToolTip(
            "Templates / not placement-ready (often _New* rows). Not MASTER/STANDART and not S-library."
        )
        self._cb_conf_10 = QtWidgets.QCheckBox("10 — newly created")
        self._cb_conf_10.setToolTip("Just created in user/working library.")
        self._cb_conf_20 = QtWidgets.QCheckBox("20 — partially proven")
        self._cb_conf_20.setToolTip("Some placement history; not fully verified.")
        self._cb_conf_40 = QtWidgets.QCheckBox("40 — production ready")
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
            conf_layout.addWidget(w)
        hw_layout.addWidget(conf_box)
        self._load_confidence_filters()
        hw_layout.addStretch(1)
        self._stack.addWidget(hw)

        ym = QtWidgets.QWidget()
        ym_layout = QtWidgets.QVBoxLayout(ym)
        ym_layout.setContentsMargins(0, 0, 0, 0)

        self._yam_tou_label = QtWidgets.QLabel("<no .tou>")
        self._yam_tou_label.setWordWrap(False)
        ym_layout.addWidget(self._yam_tou_label)
        tou_btn = QtWidgets.QPushButton("Open .tou…")
        tou_btn.clicked.connect(self._browse_yamaha_tou)
        ym_layout.addWidget(tou_btn)

        self._yam_lib_label = QtWidgets.QLabel("<no .lib>")
        self._yam_lib_label.setWordWrap(False)
        ym_layout.addWidget(self._yam_lib_label)
        lib_btn = QtWidgets.QPushButton("Open .lib…")
        lib_btn.clicked.connect(self._browse_yamaha_lib)
        ym_layout.addWidget(lib_btn)

        yam_reload = QtWidgets.QPushButton("Reload preview")
        yam_reload.clicked.connect(self._reload_yamaha_preview)
        ym_layout.addWidget(yam_reload)
        ym_layout.addStretch(1)
        self._stack.addWidget(ym)

        left_l.addWidget(self._stack)
        left_l.addStretch(1)
        root.addWidget(left, 0)

        self._hanwha_editor_window: Optional[QtWidgets.QMainWindow] = None
        self._mdb_load_thread: Optional[HanwhaSqliteImportThread] = None
        self._mdb_load_gen = 0
        self._mdb_busy = False
        self._hanwha_cache_dir: str = ""
        self._fp_thread: Optional[HanwhaFootprintBuildThread] = None
        self._fp_gen = 0
        self._fp_pending: Optional[tuple[str, str, int]] = None

        self._table = QtWidgets.QTableView()
        self._table.setAlternatingRowColors(True)
        self._table.setModel(self._table_model)
        self._table.setSortingEnabled(True)
        hdr = self._table.horizontalHeader()
        hdr.setStretchLastSection(False)
        hdr.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Interactive)
        self._table.selectionModel().currentChanged.connect(self._on_table_current_changed)

        self._fp_preview = FootprintPreviewWidget(self)
        self._fp_debounce = QtCore.QTimer(self)
        self._fp_debounce.setSingleShot(True)
        self._fp_debounce.setInterval(150)
        self._fp_debounce.timeout.connect(self._load_selected_footprint)

        split = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        split.addWidget(self._table)
        split.addWidget(self._fp_preview)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        split.setChildrenCollapsible(False)
        root.addWidget(split, 1)
        self._show_hanwha_preview(self._hanwha_df)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        self._refresh_path_elides()

    def _refresh_path_elides(self) -> None:
        _elide_label(self._path_label, self._mdb_path or "<no .mdb loaded>")
        _elide_label(self._yam_tou_label, self._yam_tou_path or "<no .tou>")
        _elide_label(self._yam_lib_label, self._yam_lib_path or "<no .lib>")

    def _show_vendor_help(self) -> None:
        mode = self._vendor_combo.currentData()
        text = _HANWHA_HELP if mode == 0 else _YAMAHA_HELP
        QtWidgets.QMessageBox.information(self, "Machine library", text)

    def _show_level_help(self) -> None:
        QtWidgets.QMessageBox.information(
            self,
            "Clean BOM — Level",
            "PART_Det.CONFIDENCE_LEVEL (T-OLP column ST).\n\n"
            "Unchecked levels are excluded from «From machine library» matching "
            "in Clean BOM. Unknown numeric levels (not 0/10/20/40) stay included "
            "until mapped.\n\n"
            "This table still lists every loaded row. Level is not LIBRARY_TYPE "
            "and 0 is not MASTER/STANDART.",
        )

    def _valvet_profile_id(self) -> str:
        from app.constants import PROFILE_LAST_ACTIVE_KEY

        raw = "default"
        if self._settings is not None:
            raw = str(
                self._settings.value(PROFILE_LAST_ACTIVE_KEY, "default") or "default"
            )
        t = (raw or "default").strip().replace(" ", "_")
        out = re.sub(r"[^a-zA-Z0-9_-]", "", t)
        return out[:64] or "default"

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

    def _show_hanwha_preview(self, frame: pd.DataFrame) -> None:
        view = machine_lib_preview_frame(frame)
        disp, tips = build_column_header_metadata(view.columns)
        self._table_model.update_dataframe(view)
        self._table_model.set_column_header_metadata(disp, tips)

    def _set_mdb_busy(self, busy: bool) -> None:
        for w in (self._btn_open_mdb, self._btn_reload_mdb):
            w.setEnabled(not busy)
        if busy:
            self._mdb_progress.setRange(0, 0)
            self._mdb_progress.show()
        else:
            self._mdb_progress.hide()
            self._mdb_progress.setRange(0, 100)
            self._mdb_progress.setValue(0)
        if busy and not self._mdb_busy:
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
            self._mdb_busy = True
        elif not busy and self._mdb_busy:
            QtWidgets.QApplication.restoreOverrideCursor()
            self._mdb_busy = False

    def _on_vendor_changed(self, _idx: int) -> None:
        mode = self._vendor_combo.currentData()
        self._stack.setCurrentIndex(0 if mode == 0 else 1)
        if mode == 0:
            if self._mdb_path:
                self._start_mdb_load()
            else:
                self._hanwha_df = part_det_rows_to_dataframe([])
                self._show_hanwha_preview(self._hanwha_df)
            self._fp_preview.set_idle("Select a part")
        else:
            self._reload_yamaha_preview()
            self._fp_preview.set_yamaha_placeholder()

    def _browse_mdb(self) -> None:
        start = os.path.expanduser("~")
        if self._settings is not None:
            start = str(self._settings.value("machine_lib/last_mdb_dir", start) or start)
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select Hanwha UPD library (.mdb)",
            start,
            "Access database (*.mdb *.MDB);;All (*.*)",
        )
        if path:
            self._mdb_path = path
            self._refresh_path_elides()
            if self._settings is not None:
                self._settings.setValue(
                    "machine_lib/last_mdb_dir", os.path.dirname(path)
                )
            self._start_mdb_load()

    def _start_mdb_load(self, *, force: bool = False) -> None:
        if not self._mdb_path:
            return
        if self._mdb_load_thread is not None and self._mdb_load_thread.isRunning():
            return
        self._mdb_load_gen += 1
        gen = self._mdb_load_gen
        self._tables_label.setText("Importing .mdb → SQLite cache (one-time ODBC)…")
        lock = Path(self._mdb_path).with_suffix(".ldb")
        if not lock.is_file():
            lock = Path(self._mdb_path).with_suffix(".LDB")
        if lock.is_file():
            self._tables_label.setText(
                "Importing… Access lock (.ldb) found — close the library in Microsoft Access if this stalls."
            )
        self._set_mdb_busy(True)
        from app_paths import hanwha_lib_cache_dir

        cache = str(hanwha_lib_cache_dir(self._valvet_profile_id()))
        self._hanwha_cache_dir = cache
        thread = HanwhaSqliteImportThread(
            self._mdb_path, cache, parent=self, force=force
        )
        thread.load_gen = gen
        self._mdb_load_thread = thread
        thread.result_ready.connect(
            self._on_mdb_load_finished,
            QtCore.Qt.ConnectionType.QueuedConnection,
        )
        thread.progress.connect(
            self._on_mdb_load_progress,
            QtCore.Qt.ConnectionType.QueuedConnection,
        )
        thread.finished.connect(
            self._on_mdb_load_thread_finished,
            QtCore.Qt.ConnectionType.QueuedConnection,
        )
        thread.start()

    def _on_mdb_load_progress(self, pct: int, msg: str) -> None:
        if msg:
            self._tables_label.setText(msg)
        if pct > 0:
            if self._mdb_progress.minimum() == 0 and self._mdb_progress.maximum() == 0:
                self._mdb_progress.setRange(0, 100)
            self._mdb_progress.setValue(min(100, max(0, pct)))

    def _on_mdb_load_finished(self, df: object, err: str) -> None:
        sender = self.sender()
        gen = getattr(sender, "load_gen", None) if sender is not None else None
        if gen is not None and gen != self._mdb_load_gen:
            return
        self._set_mdb_busy(False)
        if err:
            self._tables_label.setText(err.split("\n", 1)[0])
            QtWidgets.QMessageBox.warning(self, "Machine library", err)
            return
        frame = df if isinstance(df, pd.DataFrame) else part_det_rows_to_dataframe([])
        self._hanwha_df = frame
        self._show_hanwha_preview(frame)
        n = 0 if frame is None else len(frame)
        self._tables_label.setText(f"PART_Det: {n} rows (SQLite cache)")

    def _on_mdb_load_thread_finished(self) -> None:
        t = self._mdb_load_thread
        self._mdb_load_thread = None
        if t is not None:
            t.wait(5000)
            t.deleteLater()

    def _reload_part_det(self) -> None:
        if not self._mdb_path:
            QtWidgets.QMessageBox.information(
                self, "Machine library", "Select an .mdb file first."
            )
            return
        self._start_mdb_load(force=True)

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
            self._refresh_path_elides()
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
            self._refresh_path_elides()
            self._reload_yamaha_preview()

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
            empty = pd.DataFrame(columns=["PARTNAME", "Kind", "File"])
            self._table_model.update_dataframe(empty)
            self._table_model.set_column_header_metadata({}, {})
            self._fp_preview.set_yamaha_placeholder()
            return
        self._yamaha_partnames = names
        df = (
            pd.DataFrame(rows)
            if rows
            else pd.DataFrame(columns=["PARTNAME", "Kind", "File"])
        )
        self._table_model.update_dataframe(df)
        self._table_model.set_column_header_metadata({}, {})
        self._fp_preview.set_yamaha_placeholder()

    def _open_hanwha_editor(self) -> None:
        def _sync_path_chosen(p: str) -> None:
            self._mdb_path = p
            self._refresh_path_elides()
            self._start_mdb_load()

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

    def _on_table_current_changed(
        self, current: QtCore.QModelIndex, _prev: QtCore.QModelIndex
    ) -> None:
        if self._vendor_combo.currentData() != 0:
            return
        if not current.isValid():
            self._fp_preview.set_idle("Select a part")
            return
        self._fp_debounce.start()

    def _selected_hanwha_keys(self) -> tuple[str, str, str]:
        """PARTNAME, PROFILENAME, PARTDESC from the current table row."""
        idx = self._table.currentIndex()
        if not idx.isValid():
            return "", "", ""
        row = self._table_model.get_row_values(idx.row())
        partname = str(row.get("PARTNAME") or "").strip()
        partdesc = str(row.get("PARTDESC") or "").strip()
        profilename = partname
        df = self._hanwha_df
        if df is not None and not df.empty and partname and "PARTNAME" in df.columns:
            hit = df[df["PARTNAME"].astype(str) == partname]
            if not hit.empty:
                rec = hit.iloc[0]
                if "PROFILENAME" in hit.columns:
                    pn = str(rec.get("PROFILENAME") or "").strip()
                    if pn:
                        profilename = pn
                if not partdesc and "PARTDESC" in hit.columns:
                    partdesc = str(rec.get("PARTDESC") or "").strip()
        return partname, profilename, partdesc

    def _fp_thread_running(self) -> bool:
        t = self._fp_thread
        if t is None:
            return False
        try:
            from shiboken6 import isValid

            if not isValid(t):
                self._fp_thread = None
                return False
            return bool(t.isRunning())
        except RuntimeError:
            self._fp_thread = None
            return False

    def _load_selected_footprint(self) -> None:
        if self._vendor_combo.currentData() != 0:
            self._fp_preview.set_yamaha_placeholder()
            return
        from machine_library.hanwha_sqlite_cache import sqlite_path as vision_sqlite_path

        if not self._hanwha_cache_dir or not vision_sqlite_path(
            self._hanwha_cache_dir
        ).is_file():
            self._fp_preview.set_idle("Open a Hanwha .mdb first (builds SQLite cache)")
            return
        _part, profile, desc = self._selected_hanwha_keys()
        if not profile:
            self._fp_preview.set_idle("Select a part")
            return
        self._fp_gen += 1
        gen = self._fp_gen
        self._fp_preview.set_loading(profile)
        # One SQLite lookup at a time. Queue the latest row if a load is in flight.
        if self._fp_thread_running():
            self._fp_pending = (profile, desc, gen)
            return
        self._fp_pending = None
        self._start_footprint_thread(profile, desc, gen)

    def _start_footprint_thread(self, profile: str, desc: str, gen: int) -> None:
        thread = HanwhaFootprintBuildThread(
            self._hanwha_cache_dir, profile, partdesc=desc, parent=self
        )
        thread.load_gen = gen
        self._fp_thread = thread
        thread.result_ready.connect(
            self._on_footprint_ready,
            QtCore.Qt.ConnectionType.QueuedConnection,
        )
        thread.finished.connect(
            self._on_fp_thread_finished,
            QtCore.Qt.ConnectionType.QueuedConnection,
        )
        thread.start()

    def _on_fp_thread_finished(self) -> None:
        sender = self.sender()
        if sender is self._fp_thread:
            self._fp_thread = None
        if sender is not None:
            sender.wait(5000)
            sender.deleteLater()
        pending = self._fp_pending
        if pending is None or self._fp_thread_running():
            return
        profile, desc, gen = pending
        if gen != self._fp_gen:
            self._fp_pending = None
            return
        self._fp_pending = None
        self._start_footprint_thread(profile, desc, gen)

    def _on_footprint_ready(self, result: object, err: str) -> None:
        sender = self.sender()
        gen = getattr(sender, "load_gen", None) if sender is not None else None
        if gen is not None and gen != self._fp_gen:
            return
        from pcb_preview.upd_footprint_builder import FootprintBuildResult

        if err:
            self._fp_preview.set_idle(err.split("\n", 1)[0])
            return
        if not isinstance(result, FootprintBuildResult):
            self._fp_preview.set_idle("No geometry")
            return
        _part, profile, _d = self._selected_hanwha_keys()
        try:
            self._fp_preview.show_result(
                result, title=profile or result.partgroup_name
            )
        except Exception as e:
            logger.error("footprint preview paint failed: %s", e)
            self._fp_preview.set_idle(str(e)[:400])

