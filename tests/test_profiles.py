"""Profile New vs Clone on the Project tab."""

from __future__ import annotations

import json
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


@pytest.fixture
def import_parsers():
    import parsers  # noqa: F401


def _ini_settings(tmp_path: Path) -> QtCore.QSettings:
    ini = tmp_path / "valvet.ini"
    return QtCore.QSettings(str(ini), QtCore.QSettings.Format.IniFormat)


def test_profile_new_gathers_current_ui(import_parsers, qapp, tmp_path, mocker) -> None:
    from app.window import MainWindow

    settings = _ini_settings(tmp_path)
    settings.setValue("experimental/enable_step_3d", False)
    win = MainWindow(settings=settings)
    try:
        mocker.patch.object(
            QtWidgets.QInputDialog, "getText", return_value=("alpha", True)
        )
        win._on_profile_new_clicked()
        assert win.profile_combo.currentText() == "alpha"
        raw = str(settings.value("profiles/alpha/state_json", "") or "")
        data = json.loads(raw)
        assert data.get("v") == 1
        assert "ui" in data
        assert "bom" in data
    finally:
        win.close()


def test_profile_clone_copies_stored_blob(
    import_parsers, qapp, tmp_path, mocker
) -> None:
    from app.window import MainWindow

    settings = _ini_settings(tmp_path)
    settings.setValue("experimental/enable_step_3d", False)
    win = MainWindow(settings=settings)
    try:
        blob = json.dumps({"v": 1, "marker": "cloned-src"})
        settings.setValue("profiles/default/state_json", blob)
        mocker.patch.object(
            QtWidgets.QInputDialog, "getText", return_value=("beta", True)
        )
        win._on_profile_clone_clicked()
        assert win.profile_combo.currentText() == "beta"
        copied = str(settings.value("profiles/beta/state_json", "") or "")
        assert json.loads(copied)["marker"] == "cloned-src"
    finally:
        win.close()
