"""Headless PySide6 startup smoke: main window tabs and debug dialogs."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6 import QtWidgets
from PySide6.QtCore import QSettings


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def _ini_settings(tmp_path: Path) -> QSettings:
    ini = tmp_path / "valvet.ini"
    return QSettings(str(ini), QSettings.Format.IniFormat)


def _set_experimental(settings: QSettings, *, enabled: bool) -> None:
    for key in ("pcb_preview", "step_3d"):
        settings.setValue(f"experimental/enable_{key}", enabled)


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
        assert win.tabs.count() == 7
    finally:
        win.close()


@pytest.mark.parametrize(
    "experimental_on,expected_tabs",
    [
        (False, 7),
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
        assert win.btn_browse_bom.text() == win.ui_tr("project.browse_bom")
        from ui.chrome import LEFT_RAIL_W

        assert LEFT_RAIL_W == 200
        for w in (
            win.gb_bom_file.parentWidget(),
            win.gb_pnp_file.parentWidget(),
            win.btn_merge.parentWidget(),
            win.btn_cross_check.parentWidget(),
        ):
            assert w is not None
            assert w.width() == LEFT_RAIL_W
    finally:
        win.close()


def test_debug_logs_checkbox_calls_set_debug_mode(
    import_parsers, qapp, tmp_path, monkeypatch
) -> None:
    from app.window import MainWindow

    states: list[bool] = []
    monkeypatch.setattr(
        "logger.set_debug_mode", lambda on, **_k: states.append(bool(on))
    )
    settings = _ini_settings(tmp_path)
    _set_experimental(settings, enabled=False)
    win = MainWindow(settings=settings)
    try:
        assert win.chk_colorful.isChecked() is False
        assert states[-1] is False
        win.chk_colorful.setChecked(True)
        assert states[-1] is True
        win.chk_colorful.setChecked(False)
        assert states[-1] is False
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
