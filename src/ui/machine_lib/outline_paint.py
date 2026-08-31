"""QPainterPath helpers for FootprintOutlineMM (shared by PCB Preview and Machine Lib)."""

from __future__ import annotations

from PySide6 import QtCore, QtGui

from pcb_preview.types import FootprintOutlineMM


def outline_to_path(
    outline: FootprintOutlineMM, y_flip: bool = True
) -> QtGui.QPainterPath:
    path = QtGui.QPainterPath()
    fy = -1.0 if y_flip else 1.0

    def qy(y: float) -> float:
        return y * fy

    for ln in outline.lines:
        path.moveTo(ln.x1, qy(ln.y1))
        path.lineTo(ln.x2, qy(ln.y2))
    for c in outline.circles:
        cy = qy(c.cy)
        path.addEllipse(
            QtCore.QRectF(
                c.cx - c.radius_mm,
                cy - c.radius_mm,
                2 * c.radius_mm,
                2 * c.radius_mm,
            )
        )
    for p in outline.pads:
        w, h = p.width_mm, p.height_mm
        rect = QtCore.QRectF(-w / 2, -h / 2, w, h)
        poly = QtGui.QPolygonF(rect)
        tr = QtGui.QTransform()
        tr.rotate(-p.rotation_deg if y_flip else p.rotation_deg)
        poly = tr.map(poly)
        poly.translate(p.cx, qy(p.cy))
        path.addPolygon(poly)
    return path
