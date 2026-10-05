"""Phase-2 logging hardening: crash-safe logger, no PII in logs, opt-in alerts.

Covers plan items 2.1-2.7, 2.9 and 4.12.
"""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import pytest

import logger
import session_file_log
from clean_alerts import append_missing_tokens_log, missing_tokens_log_path

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


class _Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@contextmanager
def captured_root():
    """Collect every record that reaches root, whatever emitted it."""
    root = logging.getLogger()
    cap = _Capture()
    root.addHandler(cap)
    try:
        yield cap
    finally:
        root.removeHandler(cap)


@pytest.fixture
def isolated_logging():
    """Undo config()/_disable_file_logging() so tests stay independent."""
    root = logging.getLogger()
    before = list(root.handlers)
    level = root.level
    facade = logger._facade
    debug_flag = logger._debug_mode
    try:
        yield
    finally:
        for handler in list(root.handlers):
            if handler in before:
                continue
            root.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass
        root.setLevel(level)
        logger._facade = facade
        logger._debug_mode = debug_flag


def _owned_file_handlers() -> list[logging.FileHandler]:
    return [
        h
        for h in logging.getLogger().handlers
        if isinstance(h, logging.FileHandler) and getattr(h, "_valvet_owned", False)
    ]


# ---------------------------------------------------------------------------
# 2.1 / 2.2 logger must not crash startup
# ---------------------------------------------------------------------------


def test_config_survives_unwritable_logs_dir(monkeypatch, isolated_logging) -> None:
    def _boom(*_a, **_k):
        raise PermissionError(13, "denied")

    monkeypatch.setattr(logger.os, "makedirs", _boom)
    logger.config(use_color_logs=False)  # must not raise

    assert logger.debug_mode_enabled() is True
    assert _owned_file_handlers() == []
    with captured_root() as cap:
        logger.info("console only, still alive")
    assert [r.getMessage() for r in cap.records] == ["console only, still alive"]


def test_package_still_imports_after_failed_logger_init(
    monkeypatch, isolated_logging
) -> None:
    import importlib

    def _boom(*_a, **_k):
        raise OSError(28, "no space left on device")

    monkeypatch.setattr(logger.os, "makedirs", _boom)
    logger.config(use_color_logs=False)
    for name in ("smt_processor", "clean_component", "ui.files"):
        assert importlib.import_module(name) is not None


def test_makedirs_is_called_with_exist_ok(
    monkeypatch, isolated_logging, tmp_path
) -> None:
    seen: dict = {}

    def _makedirs(path, exist_ok=False):
        seen["path"] = path
        seen["exist_ok"] = exist_ok
        Path(path).mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(logger.os, "makedirs", _makedirs)
    monkeypatch.setattr(logger, "__get_logs_directory", lambda: str(tmp_path / "logs"))
    logger.config(use_color_logs=False)
    assert seen["exist_ok"] is True
    assert seen["path"] == str(tmp_path / "logs")


def test_file_handler_is_delayed(monkeypatch, isolated_logging, tmp_path) -> None:
    logs_dir = tmp_path / "logs"
    monkeypatch.setattr(logger, "__get_logs_directory", lambda: str(logs_dir))
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    handler = logger._open_log_file()
    assert handler is not None
    assert handler.delay is True
    root.addHandler(handler)

    assert list(logs_dir.glob("*.log")) == [], "empty log file created eagerly"
    logger.info("first real record")

    files = list(logs_dir.glob("*.log"))
    assert len(files) == 1
    assert "first real record" in files[0].read_text(encoding="utf-8")


def test_configured_file_handler_writes_records(
    monkeypatch, isolated_logging, tmp_path
) -> None:
    logs_dir = tmp_path / "logs"
    monkeypatch.setattr(logger, "__get_logs_directory", lambda: str(logs_dir))
    logger.config(use_color_logs=False)
    logger.info("routed to the dated file")
    files = list(logs_dir.glob("*.log"))
    assert len(files) == 1
    assert "routed to the dated file" in files[0].read_text(encoding="utf-8")


