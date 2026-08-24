"""Resolve VALVET window / taskbar icon (dev tree and PyInstaller)."""

from __future__ import annotations

import sys
from pathlib import Path


def _meipass() -> Path | None:
    raw = getattr(sys, "_MEIPASS", None)
    return Path(raw) if raw else None


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def application_icon_path() -> Path | None:
    names = ("icon.ico", "icon-256.png", "icon-512.png", "icon.svg")
    bases: list[Path] = []
    mp = _meipass()
    if mp is not None:
        bases.append(mp / "img")
        bases.append(mp)
    bases.append(repo_root() / "img")
    for base in bases:
        for name in names:
            p = base / name
            if p.is_file():
                return p
    return None
