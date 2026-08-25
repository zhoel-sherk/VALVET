"""CLI package must not pull PySide6."""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

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
