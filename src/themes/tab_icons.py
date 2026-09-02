# SPDX-License-Identifier: MIT
"""16px outline icons for the main window tab bar."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PySide6 import QtGui

_ASSETS = Path(__file__).resolve().parent / "assets" / "tabs"

_TAB_ICON_FILES: dict[str, str] = {
    "project": "project.svg",
    "bom": "bom.svg",
    "pnp": "pnp.svg",
    "package": "package.svg",
    "clean_bom": "clean_bom.svg",
    "merge": "merge.svg",
    "pcb_preview": "pcb_preview.svg",
    "step_3d": "step_3d.svg",
    "machine_lib": "machine_lib.svg",
    "settings": "settings.svg",
}


@lru_cache(maxsize=16)
def tab_icon(key: str) -> QtGui.QIcon:
    name = _TAB_ICON_FILES.get(key)
    if not name:
        return QtGui.QIcon()
    path = _ASSETS / name
    if not path.is_file():
        return QtGui.QIcon()
    return QtGui.QIcon(str(path))
