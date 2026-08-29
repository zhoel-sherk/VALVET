"""PCB Preview tab: QGraphicsView + Gerber layers + PnP overlay."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from pcb_preview.alignment import Similarity2D
from pcb_preview.footprint_db import FootprintStore
from ui.machine_lib.outline_paint import outline_to_path as _outline_to_path
from pcb_preview.engine.identify import (
    guess_layer_kind,
    layer_default_opacity,
    layer_default_rgb,
    layer_default_z,
)
from pcb_preview.gerber_io import (
    GerberUnitMode,
    gerber_to_scene_mm_scale,
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
from pcb_preview_load_thread import GerberLoadThread


# Centroid marker radius in mm (scene units); stroke is cosmetic (pixels) so it stays visible.
_CENTROID_RADIUS_MM = 0.45
_SEL_RING_SCALE = 2.8
# Ref label height in scene mm (~font * scale). User can raise this in Settings.
_LABEL_SCENE_SCALE = 0.12
# Half-length of each arm of the centroid X-cross (mm, local item space).
_CROSS_HALF_MM = 0.9
# Gerber raster: pixels per mm of SVG viewBox (higher = sharper, more memory).
_GERBER_PX_PER_MM = 14.0


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
        self._label.setZValue(2)
        self.addToGroup(self._label)
        self.set_label_scale(_LABEL_SCENE_SCALE)

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
        # QGraphicsItemGroup.addToGroup bakes scale into transform(); setScale() then
        # multiplies and cannot be reverted. Replace the transform instead.
        s = max(0.04, min(1.0, float(scale)))
        self.prepareGeometryChange()
        self._label.setScale(1.0)
        self._label.setTransform(QtGui.QTransform.fromScale(s, s))

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
    """One loaded Gerber bitmap in the scene (native bbox is backend millimetres)."""

    path: str
    display_name: str
    pixmap_item: QtWidgets.QGraphicsPixmapItem
    bbox_mm: BBoxMM
    native_bbox_mm: BBoxMM
    s_raster: float
    rgb: tuple[int, int, int] = (120, 160, 200)
    opacity: float = 0.8


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
        self._gerber_thread: Any = None

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
        self._rb_g_mils = QtWidgets.QRadioButton("mils → mm")
        self._rb_g_in = QtWidgets.QRadioButton("inch → mm")
        self._rb_g_auto.setChecked(True)
        self._bg_gunit = QtWidgets.QButtonGroup(self)
        for rb in (self._rb_g_auto, self._rb_g_mm, self._rb_g_mils, self._rb_g_in):
            self._bg_gunit.addButton(rb)
            lu.addWidget(rb)
        self._bg_gunit.buttonToggled.connect(self._on_gerber_unit_toggled)
        self._rb_g_auto.setToolTip(
            "Backends already convert Gerber to millimetres; scene grid is mm (same as PnP)."
        )
        self._rb_g_mm.setToolTip("Treat loaded Gerber as millimetres (×1).")
        self._rb_g_mils.setToolTip(
            "Scale Gerber by 0.0254 (mils → mm), same factor as PnP."
        )
        self._rb_g_in.setToolTip(
            "Scale Gerber by 25.4 (inch → mm). Use only if the backend left inches."
        )

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
        self._layer_list.currentRowChanged.connect(self._on_layer_row_changed)
        gl.addWidget(self._layer_list)
        style_row = QtWidgets.QHBoxLayout()
        self._lbl_layer_color = QtWidgets.QLabel("Color")
        self._btn_layer_color = QtWidgets.QPushButton()
        self._btn_layer_color.setFixedSize(28, 22)
        self._btn_layer_color.clicked.connect(self._on_pick_layer_color)
        self._lbl_layer_opacity = QtWidgets.QLabel("Opacity")
        self._spin_layer_opacity = QtWidgets.QDoubleSpinBox()
        self._spin_layer_opacity.setRange(0.05, 1.0)
        self._spin_layer_opacity.setSingleStep(0.05)
        self._spin_layer_opacity.setValue(0.8)
        self._spin_layer_opacity.valueChanged.connect(self._on_layer_opacity_changed)
        style_row.addWidget(self._lbl_layer_color)
        style_row.addWidget(self._btn_layer_color)
        style_row.addWidget(self._lbl_layer_opacity)
        style_row.addWidget(self._spin_layer_opacity)
        gl.addLayout(style_row)
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
        self._rb_g_mils.setText(self._tr("pcb.gerber_mils"))
        self._rb_g_in.setText(self._tr("pcb.gerber_in"))
        self._grp_pnp_xy.setTitle(self._tr("pcb.pnp_xy"))
        self._grp_nudge.setTitle(self._tr("pcb.nudge"))
        self._grp_layers.setTitle(self._tr("pcb.layers"))
        self._btn_clear_layers.setText(self._tr("pcb.clear_layers"))
        self._btn_rm_layer.setText(self._tr("pcb.remove_layer"))
        self._lbl_layer_color.setText(self._tr("pcb.layer_color"))
        self._lbl_layer_opacity.setText(self._tr("pcb.layer_opacity"))
        self._btn_layer_color.setToolTip(self._tr("pcb.layer_color_tooltip"))
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
        self._update_scene_rect_from_content()

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
        gunit = self._gerber_unit_mode()
        if gunit == "inch":
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
        self._rb_g_mils.blockSignals(True)
        self._rb_g_in.blockSignals(True)
        if gu == "mm":
            self._rb_g_mm.setChecked(True)
        elif gu in ("mils", "mil"):
            self._rb_g_mils.setChecked(True)
        elif gu in ("in", "inch"):
            self._rb_g_in.setChecked(True)
        else:
            self._rb_g_auto.setChecked(True)
        self._rb_g_auto.blockSignals(False)
        self._rb_g_mm.blockSignals(False)
        self._rb_g_mils.blockSignals(False)
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
        self._rescale_all_gerber_layers(log=False)

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

    def _gerber_unit_mode(self) -> GerberUnitMode:
        if self._rb_g_mils.isChecked():
            return "mils"
        if self._rb_g_in.isChecked():
            return "inch"
        if self._rb_g_mm.isChecked():
            return "mm"
        return "auto"

    def _on_gerber_unit_toggled(self, _btn: object, checked: bool) -> None:
        if not checked:
            return
        self._rescale_all_gerber_layers(log=True)

    def _gerber_user_mm_scale(self, path: str) -> tuple[float, str]:
        header = peek_rs274x_linear_unit(path)
        return gerber_to_scene_mm_scale(self._gerber_unit_mode(), header)

    def _apply_layer_user_scale(
        self, row: _GerberLayerRow, user_mm_scale: float
    ) -> None:
        row.pixmap_item.setScale(row.s_raster * user_mm_scale)
        nb = row.native_bbox_mm
        row.pixmap_item.setPos(nb.min_x * user_mm_scale, nb.min_y * user_mm_scale)
        row.bbox_mm = scale_bbox_mm(nb, user_mm_scale)

    def _rescale_all_gerber_layers(self, *, log: bool) -> None:
        note = ""
        for row in self._layers:
            u_scale, note = self._gerber_user_mm_scale(row.path)
            self._apply_layer_user_scale(row, u_scale)
        self._update_scene_rect_from_content()
        if log and self._layers and note:
            self._append_log(f"Gerber on shared mm grid: {note}")

    def _browse_gerber(self) -> None:
        if self._gerber_thread is not None and self._gerber_thread.isRunning():
            return
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
        self._btn_gerber.setEnabled(False)
        self._append_log(self._tr("pcb.gerber_loading"))
        thread = GerberLoadThread(path, self._px_per_mm, self)
        thread.result_ready.connect(
            self._on_gerber_loaded,
            QtCore.Qt.ConnectionType.QueuedConnection,
        )
        thread.finished.connect(
            self._on_gerber_thread_finished,
            QtCore.Qt.ConnectionType.QueuedConnection,
        )
        self._gerber_thread = thread
        thread.start()

    def _on_gerber_thread_finished(self) -> None:
        self._btn_gerber.setEnabled(True)
        t = self._gerber_thread
        self._gerber_thread = None
        if t is not None:
            t.wait(5000)
            t.deleteLater()

    def _on_gerber_loaded(self, packed: object) -> None:
        if not isinstance(packed, tuple) or len(packed) != 3:
            return
        payload, image, vb = packed
        if not isinstance(payload, GerberSvgPayload):
            return
        if payload.errors:
            self._append_log("Gerber: " + "; ".join(payload.errors))
        if image is None or not payload.svg:
            if not payload.errors:
                self._append_log("Invalid SVG from Gerber backend")
            return
        u_scale, unit_note = self._gerber_user_mm_scale(payload.source_path)
        self._install_gerber_image(payload, image, vb, u_scale, unit_note)

    def _install_gerber_image(
        self,
        payload: GerberSvgPayload,
        image: QtGui.QImage,
        vb: QtCore.QRectF,
        user_mm_scale: float,
        unit_note: str,
    ) -> None:
        pm = QtGui.QPixmap.fromImage(image)
        item = self._scene.addPixmap(pm)
        item.setTransformationMode(QtCore.Qt.TransformationMode.SmoothTransformation)
        w_px = max(1, image.width())
        h_px = max(1, image.height())
        s_rx = (vb.width() / float(w_px)) if w_px else 1.0
        s_ry = (vb.height() / float(h_px)) if h_px else 1.0
        s_raster = 0.5 * (s_rx + s_ry)
        native = payload.bbox_mm
        if native.width > 0 and native.height > 0:
            s_raster = 0.5 * (
                (native.width / float(w_px)) + (native.height / float(h_px))
            )
        name = os.path.basename(payload.source_path)
        kind = guess_layer_kind(payload.source_path)
        rgb = layer_default_rgb(kind)
        opacity = layer_default_opacity(kind)
        row = _GerberLayerRow(
            path=payload.source_path,
            display_name=name,
            pixmap_item=item,
            bbox_mm=native,
            native_bbox_mm=native,
            s_raster=s_raster,
            rgb=rgb,
            opacity=opacity,
        )
        self._layers.append(row)
        self._apply_layer_style(row)
        self._apply_layer_user_scale(row, user_mm_scale)

        lw_item = QtWidgets.QListWidgetItem(name)
        lw_item.setFlags(
            lw_item.flags()
            | QtCore.Qt.ItemFlag.ItemIsUserCheckable
            | QtCore.Qt.ItemFlag.ItemIsEnabled
        )
        lw_item.setCheckState(QtCore.Qt.CheckState.Checked)
        self._layer_list.blockSignals(True)
        self._layer_list.addItem(lw_item)
        self._layer_list.setCurrentItem(lw_item)
        self._layer_list.blockSignals(False)

        self._apply_layer_z_order()
        self._sync_layer_style_controls()
        self._update_scene_rect_from_content()
        self._fit_all_content()
        extra = f"  [{unit_note}]" if unit_note else ""
        backend = payload.backend_name or "?"
        bb = row.bbox_mm
        self._append_log(
            f"Gerber layer added ({backend}): {name}  "
            f"size {bb.width:.2f}×{bb.height:.2f} mm  "
            f"origin ({bb.min_x:.2f}, {bb.min_y:.2f}) mm{extra}"
        )

    def _apply_layer_style(self, row: _GerberLayerRow) -> None:
        item = row.pixmap_item
        item.setOpacity(row.opacity)
        effect = QtWidgets.QGraphicsColorizeEffect()
        effect.setColor(QtGui.QColor(*row.rgb))
        effect.setStrength(1.0)
        item.setGraphicsEffect(effect)

    def _current_layer_row(self) -> _GerberLayerRow | None:
        i = self._layer_list.currentRow()
        if i < 0 or i >= len(self._layers):
            return None
        return self._layers[i]

    def _sync_layer_style_controls(self) -> None:
        row = self._current_layer_row()
        self._spin_layer_opacity.blockSignals(True)
        if row is None:
            self._spin_layer_opacity.setValue(0.8)
            self._btn_layer_color.setStyleSheet("")
        else:
            self._spin_layer_opacity.setValue(row.opacity)
            c = QtGui.QColor(*row.rgb)
            self._btn_layer_color.setStyleSheet(
                f"QPushButton {{ background-color: {c.name()}; border: 1px solid #666; }}"
            )
        self._spin_layer_opacity.blockSignals(False)

    def _on_layer_row_changed(self, _row: int) -> None:
        self._sync_layer_style_controls()

    def _on_pick_layer_color(self) -> None:
        row = self._current_layer_row()
        if row is None:
            return
        start = QtGui.QColor(*row.rgb)
        chosen = QtWidgets.QColorDialog.getColor(
            start, self, self._tr("pcb.layer_color")
        )
        if not chosen.isValid():
            return
        row.rgb = (chosen.red(), chosen.green(), chosen.blue())
        self._apply_layer_style(row)
        self._sync_layer_style_controls()

    def _on_layer_opacity_changed(self, value: float) -> None:
        row = self._current_layer_row()
        if row is None:
            return
        row.opacity = float(value)
        self._apply_layer_style(row)

    def _apply_layer_z_order(self) -> None:
        """Filename kind sets base z; list index breaks ties. PnP stays at 10."""
        n = min(self._layer_list.count(), len(self._layers))
        for i in range(n):
            kind = guess_layer_kind(self._layers[i].path)
            z = layer_default_z(kind) + float(i) * 0.05
            self._layers[i].pixmap_item.setZValue(z)

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
        self._sync_layer_style_controls()
        self._update_scene_rect_from_content()
        self._fit_all_content()

    def _clear_gerber_layers(self) -> None:
        for entry in self._layers:
            self._scene.removeItem(entry.pixmap_item)
        self._layers.clear()
        self._layer_list.clear()
        self._sync_layer_style_controls()
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
