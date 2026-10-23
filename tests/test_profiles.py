"""Profile New vs Clone on the Project tab."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6 import QtCore, QtWidgets


def _ini_settings(tmp_path: Path) -> QtCore.QSettings:
    ini = tmp_path / "valvet.ini"
    return QtCore.QSettings(str(ini), QtCore.QSettings.Format.IniFormat)


def test_profile_new_gathers_current_ui(import_parsers, main_window, mocker) -> None:

    mocker.patch.object(QtWidgets.QInputDialog, "getText", return_value=("alpha", True))
    main_window._on_profile_new_clicked()
    assert main_window.profile_combo.currentText() == "alpha"
    settings = main_window._settings
    raw = str(settings.value("profiles/alpha/state_json", "") or "")
    data = json.loads(raw)
    assert data.get("v") == 1
    assert "ui" in data
    assert "bom" in data
    # Clean up
    settings.remove("profiles/alpha")
    main_window.profile_combo.setCurrentIndex(0)


def test_profile_clone_copies_stored_blob(import_parsers, main_window, mocker) -> None:

    settings = main_window._settings
    blob = json.dumps({"v": 1, "marker": "cloned-src"})
    settings.setValue("profiles/default/state_json", blob)
    mocker.patch.object(QtWidgets.QInputDialog, "getText", return_value=("beta", True))
    main_window._on_profile_clone_clicked()
    assert main_window.profile_combo.currentText() == "beta"
    copied = str(settings.value("profiles/beta/state_json", "") or "")
    assert json.loads(copied)["marker"] == "cloned-src"
    # Clean up
    settings.remove("profiles/default")
    settings.remove("profiles/beta")
    main_window.profile_combo.setCurrentIndex(0)
