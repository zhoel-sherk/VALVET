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


class DropGroupBox(QtWidgets.QGroupBox):
    """Group box that accepts file drops and forwards them to MainWindow handlers."""

    def __init__(
        self,
        title: str,
        win: Any,
        on_drop: Callable[[str], None],
        *,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(title, parent)
        self._win = win
        self._on_drop = on_drop
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dragMoveEvent(self, event: QtGui.QDragMoveEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QtGui.QDropEvent) -> None:
        for url in event.mimeData().urls():
            if not url.isLocalFile():
                continue
            path = url.toLocalFile()
            if path and os.path.isfile(path):
                self._on_drop(path)
                event.acceptProposedAction()
                return
        event.ignore()


class DropRowWidget(QtWidgets.QWidget):
    """Horizontal row inside the PnP group — drop target for primary or secondary file."""

    def __init__(
        self,
        win: Any,
        on_drop: Callable[[str], None],
        *,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_drop = on_drop
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dragMoveEvent(self, event: QtGui.QDragMoveEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QtGui.QDropEvent) -> None:
        for url in event.mimeData().urls():
            if not url.isLocalFile():
                continue
            path = url.toLocalFile()
            if path and os.path.isfile(path):
                self._on_drop(path)
                event.acceptProposedAction()
                return
        event.ignore()


def setup_project_tab(win: Any, layout: QtWidgets.QVBoxLayout) -> None:
    """Populate ``layout`` on the Project tab; attributes live on ``win`` (MainWindow)."""
    from ui.chrome import CHROME_SPACING, action_button, apply_equal_widths

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
    win.btn_browse_bom = action_button(win.ui_tr("project.browse_bom"))
    win.btn_browse_bom.clicked.connect(win._browse_bom)
    bom_layout.addWidget(win.btn_browse_bom)

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
    win.btn_browse_pnp = action_button(win.ui_tr("project.browse_pnp"))
    win.btn_browse_pnp.clicked.connect(win._browse_pnp)
    row1_layout.addWidget(win.btn_browse_pnp)
    pnp_outer.addWidget(row1)

    row2 = DropRowWidget(win, win._drop_pnp_secondary)
    row2_layout = QtWidgets.QVBoxLayout(row2)
    row2_layout.setContentsMargins(0, 0, 0, 0)
    win.pnp_path2_label = PathLabel(win.ui_tr("project.no_file"))
    row2_layout.addWidget(win.pnp_path2_label)
    pnp2_btns = QtWidgets.QHBoxLayout()
    win.btn_clear_pnp_optional = QtWidgets.QPushButton(
        win.ui_tr("project.pnp_clear_optional")
    )
    win.btn_clear_pnp_optional.setMaximumWidth(88)
    win.btn_clear_pnp_optional.clicked.connect(win._clear_pnp_secondary_only)
    pnp2_btns.addWidget(win.btn_clear_pnp_optional)
    win.btn_browse_pnp2 = action_button(win.ui_tr("project.browse_pnp2"))
    win.btn_browse_pnp2.clicked.connect(win._browse_pnp_secondary)
    pnp2_btns.addWidget(win.btn_browse_pnp2, 1)
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

    win.lbl_pnp_topbot_help = QtWidgets.QLabel(win.ui_tr("project.pnp_topbot_help"))
    win.lbl_pnp_topbot_help.setWordWrap(True)
    load_inner.addWidget(win.lbl_pnp_topbot_help)

    top.addWidget(win.project_load_group, 0, 0)

    win.project_settings_group = QtWidgets.QGroupBox(win.ui_tr("project.settings"))
    settings_layout = QtWidgets.QVBoxLayout(win.project_settings_group)
    settings_layout.setSpacing(CHROME_SPACING)

    win.chk_colorful = QtWidgets.QCheckBox(win.ui_tr("project.debug_logs"))
    win.chk_colorful.setToolTip(win.ui_tr("project.debug_logs_hint"))
    win.chk_colorful.toggled.connect(win._on_colorful_logs_toggled)
    settings_layout.addWidget(win.chk_colorful)

    win.btn_project_debug = action_button(win.ui_tr("project.advanced"))
    win.btn_project_debug.clicked.connect(win._open_debug_settings)
    settings_layout.addWidget(win.btn_project_debug)
    win.btn_project_save_pack = action_button(win.ui_tr("project.save_session"))
    win.btn_project_save_pack.clicked.connect(win._menu_save_boomerpack)
    settings_layout.addWidget(win.btn_project_save_pack)
    win.btn_project_load_pack = action_button(win.ui_tr("project.load_session"))
    win.btn_project_load_pack.clicked.connect(win._menu_load_boomerpack)
    settings_layout.addWidget(win.btn_project_load_pack)
    apply_equal_widths(
        (
            win.btn_browse_bom,
            win.btn_browse_pnp,
            win.btn_browse_pnp2,
            win.btn_project_debug,
            win.btn_project_save_pack,
            win.btn_project_load_pack,
        )
    )
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

    win.project_console_group = QtWidgets.QGroupBox(win.ui_tr("project.console"))
    console_outer = QtWidgets.QVBoxLayout(win.project_console_group)

    win.console = QtWidgets.QTextEdit()
    win.console.setObjectName("project_console")
    win.console.setFont(build_mono_font(win._settings))
    win.console.setReadOnly(True)
    console_outer.addWidget(win.console)

    layout.addWidget(win.project_console_group, 1)

    win.log_message.connect(win._on_log_message)