def test_disable_file_logging_closes_and_releases_handler(
    monkeypatch, isolated_logging, tmp_path
) -> None:
    monkeypatch.setattr(logger, "__get_logs_directory", lambda: str(tmp_path / "logs"))
    logger.config(use_color_logs=False)
    logger.info("open the file")
    handler = _owned_file_handlers()[0]
    assert handler.stream is not None

    logger._disable_file_logging()

    assert handler.stream is None, "handle left open (file stays locked on Windows)"
    assert handler not in logging.getLogger().handlers
    assert _owned_file_handlers() == []
    assert logger.debug_mode_enabled() is False


# ---------------------------------------------------------------------------
# 2.3 root logger + real pathname/lineno
# ---------------------------------------------------------------------------


def test_module_level_logger_is_captured(
    monkeypatch, isolated_logging, tmp_path
) -> None:
    """getLogger(__name__) modules were invisible to the old private logger."""
    monkeypatch.setattr(logger, "__get_logs_directory", lambda: str(tmp_path / "logs"))
    logger.config(use_color_logs=False)
    with captured_root() as cap:
        logging.getLogger("machine_library.yamaha_devlib").info("from a module logger")
    assert "from a module logger" in [r.getMessage() for r in cap.records]


def test_record_pathname_is_the_real_caller(isolated_logging) -> None:
    with captured_root() as cap:
        logger.warning("before config")
    record = cap.records[-1]
    assert record.pathname == __file__
    assert record.funcName == "test_record_pathname_is_the_real_caller"


def test_record_pathname_is_the_real_caller_after_config(
    monkeypatch, isolated_logging, tmp_path
) -> None:
    monkeypatch.setattr(logger, "__get_logs_directory", lambda: str(tmp_path / "logs"))
    logger.config(use_color_logs=False)
    with captured_root() as cap:
        logger.info("after config")
    record = cap.records[-1]
    assert record.pathname == __file__
    assert record.lineno > 0


# ---------------------------------------------------------------------------
# 2.4 session file log
# ---------------------------------------------------------------------------


def test_session_log_survives_oserror(tmp_path: Path, mocker) -> None:
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x", encoding="utf-8")
    warn_spy = mocker.spy(logger, "warning")
    session_file_log._write_failed_warned = False

    # mkdir under a regular file raises NotADirectoryError (an OSError).
    session_file_log.append_session_line(
        blocker / "sub" / "sessionlog.txt", "info", "line"
    )

    assert warn_spy.called
    assert "continuing" in str(warn_spy.call_args.args[0])


def test_session_log_drops_debug_before_writing(tmp_path: Path) -> None:
    path = tmp_path / "sessionlog.txt"
    now = datetime(2026, 9, 1, 23, 30, 6)
    session_file_log.append_session_line(path, "debug", "chatty", now=now)
    session_file_log.append_session_line(path, "info", "kept", now=now)
    session_file_log.append_session_line(path, "error", "boom", now=now)

    text = path.read_text(encoding="utf-8")
    assert "chatty" not in text
    assert "DEBUG" not in text
    assert "INFO kept" in text
    assert "ERROR boom" in text


def test_session_log_warns_only_once(tmp_path: Path, mocker) -> None:
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x", encoding="utf-8")
    warn_spy = mocker.spy(logger, "warning")
    session_file_log._write_failed_warned = False
    target = blocker / "sub" / "sessionlog.txt"
    session_file_log.append_session_line(target, "info", "a")
    session_file_log.append_session_line(target, "info", "b")
    assert warn_spy.call_count == 1


# ---------------------------------------------------------------------------
# 2.5 no absolute paths in logs
# ---------------------------------------------------------------------------


def _load_line(text: str, marker: str) -> str:
    return next(line for line in text.splitlines() if marker in line)


def _qapp():
    from PySide6 import QtWidgets

    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def _main_window(tmp_path: Path):
    from PySide6 import QtCore

    from app.window import MainWindow

    settings = QtCore.QSettings(
        str(tmp_path / "t.ini"), QtCore.QSettings.Format.IniFormat
    )
    settings.setValue("experimental/enable_step_3d", False)
    return MainWindow(settings=settings)


