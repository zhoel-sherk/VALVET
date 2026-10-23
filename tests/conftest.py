"""Pytest hooks: headless Qt for CI and sandboxed runs."""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager

import pytest

# Must run before any PySide6 import (avoids abort without a display).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# ---------------------------------------------------------------------------
# Logging capture utilities (shared across test modules)
# ---------------------------------------------------------------------------


class LogCapture(logging.Handler):
    """Logging handler that captures all records for inspection in tests."""

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.fixture
def log_capture():
    """Fixture that captures all log records from the root logger.
    
    Usage:
        def test_something(log_capture):
            logger.info("test message")
            assert len(log_capture.records) == 1
            assert log_capture.records[0].getMessage() == "test message"
    """
    root = logging.getLogger()
    capture = LogCapture()
    root.addHandler(capture)
    try:
        yield capture
    finally:
        root.removeHandler(capture)


@contextmanager
def captured_root():
    """Context manager that captures all records from the root logger.
    
    Usage:
        with captured_root() as cap:
            logger.info("test message")
        assert len(cap.records) == 1
    """
    root = logging.getLogger()
    capture = LogCapture()
    root.addHandler(capture)
    try:
        yield capture
    finally:
        root.removeHandler(capture)


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


@pytest.fixture(scope="module")
def main_window(qapp, tmp_path_factory):
    """Module-scoped MainWindow instance to avoid repeated creation.
    
    Creates a single MainWindow per test module, reducing test time by ~10s per test.
    Uses tmp_path_factory to create a module-level temporary directory for settings.
    """
    from PySide6 import QtCore
    from app.window import MainWindow

    tmp_path = tmp_path_factory.mktemp("main_window")
    settings = QtCore.QSettings(
        str(tmp_path / "valvet.ini"),
        QtCore.QSettings.Format.IniFormat,
    )
    settings.setValue("experimental/enable_step_3d", False)
    win = MainWindow(settings=settings)
    yield win
    win.close()


@pytest.fixture(autouse=True)
def _reset_main_window_state(main_window):
    """Reset MainWindow state between tests to prevent cross-test contamination."""
    yield
    # Reset state after each test
    # Disconnect all signal handlers (only if there are connections)
    try:
        if main_window.log_message.receivers() > 0:
            main_window.log_message.disconnect()
    except (RuntimeError, TypeError, AttributeError):
        pass  # No connections to disconnect or method not available
    # Reset BOM data but keep bom_model instance
    if hasattr(main_window, '_bom_df'):
        main_window._bom_df = None
    if hasattr(main_window, '_clean_imported_comments'):
        main_window._clean_imported_comments = []
