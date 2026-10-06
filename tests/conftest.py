"""Pytest hooks: headless Qt for CI and sandboxed runs."""

from __future__ import annotations

import os

import pytest

# Must run before any PySide6 import (avoids abort without a display).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def _sandbox_session_and_debug_files(tmp_path, monkeypatch):
    """Keep GUI tests from writing repo logs/ (debug default + sessionlog)."""
    monkeypatch.setattr("session_file_log.repo_logs_dir", lambda: tmp_path / "logs")
    monkeypatch.setattr("logger.set_debug_mode", lambda *_a, **_k: None)


@pytest.fixture(scope="session")
def qapp():
    """Headless QApplication, created once and reused.

    Qt permits a single QApplication per process, so every test needs this to be
    get-or-create rather than a plain constructor. Several test modules used to
    carry an identical private copy of this helper.
    """
    from PySide6 import QtWidgets

    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


@pytest.fixture
def import_parsers():
    """Import the ``parsers`` package so its registry side effects are in place."""
    import parsers  # noqa: F401


@pytest.fixture
def corpus_cfg():
    """CleanConfig loaded from the shared parser corpus profile."""
    from tools.clean_corpus_lib import load_corpus_profile

    return load_corpus_profile()
