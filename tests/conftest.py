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
