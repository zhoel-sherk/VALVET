"""CLI package must not pull PySide6."""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import cli.argparse_app as argparse_app
import logger

_SRC = Path(__file__).resolve().parents[1] / "src"
_CLI = _SRC / "cli"


def test_cli_sources_have_no_pyside6_imports() -> None:
    forbidden = ("PySide6", "pcb_preview_tab", "step_3d")
    for path in _CLI.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for needle in forbidden:
                        assert needle not in alias.name, f"{path}: import {alias.name}"
            elif isinstance(node, ast.ImportFrom) and node.module:
                for needle in forbidden:
                    assert needle not in node.module, f"{path}: from {node.module}"


def test_cli_pipeline_and_argparse_import_without_pyside6() -> None:
    script = (
        "import sys; "
        "assert not any(k == 'PySide6' or k.startswith('PySide6.') for k in sys.modules); "
        "import cli.pipeline, cli.argparse_app, cli.hanwha, cli.session; "
        "bad = [k for k in sys.modules if k == 'PySide6' or k.startswith('PySide6.')]; "
        "assert not bad, bad"
    )
    proc = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(_SRC.parent),
        env={**os.environ, "PYTHONPATH": str(_SRC)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_argparse_load_missing_file_logs_error(tmp_path: Path, monkeypatch) -> None:
    """A missing BOM must return non-zero and log the error, not crash silently."""
    monkeypatch.chdir(tmp_path)
    errors: list[str] = []

    def _capture_error(msg: str, *args, **kwargs) -> None:
        errors.append(msg % args if args else msg)

    monkeypatch.setattr(logger, "error", _capture_error)
    code = argparse_app.main(["load-bom", str(tmp_path / "missing.csv")])
    assert code == 1
    assert errors
    assert any("missing.csv" in e for e in errors)


def test_argparse_session_reload_warning_logged(tmp_path: Path, monkeypatch) -> None:
    """A session pointing to a now-missing table must warn, not silently ignore."""
    monkeypatch.chdir(tmp_path)
    sess = tmp_path / "session.json"
    sess.write_text(
        json.dumps({"bom_path": str(tmp_path / "missing.csv"), "pnp_path": ""}),
        encoding="utf-8",
    )
    warnings: list[str] = []

    def _capture_warning(msg: str, *args, **kwargs) -> None:
        warnings.append(msg % args if args else msg)

    monkeypatch.setattr(logger, "warning", _capture_warning)
    code = argparse_app.main(["--session", str(sess), "map"])
    assert code == 0
    assert warnings
    assert any("missing.csv" in w for w in warnings)
