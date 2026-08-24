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
    ini = tmp_path / "boomer.ini"
    return QSettings(str(ini), QSettings.Format.IniFormat)


def _set_experimental(settings: QSettings, *, enabled: bool) -> None:
    for key in ("pcb_preview", "step_3d"):
        settings.setValue(f"experimental/enable_{key}", enabled)


@pytest.fixture
def import_parsers():
    import parsers  # noqa: F401


def test_main_window_constructs(import_parsers, qapp, tmp_path) -> None:
    from app_pyside6 import MainWindow

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
    from app_pyside6 import MainWindow

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
    from app_pyside6 import MainWindow
    from debug_settings_dialog import DebugSettingsDialog

    settings = _ini_settings(tmp_path)
    _set_experimental(settings, enabled=False)
    main = MainWindow(settings=settings)
    dlg = DebugSettingsDialog(main)
    try:
        tabs = dlg.findChild(QtWidgets.QTabWidget)
        assert tabs is not None
        assert tabs.count() == 6
        for i in range(tabs.count()):
            tabs.setCurrentIndex(i)
            qapp.processEvents()
    finally:
        dlg.close()
        main.close()


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
