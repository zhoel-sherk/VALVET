"""Clean BOM tab (package). Public API unchanged: CleanTabMixin."""

from __future__ import annotations

from ui.clean_tab.actions import CleanActionsMixin
from ui.clean_tab.build import CleanBuildMixin
from ui.clean_tab.helpers import (
    _CLEAN_PRESET_COMPACT,
    _CLEAN_PRESET_SMT,
    _clean_input_cells,
    _clean_int_list,
    _clean_preview_frame,
)
from ui.clean_tab.settings import CleanSettingsMixin
from ui.clean_tab.texts import CleanTextsMixin
from ui.clean_tab.view_state import CleanViewStateMixin


class CleanTabMixin(
    CleanBuildMixin,
    CleanViewStateMixin,
    CleanTextsMixin,
    CleanSettingsMixin,
    CleanActionsMixin,
):
    """Composed Clean BOM mixin; MainWindow inherits this unchanged."""


__all__ = [
    "CleanTabMixin",
    "_CLEAN_PRESET_COMPACT",
    "_CLEAN_PRESET_SMT",
    "_clean_input_cells",
    "_clean_int_list",
    "_clean_preview_frame",
]
