"""
src/main.py          – start the desktop app
src/app/             – shell: window, constants, background workers
src/ui/              – one module per main tab + shared widgets
src/services/        – Qt-free business logic
src/parsers/         – BOM clean parsers
src/pcb_preview/     – Gerber/PnP preview core (no Qt)
"""

from app.constants import (
    _BOM_MAPPING_ROLES,
    _DANGER_CLEAR_BTN_STYLE,
    _MAPPING_COMBO_HIGHLIGHT_STYLE,
    _MAPPING_COMBO_MAX_HEIGHT,
    _MAPPING_I18N_KEY,
    _PNP_MAPPING_ROLES,
    _PREVIEW_TABLE_HDR_HEIGHT,
    _RCL_ROW_DISABLED_STYLE,
    _TABLE_COL_MAX_WIDTH,
    APP_NAME,
    APP_VERSION,
    HIDDEN_TABLE_HAS_HEADER_ROW,
    PROFILE_LAST_ACTIVE_KEY,
    PROFILE_NAMES_KEY,
    PROFILE_STATE_VERSION,
    SETTINGS_APP,
    SETTINGS_ORG,
    VERSION_DISPLAY,
)
from app.window import MainWindow

__all__ = [
    "APP_NAME",
    "APP_VERSION",
    "HIDDEN_TABLE_HAS_HEADER_ROW",
    "MainWindow",
    "PROFILE_LAST_ACTIVE_KEY",
    "PROFILE_NAMES_KEY",
    "PROFILE_STATE_VERSION",
    "SETTINGS_APP",
    "SETTINGS_ORG",
    "VERSION_DISPLAY",
    "_BOM_MAPPING_ROLES",
    "_DANGER_CLEAR_BTN_STYLE",
    "_MAPPING_COMBO_HIGHLIGHT_STYLE",
    "_MAPPING_COMBO_MAX_HEIGHT",
    "_MAPPING_I18N_KEY",
    "_PNP_MAPPING_ROLES",
    "_PREVIEW_TABLE_HDR_HEIGHT",
    "_RCL_ROW_DISABLED_STYLE",
    "_TABLE_COL_MAX_WIDTH",
]
