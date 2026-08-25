"""Background Gerber parse + SVG raster (QImage). QPixmap stays on the GUI thread."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtGui
from PySide6.QtSvg import QSvgRenderer

from pcb_preview.gerber_io import load_gerber_svg
from pcb_preview.types import GerberSvgPayload

# Must match pcb_preview_tab._GERBER_PX_PER_MM
DEFAULT_PX_PER_MM = 14.0


def rasterize_gerber_svg(
    svg: str, px_per_mm: float = DEFAULT_PX_PER_MM
) -> tuple[QtGui.QImage | None, QtCore.QRectF]:
    if not svg:
        return None, QtCore.QRectF()
    renderer = QSvgRenderer(QtCore.QByteArray(svg.encode("utf-8")))
    if not renderer.isValid():
        return None, QtCore.QRectF()
    vb = renderer.viewBoxF()
    w_px = max(2, int(vb.width() * px_per_mm + 2))
    h_px = max(2, int(vb.height() * px_per_mm + 2))
    img = QtGui.QImage(w_px, h_px, QtGui.QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QtCore.Qt.GlobalColor.transparent)
    p = QtGui.QPainter(img)
    renderer.render(p, QtCore.QRectF(0, 0, w_px, h_px))
    p.end()
    # SVG Y is down after gerbonara/pygerber flip; mirror so manufacturing +Y
    # matches PnP / QGraphicsScene (same millimetre numbers).
    img = img.flipped(QtCore.Qt.Orientation.Vertical)
    return img, vb


def manufacturing_viewbox_mm(payload: GerberSvgPayload) -> QtCore.QRectF:
    """Pose in scene mm: parser bbox, not a 0-origin SVG viewBox."""
    bb = payload.bbox_mm
    return QtCore.QRectF(bb.min_x, bb.min_y, bb.width, bb.height)


class GerberLoadThread(QtCore.QThread):
    result_ready = QtCore.Signal(object)

    def __init__(
        self,
        path: str,
        px_per_mm: float = DEFAULT_PX_PER_MM,
        parent: Optional[QtCore.QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._path = path
        self._px_per_mm = float(px_per_mm)

    def run(self) -> None:
        payload: GerberSvgPayload = load_gerber_svg(self._path)
        image, _svg_vb = rasterize_gerber_svg(payload.svg, self._px_per_mm)
        pose = manufacturing_viewbox_mm(payload)
        self.result_ready.emit((payload, image, pose))
