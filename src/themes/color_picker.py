"""Colour dialog: prefer vcolorpicker (qtpy + PySide6); fallback Qt QColorDialog."""

from __future__ import annotations

import os

from PySide6 import QtCore, QtGui, QtWidgets


def pick_hex_color(
    parent: QtWidgets.QWidget | None, initial_hex: str, title: str
) -> str | None:
    """Return ``#RRGGBB`` if the user confirms, otherwise ``None``."""
    raw = (initial_hex or "").strip()
    q = QtGui.QColor(raw) if raw else QtGui.QColor("#000000")
    if not q.isValid():
        q = QtGui.QColor("#000000")
    lc = (q.red(), q.green(), q.blue())

    try:
        os.environ.setdefault("QT_API", "pyside6")
        from vcolorpicker import ColorPicker
        from vcolorpicker.vcolorpicker import hsv2rgb

        picker = ColorPicker(lightTheme=False, useAlpha=False)
        if parent is not None:
            picker.setParent(parent)
        picker.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        picker.setWindowTitle(title)
        picker.lastcolor = lc
        picker.setRGB(lc)
        picker.rgbChanged()
        r0, g0, b0 = lc
        picker.ui.lastcolor_vis.setStyleSheet(f"background-color: rgb({r0},{g0},{b0})")
        if picker.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return None
        rr, gg, bb = hsv2rgb(picker.color)
        out = QtGui.QColor(int(round(rr)), int(round(gg)), int(round(bb)))
        return out.name()
    except Exception:
        c = QtWidgets.QColorDialog.getColor(q, parent, title)
        if not c.isValid():
            return None
        return c.name()
