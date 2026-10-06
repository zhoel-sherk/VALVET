"""Clean tab logging: no absolute paths, no BOM comment text, tracebacks kept.

Session logs are written into a folder that ships inside the release zip, so
anything ``_log``/``logger`` records travels with the app. This module pins the
three rules that keep that safe:

- no logging call carries an absolute path (structural AST check, not prose);
- the BOM comment text never reaches the log, only the row number and length;
- ``except`` branches use ``logger.exception`` so the stack survives.

It also proves the module still imports and that ``_clean_config_from_ui`` still
wires the codec / library / pipeline surface, so the log edits cannot quietly
break the Convert! path.
"""

from __future__ import annotations

import ast
import json
import logging
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "ui" / "clean_tab.py"

_LOG_FUNCS = {
    "_log",
    "debug",
    "info",
    "warning",
    "error",
    "exception",
    "critical",
    "fatal",
}


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
        str(tmp_path / "clean_log.ini"), QtCore.QSettings.Format.IniFormat
    )
    settings.setValue("experimental/enable_step_3d", False)
    return MainWindow(settings=settings)


def _tree() -> ast.Module:
    return ast.parse(SRC.read_text(encoding="utf-8"))


def _with_parents(tree: ast.Module) -> ast.Module:
    """Attach ``parent`` so attribute wrappers can be told from bare names."""
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            child.parent = node  # type: ignore[attr-defined]
    return tree


def _is_log_call(node: ast.Call) -> bool:
    func = node.func
    if not isinstance(func, ast.Attribute):
        return False
    value = func.value
    if isinstance(value, ast.Name):
        return value.id in ("logger", "self") and func.attr in _LOG_FUNCS
    return func.attr in _LOG_FUNCS


def _mentions_absolute_path(node: ast.AST) -> bool:
    """abspath / realpath / Path(...).resolve() / dirname anywhere inside."""
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        func = sub.func
        if not isinstance(func, ast.Attribute):
            continue
        if func.attr in ("abspath", "realpath", "resolve", "dirname", "expanduser"):
            return True
    return False


def _closes_over_path_variable(node: ast.AST, names: set[str]) -> bool:
    """A bare ``path`` / ``lib_path`` in a log arg would print the whole path.

    ``path.name`` / ``os.path.basename(path)`` is the sanctioned form, so a
    path name that is the value of a basename attribute does not count.
    """
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Name) or sub.id not in names:
            continue
        parent = getattr(sub, "parent", None)
        if (
            isinstance(parent, ast.Attribute)
            and parent.value is sub
            and parent.attr in ("name", "basename")
        ):
            continue
        return True
    return False


# ---------------------------------------------------------------------------
# 1. no absolute path in any log call
# ---------------------------------------------------------------------------


def test_no_log_call_resolves_an_absolute_path() -> None:
    offenders = []
    for node in ast.walk(_tree()):
        if not isinstance(node, ast.Call) or not _is_log_call(node):
            continue
        for arg in node.args:
            if _mentions_absolute_path(arg):
                offenders.append((node.lineno, ast.unparse(arg)))
    assert not offenders, f"absolute path logged from Clean tab: {offenders}"


def test_no_log_call_prints_a_bare_path_variable() -> None:
    """The other shape of the same leak: a path object interpolated directly."""
    offenders = []
    for node in ast.walk(_with_parents(_tree())):
        if not isinstance(node, ast.Call) or not _is_log_call(node):
            continue
        for arg in node.args:
            if _closes_over_path_variable(arg, {"path", "lib_path", "lib_dir"}):
                offenders.append((node.lineno, ast.unparse(arg)))
    assert not offenders, f"path variable logged verbatim from Clean tab: {offenders}"


def test_clean_tab_still_logs_paths_by_name_somewhere() -> None:
    """The positive half: file names stay logged, the directory does not."""
    text = SRC.read_text(encoding="utf-8")
    assert "os.path.abspath" not in text
    assert "os.path.realpath" not in text
    assert 'self._log(f"Clean BOM: saved {name}"' in text
    assert "Learned component saved to {path.name}" in text


