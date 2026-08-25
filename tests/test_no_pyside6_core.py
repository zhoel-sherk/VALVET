"""Core Qt-free paths must not import PySide6."""

from __future__ import annotations

import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"

_CORE_GLOBS = (
    "smt_processor.py",
    "clean_component.py",
    "clean_alerts.py",
    "hanwha_case_lint.py",
    "pcb_preview/**/*.py",
    "machine_library/**/*.py",
    "step_3d/occ_load.py",
    "services/**/*.py",
    "cli/**/*.py",
    "parsers/**/*.py",
    "hanwha_mdb_edit/core/**/*.py",
)


def _iter_core_files() -> list[Path]:
    files: list[Path] = []
    for pattern in _CORE_GLOBS:
        if "/" in pattern or pattern.endswith(".py"):
            files.extend(_SRC.glob(pattern))
        else:
            p = _SRC / pattern
            if p.is_file():
                files.append(p)
    return [p for p in files if p.is_file()]


def test_core_python_has_no_pyside6_import() -> None:
    hits: list[str] = []
    for path in _iter_core_files():
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                if name == "PySide6" or name.startswith("PySide6."):
                    hits.append(f"{path.relative_to(_SRC)}: {name}")
    assert hits == []
