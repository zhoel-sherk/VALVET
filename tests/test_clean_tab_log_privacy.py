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
from typing import Callable

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


def _check_no_absolute_paths() -> list[str]:
    """Check that no log call resolves an absolute path."""
    offenders = []
    for node in ast.walk(_tree()):
        if not isinstance(node, ast.Call) or not _is_log_call(node):
            continue
        for arg in node.args:
            if _mentions_absolute_path(arg):
                offenders.append(f"line {node.lineno}: {ast.unparse(arg)}")
    return offenders


def _check_no_bare_path_variables() -> list[str]:
    """Check that no log call prints a bare path variable."""
    offenders = []
    for node in ast.walk(_with_parents(_tree())):
        if not isinstance(node, ast.Call) or not _is_log_call(node):
            continue
        for arg in node.args:
            if _closes_over_path_variable(arg, {"path", "lib_path", "lib_dir"}):
                offenders.append(f"line {node.lineno}: {ast.unparse(arg)}")
    return offenders


def _check_still_logs_paths_by_name() -> list[str]:
    """Positive check: file names are still logged."""
    text = SRC.read_text(encoding="utf-8")
    violations = []
    if "os.path.abspath" in text:
        violations.append("os.path.abspath found")
    if "os.path.realpath" in text:
        violations.append("os.path.realpath found")
    if 'self._log(f"Clean BOM: saved {name}"' not in text:
        violations.append("saved file name log not found")
    if "Learned component saved to {path.name}" not in text:
        violations.append("component saved log not found")
    return violations


def _check_no_truncated_comments() -> list[str]:
    """Check that no truncated comment echoes in logs."""
    text = SRC.read_text(encoding="utf-8")
    violations = []
    if "sample row {i}: {one}" in text:
        violations.append("truncated sample row format found")
    if "one[:70]" in text:
        violations.append("sliced comment variable found")
    return violations


def _check_logger_exception_in_except() -> list[str]:
    """Check that logger.error is not used inside except blocks."""
    seen = []
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

    violations = []
    errors_in_except = [(ln, a) for ln, a in seen if a == "error"]
    if errors_in_except:
        violations.append(f"logger.error in except blocks: {errors_in_except}")

    exception_count = [a for _, a in seen].count("exception")
    if exception_count < 2:
        violations.append(
            f"Expected at least 2 logger.exception calls, found {exception_count}"
        )

    return violations


def _check_logger_error_outside_except() -> list[str]:
    """Check that logger.error outside except blocks is preserved."""
    in_except_lines = set()
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

    violations = []
    if len(outside) < 3:
        violations.append(
            f"Expected at least 3 logger.error calls outside except, found {len(outside)}"
        )

    return violations


# ---------------------------------------------------------------------------
# 1. no absolute path in any log call
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "check_name,check_func",
    [
        ("no_absolute_paths", _check_no_absolute_paths),
        ("no_bare_path_variables", _check_no_bare_path_variables),
        ("still_logs_paths_by_name", _check_still_logs_paths_by_name),
        ("no_truncated_comments", _check_no_truncated_comments),
        ("logger_exception_in_except", _check_logger_exception_in_except),
        ("logger_error_outside_except", _check_logger_error_outside_except),
    ],
    ids=[
        "no-absolute-paths",
        "no-bare-path-variables",
        "still-logs-paths-by-name",
        "no-truncated-comments",
        "logger-exception-in-except",
        "logger-error-outside-except",
    ],
)
def test_ast_log_checks(check_name: str, check_func: Callable) -> None:
    """Parameterized AST checks for clean_tab.py logging."""
    violations = check_func()
    assert not violations, f"{check_name} failed: {violations}"


# ---------------------------------------------------------------------------
# 2. BOM comment text stays out of the log
# ---------------------------------------------------------------------------


def test_import_log_does_not_print_comment_text(main_window) -> None:
    """The sample-row lines carry the row number and length, never the text."""
    pytest.importorskip("PySide6")
    import pandas as pd

    lines: list[str] = []
    main_window.log_message.connect(lambda msg, _lvl: lines.append(str(msg)))
    secret = "ACME-CONFIDENTIAL 0805 33pF 50V lot7731"
    df = pd.DataFrame({"Comment": [secret], "Part": ["12345"]})
    main_window._bom_df = df
    main_window.bom_model.update_dataframe(df)

    main_window._clean_import()

    panel = "\n".join(lines)
    assert secret not in panel
    assert "ACME-CONFIDENTIAL" not in panel
    assert "7731" not in panel
    # Still useful for the operator: which rows and how much text came in.
    assert "sample row 1" in panel
    assert "char(s) imported" in panel
    assert "imported 1 row(s)" in panel


def test_convert_failure_log_keeps_traceback(main_window, monkeypatch, caplog) -> None:
    """Behavioural half: logger.exception really attaches exc_info here."""
    import ui.clean_tab as clean_tab

    main_window._clean_imported_comments = ["CAP 100nF"]

    def boom(_comments, _cfg):
        raise ValueError("kaboom")

    monkeypatch.setattr(clean_tab, "clean_preview", boom)
    with caplog.at_level(logging.ERROR):
        main_window._run_clean_preview()
    record = next(r for r in caplog.records if "clean_preview failed" in r.getMessage())
    assert record.levelno == logging.ERROR
    assert record.exc_info is not None
    assert "ValueError: kaboom" in logging.Formatter().formatException(record.exc_info)


