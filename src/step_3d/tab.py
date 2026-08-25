"""PySide6 tab: open STEP/STP, tessellate via pythonocc or external CLI, preview in PyVista."""

from __future__ import annotations

import os
import tempfile
from typing import Any, Callable, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from step_3d.conversion import run_step_to_mesh
from step_3d.occ_load import (
    DEFAULT_LIN_DEFLECTION,
    StepLoadResult,
    TessellatedPart,
    clamp_lin_deflection,
    pythonocc_available,
)
from step_3d.viewer_pyvista import PyVistaViewPane

import logger

_SETTINGS_CMD = "step_3d/converter_command"
_SETTINGS_DEFLECT = "step_3d/lin_deflection"
_SETTINGS_BG = "step_3d/bg_color"
_DEFAULT_BG_HEX = "#c0c0c8"
_STEP_FILTER = "STEP files (*.stp *.step *.st);;All files (*.*)"
_LARGE_FILE_BYTES = 40 * 1024 * 1024

_ui_tr_type = Callable[[str], str]


def _has_pyvista_stack() -> bool:
    try:
        import pyvistaqt  # noqa: F401

        import pyvista  # noqa: F401
    except ImportError:
        return False
    return True


class Step3DTabWidget(QtWidgets.QWidget):
    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
        *,
        settings: Any,
        ui_tr: _ui_tr_type,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._ui_tr = ui_tr
        self._temp_mesh: str | None = None
        self._load_thread: Any = None
        self._parts: list[TessellatedPart] = []
        self._tree_items: dict[str, QtWidgets.QTreeWidgetItem] = {}
        self._children: dict[str, list[str]] = {}

        root = QtWidgets.QVBoxLayout(self)
        top = QtWidgets.QHBoxLayout()
        self._btn_open = QtWidgets.QPushButton(self._ui_tr("step_3d.open"))
        self._btn_open.clicked.connect(self._on_open_step)
        top.addWidget(self._btn_open)
        self._btn_cancel = QtWidgets.QPushButton(self._ui_tr("step_3d.cancel_load"))
        self._btn_cancel.clicked.connect(self._on_cancel_load)
        self._btn_cancel.setEnabled(False)
        top.addWidget(self._btn_cancel)
        self._btn_conv = QtWidgets.QPushButton(
            self._ui_tr("step_3d.converter_settings")
        )
        self._btn_conv.setToolTip(self._ui_tr("step_3d.converter_tooltip"))
        self._btn_conv.clicked.connect(self._open_converter_dialog)
        top.addWidget(self._btn_conv)
        self._lab_defl = QtWidgets.QLabel(self._ui_tr("step_3d.deflection"))
        top.addWidget(self._lab_defl)
        self._spin_defl = QtWidgets.QDoubleSpinBox()
        self._spin_defl.setRange(0.05, 5.0)
        self._spin_defl.setSingleStep(0.05)
        self._spin_defl.setDecimals(2)
        self._spin_defl.setValue(self._lin_deflection())
        self._spin_defl.setToolTip(self._ui_tr("step_3d.deflection_tooltip"))
        self._spin_defl.valueChanged.connect(self._on_defl_changed)
        top.addWidget(self._spin_defl)
        self._btn_bg = QtWidgets.QPushButton()
        self._btn_bg.setFixedSize(28, 22)
        self._btn_bg.clicked.connect(self._on_pick_bg)
        self._btn_bg.setToolTip(self._ui_tr("step_3d.bg_color_tooltip"))
        top.addWidget(self._btn_bg)
        self._paint_bg_btn()
        top.addStretch(1)
        root.addLayout(top)

        self._hint = QtWidgets.QLabel()
        self._hint.setWordWrap(True)
        root.addWidget(self._hint)

        self._progress = QtWidgets.QProgressBar()
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        split = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        split.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        self._tree = QtWidgets.QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setMinimumWidth(160)
        self._tree.setUniformRowHeights(True)
        self._tree.itemChanged.connect(self._on_tree_item_changed)
        self._tree.itemSelectionChanged.connect(self._on_tree_selection)
        split.addWidget(self._tree)

        self._stack = QtWidgets.QStackedWidget()
        self._stack.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        split.addWidget(self._stack)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        root.addWidget(split, stretch=1)

        self._placeholder = QtWidgets.QLabel()
        self._placeholder.setWordWrap(True)
        self._placeholder.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignLeft
        )
        self._stack.addWidget(self._placeholder)

        self._pv_capable = _has_pyvista_stack()
        self._view: PyVistaViewPane | None = None
        if self._pv_capable:
            self._placeholder.setMinimumHeight(280)
            self._placeholder.setText("")
            self._stack.setCurrentWidget(self._placeholder)
        else:
            self._placeholder.setText(self._ui_tr("step_3d.msg_missing_pyvista"))
            self._stack.setCurrentWidget(self._placeholder)

        self.refresh_static_texts()

    def refresh_static_texts(self) -> None:
        """Re-apply translated strings (e.g. after UI language change)."""
        self._btn_open.setText(self._ui_tr("step_3d.open"))
        self._btn_cancel.setText(self._ui_tr("step_3d.cancel_load"))
        self._btn_conv.setText(self._ui_tr("step_3d.converter_settings"))
        self._btn_conv.setToolTip(self._ui_tr("step_3d.converter_tooltip"))
        self._spin_defl.setToolTip(self._ui_tr("step_3d.deflection_tooltip"))
        self._lab_defl.setText(self._ui_tr("step_3d.deflection"))
        self._btn_bg.setToolTip(self._ui_tr("step_3d.bg_color_tooltip"))
        self._hint.setText(self._ui_tr("step_3d.hint_mouse"))
        self._tree.setHeaderLabel(self._ui_tr("step_3d.tree_title"))
        if not self._pv_capable:
            self._placeholder.setText(self._ui_tr("step_3d.msg_missing_pyvista"))
        elif self._view is None:
            self._placeholder.setText("")

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        super().showEvent(event)
        if self._pv_capable:
            QtCore.QTimer.singleShot(0, self._try_init_viewer)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        if self._pv_capable and self._view is None and self.isVisible():
            if self.width() >= 64 and self.height() >= 64:
                self._try_init_viewer()

    def _try_init_viewer(self) -> None:
        if not self._pv_capable or self._view is not None:
            return
        if not self.isVisible():
            return
        if self.width() < 64 or self.height() < 64:
            return
        try:
            self._view = PyVistaViewPane(self)
            self._view.set_background_rgb(self._bg_rgb())
            self._view.part_picked.connect(self._on_part_picked)
        except Exception as e:
            logger.error("step_3d: failed to create VTK view: %s", e)
            err_s = str(e)[:800]
            self._placeholder.setText(
                self._ui_tr("step_3d.msg_vtk_init_failed", err=err_s)
            )
            self._stack.setCurrentWidget(self._placeholder)
            return
        self._stack.addWidget(self._view)
        self._stack.setCurrentWidget(self._view)

    def _ensure_viewer(self) -> None:
        """Create the VTK widget on demand (file open or first show)."""
        self._try_init_viewer()

    def _converter_command(self) -> str:
        if self._settings is None:
            return ""
        v = self._settings.value(_SETTINGS_CMD, "")
        return str(v).strip() if v is not None else ""

    def _set_converter_command(self, cmd: str) -> None:
        if self._settings is not None:
            self._settings.setValue(_SETTINGS_CMD, cmd.strip())

    def _lin_deflection(self) -> float:
        if self._settings is None:
            return DEFAULT_LIN_DEFLECTION
        return clamp_lin_deflection(
            self._settings.value(_SETTINGS_DEFLECT, DEFAULT_LIN_DEFLECTION)
        )

    def _on_defl_changed(self, value: float) -> None:
        if self._settings is not None:
            self._settings.setValue(_SETTINGS_DEFLECT, float(value))

    def _bg_hex(self) -> str:
        raw = _DEFAULT_BG_HEX
        if self._settings is not None:
            v = self._settings.value(_SETTINGS_BG, _DEFAULT_BG_HEX)
            if v is not None:
                raw = str(v)
        c = QtGui.QColor(raw)
        if not c.isValid():
            c = QtGui.QColor(_DEFAULT_BG_HEX)
        return c.name()

    def _bg_rgb(self) -> tuple[float, float, float]:
        c = QtGui.QColor(self._bg_hex())
        return (float(c.redF()), float(c.greenF()), float(c.blueF()))

    def _paint_bg_btn(self) -> None:
        hex_c = self._bg_hex()
        self._btn_bg.setStyleSheet(
            f"QPushButton {{ background-color: {hex_c}; border: 1px solid #666; }}"
        )

    def _on_pick_bg(self) -> None:
        start = QtGui.QColor(self._bg_hex())
        chosen = QtWidgets.QColorDialog.getColor(
            start, self, self._ui_tr("step_3d.bg_color")
        )
        if not chosen.isValid():
            return
        hex_c = chosen.name()
        if self._settings is not None:
            self._settings.setValue(_SETTINGS_BG, hex_c)
        self._paint_bg_btn()
        if self._view is not None:
            self._view.set_background_rgb(self._bg_rgb())

    def _open_converter_dialog(self) -> None:
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(self._ui_tr("step_3d.converter_dialog_title"))
        lay = QtWidgets.QVBoxLayout(dlg)
        lab = QtWidgets.QLabel(self._ui_tr("step_3d.converter_dialog_help"))
        lab.setWordWrap(True)
        lay.addWidget(lab)
        edit = QtWidgets.QLineEdit(self._converter_command())
        edit.setPlaceholderText(self._ui_tr("step_3d.converter_placeholder"))
        lay.addWidget(edit)
        row = QtWidgets.QHBoxLayout()
        ok = QtWidgets.QPushButton(self._ui_tr("step_3d.ok"))
        cancel = QtWidgets.QPushButton(self._ui_tr("step_3d.cancel"))
        row.addStretch()
        row.addWidget(ok)
        row.addWidget(cancel)
        lay.addLayout(row)
        ok.clicked.connect(dlg.accept)
        cancel.clicked.connect(dlg.reject)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._set_converter_command(edit.text())

    def _cleanup_temp_mesh(self) -> None:
        if self._temp_mesh and os.path.isfile(self._temp_mesh):
            try:
                os.unlink(self._temp_mesh)
            except OSError:
                pass
        self._temp_mesh = None

    def _on_open_step(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            self._ui_tr("step_3d.open_dialog_title"),
            "",
            _STEP_FILTER,
        )
        if not path:
            return
        if not self._pv_capable:
            QtWidgets.QMessageBox.warning(
                self,
                self._ui_tr("step_3d.msg_title_error"),
                self._ui_tr("step_3d.msg_missing_pyvista"),
            )
            return
        self._ensure_viewer()
        if self._view is None:
            QtWidgets.QMessageBox.warning(
                self,
                self._ui_tr("step_3d.msg_title_error"),
                self._ui_tr("step_3d.msg_vtk_init_failed_short"),
            )
            return
        use_occ = pythonocc_available()
        cmd_tpl = self._converter_command()
        if not use_occ and not cmd_tpl:
            QtWidgets.QMessageBox.information(
                self,
                self._ui_tr("step_3d.msg_title_converter"),
                self._ui_tr("step_3d.msg_missing_backend"),
            )
            self._open_converter_dialog()
            cmd_tpl = self._converter_command()
            if not cmd_tpl:
                return
        try:
            size = os.path.getsize(path)
        except OSError:
            size = 0
        if size >= _LARGE_FILE_BYTES:
            QtWidgets.QMessageBox.information(
                self,
                self._ui_tr("step_3d.msg_title_error"),
                self._ui_tr("step_3d.msg_large_file"),
            )
            if self._spin_defl.value() <= 0.31:
                self._spin_defl.setValue(1.0)
        if use_occ:
            self._start_occ_load(path)
            return
        self._load_via_cli(path, cmd_tpl)

    def _start_occ_load(self, path: str) -> None:
        from step_3d.worker import StepLoadThread

        if self._load_thread is not None and self._load_thread.isRunning():
            return
        self._btn_open.setEnabled(False)
        self._btn_cancel.setEnabled(True)
        self._progress.setVisible(True)
        self._progress.setRange(0, 0)
        self._progress.setFormat(self._ui_tr("step_3d.loading"))
        thread = StepLoadThread(path, self._spin_defl.value(), self)
        thread.progress.connect(self._on_occ_progress)
        thread.result_ready.connect(self._on_occ_result)
        thread.finished.connect(self._on_occ_thread_finished)
        self._load_thread = thread
        thread.start()

    def _on_occ_progress(self, done: int, total: int, msg: str) -> None:
        if total > 0:
            self._progress.setRange(0, max(total, 1))
            self._progress.setValue(min(done, total))
        else:
            self._progress.setRange(0, 0)
        self._progress.setFormat(f"{msg} (%v/%m)" if total > 0 else msg)

    def _on_occ_result(self, result: object) -> None:
        if not isinstance(result, StepLoadResult):
            return
        if result.cancelled:
            logger.info("step_3d: load cancelled")
            QtWidgets.QMessageBox.information(
                self,
                self._ui_tr("step_3d.msg_title_error"),
                self._ui_tr("step_3d.msg_cancelled"),
            )
            return
        if result.error:
            logger.error("step_3d: OCC load failed: %s", result.error)
            QtWidgets.QMessageBox.critical(
                self,
                self._ui_tr("step_3d.msg_title_error"),
                self._ui_tr("step_3d.msg_occ_failed", err=result.error),
            )
            return
        if self._view is None:
            return
        self._cleanup_temp_mesh()
        self._parts = list(result.parts)
        n_mesh = sum(1 for p in self._parts if p.has_mesh)
        try:
            self._view.load_parts(self._parts, show_edges=False)
        except Exception as e:
            logger.error("step_3d: pyvista parts load failed: %s", e)
            QtWidgets.QMessageBox.critical(
                self,
                self._ui_tr("step_3d.msg_title_error"),
                str(e),
            )
            return
        self._rebuild_tree()
        if n_mesh < 1:
            QtWidgets.QMessageBox.warning(
                self,
                self._ui_tr("step_3d.msg_title_error"),
                self._ui_tr("step_3d.msg_empty_mesh"),
            )
        logger.info(
            "step_3d: loaded OCC mesh from %s (%s parts)",
            result.source_path,
            n_mesh,
        )

    def _on_occ_thread_finished(self) -> None:
        self._btn_open.setEnabled(True)
        self._btn_cancel.setEnabled(False)
        self._progress.setVisible(False)
        thread = self._load_thread
        self._load_thread = None
        if thread is not None:
            thread.deleteLater()

    def _on_cancel_load(self) -> None:
        if self._load_thread is not None:
            self._load_thread.request_cancel()

    def _rebuild_tree(self) -> None:
        self._tree.blockSignals(True)
        self._tree.clear()
        items: dict[str, QtWidgets.QTreeWidgetItem] = {}
        for part in self._parts:
            item = QtWidgets.QTreeWidgetItem([part.name])
            item.setData(0, QtCore.Qt.ItemDataRole.UserRole, part.id)
            item.setCheckState(0, QtCore.Qt.CheckState.Checked)
            items[part.id] = item
        for part in self._parts:
            item = items[part.id]
            parent = items.get(part.parent_id) if part.parent_id else None
            if parent is None:
                self._tree.addTopLevelItem(item)
            else:
                parent.addChild(item)
        self._tree_items = items
        children: dict[str, list[str]] = {}
        for part in self._parts:
            if part.parent_id:
                children.setdefault(part.parent_id, []).append(part.id)
        self._children = children
        for i in range(min(self._tree.topLevelItemCount(), 32)):
            top = self._tree.topLevelItem(i)
            if top is not None:
                top.setExpanded(True)
        self._tree.blockSignals(False)

    def _subtree_ids(self, part_id: str) -> list[str]:
        out: list[str] = []
        stack = [part_id]
        while stack:
            pid = stack.pop()
            out.append(pid)
            kids = self._children.get(pid)
            if kids:
                stack.extend(kids)
        return out

    def _on_tree_item_changed(self, item: QtWidgets.QTreeWidgetItem, column: int) -> None:
        if self._view is None:
            return
        pid = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        if not pid:
            return
        visible = item.checkState(0) == QtCore.Qt.CheckState.Checked
        ids = self._subtree_ids(str(pid))
        want = (
            QtCore.Qt.CheckState.Checked if visible else QtCore.Qt.CheckState.Unchecked
        )
        self._tree.blockSignals(True)
        try:
            for child_id in ids[1:]:
                child_item = self._tree_items.get(child_id)
                if child_item is not None and child_item.checkState(0) != want:
                    child_item.setCheckState(0, want)
        finally:
            self._tree.blockSignals(False)
        self._view.set_parts_visible(ids, visible)

    def _on_tree_selection(self) -> None:
        if self._view is None:
            return
        items = self._tree.selectedItems()
        if not items:
            self._view.highlight_part(None)
            return
        pid = items[0].data(0, QtCore.Qt.ItemDataRole.UserRole)
        self._view.highlight_part(str(pid) if pid else None)

    def _on_part_picked(self, part_id: str) -> None:
        item = self._tree_items.get(part_id)
        if item is None:
            self._view.highlight_part(part_id) if self._view else None
            return
        self._tree.blockSignals(True)
        self._tree.setCurrentItem(item)
        self._tree.blockSignals(False)
        if self._view is not None:
            self._view.highlight_part(part_id)

    def _load_via_cli(self, path: str, cmd_tpl: str) -> None:
        fd, tmp_path = tempfile.mkstemp(prefix="valvet_step3d_", suffix=".obj")
        os.close(fd)
        try:
            res = run_step_to_mesh(path, tmp_path, command_template=cmd_tpl)
        except Exception as e:
            self._cleanup_temp_mesh()
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            logger.error("step_3d: conversion raised: %s", e)
            QtWidgets.QMessageBox.critical(
                self,
                self._ui_tr("step_3d.msg_title_error"),
                str(e),
            )
            return

        if not res.ok:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            logger.error(
                "step_3d: converter failed rc=%s cmd=%s log=%s",
                res.returncode,
                res.command_display,
                res.combined_log,
            )
            detail = res.combined_log.strip()
            if len(detail) > 4000:
                detail = detail[:4000] + "\n…"
            body = self._ui_tr("step_3d.msg_conversion_failed", rc=res.returncode)
            if detail:
                body = f"{body}\n\n{detail}"
            QtWidgets.QMessageBox.critical(
                self,
                self._ui_tr("step_3d.msg_title_error"),
                body,
            )
            return

        self._cleanup_temp_mesh()
        self._temp_mesh = tmp_path
        try:
            assert self._view is not None
            self._view.load_mesh_path(tmp_path, show_edges=False)
        except Exception as e:
            logger.error("step_3d: pyvista load failed: %s", e)
            self._cleanup_temp_mesh()
            QtWidgets.QMessageBox.critical(
                self,
                self._ui_tr("step_3d.msg_title_error"),
                str(e),
            )
            return
        self._parts = [
            TessellatedPart(id="cli_mesh", name=os.path.basename(path), parent_id=None)
        ]
        self._rebuild_tree()
        logger.info("step_3d: loaded mesh from %s", path)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self._on_cancel_load()
        if self._load_thread is not None:
            self._load_thread.wait(2000)
        self._cleanup_temp_mesh()
        super().closeEvent(event)