def test_bom_and_pnp_load_logs_use_basename_only(tmp_path: Path, monkeypatch) -> None:
    """Session logs ship inside the release zip: no absolute path in them."""
    pytest.importorskip("PySide6")
    import pandas as pd

    import ui.files as files_mod

    _qapp()
    bom = tmp_path / "customer_project_bom.csv"
    bom.write_text("Comment,Part\nMLCC_1206_22uF,123\n", encoding="utf-8")
    pnp = tmp_path / "customer_project_pnp.csv"
    pnp.write_text("Designator,Mid X,Mid Y,Layer\nR1,1.0,2.0,Top\n", encoding="utf-8")

    # Parsers are stubbed: this test is about what the log lines contain.
    bom_df = pd.DataFrame({"Comment": ["MLCC_1206_22uF"], "Part": ["123"]})
    pnp_df = pd.DataFrame(
        {"Designator": ["R1"], "Mid X": [1.0], "Mid Y": [2.0], "Layer": ["Top"]}
    )
    monkeypatch.setattr(files_mod, "read_file", lambda *a, **k: bom_df.copy())
    monkeypatch.setattr(
        files_mod.FilesMixin,
        "_read_pnp_dataframe_from_disk",
        lambda self, path, sep, sheet_name=None: pnp_df.copy(),
    )

    win = _main_window(tmp_path)
    try:
        win.chk_session_log.setChecked(True)
        win._load_bom(str(bom), force_original=True)
        win._load_pnp(str(pnp), force_original=True)
        assert win._session_log_path is not None
        text = win._session_log_path.read_text(encoding="utf-8")

        bom_line = _load_line(text, "Loaded BOM")
        pnp_line = _load_line(text, "Loaded PnP")
        assert str(tmp_path) not in text
        assert str(bom) not in text
        assert str(pnp) not in text
        assert "customer_project_bom.csv" in bom_line
        assert "customer_project_pnp.csv" in pnp_line
    finally:
        win.close()


# ---------------------------------------------------------------------------
# 2.6 opt-in missing tokens log
# ---------------------------------------------------------------------------


