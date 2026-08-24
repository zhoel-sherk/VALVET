"""
Cross-platform writable directories for VALVET (no business logic).

Uses ``platformdirs`` with ``roaming=True`` on Windows so paths stay aligned with
``QStandardPaths.AppDataLocation`` / typical ``QSettings`` file locations.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ORG = "VALVET"
_APP = "VALVET"


def user_state_dir() -> Path:
    """Per-user app data root (Roaming on Windows, XDG data home on Linux, Application Support on macOS)."""
    try:
        from platformdirs import user_data_dir

        return Path(user_data_dir(_APP, _ORG, roaming=True))
    except ImportError:
        return _fallback_user_state_dir()


def _fallback_user_state_dir() -> Path:
    if os.name == "nt":
        base = os.environ.get("APPDATA", "").strip()
        if base:
            return Path(base) / _ORG / _APP
        return Path.home() / _ORG / _APP
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / _ORG / _APP
    xdg = os.environ.get("XDG_DATA_HOME", "").strip()
    if xdg:
        return Path(xdg) / _APP
    return Path.home() / ".local" / "share" / _APP


def autosave_root() -> Path:
    return user_state_dir() / "autosave"


def hanwha_mdb_autosave_root() -> Path:
    return autosave_root() / "hanwha_mdb"


def pcb_preview_data_root() -> Path:
    """
    Footprint / PCB preview cache. Prefer legacy Linux path if it already exists
    so existing installs keep their cache; new installs use unified layout under user_state_dir.
    """
    legacy = Path.home() / ".local" / "share" / "VALVET" / "pcb_preview_data"
    unified = user_state_dir() / "pcb_preview_data"
    if legacy.exists() and legacy.is_dir():
        return legacy
    unified.mkdir(parents=True, exist_ok=True)
    return unified


def user_parsers_dir() -> Path:
    """Optional user BOM parser scripts (``*.py``). Same family of paths as autosave / QSettings data."""
    d = user_state_dir() / "user_parsers"
    d.mkdir(parents=True, exist_ok=True)
    return d
