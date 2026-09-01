"""Project tab layout (thin UI — widgets and signals only)."""

from __future__ import annotations

import os
from typing import Any, Callable

from PySide6 import QtCore, QtGui, QtWidgets

from themes.fonts_loader import build_mono_font
from ui_i18n import UI_LANGUAGE_OPTIONS


class PathLabel(QtWidgets.QLabel):
    """Basename + middle-elide; full path in tooltip; re-elides on resize."""

    def __init__(
        self, empty_text: str = "", parent: QtWidgets.QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._full_path = ""
        self._empty_text = empty_text
        self.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        self.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.MinimumExpanding,
        )
        self.setMinimumHeight(40)
        self.setText(empty_text)

    def set_path(self, path: str, *, empty_text: str | None = None) -> None:
        if empty_text is not None:
            self._empty_text = empty_text
        self._full_path = path or ""
        self._relayout()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._relayout()

    def _relayout(self) -> None:
        if self._full_path:
            base = os.path.basename(self._full_path)
            width = max(self.width() - 4, 80)
            elided = self.fontMetrics().elidedText(
                base, QtCore.Qt.TextElideMode.ElideMiddle, width
            )
            self.setText(elided)
            self.setToolTip(self._full_path)
        else:
            self.setText(self._empty_text)
            self.setToolTip("")


def configure_path_label(
    label: QtWidgets.QLabel, path: str, *, empty_text: str
) -> None:
    """Show basename with middle-elide; full path in tooltip."""
    if isinstance(label, PathLabel):
        label.set_path(path, empty_text=empty_text)
        return
    label.setTextFormat(QtCore.Qt.TextFormat.PlainText)
    label.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
    label.setSizePolicy(
        QtWidgets.QSizePolicy.Policy.Expanding,
        QtWidgets.QSizePolicy.Policy.Preferred,
    )
    if path:
        base = os.path.basename(path)
        fm = label.fontMetrics()
        width = max(label.width(), 120)
        elided = fm.elidedText(base, QtCore.Qt.TextElideMode.ElideMiddle, width)
        label.setText(elided)
        label.setToolTip(path)
    else:
        label.setText(empty_text)
        label.setToolTip("")


def _drop_local_path(
    event: QtGui.QDropEvent | QtGui.QDragEnterEvent | QtGui.QDragMoveEvent,
    *,
    allow_dirs: bool = False,
    suffixes: tuple[str, ...] | None = None,
) -> str:
    """First local path that matches file/dir rules, or empty."""
    if not event.mimeData().hasUrls():
        return ""
    for url in event.mimeData().urls():
        if not url.isLocalFile():
            continue
        path = url.toLocalFile()
        if not path:
            continue
        if os.path.isdir(path):
            if allow_dirs:
                return path
            continue
        if os.path.isfile(path):
            if suffixes:
                low = path.lower()
                if not any(low.endswith(s) for s in suffixes):
                    continue
            return path
    return ""


class DropGroupBox(QtWidgets.QGroupBox):
    """Group box that accepts file drops and forwards them to MainWindow handlers."""

    def __init__(
        self,
        title: str,
        win: Any,
        on_drop: Callable[[str], None],
        *,
        parent: QtWidgets.QWidget | None = None,
        allow_dirs: bool = False,
        suffixes: tuple[str, ...] | None = None,
    ) -> None:
        super().__init__(title, parent)
        self._win = win
        self._on_drop = on_drop
        self._allow_dirs = allow_dirs
        self._suffixes = suffixes
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:
        if _drop_local_path(
            event, allow_dirs=self._allow_dirs, suffixes=self._suffixes
        ):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QtGui.QDragMoveEvent) -> None:
        if _drop_local_path(
            event, allow_dirs=self._allow_dirs, suffixes=self._suffixes
        ):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QtGui.QDropEvent) -> None:
        path = _drop_local_path(
            event, allow_dirs=self._allow_dirs, suffixes=self._suffixes
        )
        if path:
            self._on_drop(path)
            event.acceptProposedAction()
            return
        event.ignore()