def test_missing_tokens_log_writes_nothing_when_flag_off(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("VALVET_MISSING_TOKENS_LOG", raising=False)
    monkeypatch.delenv("BOOMER_MISSING_TOKENS_LOG", raising=False)
    monkeypatch.setattr("app_paths.user_state_dir", lambda: tmp_path / "state")

    assert missing_tokens_log_path() is None
    append_missing_tokens_log({"row": 1, "original": "SECRET BOM TEXT"})

    assert list(tmp_path.rglob("*.jsonl")) == []


def test_missing_tokens_log_writes_no_component_text(
    monkeypatch, tmp_path: Path
) -> None:
    log_path = tmp_path / "missing_tokens.jsonl"
    monkeypatch.setenv("VALVET_MISSING_TOKENS_LOG", str(log_path))
    original = "MLCC_1206_22uF_X7R_10%_50V CONFIDENTIAL"
    cleaned = "1206_22uF_X7R_10%_50V CONFIDENTIAL"

    append_missing_tokens_log(
        {
            "row": 1,
            "type": "CAP",
            "source": "regex",
            "alert": "missing=voltage;present=4/5",
            "original": original,
            "cleaned": cleaned,
        }
    )

    text = log_path.read_text(encoding="utf-8")
    payload = json.loads(text.strip())
    assert "CONFIDENTIAL" not in text
    assert "original" not in payload
    assert "cleaned" not in payload
    assert payload["original_len"] == len(original)
    assert payload["cleaned_len"] == len(cleaned)
    assert payload["alert"].startswith("missing=")
    assert payload["row"] == 1


def test_missing_tokens_log_flag_uses_default_state_dir(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("BOOMER_MISSING_TOKENS_LOG", raising=False)
    monkeypatch.setenv("VALVET_MISSING_TOKENS_LOG", "1")
    monkeypatch.setattr("app_paths.user_state_dir", lambda: tmp_path / "state")

    append_missing_tokens_log({"row": 2, "type": "CAP"})

    assert (tmp_path / "state" / "logs" / "missing_tokens.jsonl").exists()


def test_missing_tokens_log_legacy_env_still_honoured(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("VALVET_MISSING_TOKENS_LOG", raising=False)
    log_path = tmp_path / "legacy.jsonl"
    monkeypatch.setenv("BOOMER_MISSING_TOKENS_LOG", str(log_path))
    append_missing_tokens_log({"row": 3, "original": "HIDDEN"})
    assert "HIDDEN" not in log_path.read_text(encoding="utf-8")


def test_missing_tokens_log_write_failure_does_not_raise(
    monkeypatch, tmp_path: Path
) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setenv("VALVET_MISSING_TOKENS_LOG", str(blocker / "sub" / "m.jsonl"))
    append_missing_tokens_log({"row": 4})  # OSError swallowed


# ---------------------------------------------------------------------------
# 2.7 logger.exception
# ---------------------------------------------------------------------------


def test_exception_carries_traceback(isolated_logging) -> None:
    with captured_root() as cap:
        try:
            raise ValueError("kaboom")
        except ValueError as exc:
            logger.exception("convert failed: %s", exc)

    record = cap.records[-1]
    assert record.levelno == logging.ERROR
    assert record.exc_info is not None
    assert "ValueError: kaboom" in logging.Formatter().formatException(record.exc_info)


def test_exception_is_used_at_step_3d_error_sites() -> None:
    """The four step_3d except-branches must keep the stack."""
    import ast

    src = Path(__file__).resolve().parents[1] / "src" / "step_3d" / "tab.py"
    tree = ast.parse(src.read_text(encoding="utf-8"))
    in_except: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        for sub in ast.walk(node):
            if (
                isinstance(sub, ast.Call)
                and isinstance(sub.func, ast.Attribute)
                and isinstance(sub.func.value, ast.Name)
                and sub.func.value.id == "logger"
            ):
                in_except.append(sub.func.attr)
    assert "error" not in in_except, f"logger.error left inside except: {in_except}"
    assert in_except.count("exception") >= 4


# ---------------------------------------------------------------------------
# 2.9 + 4.12
# ---------------------------------------------------------------------------


def test_step_3d_converter_log_is_truncated() -> None:
    import ast

    src = Path(__file__).resolve().parents[1] / "src" / "step_3d" / "tab.py"
    tree = ast.parse(src.read_text(encoding="utf-8"))
    calls = [
        ast.unparse(n)
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and isinstance(n.func.value, ast.Name)
        and n.func.value.id == "logger"
        and n.func.attr == "error"
        and "converter failed" in ast.unparse(n)
    ]
    assert calls, "the converter-failure log line disappeared"
    assert "res.combined_log" not in calls[0], "raw combined_log still logged"
    assert "detail" in calls[0]


def test_pnp_layer_override_keeps_dirty_flag_and_autosave(tmp_path: Path) -> None:
    """4.12: the layer patch is an edit again, not a silent DataFrame write."""
    pytest.importorskip("PySide6")
    import pandas as pd

    _qapp()
    win = _main_window(tmp_path)
    try:
        df = pd.DataFrame(
            {
                "Designator": ["R1", "C1", "R2"],
                "Mid X": [1.0, 3.0, 5.0],
                "Mid Y": [2.0, 4.0, 6.0],
                "Layer": ["Top", "Top", "Top"],
            }
        )
        win._pnp_df = df
        win.pnp_model.update_dataframe(df)
        win._fill_pnp_combos()
        win._pnp_primary_row_count = 2
        win._pnp_dirty = False
        win.chk_pnp_layer_override.setChecked(True)
        win.edit_pnp_layer_tokens.setText("Top Bottom")

        win._inject_pnp_layer_values()

        assert list(win._pnp_df["Layer"]) == ["Top", "Top", "Bottom"]
        assert win.pnp_model.get_dataframe() is win._pnp_df
        # The whole point of 4.12: dirty flag and autosave both survive.
        assert win._pnp_dirty is True
        assert win._autosave_timer.isActive() is True

        win._pnp_source_path = str(tmp_path / "pnp.csv")
        win._autosave_dirty_working_copies()
        assert list(Path(win._autosave_dir).glob("*")), "no autosave snapshot written"
    finally:
        win.close()