# ---------------------------------------------------------------------------
# 2. BOM comment text stays out of the log
# ---------------------------------------------------------------------------


def test_import_log_does_not_print_comment_text(tmp_path: Path) -> None:
    """The sample-row lines carry the row number and length, never the text."""
    pytest.importorskip("PySide6")
    import pandas as pd

    _qapp()
    win = _main_window(tmp_path)
    lines: list[str] = []
    win.log_message.connect(lambda msg, _lvl: lines.append(str(msg)))
    try:
        secret = "ACME-CONFIDENTIAL 0805 33pF 50V lot7731"
        df = pd.DataFrame({"Comment": [secret], "Part": ["12345"]})
        win._bom_df = df
        win.bom_model.update_dataframe(df)

        win._clean_import()

        panel = "\n".join(lines)
        assert secret not in panel
        assert "ACME-CONFIDENTIAL" not in panel
        assert "7731" not in panel
        # Still useful for the operator: which rows and how much text came in.
        assert "sample row 1" in panel
        assert "char(s) imported" in panel
        assert "imported 1 row(s)" in panel
    finally:
        win.close()
        win.deleteLater()


def test_import_log_has_no_truncated_comment_echo() -> None:
    """No sliced copy of a sample row may reach the log either."""
    text = SRC.read_text(encoding="utf-8")
    assert "sample row {i}: {one}" not in text
    assert "one[:70]" not in text


# ---------------------------------------------------------------------------
# 3. logger.exception instead of logger.error(str(e))
# ---------------------------------------------------------------------------


def test_no_logger_error_inside_except_blocks() -> None:
    seen: list[tuple[int, str]] = []
    for node in ast.walk(_tree()):
        if not isinstance(node, ast.ExceptHandler):
            continue
        for sub in ast.walk(node):
            if (
                isinstance(sub, ast.Call)
                and isinstance(sub.func, ast.Attribute)
                and isinstance(sub.func.value, ast.Name)
                and sub.func.value.id == "logger"
            ):
                seen.append((sub.lineno, sub.func.attr))
    assert not [(ln, a) for ln, a in seen if a == "error"], (
        f"logger.error left inside an except block: {seen}"
    )
    assert [a for _, a in seen].count("exception") >= 2


def test_state_only_logger_errors_were_left_alone() -> None:
    """logger.error outside except logs a state, not an exception: untouched."""
    in_except_lines: set[int] = set()
    for node in ast.walk(_tree()):
        if isinstance(node, ast.ExceptHandler):
            for sub in ast.walk(node):
                line = getattr(sub, "lineno", None)
                if line is not None:
                    in_except_lines.add(line)
    outside = [
        node.lineno
        for node in ast.walk(_tree())
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "logger"
        and node.func.attr == "error"
        and node.lineno not in in_except_lines
    ]
    # PN column not configured / no comments imported / comment column missing.
    assert len(outside) >= 3


def test_convert_failure_log_keeps_traceback(
    tmp_path: Path, monkeypatch, caplog
) -> None:
    """Behavioural half: logger.exception really attaches exc_info here."""
    import ui.clean_tab as clean_tab

    _qapp()
    win = _main_window(tmp_path)
    try:
        win._clean_imported_comments = ["CAP 100nF"]

        def boom(_comments, _cfg):
            raise ValueError("kaboom")

        monkeypatch.setattr(clean_tab, "clean_preview", boom)
        with caplog.at_level(logging.ERROR):
            win._run_clean_preview()
        record = next(
            r for r in caplog.records if "clean_preview failed" in r.getMessage()
        )
        assert record.levelno == logging.ERROR
        assert record.exc_info is not None
        assert "ValueError: kaboom" in logging.Formatter().formatException(
            record.exc_info
        )
    finally:
        win.close()
        win.deleteLater()


