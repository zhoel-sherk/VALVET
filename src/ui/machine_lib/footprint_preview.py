"""Machine Lib: millimetre footprint canvas + metadata for one Hanwha profile."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from pcb_preview.types import FootprintOutlineMM
from pcb_preview.upd_footprint_builder import FootprintBuildResult
from ui.machine_lib.outline_paint import outline_to_path


def _pin1_meta_line(result: FootprintBuildResult) -> str:
    if result.polarity == "none":
        return "Pin 1: —  (no polarity)"
    if result.pin1_kind == "mdb":
        return (
            f"Pin 1: {result.pin1_x_mm:.3f}, {result.pin1_y_mm:.3f} mm  (MDB)"
        )
    if result.pin1_kind == "lead1":
        return (
            f"Pin 1: {result.pin1_x_mm:.3f}, {result.pin1_y_mm:.3f} mm  "
            "(first reconstructed lead)"
        )
    return "Pin 1: polar  (position not in MDB)"


class _ZoomView(QtWidgets.QGraphicsView):
    def __init__(
        self,
        scene: QtWidgets.QGraphicsScene,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(scene, parent)
        self.setTransformationAnchor(
            QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse
        )
        self.setResizeAnchor(
            QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse
        )
        self.setDragMode(QtWidgets.QGraphicsView.DragMode.ScrollHandDrag)
        self.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        if event.angleDelta().y() == 0:
            return super().wheelEvent(event)
        factor = 1.15 ** (event.angleDelta().y() / 120.0)
        self.scale(factor, factor)
        event.accept()


class FootprintPreviewWidget(QtWidgets.QWidget):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._scene = QtWidgets.QGraphicsScene(self)
        self._view = _ZoomView(self._scene, self)
        self._view.setMinimumWidth(180)
        self._meta = QtWidgets.QLabel("Select a part")
        self._meta.setWordWrap(True)
        self._meta.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._view, stretch=1)
        lay.addWidget(self._meta, stretch=0)

    def set_yamaha_placeholder(self) -> None:
        self.set_idle("Select a Yamaha part")

    def set_idle(self, text: str = "Select a part") -> None:
        self._scene.clear()
        self._meta.setText(text)

    def set_loading(self, name: str) -> None:
        self._meta.setText(f"Loading geometry for {name}…")

    def show_result(self, result: FootprintBuildResult, *, title: str) -> None:
        self._scene.clear()
        lines = [
            f"{title}",
            f"Type: {result.partgroup_name or '—'}  VISIONTYPE={result.vision_type}",
            f"SIZE {result.size_x_mm:.3f} × {result.size_y_mm:.3f} × {result.size_z_mm:.3f} mm",
            f"source={result.outline.source}",
        ]
        if result.partdesc:
            lines.insert(1, result.partdesc)
        lines.append(_pin1_meta_line(result))
        if result.error:
            lines.append(f"Error: {result.error}")
            self._meta.setText("\n".join(lines))
            return
        self._draw_outline(result)
        if result.warnings:
            lines.append(" · ".join(result.warnings))
        self._meta.setText("\n".join(lines))
        self._view.fitInView(
            self._scene.itemsBoundingRect().adjusted(-0.4, -0.4, 0.4, 0.4),
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
        )

    def _draw_outline(self, result: FootprintBuildResult) -> None:
        outline = result.outline
        pin1_x = result.pin1_x_mm
        pin1_y = result.pin1_y_mm
        body = FootprintOutlineMM(
            lines=outline.lines,
            bbox=outline.bbox,
            source=outline.source,
        )
        pads = FootprintOutlineMM(pads=outline.pads, source=outline.source)
        circ = FootprintOutlineMM(circles=outline.circles, source=outline.source)
        y_flip = True
        sx, sy = result.size_x_mm, result.size_y_mm
        if sx > 0 and sy > 0:
            fy = -1.0
            body_rect = QtCore.QRectF(-sx / 2.0, fy * (sy / 2.0), sx, sy)
            fill = self._scene.addRect(body_rect)
            fill.setPen(QtGui.QPen(QtCore.Qt.PenStyle.NoPen))
            fill.setBrush(QtGui.QBrush(QtGui.QColor(80, 160, 255, 45)))
        body_item = self._scene.addPath(outline_to_path(body, y_flip))
        bp = QtGui.QPen(QtGui.QColor(80, 160, 255))
        bp.setCosmetic(True)
        bp.setWidthF(2.0)
        body_item.setPen(bp)
        pad_item = self._scene.addPath(outline_to_path(pads, y_flip))
        pp = QtGui.QPen(QtGui.QColor(70, 200, 110))
        pp.setCosmetic(True)
        pp.setWidthF(2.0)
        pad_item.setPen(pp)
        pad_item.setBrush(QtGui.QBrush(QtGui.QColor(70, 200, 110, 90)))
        circ_item = self._scene.addPath(outline_to_path(circ, y_flip))
        cp = QtGui.QPen(QtGui.QColor(255, 150, 60))
        cp.setCosmetic(True)
        cp.setWidthF(1.5)
        circ_item.setPen(cp)
        bb = outline.bbox
        if bb.width > 0 or bb.height > 0:
            fy = -1.0
            rect = QtCore.QRectF(bb.min_x, fy * bb.max_y, bb.width, bb.height)
            box = self._scene.addRect(rect)
            dp = QtGui.QPen(QtGui.QColor(180, 180, 180, 160))
            dp.setCosmetic(True)
            dp.setStyle(QtCore.Qt.PenStyle.DashLine)
            box.setPen(dp)
        if result.pin1_kind != "none":
            span = min(bb.width, bb.height) if (bb.width > 0 and bb.height > 0) else 1.0
            r = max(0.12, min(0.45, span * 0.08))
            fy = -1.0
            py = fy * pin1_y
            dot = self._scene.addEllipse(pin1_x - r, py - r, 2 * r, 2 * r)
            dot.setBrush(QtGui.QBrush(QtGui.QColor(255, 80, 80)))
            dot.setPen(QtGui.QPen(QtCore.Qt.PenStyle.NoPen))
            label = self._scene.addSimpleText("1")
            font = label.font()
            font.setBold(True)
            label.setFont(font)
            label.setBrush(QtGui.QBrush(QtGui.QColor(255, 220, 220)))
            label.setFlag(
                QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations,
                True,
            )
            label.setPos(pin1_x + r, py - r)
