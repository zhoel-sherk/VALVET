"""PCB Preview tab: QGraphicsView + Gerber layers + PnP overlay."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtSvg import QSvgRenderer

from pcb_preview.alignment import Similarity2D
from pcb_preview.footprint_db import FootprintStore
from pcb_preview.gerber_io import (
    load_gerber_svg,
    peek_rs274x_linear_unit,
    scale_bbox_mm,
)
from pcb_preview.types import (
    BBoxMM,
    FootprintOutlineMM,
    GerberSvgPayload,
    PlacementRecord,
)

import pcb_preview_bridge


# Centroid marker radius in mm (scene units); stroke is cosmetic (pixels) so it stays visible.
_CENTROID_RADIUS_MM = 0.45
_SEL_RING_SCALE = 2.8
# Ref label height in scene mm (~font * scale). User can raise this in Settings.
_LABEL_SCENE_SCALE = 0.12
# Half-length of each arm of the centroid X-cross (mm, local item space).
_CROSS_HALF_MM = 0.9
# Gerber raster: pixels per mm of SVG viewBox (higher = sharper, more memory).
_GERBER_PX_PER_MM = 14.0


def _outline_to_path(
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
                c.cx - c.radius_mm, cy - c.radius_mm, 2 * c.radius_mm, 2 * c.radius_mm
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


def _similarity_to_qtransform(sim: Similarity2D) -> QtGui.QTransform:
    s, c, sn = sim.scale, sim.cos_t, sim.sin_t
    return QtGui.QTransform(s * c, s * sn, -s * sn, s * c, sim.tx, sim.ty)


def _pnp_mirror_transform(mx: int, my: int) -> QtGui.QTransform:
    """Mirror PnP in board mm before similarity: x' = mx*x, y' = my*y (mx,my ∈ {−1, +1})."""
    return QtGui.QTransform(float(mx), 0.0, 0.0, float(my), 0.0, 0.0)


def _compose_pnp_preview_transform(
    sim: Similarity2D, mirror_x: int, mirror_y: int
) -> QtGui.QTransform:
    """Apply mirror in placement space, then similarity: p ↦ sim(mirror(p))."""
    return _similarity_to_qtransform(sim) * _pnp_mirror_transform(mirror_x, mirror_y)


def _bbox_union(a: QtCore.QRectF, b: QtCore.QRectF) -> QtCore.QRectF:
    if not a.isValid():
        return b
    if not b.isValid():
        return a
    return a.united(b)


class ZoomGraphicsView(QtWidgets.QGraphicsView):
    """Wheel zoom (anchor under mouse); scene coordinates stay in mm for PnP + Gerber."""

    def __init__(
        self,
        scene: QtWidgets.QGraphicsScene,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(scene, parent)
        self.setTransformationAnchor(
            QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse
        )
        self.setResizeAnchor(QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse)

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        if event.angleDelta().y() == 0:
            return super().wheelEvent(event)
        factor = 1.15 ** (event.angleDelta().y() / 120.0)
        self.scale(factor, factor)
        event.accept()


class PlacementGroupItem(QtWidgets.QGraphicsItemGroup):
    """One ref: centroid (always) + optional footprint path + label."""

    def __init__(self, placement: PlacementRecord, outline: FootprintOutlineMM):
        super().__init__()
        self._placement = placement
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setData(0, placement.ref)

        r = _CENTROID_RADIUS_MM
        self._dot = QtWidgets.QGraphicsEllipseItem(-r, -r, 2 * r, 2 * r)
        self._dot.setBrush(QtGui.QBrush(QtGui.QColor(255, 120, 20, 220)))
        dp = QtGui.QPen(QtGui.QColor(180, 60, 0))
        dp.setCosmetic(True)
        dp.setWidthF(2.0)
        self._dot.setPen(dp)
        self._dot.setZValue(1)
        self.addToGroup(self._dot)

        path = _outline_to_path(outline)
        self._path_item = QtWidgets.QGraphicsPathItem(path)
        pp = QtGui.QPen(QtGui.QColor(60, 140, 255))
        pp.setCosmetic(True)
        pp.setWidthF(2.0)
        pp.setJoinStyle(QtCore.Qt.PenJoinStyle.RoundJoin)
        pp.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
        self._path_item.setPen(pp)
        self._path_item.setZValue(0)
        self.addToGroup(self._path_item)

        h = _CROSS_HALF_MM
        self._cross1 = QtWidgets.QGraphicsLineItem(-h, -h, h, h)
        self._cross2 = QtWidgets.QGraphicsLineItem(-h, h, h, -h)
        xp = QtGui.QPen(QtGui.QColor(255, 210, 120))
        xp.setCosmetic(True)
        xp.setWidthF(1.5)
        xp.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
        self._cross1.setPen(xp)
        self._cross2.setPen(xp)
        self._cross1.setZValue(0.5)
        self._cross2.setZValue(0.5)
        self.addToGroup(self._cross1)
        self.addToGroup(self._cross2)

        self._label = QtWidgets.QGraphicsSimpleTextItem(placement.ref)
        self._label.setBrush(QtGui.QBrush(QtGui.QColor(255, 235, 160)))
        lf = self._label.font()
        lf.setFamily("Sans")
        lf.setPointSizeF(10.0)
        self._label.setFont(lf)
        self._label.setPos(r + 0.2, -r - 0.2)
        self._label.setScale(_LABEL_SCENE_SCALE)
        self._label.setZValue(2)
        self.addToGroup(self._label)

        rr = _CENTROID_RADIUS_MM * _SEL_RING_SCALE
        self._sel_ring = QtWidgets.QGraphicsEllipseItem(-rr, -rr, 2 * rr, 2 * rr)
        rp = QtGui.QPen(QtGui.QColor(255, 255, 80))
        rp.setCosmetic(True)
        rp.setWidthF(4.0)
        rp.setStyle(QtCore.Qt.PenStyle.DashLine)
        self._sel_ring.setPen(rp)
        self._sel_ring.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        self._sel_ring.setZValue(3)
        self._sel_ring.setVisible(False)
        self.addToGroup(self._sel_ring)

        self.setPos(placement.x_mm, placement.y_mm)
        self.setRotation(-placement.rotation_deg)

    def path_item(self) -> QtWidgets.QGraphicsPathItem:
        return self._path_item

    def ref(self) -> str:
        return self._placement.ref

    def apply_selection_style(
        self, selected: bool, ref_a: bool = False, ref_b: bool = False
    ) -> None:
        ring_on = selected or ref_a or ref_b
        self._sel_ring.setVisible(ring_on)
        if selected:
            dp = QtGui.QPen(QtGui.QColor(255, 255, 80))
            dp.setCosmetic(True)
            dp.setWidthF(4.0)
            dp.setStyle(QtCore.Qt.PenStyle.DashLine)
            self._sel_ring.setPen(dp)
        elif ref_a and not ref_b:
            ap = QtGui.QPen(QtGui.QColor(80, 220, 255))
            ap.setCosmetic(True)
            ap.setWidthF(5.0)
            ap.setStyle(QtCore.Qt.PenStyle.SolidLine)
            self._sel_ring.setPen(ap)
        elif ref_b and not ref_a:
            bp = QtGui.QPen(QtGui.QColor(255, 120, 255))
            bp.setCosmetic(True)
            bp.setWidthF(5.0)
            bp.setStyle(QtCore.Qt.PenStyle.SolidLine)
            self._sel_ring.setPen(bp)
        elif ref_a and ref_b:
            dp = QtGui.QPen(QtGui.QColor(255, 255, 255))
            dp.setCosmetic(True)
            dp.setWidthF(5.0)
            dp.setStyle(QtCore.Qt.PenStyle.DashLine)
            self._sel_ring.setPen(dp)
        elif ring_on:
            mp = QtGui.QPen(QtGui.QColor(160, 200, 255))
            mp.setCosmetic(True)
            mp.setWidthF(3.0)
            mp.setStyle(QtCore.Qt.PenStyle.DotLine)
            self._sel_ring.setPen(mp)

        if selected:
            p = QtGui.QPen(QtGui.QColor(255, 90, 60))
            p.setCosmetic(True)
            p.setWidthF(4.5)
            self._path_item.setPen(p)
            cxp = QtGui.QPen(QtGui.QColor(255, 255, 200))
            cxp.setCosmetic(True)
            cxp.setWidthF(2.0)
            cxp.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
            self._cross1.setPen(cxp)
            self._cross2.setPen(cxp)
            self._dot.setBrush(QtGui.QBrush(QtGui.QColor(255, 220, 60, 255)))
            dr = _CENTROID_RADIUS_MM * 1.35
            self._dot.setRect(-dr, -dr, 2 * dr, 2 * dr)
            self._label.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 220)))
        elif ref_a or ref_b:
            p = QtGui.QPen(QtGui.QColor(120, 200, 255))
            p.setCosmetic(True)
            p.setWidthF(2.8)
            self._path_item.setPen(p)
            cxp = QtGui.QPen(QtGui.QColor(255, 230, 160))
            cxp.setCosmetic(True)
            cxp.setWidthF(1.8)
            cxp.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
            self._cross1.setPen(cxp)
            self._cross2.setPen(cxp)
            self._dot.setBrush(QtGui.QBrush(QtGui.QColor(255, 180, 40, 230)))
            dr = _CENTROID_RADIUS_MM * 1.12
            self._dot.setRect(-dr, -dr, 2 * dr, 2 * dr)
            self._label.setBrush(QtGui.QBrush(QtGui.QColor(255, 250, 200)))
        else:
            p = QtGui.QPen(QtGui.QColor(60, 140, 255))
            p.setCosmetic(True)
            p.setWidthF(2.0)
            self._path_item.setPen(p)
            cxp = QtGui.QPen(QtGui.QColor(255, 210, 120))
            cxp.setCosmetic(True)
            cxp.setWidthF(1.5)
            cxp.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
            self._cross1.setPen(cxp)
            self._cross2.setPen(cxp)
            self._dot.setBrush(QtGui.QBrush(QtGui.QColor(255, 120, 20, 220)))
            dr = _CENTROID_RADIUS_MM
            self._dot.setRect(-dr, -dr, 2 * dr, 2 * dr)
            self._label.setBrush(QtGui.QBrush(QtGui.QColor(255, 235, 160)))

    def set_label_scale(self, scale: float) -> None:
        self._label.setScale(max(0.04, float(scale)))

    def set_labels_visible(self, on: bool) -> None:
        self._label.setVisible(on)

    def set_footprint_visible(self, on: bool) -> None:
        self._path_item.setVisible(on)


class PnpArrowNudgeBar(QtWidgets.QWidget):
    """Compact diamond nudge pad around the step field (mm); fixed width."""

    nudgeRequested = QtCore.Signal(float, float)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        self._step = QtWidgets.QLineEdit("0.5")
        self._step.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._step.setFixedWidth(46)
        self._step.setMaximumHeight(30)
        self._step.setToolTip("Step size in millimeters for nudge buttons")
        val = QtGui.QDoubleValidator(0.0001, 1.0e9, 6, self)
        val.setNotation(QtGui.QDoubleValidator.Notation.StandardNotation)
        self._step.setValidator(val)
        st = self.style()
        lay = QtWidgets.QGridLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        gap = 4
        lay.setHorizontalSpacing(gap)
        lay.setVerticalSpacing(gap)
        lay.setColumnStretch(0, 0)
        lay.setColumnStretch(1, 0)
        lay.setColumnStretch(2, 0)
        lay.setRowStretch(0, 0)
        lay.setRowStretch(1, 0)
        lay.setRowStretch(2, 0)
        sz = 36
        icon_sz = 28
        for gr, gc, dx, dy, spix in (
            (0, 1, 0.0, -1.0, QtWidgets.QStyle.StandardPixmap.SP_ArrowUp),
            (1, 0, -1.0, 0.0, QtWidgets.QStyle.StandardPixmap.SP_ArrowLeft),
            (1, 2, 1.0, 0.0, QtWidgets.QStyle.StandardPixmap.SP_ArrowRight),
            (2, 1, 0.0, 1.0, QtWidgets.QStyle.StandardPixmap.SP_ArrowDown),
        ):
            tb = QtWidgets.QToolButton()
            tb.setIcon(st.standardIcon(spix))
            tb.setIconSize(QtCore.QSize(icon_sz, icon_sz))
            tb.setFixedSize(sz, sz)
            tb.setAutoRaise(True)
            tb.setToolTip("Shift PnP placements")
            tb.setAutoRepeat(True)
            tb.setAutoRepeatDelay(400)
            tb.setAutoRepeatInterval(55)
            tb.clicked.connect(lambda _=False, ux=dx, uy=dy: self._emit_nudge(ux, uy))
            lay.addWidget(tb, gr, gc)
        lay.addWidget(self._step, 1, 1, QtCore.Qt.AlignmentFlag.AlignCenter)
        m = lay.contentsMargins()
        w = m.left() + m.right() + 3 * sz + 2 * gap
        h = m.top() + m.bottom() + 3 * sz + 2 * gap
        self.setFixedSize(w, h)

    def step_mm(self) -> float:
        t = self._step.text().strip().replace(",", ".")
        try:
            v = float(t)
            return v if v > 0 else 0.5
        except ValueError:
            return 0.5

    def _emit_nudge(self, dx: float, dy: float) -> None:
        s = self.step_mm()
        self.nudgeRequested.emit(dx * s, dy * s)


@dataclass
class _GerberLayerRow:
    """One loaded Gerber bitmap in the scene."""

    path: str
    display_name: str
    pixmap_item: QtWidgets.QGraphicsPixmapItem
    bbox_mm: BBoxMM


class PcbPreviewTab(QtWidgets.QWidget):
    """Gerber SVG layers + PnP overlay, 2-point alignment, list navigation."""

    #: Emitted when the user picks mm (True) or mils (False) for PnP table X/Y (mirrors main window).
    pnp_xy_unit_mm_selected = QtCore.Signal(bool)

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
        settings: Optional[Any] = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self._store = FootprintStore()
        self._placements: list[PlacementRecord] = []
        self._items: dict[str, PlacementGroupItem] = {}
        self._layers: list[_GerberLayerRow] = []
        self._placements_root = QtWidgets.QGraphicsItemGroup()
        self._preview_sim = Similarity2D.identity()
        self._pnp_mirror_x = 1
        self._pnp_mirror_y = 1
        self._px_per_mm = _GERBER_PX_PER_MM
        self._label_scale = _LABEL_SCENE_SCALE
        self._show_labels = True
        self._show_footprints = True
        self._placements_fp: tuple[Any, ...] | None = None
        self._did_initial_fit = False

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        top = QtWidgets.QHBoxLayout()
        self._btn_gerber = QtWidgets.QPushButton("Add Gerber")
        self._btn_gerber.clicked.connect(self._browse_gerber)
        top.addWidget(self._btn_gerber)
        self._btn_fit = QtWidgets.QPushButton("Fit all")
        self._btn_fit.clicked.connect(self._fit_all_with_reset_view)
        top.addWidget(self._btn_fit)
        self._btn_zoom_in = QtWidgets.QPushButton("Zoom +")
        top.addWidget(self._btn_zoom_in)
        self._btn_zoom_out = QtWidgets.QPushButton("Zoom −")
        top.addWidget(self._btn_zoom_out)
        self._btn_reset = QtWidgets.QPushButton("Reset transform")
        self._btn_reset.clicked.connect(self._reset_transform)
        top.addWidget(self._btn_reset)
        self._btn_center = QtWidgets.QPushButton("Center on selection")
        self._btn_center.clicked.connect(self._center_selection)
        top.addWidget(self._btn_center)
        top.addStretch()
        root.addLayout(top)

        self._scene = QtWidgets.QGraphicsScene()
        self._scene.setSceneRect(-5, -5, 200, 200)
        self._view = ZoomGraphicsView(self._scene)
        self._view.setDragMode(QtWidgets.QGraphicsView.DragMode.RubberBandDrag)
        self._view.setRenderHints(
            QtGui.QPainter.RenderHint.Antialiasing
            | QtGui.QPainter.RenderHint.SmoothPixmapTransform
        )
        root.addWidget(self._view, 1)

        self._btn_zoom_in.clicked.connect(self._zoom_view_in)
        self._btn_zoom_out.clicked.connect(self._zoom_view_out)

        self._chk_mirror_x = QtWidgets.QCheckBox("Mirror PnP X")
        self._chk_mirror_x.toggled.connect(self._on_mirror_x_toggled)
        self._chk_mirror_y = QtWidgets.QCheckBox("Mirror PnP Y")
        self._chk_mirror_y.toggled.connect(self._on_mirror_y_toggled)

        grp_u = QtWidgets.QGroupBox("Gerber units")
        self._grp_gunit = grp_u
        lu = QtWidgets.QVBoxLayout(grp_u)
        self._rb_g_auto = QtWidgets.QRadioButton("Auto")
        self._rb_g_mm = QtWidgets.QRadioButton("mm")
        self._rb_g_in = QtWidgets.QRadioButton("inch → mm")
        self._rb_g_auto.setChecked(True)
        self._bg_gunit = QtWidgets.QButtonGroup(self)
        for rb in (self._rb_g_auto, self._rb_g_mm, self._rb_g_in):
            self._bg_gunit.addButton(rb)
            lu.addWidget(rb)

        grp_pnp_xy = QtWidgets.QGroupBox("PnP coordinates")
        self._grp_pnp_xy = grp_pnp_xy
        lpxy = QtWidgets.QHBoxLayout(grp_pnp_xy)
        self._rb_pnp_xy_mm = QtWidgets.QRadioButton("mm")
        self._rb_pnp_xy_mils = QtWidgets.QRadioButton("mils")
        self._rb_pnp_xy_mm.setChecked(True)
        self._rb_pnp_xy_mm.toggled.connect(
            lambda on: on and self.pnp_xy_unit_mm_selected.emit(True)
        )
        self._rb_pnp_xy_mils.toggled.connect(
            lambda on: on and self.pnp_xy_unit_mm_selected.emit(False)
        )
        lpxy.addWidget(self._rb_pnp_xy_mm)
        lpxy.addWidget(self._rb_pnp_xy_mils)

        grp_nudge = QtWidgets.QGroupBox("PnP nudge (mm)")
        self._grp_nudge = grp_nudge
        lnudge = QtWidgets.QVBoxLayout(grp_nudge)
        self._nudge_bar = PnpArrowNudgeBar()
        self._nudge_bar.nudgeRequested.connect(self._on_pnp_nudge_mm)
        lnudge.addWidget(
            self._nudge_bar, alignment=QtCore.Qt.AlignmentFlag.AlignHCenter
        )

        grp = QtWidgets.QGroupBox("Gerber layers")
        self._grp_layers = grp
        gl = QtWidgets.QVBoxLayout(grp)
        self._layer_list = QtWidgets.QListWidget()
        self._layer_list.setMaximumHeight(120)
        self._layer_list.itemChanged.connect(self._on_layer_item_changed)
        gl.addWidget(self._layer_list)
        self._btn_clear_layers = QtWidgets.QPushButton("Clear layers")
        self._btn_clear_layers.clicked.connect(self._clear_gerber_layers)
        gl.addWidget(self._btn_clear_layers)
        self._btn_rm_layer = QtWidgets.QPushButton("Remove selected layer")
        self._btn_rm_layer.clicked.connect(self._remove_selected_layer)
        gl.addWidget(self._btn_rm_layer)

        self._lbl_refs = QtWidgets.QLabel("PnP refs")
        self._list = QtWidgets.QListWidget()
        self._list.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self._list.setMaximumHeight(140)
        self._list.itemSelectionChanged.connect(self._on_list_selection)

        view_opts = QtWidgets.QHBoxLayout()
        self._lbl_label_scale = QtWidgets.QLabel("Ref label size")
        self._spin_label_scale = QtWidgets.QDoubleSpinBox()
        self._spin_label_scale.setRange(0.04, 1.0)
        self._spin_label_scale.setSingleStep(0.02)
        self._spin_label_scale.setValue(self._label_scale)
        self._spin_label_scale.valueChanged.connect(self._on_label_scale_changed)
        self._chk_show_labels = QtWidgets.QCheckBox("Show labels")
        self._chk_show_labels.setChecked(True)
        self._chk_show_labels.toggled.connect(self._on_show_labels_toggled)
        self._chk_show_footprints = QtWidgets.QCheckBox("Show footprints")
        self._chk_show_footprints.setChecked(True)
        self._chk_show_footprints.toggled.connect(self._on_show_footprints_toggled)
        view_opts.addWidget(self._lbl_label_scale)
        view_opts.addWidget(self._spin_label_scale)
        view_opts.addWidget(self._chk_show_labels)
        view_opts.addWidget(self._chk_show_footprints)
        view_opts.addWidget(self._chk_mirror_x)
        view_opts.addWidget(self._chk_mirror_y)
        view_opts.addStretch()

        settings_grid = QtWidgets.QGridLayout()
        settings_grid.addLayout(view_opts, 0, 0, 1, 3)
        settings_grid.addWidget(grp_u, 1, 0)
        settings_grid.addWidget(grp_pnp_xy, 1, 1)
        settings_grid.addWidget(grp_nudge, 1, 2)
        settings_grid.addWidget(grp, 2, 0)
        refs_col = QtWidgets.QVBoxLayout()
        refs_col.addWidget(self._lbl_refs)
        refs_col.addWidget(self._list, 1)
        refs_wrap = QtWidgets.QWidget()
        refs_wrap.setLayout(refs_col)
        settings_grid.addWidget(refs_wrap, 2, 1, 1, 2)

        self._log = QtWidgets.QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(200)
        self._log.setMaximumHeight(80)
        settings_grid.addWidget(self._log, 3, 0, 1, 3)

        self._pcb_settings_panel = QtWidgets.QFrame()
        self._pcb_settings_panel.setLayout(settings_grid)

        self._btn_pcb_settings_toggle = QtWidgets.QToolButton()
        self._btn_pcb_settings_toggle.setCheckable(True)
        self._btn_pcb_settings_toggle.setToolButtonStyle(
            QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self._btn_pcb_settings_toggle.setArrowType(QtCore.Qt.ArrowType.RightArrow)
        self._btn_pcb_settings_toggle.toggled.connect(self._on_pcb_settings_toggled)
        root.addWidget(self._btn_pcb_settings_toggle)
        root.addWidget(self._pcb_settings_panel)
        expanded = False
        if self._settings is not None:
            expanded = bool(
                self._settings.value("pcb_preview/settings_expanded", False, type=bool)
            )
        self._btn_pcb_settings_toggle.blockSignals(True)
        self._btn_pcb_settings_toggle.setChecked(expanded)
        self._btn_pcb_settings_toggle.blockSignals(False)
        self._pcb_settings_panel.setVisible(expanded)
        self._btn_pcb_settings_toggle.setArrowType(
            QtCore.Qt.ArrowType.DownArrow if expanded else QtCore.Qt.ArrowType.RightArrow
        )

        self._scene.addItem(self._placements_root)
        self._placements_root.setZValue(10.0)
        self._set_placements_root_transform()
        self.refresh_static_texts()

    def _set_placements_root_transform(self) -> None:
        self._placements_root.setTransform(
            _compose_pnp_preview_transform(
                self._preview_sim, self._pnp_mirror_x, self._pnp_mirror_y
            )
        )

    def _append_log(self, msg: str) -> None:
        self._log.appendPlainText(msg)

    def _tr(self, key: str) -> str:
        w: Any = self.parent()
        while w is not None:
            fn = getattr(w, "ui_tr", None)
            if callable(fn):
                return str(fn(key))
            w = w.parent()
        return key

    def refresh_static_texts(self) -> None:
        if not hasattr(self, "_btn_gerber"):
            return
        self._btn_gerber.setText(self._tr("pcb.add_gerber"))
        self._btn_fit.setText(self._tr("pcb.fit_all"))
        self._btn_zoom_in.setText(self._tr("pcb.zoom_in"))
        self._btn_zoom_out.setText(self._tr("pcb.zoom_out"))
        self._btn_reset.setText(self._tr("pcb.reset_transform"))
        self._btn_center.setText(self._tr("pcb.center_sel"))
        self._btn_pcb_settings_toggle.setText(self._tr("pcb.settings"))
        self._chk_mirror_x.setText(self._tr("pcb.mirror_x"))
        self._chk_mirror_y.setText(self._tr("pcb.mirror_y"))
        self._grp_gunit.setTitle(self._tr("pcb.gerber_units"))
        self._rb_g_auto.setText(self._tr("pcb.gerber_auto"))
        self._rb_g_mm.setText(self._tr("pcb.gerber_mm"))
        self._rb_g_in.setText(self._tr("pcb.gerber_in"))
        self._grp_pnp_xy.setTitle(self._tr("pcb.pnp_xy"))
        self._grp_nudge.setTitle(self._tr("pcb.nudge"))
        self._grp_layers.setTitle(self._tr("pcb.layers"))
        self._btn_clear_layers.setText(self._tr("pcb.clear_layers"))
        self._btn_rm_layer.setText(self._tr("pcb.remove_layer"))
        self._lbl_refs.setText(self._tr("pcb.refs"))
        self._lbl_label_scale.setText(self._tr("pcb.label_scale"))
        self._chk_show_labels.setText(self._tr("pcb.show_labels"))
        self._chk_show_footprints.setText(self._tr("pcb.show_footprints"))

    def _on_pcb_settings_toggled(self, expanded: bool) -> None:
        self._pcb_settings_panel.setVisible(expanded)
        self._btn_pcb_settings_toggle.setArrowType(
            QtCore.Qt.ArrowType.DownArrow if expanded else QtCore.Qt.ArrowType.RightArrow
        )
        if self._settings is not None:
            self._settings.setValue("pcb_preview/settings_expanded", expanded)

    def _on_label_scale_changed(self, value: float) -> None:
        self._label_scale = float(value)
        for it in self._items.values():
            it.set_label_scale(self._label_scale)

    def _on_show_labels_toggled(self, on: bool) -> None:
        self._show_labels = bool(on)
        for it in self._items.values():
            it.set_labels_visible(self._show_labels)

    def _on_show_footprints_toggled(self, on: bool) -> None:
        self._show_footprints = bool(on)
        for it in self._items.values():
            it.set_footprint_visible(self._show_footprints)

    def _placements_fingerprint(self, df: Any, kwargs: dict[str, Any]) -> tuple[Any, ...]:
        if df is None:
            return (None,)
        cols = tuple(str(c) for c in df.columns)
        return (
            id(df),
            getattr(df, "shape", None),
            cols,
            tuple(sorted((str(k), repr(v)) for k, v in kwargs.items())),
        )

    def sync_pnp_xy_units_ui(self, *, mm: bool) -> None:
        """Keep mm/mils radios aligned with the main window (does not emit signals)."""
        self._rb_pnp_xy_mm.blockSignals(True)
        self._rb_pnp_xy_mils.blockSignals(True)
        self._rb_pnp_xy_mm.setChecked(mm)
        self._rb_pnp_xy_mils.setChecked(not mm)
        self._rb_pnp_xy_mm.blockSignals(False)
        self._rb_pnp_xy_mils.blockSignals(False)

    def export_ui_prefs(self) -> dict[str, Any]:
        """Serializable PCB Preview UI prefs (checkboxes / radios / nudge step only — not layer paths)."""
        gunit = "auto"
        if self._rb_g_mm.isChecked():
            gunit = "mm"
        elif self._rb_g_in.isChecked():
            gunit = "in"
        return {
            "mirror_x": self._chk_mirror_x.isChecked(),
            "mirror_y": self._chk_mirror_y.isChecked(),
            "gerber_unit": gunit,
            "nudge_step": self._nudge_bar._step.text().strip() or "0.5",
            "label_scale": self._label_scale,
            "show_labels": self._show_labels,
            "show_footprints": self._show_footprints,
        }

    def apply_ui_prefs(self, prefs: dict[str, Any]) -> None:
        if not prefs:
            return
        mx = bool(prefs.get("mirror_x", False))
        my = bool(prefs.get("mirror_y", False))
        self._chk_mirror_x.blockSignals(True)
        self._chk_mirror_y.blockSignals(True)
        self._chk_mirror_x.setChecked(mx)
        self._chk_mirror_y.setChecked(my)
        self._chk_mirror_x.blockSignals(False)
        self._chk_mirror_y.blockSignals(False)
        self._pnp_mirror_x = -1 if mx else 1
        self._pnp_mirror_y = -1 if my else 1

        gu = str(prefs.get("gerber_unit", "auto")).lower()
        self._rb_g_auto.blockSignals(True)
        self._rb_g_mm.blockSignals(True)
        self._rb_g_in.blockSignals(True)
        if gu == "mm":
            self._rb_g_mm.setChecked(True)
        elif gu == "in":
            self._rb_g_in.setChecked(True)
        else:
            self._rb_g_auto.setChecked(True)
        self._rb_g_auto.blockSignals(False)
        self._rb_g_mm.blockSignals(False)
        self._rb_g_in.blockSignals(False)

        step = str(prefs.get("nudge_step", "0.5")).strip()
        if step:
            self._nudge_bar._step.setText(step)
        if "label_scale" in prefs:
            try:
                self._label_scale = float(prefs["label_scale"])
            except (TypeError, ValueError):
                pass
            self._spin_label_scale.blockSignals(True)
            self._spin_label_scale.setValue(self._label_scale)
            self._spin_label_scale.blockSignals(False)
        if "show_labels" in prefs:
            self._show_labels = bool(prefs["show_labels"])
            self._chk_show_labels.blockSignals(True)
            self._chk_show_labels.setChecked(self._show_labels)
            self._chk_show_labels.blockSignals(False)
        if "show_footprints" in prefs:
            self._show_footprints = bool(prefs["show_footprints"])
            self._chk_show_footprints.blockSignals(True)
            self._chk_show_footprints.setChecked(self._show_footprints)
            self._chk_show_footprints.blockSignals(False)
        for it in self._items.values():
            it.set_label_scale(self._label_scale)
            it.set_labels_visible(self._show_labels)
            it.set_footprint_visible(self._show_footprints)
        self._set_placements_root_transform()

    def _zoom_view_in(self) -> None:
        self._view.scale(1.2, 1.2)

    def _zoom_view_out(self) -> None:
        self._view.scale(1.0 / 1.2, 1.0 / 1.2)

    def _on_mirror_x_toggled(self, checked: bool) -> None:
        self._pnp_mirror_x = -1 if checked else 1
        self._set_placements_root_transform()
        self._update_scene_rect_from_content()
        self._append_log(f"PnP mirror X: {'on' if checked else 'off'}")

    def _on_mirror_y_toggled(self, checked: bool) -> None:
        self._pnp_mirror_y = -1 if checked else 1
        self._set_placements_root_transform()
        self._update_scene_rect_from_content()
        self._append_log(f"PnP mirror Y: {'on' if checked else 'off'}")

    def _sync_all_placement_styles(self) -> None:
        sel = {it.text() for it in self._list.selectedItems()}
        for ref, g in self._items.items():
            g.setSelected(ref in sel)
            g.apply_selection_style(ref in sel, ref_a=False, ref_b=False)

    def _on_pnp_nudge_mm(self, dx_mm: float, dy_mm: float) -> None:
        refs = [it.text() for it in self._list.selectedItems()]
        if not refs:
            refs = list(self._items.keys())
        delta = QtCore.QPointF(dx_mm, dy_mm)
        for r in refs:
            if r in self._items:
                it = self._items[r]
                it.setPos(it.pos() + delta)
        self._update_scene_rect_from_content()

    def _gerber_user_mm_scale(self, path: str) -> tuple[float, str]:
        if self._rb_g_in.isChecked():
            return 25.4, "UI inch→mm ×25.4"
        if self._rb_g_mm.isChecked():
            return 1.0, "UI mm ×1"
        u = peek_rs274x_linear_unit(path)
        return 1.0, f"Auto header={u!r}; gerbonara→scene ×1"

    def _browse_gerber(self) -> None:
        start = ""
        if self._settings is not None:
            start = str(self._settings.value("pcb_preview/last_gerber_dir", "") or "")
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Add Gerber layer",
            start,
            "Gerber (*.gbr *.gtp *.gtl *.gto *.gts *.pho *.ger *.art);;All (*.*)",
        )
        if not path:
            return
        if self._settings is not None:
            self._settings.setValue(
                "pcb_preview/last_gerber_dir", os.path.dirname(path)
            )
        payload = load_gerber_svg(path)
        if payload.errors:
            self._append_log("Gerber: " + "; ".join(payload.errors))
        if not payload.svg:
            return
        u_scale, unit_note = self._gerber_user_mm_scale(path)
        self._append_gerber_layer(payload, u_scale, unit_note)

    def _append_gerber_layer(
        self, payload: GerberSvgPayload, user_mm_scale: float = 1.0, unit_note: str = ""
    ) -> None:
        renderer = QSvgRenderer(QtCore.QByteArray(payload.svg.encode("utf-8")))
        if not renderer.isValid():
            self._append_log("Invalid SVG from gerbonara")
            return
        vb = renderer.viewBoxF()
        w_px = max(2, int(vb.width() * self._px_per_mm + 2))
        h_px = max(2, int(vb.height() * self._px_per_mm + 2))
        img = QtGui.QImage(w_px, h_px, QtGui.QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(QtCore.Qt.GlobalColor.transparent)
        p = QtGui.QPainter(img)
        renderer.render(p, QtCore.QRectF(0, 0, w_px, h_px))
        p.end()
        pm = QtGui.QPixmap.fromImage(img)
        item = self._scene.addPixmap(pm)
        item.setTransformationMode(QtCore.Qt.TransformationMode.SmoothTransformation)
        # Raster is w_px×h_px; SVG viewBox is in gerbonara mm. Scale item so one scene unit matches mm.
        s_rx = (vb.width() / float(w_px)) if w_px else 1.0
        s_ry = (vb.height() / float(h_px)) if h_px else 1.0
        s_raster = 0.5 * (s_rx + s_ry)
        item.setScale(s_raster * user_mm_scale)
        item.setPos(vb.x() * user_mm_scale, vb.y() * user_mm_scale)
        base_z = -50.0
        item.setZValue(base_z + float(len(self._layers)) * 0.5)

        name = os.path.basename(payload.source_path)
        bbox_scene = scale_bbox_mm(payload.bbox_mm, user_mm_scale)
        row = _GerberLayerRow(
            path=payload.source_path,
            display_name=name,
            pixmap_item=item,
            bbox_mm=bbox_scene,
        )
        self._layers.append(row)

        lw_item = QtWidgets.QListWidgetItem(name)
        lw_item.setFlags(
            lw_item.flags()
            | QtCore.Qt.ItemFlag.ItemIsUserCheckable
            | QtCore.Qt.ItemFlag.ItemIsEnabled
        )
        lw_item.setCheckState(QtCore.Qt.CheckState.Checked)
        self._layer_list.blockSignals(True)
        self._layer_list.addItem(lw_item)
        self._layer_list.blockSignals(False)

        self._apply_layer_z_order()
        self._update_scene_rect_from_content()
        self._fit_all_content()
        bb = bbox_scene
        extra = f"  [{unit_note}]" if unit_note else ""
        self._append_log(
            f"Gerber layer added: {name}  size {bb.width:.2f}×{bb.height:.2f} mm  "
            f"origin ({bb.min_x:.2f}, {bb.min_y:.2f}) mm{extra}"
        )

    def _apply_layer_z_order(self) -> None:
        """List top → drawn on top (higher z). Bottom row = back."""
        n = min(self._layer_list.count(), len(self._layers))
        for i in range(n):
            self._layers[i].pixmap_item.setZValue(-50.0 + float(i) * 0.5)

    def _on_layer_item_changed(self, item: QtWidgets.QListWidgetItem) -> None:
        row = self._layer_list.row(item)
        if row < 0 or row >= len(self._layers):
            return
        vis = item.checkState() == QtCore.Qt.CheckState.Checked
        self._layers[row].pixmap_item.setVisible(vis)

    def _remove_selected_layer(self) -> None:
        row = self._layer_list.currentRow()
        if row < 0 or row >= len(self._layers):
            return
        entry = self._layers.pop(row)
        self._scene.removeItem(entry.pixmap_item)
        self._layer_list.takeItem(row)
        self._apply_layer_z_order()
        self._update_scene_rect_from_content()
        self._fit_all_content()

    def _clear_gerber_layers(self) -> None:
        for entry in self._layers:
            self._scene.removeItem(entry.pixmap_item)
        self._layers.clear()
        self._layer_list.clear()
        self._update_scene_rect_from_content()
        self._fit_all_content()
        self._append_log("All Gerber layers cleared.")

    def _placements_scene_rect(self) -> QtCore.QRectF:
        br = QtCore.QRectF()
        for it in self._items.values():
            br = _bbox_union(br, it.sceneBoundingRect())
        return br

    def _gerber_scene_rect(self) -> QtCore.QRectF:
        br = QtCore.QRectF()
        for entry in self._layers:
            if not entry.pixmap_item.isVisible():
                continue
            br = _bbox_union(br, entry.pixmap_item.sceneBoundingRect())
        return br

    def _update_scene_rect_from_content(self) -> None:
        br = self._gerber_scene_rect()
        br = _bbox_union(br, self._placements_scene_rect())
        if not br.isValid():
            br = QtCore.QRectF(-10, -10, 220, 220)
        m = 5.0
        self._scene.setSceneRect(br.adjusted(-m, -m, m, m))

    def _fit_all_with_reset_view(self) -> None:
        self._view.resetTransform()
        self._fit_all_content()

    def _fit_all_content(self) -> None:
        br = self._gerber_scene_rect()
        br = _bbox_union(br, self._placements_scene_rect())
        if br.isValid():
            self._view.fitInView(br, QtCore.Qt.AspectRatioMode.KeepAspectRatio)
        else:
            self._view.fitInView(
                self._scene.sceneRect(), QtCore.Qt.AspectRatioMode.KeepAspectRatio
            )

    def set_placements_from_dataframe(self, df, *, force: bool = False, **kwargs) -> None:
        fp = self._placements_fingerprint(df, kwargs)
        if not force and fp == self._placements_fp:
            return
        self._placements_fp = fp
        self._placements, warns = pcb_preview_bridge.placements_from_pnp_dataframe(
            df, **kwargs
        )
        for w in warns:
            self._append_log(w)
        self.refresh_placements()

    def refresh_placements(self) -> None:
        for it in list(self._items.values()):
            self._placements_root.removeFromGroup(it)
            self._scene.removeItem(it)
        self._items.clear()
        self._list.clear()
        for pl in self._placements:
            outline = self._store.lookup_outline(pl.footprint_name)
            if outline.source == "none" and pl.footprint_name:
                tail = pl.footprint_name.replace("\\", "/").split("/")[-1]
                outline = self._store.lookup_outline(tail)
            item = PlacementGroupItem(pl, outline)
            item.set_label_scale(self._label_scale)
            item.set_labels_visible(self._show_labels)
            item.set_footprint_visible(self._show_footprints)
            self._placements_root.addToGroup(item)
            self._items[pl.ref] = item
            self._list.addItem(pl.ref)
        self._set_placements_root_transform()
        self._sync_all_placement_styles()
        self._update_scene_rect_from_content()
        if not self._did_initial_fit and (self._items or self._layers):
            self._fit_all_content()
            self._did_initial_fit = True

    def _on_list_selection(self) -> None:
        self._sync_all_placement_styles()

    def _center_selection(self) -> None:
        refs = [it.text() for it in self._list.selectedItems()]
        if not refs:
            return
        br = QtCore.QRectF()
        for r in refs:
            if r in self._items:
                br |= self._items[r].sceneBoundingRect()
        if br.isValid():
            self._view.fitInView(br, QtCore.Qt.AspectRatioMode.KeepAspectRatio)

    # --- Disabled with UI: Gerber pick / Ref A–B (was eventFilter on viewport) ---
    # def _on_align_toggled(self, on: bool) -> None: ...
    # def _on_pick_refs_toggled(self, on: bool) -> None: ...
    # def eventFilter(self, obj, event) -> bool: ...

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        step = self._nudge_bar.step_mm()
        if event.modifiers() == QtCore.Qt.KeyboardModifier.NoModifier:
            dx = dy = 0.0
            if event.key() == QtCore.Qt.Key.Key_Left:
                dx = -step
            elif event.key() == QtCore.Qt.Key.Key_Right:
                dx = step
            elif event.key() == QtCore.Qt.Key.Key_Up:
                dy = -step
            elif event.key() == QtCore.Qt.Key.Key_Down:
                dy = step
            if dx != 0 or dy != 0:
                refs = [it.text() for it in self._list.selectedItems()]
                if len(refs) < 1:
                    refs = list(self._items.keys())
                delta = QtCore.QPointF(dx, dy)
                for r in refs:
                    if r in self._items:
                        it = self._items[r]
                        it.setPos(it.pos() + delta)
                self._update_scene_rect_from_content()
                event.accept()
                return
        super().keyPressEvent(event)

    # def _pnp_point(self, ref: str) -> Optional[tuple[float, float]]: ...  # 2-point alignment only
    # def _apply_similarity(self) -> None:
    #     from pcb_preview.alignment import similarity_from_two_point_pairs
    #     ...  # see git history: two Gerber clicks + Ref A/B + Apply

    def _reset_transform(self) -> None:
        self._preview_sim = Similarity2D.identity()
        self._pnp_mirror_x = 1
        self._pnp_mirror_y = 1
        self._chk_mirror_x.blockSignals(True)
        self._chk_mirror_y.blockSignals(True)
        self._chk_mirror_x.setChecked(False)
        self._chk_mirror_y.setChecked(False)
        self._chk_mirror_x.blockSignals(False)
        self._chk_mirror_y.blockSignals(False)
        self._set_placements_root_transform()
        self._update_scene_rect_from_content()
        self._append_log("Preview transform reset (similarity + mirrors).")

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self._store.close()
        super().closeEvent(event)