def test_save_excel_failure_log_keeps_traceback(
    main_window, tmp_path: Path, monkeypatch, caplog
) -> None:
    """The other converted site, and its GUI line stays path-free."""
    import pandas as pd

    import ui.clean_tab as clean_tab

    lines: list[str] = []
    main_window.log_message.connect(lambda msg, _lvl: lines.append(str(msg)))
    df = pd.DataFrame({"Comment": ["CAP 100nF"], "Part": ["1"]})
    main_window._bom_df = df
    main_window.bom_model.update_dataframe(df)
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
        main_window._clean_save_excel()
    record = next(r for r in caplog.records if "save Excel failed" in r.getMessage())
    assert record.exc_info is not None
    assert "OSError: disk full" in logging.Formatter().formatException(record.exc_info)
    panel = "\n".join(lines)
    assert "Save Excel error" in panel
    assert str(tmp_path) not in panel


def test_save_excel_success_logs_only_the_file_name(
    main_window, tmp_path: Path, monkeypatch
) -> None:
    """The success path: the operator still sees which file was written."""
    import pandas as pd

    import ui.clean_tab as clean_tab

    lines: list[str] = []
    main_window.log_message.connect(lambda msg, _lvl: lines.append(str(msg)))
    df = pd.DataFrame({"Comment": ["CAP 100nF"], "Part": ["1"]})
    main_window._bom_df = df
    main_window.bom_model.update_dataframe(df)
    monkeypatch.setattr(
        clean_tab.QtWidgets.QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: (str(tmp_path / "customer" / "out.xlsx"), "")),
    )
    monkeypatch.setattr(
        clean_tab.QtWidgets.QMessageBox,
        "information",
        staticmethod(lambda *a, **k: None),
    )
    monkeypatch.setattr(pd.DataFrame, "to_excel", lambda self, *a, **k: None)

    main_window._clean_save_excel()

    panel = "\n".join(lines)
    assert "Clean BOM: saved out.xlsx" in panel
    assert str(tmp_path) not in panel


# ---------------------------------------------------------------------------
# 4. module still imports; config surface untouched
# ---------------------------------------------------------------------------


def test_convert_warns_when_machine_library_import_is_running(
    main_window, monkeypatch
) -> None:
    """Convert! must not present stale Hanwha matches as final.

    The partname set only refreshes when the ``.mdb`` → SQLite import finishes,
    so a Convert! before that matches the previous library (or nothing).
    """
    main_window.clean_from_hanwha_mdb.setChecked(True)
    monkeypatch.setattr(
        main_window._machine_library_tab,
        "mdb_import_in_progress",
        lambda: True,
        raising=False,
    )
    lines: list[str] = []
    main_window.log_message.connect(lambda msg, _lvl: lines.append(str(msg)))

    main_window._warn_if_machine_library_is_importing()

    panel = "\n".join(lines)
    assert "still importing" in panel
    assert "Convert! again" in panel


def test_convert_does_not_warn_after_import_finishes(main_window, monkeypatch) -> None:
    main_window.clean_from_hanwha_mdb.setChecked(True)
    monkeypatch.setattr(
        main_window._machine_library_tab,
        "mdb_import_in_progress",
        lambda: False,
        raising=False,
    )
    lines: list[str] = []
    main_window.log_message.connect(lambda msg, _lvl: lines.append(str(msg)))

    main_window._warn_if_machine_library_is_importing()

    assert not [line for line in lines if "still importing" in line]


def test_convert_does_not_warn_without_hanwha_matching(
    main_window, monkeypatch
) -> None:
    """The warning only makes sense when Clean BOM reads the Hanwha partnames."""
    main_window.clean_from_hanwha_mdb.setChecked(False)
    monkeypatch.setattr(
        main_window._machine_library_tab,
        "mdb_import_in_progress",
        lambda: True,
        raising=False,
    )
    lines: list[str] = []
    main_window.log_message.connect(lambda msg, _lvl: lines.append(str(msg)))

    main_window._warn_if_machine_library_is_importing()

    assert not [line for line in lines if "still importing" in line]


def test_clean_tab_module_imports() -> None:
    pytest.importorskip("PySide6")
    import importlib

    mod = importlib.import_module("ui.clean_tab")
    assert hasattr(mod, "CleanTabMixin")


def test_clean_config_from_ui_surface(main_window) -> None:
    """use_pn_codecs, use_component_library and the pipeline settings still flow."""
    pytest.importorskip("PySide6")

    main_window._settings.setValue(
        "clean/pipeline_order", json.dumps(["regex", "library"])
    )
    main_window._settings.setValue("clean/pipeline_disabled", json.dumps(["hanwha"]))

    main_window.gb_clean_pn.setChecked(True)
    main_window.clean_from_db.setChecked(True)
    cfg = main_window._clean_config_from_ui()
    assert cfg.use_pn_codecs is True
    assert cfg.use_component_library is True
    assert cfg.clean_pipeline_order.index("regex") < cfg.clean_pipeline_order.index(
        "library"
    )
    assert "hanwha" in cfg.clean_pipeline_disabled

    main_window.gb_clean_pn.setChecked(False)
    main_window.clean_from_db.setChecked(False)
    off = main_window._clean_config_from_ui()
    assert off.use_pn_codecs is False
    assert off.use_component_library is False
