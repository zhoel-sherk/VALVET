"""Tests for working_copy_ui (requires PySide6)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("PySide6")

from PySide6 import QtWidgets

import working_copy
import working_copy_ui
from working_copy_ui import prompt_recover_snapshot


def _qapp() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


class _FakeMessageBox:
    """Stand-in for QMessageBox: click a named button without a real dialog."""

    ButtonRole = QtWidgets.QMessageBox.ButtonRole
    click_label = "Recovered"
    exec_calls = 0

    def __init__(self, parent=None) -> None:
        self._buttons: list[tuple[str, object]] = []

    def setWindowTitle(self, *_a: object) -> None:
        return None

    def setText(self, *_a: object) -> None:
        return None

    def addButton(self, text: str, _role: object) -> object:
        btn = object()
        self._buttons.append((str(text), btn))
        return btn

    def exec(self) -> int:
        type(self).exec_calls += 1
        return 0

    def clickedButton(self) -> object:
        want = type(self).click_label
        for text, btn in self._buttons:
            if text == want:
                return btn
        return None


def test_prompt_recover_no_snapshot_returns_none() -> None:
    _qapp()
    out = prompt_recover_snapshot(None, "/nonexistent/path/file.csv", "bom", ".")
    assert out is None


def test_prompt_recover_returns_dataframe_on_recovered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _qapp()
    src = tmp_path / "pnp.csv"
    src.write_text("source", encoding="utf-8")
    autosave = tmp_path / "autosave"
    df = pd.DataFrame({"Designator": ["R1"]})
    working_copy.save_snapshot(df, src, "pnp", autosave, dirty=True)
    _FakeMessageBox.click_label = "Recovered"
    _FakeMessageBox.exec_calls = 0
    monkeypatch.setattr(working_copy_ui.QtWidgets, "QMessageBox", _FakeMessageBox)
    out = prompt_recover_snapshot(None, str(src), "pnp", str(autosave))
    assert isinstance(out, pd.DataFrame)
    pd.testing.assert_frame_equal(out, df)
    assert _FakeMessageBox.exec_calls == 1


def test_prompt_recover_cancel_returns_cancel_literal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _qapp()
    src = tmp_path / "pnp.csv"
    src.write_text("source", encoding="utf-8")
    autosave = tmp_path / "autosave"
    df = pd.DataFrame({"Designator": ["R1"]})
    working_copy.save_snapshot(df, src, "pnp", autosave, dirty=True)
    _FakeMessageBox.click_label = "Cancel"
    _FakeMessageBox.exec_calls = 0
    monkeypatch.setattr(working_copy_ui.QtWidgets, "QMessageBox", _FakeMessageBox)
    out = prompt_recover_snapshot(None, str(src), "pnp", str(autosave))
    assert out == "cancel"


def test_prompt_recover_clean_snapshot_returns_none_without_dialog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _qapp()
    src = tmp_path / "pnp.csv"
    src.write_text("source", encoding="utf-8")
    autosave = tmp_path / "autosave"
    df = pd.DataFrame({"Designator": ["R1"]})
    working_copy.save_snapshot(df, src, "pnp", autosave, dirty=False)
    _FakeMessageBox.exec_calls = 0
    monkeypatch.setattr(working_copy_ui.QtWidgets, "QMessageBox", _FakeMessageBox)
    out = prompt_recover_snapshot(None, str(src), "pnp", str(autosave))
    assert out is None
    assert _FakeMessageBox.exec_calls == 0
