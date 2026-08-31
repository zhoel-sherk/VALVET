"""Colour dialog via Qt ``QColorDialog``."""

from __future__ import annotations

from PySide6 import QtGui, QtWidgets


def pick_hex_color(
    parent: QtWidgets.QWidget | None, initial_hex: str, title: str
) -> str | None:
    """Return ``#RRGGBB`` if the user confirms, otherwise ``None``."""
    raw = (initial_hex or "").strip()
    q = QtGui.QColor(raw) if raw else QtGui.QColor("#000000")
    if not q.isValid():
        q = QtGui.QColor("#000000")
    c = QtWidgets.QColorDialog.getColor(q, parent, title)
    if not c.isValid():
        return None
    return c.name()