class DropRowWidget(QtWidgets.QWidget):
    """Drop target row (PnP slots, Yamaha tou/lib)."""

    def __init__(
        self,
        win: Any,
        on_drop: Callable[[str], None],
        *,
        parent: QtWidgets.QWidget | None = None,
        allow_dirs: bool = False,
        suffixes: tuple[str, ...] | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_drop = on_drop
        self._allow_dirs = allow_dirs
        self._suffixes = suffixes
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:
        if _drop_local_path(
            event, allow_dirs=self._allow_dirs, suffixes=self._suffixes
        ):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QtGui.QDragMoveEvent) -> None:
        if _drop_local_path(
            event, allow_dirs=self._allow_dirs, suffixes=self._suffixes
        ):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QtGui.QDropEvent) -> None:
        path = _drop_local_path(
            event, allow_dirs=self._allow_dirs, suffixes=self._suffixes
        )
        if path:
            self._on_drop(path)
            event.acceptProposedAction()
            return
        event.ignore()


def _clear_file_button(win: Any, slot: Callable[[], None]) -> QtWidgets.QPushButton:
    btn = QtWidgets.QPushButton(win.ui_tr("project.pnp_clear_optional"))
    btn.setMaximumWidth(88)
    btn.clicked.connect(slot)
    return btn


