"""Headless PySide6 startup smoke: main window tabs and Settings rail."""

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
        assert win.tabs.objectName() == "valvetMainTabs"
        assert win.tabs.documentMode() is True
        assert win.tabs.tabBar().expanding() is False
        from themes.equal_tab_bar import EqualWidthTabBar

        assert isinstance(win.tabs.tabBar(), EqualWidthTabBar)
        widths = [
            win.tabs.tabBar().tabSizeHint(i).width() for i in range(win.tabs.count())
        ]
        merge_i = win._tab_index("merge")
        project_i = win._tab_index("project")
        assert widths[merge_i] > widths[project_i]
        assert min(widths) >= 48
        assert not win.tabs.tabIcon(win._tab_index("project")).isNull()
        assert win.tabs.count() == len(win._tab_keys_in_order)
        assert win.tabs.count() == 9
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
        (False, 9),
        (True, 10),
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


def test_settings_tab_rail_and_pages(import_parsers, qapp, tmp_path) -> None:
    from app.window import MainWindow
    from ui.chrome import LEFT_RAIL_W
    from ui.settings_tab import SETTINGS_NAV_KEYS

    settings = _ini_settings(tmp_path)
    _set_experimental(settings, enabled=False)
    main = MainWindow(settings=settings)
    try:
        assert main._tab_keys_in_order[-1] == "settings"
        assert "settings.nav_tabs" in SETTINGS_NAV_KEYS
        assert (
            main.tabs.tabText(main._tab_index("settings"))
            == main.ui_tr("tab.settings").upper()
        )
        assert not hasattr(main, "btn_project_debug")
        assert main._settings_stack.count() == 7
        assert len(main._settings_nav_buttons) == 7
        for btn, key in zip(main._settings_nav_buttons, SETTINGS_NAV_KEYS, strict=True):
            assert btn.text() == main.ui_tr(key)
        rail = main._settings_nav_buttons[0].parentWidget()
        assert rail is not None
        assert rail.width() == LEFT_RAIL_W
        for i, btn in enumerate(main._settings_nav_buttons):
            btn.click()
            qapp.processEvents()
            assert main._settings_stack.currentIndex() == i
        idx = main._tab_index("settings")
        main.tabs.setCurrentIndex(idx)
        qapp.processEvents()
    finally:
        main.close()


def test_project_profile_session_and_lang_row(import_parsers, qapp, tmp_path) -> None:
    from app.window import MainWindow

    settings = _ini_settings(tmp_path)
    _set_experimental(settings, enabled=False)
    win = MainWindow(settings=settings)
    try:
        assert win.profile_combo.currentText() == "default"
        assert win.project_profile_group.title() == win.ui_tr("project.profile_group")
        assert win.project_session_group.title() == win.ui_tr("project.session_group")
        assert win.btn_profile_new.text() == win.ui_tr("project.profile_new")
        assert win.btn_project_save_pack.text() == win.ui_tr("project.save_session")
        assert win.lang_label.text() == win.ui_tr("project.language")
        assert win.chk_colorful.parentWidget() is win.lang_combo.parentWidget()
    finally:
        win.close()


def test_clean_tab_table_first_and_i18n(import_parsers, qapp, tmp_path) -> None:
    from app.window import MainWindow

    settings = _ini_settings(tmp_path)
    _set_experimental(settings, enabled=False)
    win = MainWindow(settings=settings)
    try:
        assert "VALVET" in win.windowTitle()
        assert (
            win.tabs.tabText(win._tab_index("project"))
            == win.ui_tr("tab.project").upper()
        )
        assert (
            win.tabs.tabText(win._tab_index("clean_bom"))
            == win.ui_tr("tab.clean_bom").upper()
        )
        for i in range(win.tabs.count()):
            assert " · " not in win.tabs.tabText(i)
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
            win.gb_merge.parentWidget(),
            win.btn_cross_check.parentWidget().parentWidget(),
        ):
            assert w is not None
            assert w.width() == LEFT_RAIL_W
        merge_row = win.gb_merge.layout().itemAt(0).layout()
        assert merge_row.itemAt(0).widget() is win.btn_merge
        assert merge_row.itemAt(1).widget() is win.btn_merge_help
        assert win.btn_merge_help.text() == "?"
        rail = win.gb_merge.parentWidget().layout()
        assert rail.itemAt(0).widget() is win.gb_merge
        assert rail.itemAt(1).widget() is win.btn_cross_check.parentWidget()
        assert rail.itemAt(2).widget() is win.gb_merge_files
        assert not hasattr(win, "lbl_pnp_topbot_help")
        assert win.project_hanwha_group.acceptDrops()
        assert win.yamaha_tou_path_label.parent().acceptDrops()
        assert win.yamaha_lib_path_label.parent().acceptDrops()
        ml = win._machine_library_tab
        assert not hasattr(ml, "_btn_open_mdb")
        texts = [b.text() for b in ml.findChildren(QtWidgets.QPushButton)]
        assert "Open .mdb…" not in texts
        assert "Open .tou…" not in texts
        assert "Access ODBC (ACE)…" not in texts
        pnp2 = win.pnp_path2_label.parentWidget().layout().itemAt(1).layout()
        assert pnp2.itemAt(0).widget() is win.btn_clear_pnp_optional
        assert pnp2.itemAt(1).widget() is win.btn_browse_pnp2
        assert pnp2.itemAt(2).widget() is win.btn_pnp2_help
        assert win.btn_pnp2_help.text() == "?"
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