def test_save_excel_failure_log_keeps_traceback(
    tmp_path: Path, monkeypatch, caplog
) -> None:
    """The other converted site, and its GUI line stays path-free."""
    import pandas as pd

    import ui.clean_tab as clean_tab

    _qapp()
    win = _main_window(tmp_path)
    lines: list[str] = []
    win.log_message.connect(lambda msg, _lvl: lines.append(str(msg)))
    try:
        df = pd.DataFrame({"Comment": ["CAP 100nF"], "Part": ["1"]})
        win._bom_df = df
        win.bom_model.update_dataframe(df)
        monkeypatch.setattr(
            clean_tab.QtWidgets.QFileDialog,
            "getSaveFileName",
            staticmethod(lambda *a, **k: (str(tmp_path / "out.xlsx"), "")),
        )
        monkeypatch.setattr(
            clean_tab.QtWidgets.QMessageBox,
            "critical",
            staticmethod(lambda *a, **k: None),
        )

        def boom(self, *a, **k):
            raise OSError("disk full")

        monkeypatch.setattr(pd.DataFrame, "to_excel", boom)
        with caplog.at_level(logging.ERROR):
            win._clean_save_excel()
        record = next(
            r for r in caplog.records if "save Excel failed" in r.getMessage()
        )
        assert record.exc_info is not None
        assert "OSError: disk full" in logging.Formatter().formatException(
            record.exc_info
        )
        panel = "\n".join(lines)
        assert "Save Excel error" in panel
        assert str(tmp_path) not in panel
    finally:
        win.close()
        win.deleteLater()


def test_save_excel_success_logs_only_the_file_name(
    tmp_path: Path, monkeypatch
) -> None:
    """The success path: the operator still sees which file was written."""
    import pandas as pd

    import ui.clean_tab as clean_tab

    _qapp()
    win = _main_window(tmp_path)
    lines: list[str] = []
    win.log_message.connect(lambda msg, _lvl: lines.append(str(msg)))
    try:
        df = pd.DataFrame({"Comment": ["CAP 100nF"], "Part": ["1"]})
        win._bom_df = df
        win.bom_model.update_dataframe(df)
        monkeypatch.setattr(
            clean_tab.QtWidgets.QFileDialog,
            "getSaveFileName",
            staticmethod(lambda *a, **k: (str(tmp_path / "customer" / "out.xlsx"), "")),
        )
        monkeypatch.setattr(pd.DataFrame, "to_excel", lambda self, *a, **k: None)

        win._clean_save_excel()

        panel = "\n".join(lines)
        assert "Clean BOM: saved out.xlsx" in panel
        assert str(tmp_path) not in panel
    finally:
        win.close()
        win.deleteLater()


# ---------------------------------------------------------------------------
# 4. module still imports; config surface untouched
# ---------------------------------------------------------------------------


def test_clean_tab_module_imports() -> None:
    pytest.importorskip("PySide6")
    import importlib

    mod = importlib.import_module("ui.clean_tab")
    assert hasattr(mod, "CleanTabMixin")


def test_clean_config_from_ui_surface(tmp_path: Path) -> None:
    """use_pn_codecs, use_component_library and the pipeline settings still flow."""
    pytest.importorskip("PySide6")
    _qapp()
    win = _main_window(tmp_path)
    try:
        win._settings.setValue("clean/pipeline_order", json.dumps(["regex", "library"]))
        win._settings.setValue("clean/pipeline_disabled", json.dumps(["hanwha"]))

        win.gb_clean_pn.setChecked(True)
        win.clean_from_db.setChecked(True)
        cfg = win._clean_config_from_ui()
        assert cfg.use_pn_codecs is True
        assert cfg.use_component_library is True
        assert cfg.clean_pipeline_order.index("regex") < cfg.clean_pipeline_order.index(
            "library"
        )
        assert "hanwha" in cfg.clean_pipeline_disabled

        win.gb_clean_pn.setChecked(False)
        win.clean_from_db.setChecked(False)
        off = win._clean_config_from_ui()
        assert off.use_pn_codecs is False
        assert off.use_component_library is False
    finally:
        win.close()
        win.deleteLater()