def setup_project_tab(win: Any, layout: QtWidgets.QVBoxLayout) -> None:
    """Populate ``layout`` on the Project tab; attributes live on ``win`` (MainWindow)."""
    import sys

    from ui.chrome import (
        ACTION_BTN_MIN_H,
        CHROME_SPACING,
        action_button,
        apply_equal_widths,
        help_button,
        switch_checkbox,
    )

    top = QtWidgets.QGridLayout()
    top.setSpacing(CHROME_SPACING)
    top.setColumnStretch(0, 1)
    top.setColumnStretch(1, 1)

    win.project_load_group = QtWidgets.QGroupBox(win.ui_tr("project.load_files"))
    load_inner = QtWidgets.QVBoxLayout(win.project_load_group)
    load_inner.setSpacing(CHROME_SPACING)

    win.project_bom_group = DropGroupBox(
        win.ui_tr("project.bom_file"), win, win._load_bom
    )
    bom_layout = QtWidgets.QVBoxLayout(win.project_bom_group)
    win.bom_path_label = PathLabel(win.ui_tr("project.no_file"))
    bom_layout.addWidget(win.bom_path_label)
    bom_btns = QtWidgets.QHBoxLayout()
    win.btn_clear_bom_file = _clear_file_button(win, win._confirm_clear_bom_workspace)
    bom_btns.addWidget(win.btn_clear_bom_file)
    win.btn_browse_bom = action_button(win.ui_tr("project.browse_bom"))
    win.btn_browse_bom.clicked.connect(win._browse_bom)
    bom_btns.addWidget(win.btn_browse_bom, 1)
    bom_layout.addLayout(bom_btns)

    load_inner.addWidget(win.project_bom_group)

    win.project_pnp_group = DropGroupBox(
        win.ui_tr("project.pnp_file"), win, win._load_pnp
    )
    pnp_outer = QtWidgets.QVBoxLayout(win.project_pnp_group)

    row1 = DropRowWidget(win, win._load_pnp)
    row1_layout = QtWidgets.QVBoxLayout(row1)
    row1_layout.setContentsMargins(0, 0, 0, 0)
    win.pnp_path_label = PathLabel(win.ui_tr("project.no_file"))
    row1_layout.addWidget(win.pnp_path_label)
    pnp_btns = QtWidgets.QHBoxLayout()
    win.btn_clear_pnp_file = _clear_file_button(win, win._confirm_clear_pnp_workspace)
    pnp_btns.addWidget(win.btn_clear_pnp_file)
    win.btn_browse_pnp = action_button(win.ui_tr("project.browse_pnp"))
    win.btn_browse_pnp.clicked.connect(win._browse_pnp)
    pnp_btns.addWidget(win.btn_browse_pnp, 1)
    row1_layout.addLayout(pnp_btns)
    pnp_outer.addWidget(row1)

    row2 = DropRowWidget(win, win._drop_pnp_secondary)
    row2_layout = QtWidgets.QVBoxLayout(row2)
    row2_layout.setContentsMargins(0, 0, 0, 0)
    win.pnp_path2_label = PathLabel(win.ui_tr("project.no_file"))
    row2_layout.addWidget(win.pnp_path2_label)
    pnp2_btns = QtWidgets.QHBoxLayout()
    win.btn_clear_pnp_optional = _clear_file_button(win, win._clear_pnp_secondary_only)
    pnp2_btns.addWidget(win.btn_clear_pnp_optional)
    win.btn_browse_pnp2 = action_button(win.ui_tr("project.browse_pnp2"))
    win.btn_browse_pnp2.clicked.connect(win._browse_pnp_secondary)
    pnp2_btns.addWidget(win.btn_browse_pnp2, 1)
    win.btn_pnp2_help = help_button(win._show_pnp2_help)
    win.btn_pnp2_help.setToolTip(win.ui_tr("project.pnp2_help_title"))
    win.btn_pnp2_help.setMinimumHeight(ACTION_BTN_MIN_H)
    pnp2_btns.addWidget(win.btn_pnp2_help)
    row2_layout.addLayout(pnp2_btns)
    pnp_outer.addWidget(row2)

    row3 = QtWidgets.QHBoxLayout()
    win.chk_pnp_layer_override = QtWidgets.QCheckBox(
        win.ui_tr("project.pnp_layer_override")
    )
    win.chk_pnp_layer_override.setToolTip(win.ui_tr("project.pnp_layer_override_tip"))
    win.chk_pnp_layer_override.toggled.connect(win._on_pnp_layer_override_toggled)
    win.chk_pnp_layer_override.toggled.connect(
        lambda *_: win._schedule_pnp_layer_prefs_reload()
    )
    row3.addWidget(win.chk_pnp_layer_override)
    win.edit_pnp_layer_tokens = QtWidgets.QLineEdit()
    win.edit_pnp_layer_tokens.setPlaceholderText(
        win.ui_tr("project.pnp_layer_tokens_placeholder")
    )
    win.edit_pnp_layer_tokens.setMaximumWidth(220)
    win.edit_pnp_layer_tokens.setEnabled(False)
    win.edit_pnp_layer_tokens.setToolTip(win.ui_tr("project.pnp_layer_override_tip"))
    win.edit_pnp_layer_tokens.textEdited.connect(
        lambda *_: win._schedule_pnp_layer_prefs_reload()
    )
    row3.addWidget(win.edit_pnp_layer_tokens)
    row3.addStretch(1)
    pnp_outer.addLayout(row3)

    load_inner.addWidget(win.project_pnp_group)

    win.project_hanwha_group = DropGroupBox(
        win.ui_tr("project.hanwha_mdb"),
        win,
        win._drop_hanwha_mdb,
        suffixes=(".mdb",),
    )
    han_l = QtWidgets.QVBoxLayout(win.project_hanwha_group)
    win.hanwha_mdb_path_label = PathLabel(win.ui_tr("project.no_file"))
    han_l.addWidget(win.hanwha_mdb_path_label)
    han_btns = QtWidgets.QHBoxLayout()
    win.btn_clear_hanwha_mdb = _clear_file_button(win, win._clear_hanwha_mdb)
    han_btns.addWidget(win.btn_clear_hanwha_mdb)
    win.btn_open_mdb = action_button(win.ui_tr("project.open_mdb"))
    win.btn_open_mdb.clicked.connect(win._browse_hanwha_mdb)
    han_btns.addWidget(win.btn_open_mdb, 1)
    han_l.addLayout(han_btns)
    win.btn_access_odbc = None
    if sys.platform == "win32":
        win.btn_access_odbc = action_button(win.ui_tr("project.access_odbc"))
        win.btn_access_odbc.setToolTip(win.ui_tr("project.access_odbc_tip"))
        win.btn_access_odbc.clicked.connect(win._show_access_odbc_help)
        han_l.addWidget(win.btn_access_odbc)
    load_inner.addWidget(win.project_hanwha_group)

    win.project_yamaha_group = QtWidgets.QGroupBox(win.ui_tr("project.yamaha_libs"))
    yam_outer = QtWidgets.QVBoxLayout(win.project_yamaha_group)
    yam_tou_row = DropRowWidget(
        win,
        win._drop_yamaha_tou,
        allow_dirs=True,
        suffixes=(".tou",),
    )
    yam_tou_l = QtWidgets.QVBoxLayout(yam_tou_row)
    yam_tou_l.setContentsMargins(0, 0, 0, 0)
    win.yamaha_tou_path_label = PathLabel(win.ui_tr("project.no_file"))
    yam_tou_l.addWidget(win.yamaha_tou_path_label)
    tou_btns = QtWidgets.QHBoxLayout()
    win.btn_clear_yamaha_tou = _clear_file_button(win, win._clear_yamaha_tou)
    tou_btns.addWidget(win.btn_clear_yamaha_tou)
    win.btn_open_tou = action_button(win.ui_tr("project.open_tou"))
    win.btn_open_tou.clicked.connect(win._browse_yamaha_tou)
    tou_btns.addWidget(win.btn_open_tou, 1)
    yam_tou_l.addLayout(tou_btns)
    win.btn_open_tou_folder = action_button(win.ui_tr("project.open_tou_folder"))
    win.btn_open_tou_folder.setToolTip(win.ui_tr("project.open_tou_folder_tip"))
    win.btn_open_tou_folder.clicked.connect(win._browse_yamaha_tou_folder)
    yam_tou_l.addWidget(win.btn_open_tou_folder)
    yam_outer.addWidget(yam_tou_row)

    yam_lib_row = DropRowWidget(win, win._drop_yamaha_lib, suffixes=(".lib",))
    yam_lib_l = QtWidgets.QVBoxLayout(yam_lib_row)
    yam_lib_l.setContentsMargins(0, 0, 0, 0)
    win.yamaha_lib_path_label = PathLabel(win.ui_tr("project.no_file"))
    yam_lib_l.addWidget(win.yamaha_lib_path_label)
    lib_btns = QtWidgets.QHBoxLayout()
    win.btn_clear_yamaha_lib = _clear_file_button(win, win._clear_yamaha_lib)
    lib_btns.addWidget(win.btn_clear_yamaha_lib)
    win.btn_open_lib = action_button(win.ui_tr("project.open_lib"))
    win.btn_open_lib.clicked.connect(win._browse_yamaha_lib)
    lib_btns.addWidget(win.btn_open_lib, 1)
    yam_lib_l.addLayout(lib_btns)
    yam_outer.addWidget(yam_lib_row)
    load_inner.addWidget(win.project_yamaha_group)

    top.addWidget(win.project_load_group, 0, 0)

    win.project_settings_group = QtWidgets.QGroupBox(win.ui_tr("project.settings"))
    settings_layout = QtWidgets.QVBoxLayout(win.project_settings_group)
    settings_layout.setSpacing(CHROME_SPACING)

    win.btn_project_debug = action_button(win.ui_tr("project.advanced"))
    win.btn_project_debug.clicked.connect(win._open_debug_settings)
    settings_layout.addWidget(win.btn_project_debug)
    win.btn_project_save_pack = action_button(win.ui_tr("project.save_session"))
    win.btn_project_save_pack.clicked.connect(win._menu_save_boomerpack)
    settings_layout.addWidget(win.btn_project_save_pack)
    win.btn_project_load_pack = action_button(win.ui_tr("project.load_session"))
    win.btn_project_load_pack.clicked.connect(win._menu_load_boomerpack)
    settings_layout.addWidget(win.btn_project_load_pack)
    equal = [
        win.btn_browse_bom,
        win.btn_browse_pnp,
        win.btn_browse_pnp2,
        win.btn_open_mdb,
        win.btn_open_tou,
        win.btn_open_tou_folder,
        win.btn_open_lib,
        win.btn_project_debug,
        win.btn_project_save_pack,
        win.btn_project_load_pack,
    ]
    if win.btn_access_odbc is not None:
        equal.append(win.btn_access_odbc)
    apply_equal_widths(equal)
    settings_layout.addStretch(1)
    top.addWidget(win.project_settings_group, 0, 1)
    layout.addLayout(top)

    win._prefs_host = QtWidgets.QWidget(win)
    prefs_host_l = QtWidgets.QVBoxLayout(win._prefs_host)
    prefs_host_l.setContentsMargins(0, 0, 0, 0)
    row_prof = QtWidgets.QHBoxLayout()
    win.profile_label = QtWidgets.QLabel(win.ui_tr("project.profile"))
    row_prof.addWidget(win.profile_label)
    win.profile_combo = QtWidgets.QComboBox()
    win.profile_combo.addItems(["default"])
    row_prof.addWidget(win.profile_combo)
    win.btn_profile_clone = QtWidgets.QPushButton(win.ui_tr("project.profile_clone"))
    row_prof.addWidget(win.btn_profile_clone)
    win.btn_profile_delete = QtWidgets.QPushButton(win.ui_tr("project.profile_delete"))
    row_prof.addWidget(win.btn_profile_delete)
    row_prof.addStretch(1)
    prefs_host_l.addLayout(row_prof)
    win.profile_combo.currentTextChanged.connect(win._on_profile_combo_changed)
    win.btn_profile_clone.clicked.connect(win._on_profile_clone_clicked)
    win.btn_profile_delete.clicked.connect(win._on_profile_delete_clicked)

    row_ui = QtWidgets.QHBoxLayout()
    win.lang_label = QtWidgets.QLabel(win.ui_tr("project.language"))
    row_ui.addWidget(win.lang_label)
    win.lang_combo = QtWidgets.QComboBox()
    for label, code in UI_LANGUAGE_OPTIONS:
        win.lang_combo.addItem(label, code)
    li = win.lang_combo.findData(win._i18n.locale)
    win.lang_combo.setCurrentIndex(li if li >= 0 else 0)
    win.lang_combo.currentIndexChanged.connect(lambda *_: win._on_ui_language_changed())
    row_ui.addWidget(win.lang_combo)
    row_ui.addStretch(1)
    prefs_host_l.addLayout(row_ui)
    win._prefs_host.hide()

    log_row = QtWidgets.QHBoxLayout()
    win.chk_colorful = switch_checkbox(win.ui_tr("project.debug_logs"))
    win.chk_colorful.setToolTip(win.ui_tr("project.debug_logs_hint"))
    win.chk_colorful.setChecked(True)
    win.chk_colorful.toggled.connect(win._on_colorful_logs_toggled)
    log_row.addWidget(win.chk_colorful)
    win.chk_session_log = switch_checkbox(win.ui_tr("project.session_log"))
    win.chk_session_log.setToolTip(win.ui_tr("project.session_log_hint"))
    win.chk_session_log.setChecked(True)
    win.chk_session_log.toggled.connect(win._on_session_log_toggled)
    log_row.addWidget(win.chk_session_log)
    win.btn_project_console = action_button(win.ui_tr("project.console"))
    win.btn_project_console.clicked.connect(win._show_project_console)
    log_row.addWidget(win.btn_project_console)
    log_row.addStretch(1)
    layout.addLayout(log_row)

    win.console = QtWidgets.QTextEdit()
    win.console.setObjectName("project_console")
    win.console.setFont(build_mono_font(win._settings))
    win.console.setReadOnly(True)
    win.console.hide()
    win._console_window = None

    win.log_message.connect(win._on_log_message)
