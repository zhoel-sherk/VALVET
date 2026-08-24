"""PySide6 tab: open STEP/STP, convert via external CLI, preview mesh in PyVista."""

from __future__ import annotations

import os
import tempfile
from typing import Any, Callable, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from step_3d.conversion import run_step_to_mesh
from step_3d.viewer_pyvista import PyVistaViewPane

import logger

_SETTINGS_CMD = "step_3d/converter_command"

_STEP_FILTER = "STEP files (*.stp *.step *.st);;All files (*.*)"

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

        root = QtWidgets.QVBoxLayout(self)
        top = QtWidgets.QHBoxLayout()
        self._btn_open = QtWidgets.QPushButton(self._ui_tr("step_3d.open"))
        self._btn_open.clicked.connect(self._on_open_step)
        top.addWidget(self._btn_open)
        self._btn_conv = QtWidgets.QPushButton(
            self._ui_tr("step_3d.converter_settings")
        )
        self._btn_conv.setToolTip(self._ui_tr("step_3d.converter_tooltip"))
        self._btn_conv.clicked.connect(self._open_converter_dialog)
        top.addWidget(self._btn_conv)
        top.addStretch(1)
        root.addLayout(top)

        self._hint = QtWidgets.QLabel()
        self._hint.setWordWrap(True)
        root.addWidget(self._hint)

        self._stack = QtWidgets.QStackedWidget()
        self._stack.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        root.addWidget(self._stack, stretch=1)

        self._placeholder = QtWidgets.QLabel()
        self._placeholder.setWordWrap(True)
        self._placeholder.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignLeft
        )
        self._stack.addWidget(self._placeholder)

        # Defer VTK/QtInteractor until this tab is actually shown with a real size.
        # Eager construction while the tab is hidden triggers X11 BadWindow / vtkXOpenGLRenderWindow errors on Linux.
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
        self._btn_conv.setText(self._ui_tr("step_3d.converter_settings"))
        self._btn_conv.setToolTip(self._ui_tr("step_3d.converter_tooltip"))
        self._hint.setText(self._ui_tr("step_3d.hint_mouse"))
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
        cmd_tpl = self._converter_command()
        if not cmd_tpl:
            QtWidgets.QMessageBox.information(
                self,
                self._ui_tr("step_3d.msg_title_converter"),
                self._ui_tr("step_3d.msg_missing_converter"),
            )
            self._open_converter_dialog()
            cmd_tpl = self._converter_command()
            if not cmd_tpl:
                return

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
            self._view.load_mesh_path(tmp_path)
        except Exception as e:
            logger.error("step_3d: pyvista load failed: %s", e)
            self._cleanup_temp_mesh()
            QtWidgets.QMessageBox.critical(
                self,
                self._ui_tr("step_3d.msg_title_error"),
                str(e),
            )
            return
        logger.info("step_3d: loaded mesh from %s", path)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self._cleanup_temp_mesh()
        super().closeEvent(event)
