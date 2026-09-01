"""Headless PySide6 startup smoke: main window tabs and debug dialogs."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6 import QtCore, QtWidgets


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def _ini_settings(tmp_path: Path) -> QtCore.QSettings:
    ini = tmp_path / "valvet.ini"
    return QtCore.QSettings(str(ini), QtCore.QSettings.Format.IniFormat)


def _set_experimental(settings: QtCore.QSettings, *, enabled: bool) -> None:
    """Toggle optional Step 3D tab. PCB Preview is always created."""
    settings.setValue("experimental/enable_step_3d", enabled)


@pytest.fixture
def import_parsers():
    import parsers  # noqa: F401


def test_main_window_constructs(import_parsers, qapp, tmp_path) -> None:
    from app.window import MainWindow

    settings = _ini_settings(tmp_path)
    _set_experimental(settings, enabled=False)
    win = MainWindow(settings=settings)
    try:
        assert win.windowTitle()
        assert win.tabs.count() == len(win._tab_keys_in_order)
        assert win.tabs.count() == 8
        assert "package" in win._tab_keys_in_order
        assert hasattr(win, "_package_tab")
        assert hasattr(win, "btn_find_package")
        assert not hasattr(win, "btn_apply_package_table_merge")
        assert hasattr(win, "btn_apply_package_table")
        assert hasattr(win._package_tab, "_fp_preview")
        assert "report" not in win._tab_keys_in_order
        assert "pcb_preview" in win._tab_keys_in_order
        assert "step_3d" not in win._tab_keys_in_order
        assert hasattr(win._machine_library_tab, "_fp_preview")
        assert isinstance(win.chk_colorful, QtWidgets.QCheckBox)
        assert isinstance(win.chk_session_log, QtWidgets.QCheckBox)
        sheet = QtWidgets.QApplication.instance().styleSheet()
        assert "switch_on.svg" in sheet
        win.chk_colorful.setChecked(False)
        assert win.chk_colorful.isChecked() is False
        win.chk_colorful.setChecked(True)
        assert win.chk_colorful.isChecked() is True
    finally:
        win.close()


@pytest.mark.parametrize(
    "experimental_on,expected_tabs",
    [
        (False, 8),
        (True, 9),
    ],
)
def test_main_window_each_tab_switchable(
    import_parsers,
    qapp,
    tmp_path,
    experimental_on: bool,
    expected_tabs: int,
) -> None:
    from app.window import MainWindow

    settings = _ini_settings(tmp_path / f"exp_{experimental_on}")
    _set_experimental(settings, enabled=experimental_on)
    win = MainWindow(settings=settings)
    try:
        assert win.tabs.count() == expected_tabs
        for i, key in enumerate(win._tab_keys_in_order):
            win.tabs.setCurrentIndex(i)
            qapp.processEvents()
            assert win.tabs.currentIndex() == i
            assert win._tab_keys_in_order[i] == key
    finally:
        win.close()


def test_debug_settings_dialog_tabs(import_parsers, qapp, tmp_path) -> None:
    from app.window import MainWindow
    from debug_settings_dialog import DebugSettingsDialog

    settings = _ini_settings(tmp_path)
    _set_experimental(settings, enabled=False)
    main = MainWindow(settings=settings)
    dlg = DebugSettingsDialog(main)
    try:
        tabs = dlg.findChild(QtWidgets.QTabWidget)
        assert tabs is not None
        assert tabs.count() == 7
        for i in range(tabs.count()):
            tabs.setCurrentIndex(i)
            qapp.processEvents()
    finally:
        dlg.close()
        main.close()


def test_debug_settings_reopen_keeps_profile_widgets(
    import_parsers, qapp, tmp_path
) -> None:
    from app.window import MainWindow

    settings = _ini_settings(tmp_path)
    _set_experimental(settings, enabled=False)
    win = MainWindow(settings=settings)
    try:
        win._open_debug_settings()
        qapp.processEvents()
        dlg = win._debug_settings_dialog
        assert dlg is not None
        dlg.close()
        qapp.processEvents()
        assert win.profile_combo.currentText() == "default"
        win._open_debug_settings()
        qapp.processEvents()
        win._debug_settings_dialog.close()
        qapp.processEvents()
        win.close()
        qapp.processEvents()
    finally:
        if win.isVisible():
            win.close()


def test_clean_tab_table_first_and_i18n(import_parsers, qapp, tmp_path) -> None:
    from app.window import MainWindow

    settings = _ini_settings(tmp_path)
    _set_experimental(settings, enabled=False)
    win = MainWindow(settings=settings)
    try:
        assert "VALVET" in win.windowTitle()
        assert win.tabs.tabText(win._tab_index("project")).startswith(
            win.ui_tr("tab.group.data").upper()
        )
        assert win.tabs.tabText(win._tab_index("clean_bom")).startswith(
            win.ui_tr("tab.group.transform").upper()
        )
        assert hasattr(win, "lbl_clean_context")
        assert hasattr(win, "clean_preview_table")
        assert hasattr(win, "btn_clean_options_toggle")
        assert win.btn_clean_options_toggle.isChecked() is False
        assert win.clean_options_panel.isHidden() is True
        assert win.btn_clean_convert.isEnabled() is False
        assert win.btn_clean_apply.isEnabled() is False
        assert win.clean_res_watt_from_pack.text() == win.ui_tr("clean.watt_from_pack")
        assert win.gb_clean_everyday.title() == win.ui_tr("clean.everyday")
        assert win.lbl_clean_preset.text() == win.ui_tr("clean.preset")
        assert win.clean_format_preset.parent() is not None
        assert win.clean_res_frame.parent() is win.gb_clean_everyday or (
            win.clean_res_frame.parent() is not None
            and win.gb_clean_everyday.isAncestorOf(win.clean_res_frame)
        )
        assert win.gb_clean_mpn.isVisible() is False
        assert win.btn_clean_debug is not None
        status = win.statusBar().currentMessage()
        assert win.ui_tr("status.no_bom") in status
        assert win.findChild(QtWidgets.QLabel, "WipBanner") is None
        assert win.chk_colorful.text() == win.ui_tr("project.debug_logs")
        assert win.chk_session_log.text() == win.ui_tr("project.session_log")
        assert win.chk_colorful.isChecked() is True
        assert win.chk_session_log.isChecked() is True
        assert win.btn_project_console.text() == win.ui_tr("project.console")
        assert win.btn_browse_bom.text() == win.ui_tr("project.browse_bom")
        from ui.chrome import LEFT_RAIL_W

        assert LEFT_RAIL_W == 200
        for w in (
            win.gb_bom_file.parentWidget(),
            win.gb_pnp_file.parentWidget(),
            win.btn_merge.parentWidget(),
            win.btn_cross_check.parentWidget().parentWidget(),
        ):
            assert w is not None
            assert w.width() == LEFT_RAIL_W
    finally:
        win.close()


def test_debug_logs_checkbox_calls_set_debug_mode(
    import_parsers, qapp, tmp_path, mocker
) -> None:
    from app.window import MainWindow

    mock = mocker.patch("logger.set_debug_mode")
    settings = _ini_settings(tmp_path)
    _set_experimental(settings, enabled=False)
    win = MainWindow(settings=settings)
    try:
        assert win.chk_colorful.isChecked() is True
        win.chk_colorful.setChecked(False)
        on_arg = mock.call_args[0][0]
        assert on_arg is False
        win.chk_colorful.setChecked(True)
        on_arg = mock.call_args[0][0]
        assert on_arg is True
    finally:
        win.close()


def test_cli_debug_checks_project_debug_logs(
    import_parsers, qapp, tmp_path, monkeypatch
) -> None:
    from app.window import MainWindow

    monkeypatch.setattr("logger.set_debug_mode", lambda on, **_k: None)
    settings = _ini_settings(tmp_path)
    _set_experimental(settings, enabled=False)
    win = MainWindow(settings=settings, debug=True)
    try:
        assert win.chk_colorful.isChecked() is True
    finally:
        win.close()


def test_session_file_records_error_and_hidden_debug(
    import_parsers, qapp, tmp_path
) -> None:
    from app.window import MainWindow

    settings = _ini_settings(tmp_path)
    _set_experimental(settings, enabled=False)
    win = MainWindow(settings=settings)
    try:
        win.chk_colorful.setChecked(False)
        assert win.chk_session_log.isChecked() is True
        win._log("hidden-debug-line", "debug")
        win._log("visible-error-line", "error")
        assert win._session_log_path is not None
        text = win._session_log_path.read_text(encoding="utf-8")
        assert "DEBUG hidden-debug-line" in text
        assert "ERROR visible-error-line" in text
        html = win.console.toHtml()
        assert "visible-error-line" in html
        assert "hidden-debug-line" not in html
        win._show_project_console()
        assert win._console_window is not None
        assert win._console_window.isVisible()
        win._console_window.close()
        assert win._console_window.isVisible() is False
        assert win.console.toPlainText()  # still alive after hide
    finally:
        win.close()


def test_clean_options_expanded_from_qsettings(import_parsers, qapp, tmp_path) -> None:
    from app.window import MainWindow

    settings = _ini_settings(tmp_path)
    _set_experimental(settings, enabled=False)
    settings.setValue("clean/options_expanded", True)
    win = MainWindow(settings=settings)
    try:
        assert win.btn_clean_options_toggle.isChecked() is True
        assert win.clean_options_panel.isHidden() is False
        win._set_template_combos(
            win.clean_res_template_combos,
            "nom,pack,none,none",
            ("nom", "pack", "watt", "%"),
        )
        win._set_template_combos(
            win.clean_cap_template_combos,
            "nom,pack,none,none,none",
            ("nom", "pack", "film", "%", "V"),
        )
        win._set_template_combos(
            win.clean_ind_template_combos,
            "pack,nom,none,none,none",
            ("pack", "nom", "%", "Imax", "DCR"),
        )
        win._sync_clean_preset_from_combos()
        assert win.clean_format_preset.currentData() == "compact"
        assert win.clean_res_template_combos[0].isVisible() is False
    finally:
        win.close()


def test_clean_pipeline_debug_dialog_opens(import_parsers, qapp, tmp_path) -> None:
    from clean_debug_dialog import CleanPipelineDebugDialog

    settings = _ini_settings(tmp_path)
    dlg = CleanPipelineDebugDialog(None, settings)
    try:
        dlg.show()
        qapp.processEvents()
        assert dlg.isVisible()
    finally:
        dlg.close()


def test_clean_bom_primary_buttons_are_large_and_import_is_active(
    import_parsers, qapp, tmp_path
) -> None:
    from app.window import MainWindow
    from ui.chrome import CLEAN_PRIMARY_BTN_MIN_H, CLEAN_PRIMARY_BTN_MIN_W

    settings = _ini_settings(tmp_path)
    _set_experimental(settings, enabled=False)
    win = MainWindow(settings=settings)
    try:
        idx = win._tab_index("clean_bom")
        win.tabs.setCurrentIndex(idx)
        qapp.processEvents()
        toolbar = (
            win.btn_clean_import,
            win.btn_clean_convert,
            win.btn_clean_apply,
            win.btn_clean_learn_other,
            win.btn_clean_save,
        )
        heights = {b.minimumHeight() for b in toolbar}
        widths = {b.minimumWidth() for b in toolbar}
        assert len(heights) == 1
        assert next(iter(heights)) >= CLEAN_PRIMARY_BTN_MIN_H
        assert next(iter(heights)) <= 48
        assert len(widths) == 1
        assert next(iter(widths)) >= CLEAN_PRIMARY_BTN_MIN_W
        assert not win.btn_clean_convert.isEnabled()
        assert win.btn_clean_import.property("cleanStep") == "active"
        assert win.btn_clean_convert.property("cleanStep") == "idle"
        assert win.btn_clean_apply.property("cleanStep") == "idle"
        win.btn_clean_convert.setEnabled(True)
        win._sync_clean_primary_buttons()
        assert win.btn_clean_convert.property("cleanStep") == "active"
        assert win.btn_clean_import.property("cleanStep") == "idle"
    finally:
        win.close()


def test_pcb_preview_canvas_first(import_parsers, qapp, tmp_path) -> None:
    from app.window import MainWindow

    settings = _ini_settings(tmp_path)
    _set_experimental(settings, enabled=True)
    win = MainWindow(settings=settings)
    try:
        assert hasattr(win, "_pcb_tab")
        tab = win._pcb_tab
        assert tab._pcb_settings_panel.isHidden() is True
        assert tab._btn_center is not None
        assert tab._spin_label_scale.value() == pytest.approx(0.12)
        idx = win._tab_index("pcb_preview")
        win.tabs.setCurrentIndex(idx)
        qapp.processEvents()
        win.tabs.setCurrentIndex(idx)
        qapp.processEvents()
    finally:
        win.close()
