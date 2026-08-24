"""Compose full application QSS (qdarkstyle + tokens + profile colours)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import qdarkstyle
from PySide6 import QtWidgets

from themes import extra_application_stylesheet
from themes.colour_prefs import (
    merge_table_colours,
    merge_ui_colours,
    profile_colour_qss,
)


def compose_app_stylesheet(
    ui_colours: dict[str, Any] | None,
    table_colours: dict[str, Any] | None,
) -> str:
    u = merge_ui_colours(ui_colours)
    t = merge_table_colours(table_colours)
    return (
        qdarkstyle.load_stylesheet(qt_api="pyside6")
        + extra_application_stylesheet()
        + profile_colour_qss(u, t)
    )


def apply_composed_stylesheet(
    ui_colours: dict[str, Any] | None,
    table_colours: dict[str, Any] | None,
    *,
    apply_fonts: Callable[[], None] | None = None,
) -> None:
    """Set QApplication stylesheet; optionally call ``apply_fonts()`` afterwards."""
    app = QtWidgets.QApplication.instance()
    if app is None:
        return
    app.setStyleSheet(compose_app_stylesheet(ui_colours, table_colours))
    if apply_fonts is not None:
        apply_fonts()
