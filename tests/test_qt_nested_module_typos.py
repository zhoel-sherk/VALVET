"""Reject nested PySide6 module access (QtCore.QtCore, …)."""

from __future__ import annotations

from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"

_BAD = (
    "QtCore.QtCore",
    "QtGui.QtGui",
    "QtWidgets.QtWidgets",
)


def test_src_has_no_nested_pyside_module_access() -> None:
    hits: list[str] = []
    for path in _SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(_SRC).as_posix()
        for needle in _BAD:
            if needle in text:
                hits.append(f"{rel}: {needle}")
    assert hits == []
