"""Build FootprintOutlineMM from Hanwha UPD vision-profile rows (µm → mm).

Qt-free. Callers load rows from the profile SQLite cache (or live .mdb); this module only interprets geometry.
See doc/info/UPD_MDB_Footprint_Geometry_Report.md.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from pcb_preview.types import (
    BBoxMM,
    FootprintOutlineMM,
    PadRectMM,
    StrokeCircleMM,
    StrokeLineMM,
    union_bbox,
)

UM_PER_MM = 1000.0
_LINE_W = 0.12
_SOT23_RE = re.compile(r"SOT[\s\-]?23", re.I)
_SOT23_MORE_PINS_RE = re.compile(
    r"SOT[\s\-]?23[\s\-_]?[5-8]|SOT[\s\-]?353", re.I
)
_SOD_RE = re.compile(r"SOD[\s\-]?\d", re.I)
_TR_GROUPS = frozenset({"TR", "TR2"})

# VISION_LL_GROUP_Det.ANGLE is a cardinal index 0..3 (QFP sides / SOP 1,3).
# Not pick/supply angle: machine 90 vs -90 are opposite nozzle rotations on another field.
_LL_SIDE = {
    0: "pos_y",
    1: "pos_x",
    2: "neg_y",
    3: "neg_x",
}
# If lead span overflows the tangent body axis, rotate the group 90° CCW.
_LL_ROTATE_CCW = {
    "pos_x": "pos_y",
    "pos_y": "neg_x",
    "neg_x": "neg_y",
    "neg_y": "pos_x",
}


def um_to_mm(raw: object) -> float:
    try:
        return float(raw) / UM_PER_MM
    except (TypeError, ValueError):
        return 0.0


def _int(raw: object, default: int = 0) -> int:
    if raw is None:
        return default
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return default


def _polarized(raw: object) -> bool | None:
    if raw is None:
        return None
    if isinstance(raw, bool):
        return raw
    s = str(raw).strip().lower()
    if s in ("", "none", "nan"):
        return None
    if s in ("1", "-1", "true", "yes"):
        return True
    if s in ("0", "false", "no"):
        return False
    try:
        return int(float(raw)) != 0
    except (TypeError, ValueError):
        return None


def _row_get(row: Mapping[str, Any], *keys: str, default: object = 0) -> object:
    upper = {str(k).upper(): v for k, v in row.items()}
    for key in keys:
        if key.upper() in upper:
            return upper[key.upper()]
    return default


def body_rect_lines(size_x_mm: float, size_y_mm: float) -> tuple[StrokeLineMM, ...]:
    hx, hy = size_x_mm / 2.0, size_y_mm / 2.0
    return (
        StrokeLineMM(-hx, -hy, hx, -hy, _LINE_W),
        StrokeLineMM(hx, -hy, hx, hy, _LINE_W),
        StrokeLineMM(hx, hy, -hx, hy, _LINE_W),
        StrokeLineMM(-hx, hy, -hx, -hy, _LINE_W),
    )


def is_chip_circle(partgroup_name: str) -> bool:
    """Hanwha part group CHIP-Circle: round body (nuts, washers, fiducials)."""
    g = (partgroup_name or "").upper().replace(" ", "")
    return "CIRCLE" in g


def chip_circle_body(
    size_x_mm: float, size_y_mm: float
) -> tuple[StrokeCircleMM, ...]:
    """Circle inscribed in the chip TYPSIZE / SIZE box (diameter = min axis)."""
    d = min(abs(size_x_mm), abs(size_y_mm))
    if d <= 0:
        return ()
    return (StrokeCircleMM(0.0, 0.0, d / 2.0, _LINE_W),)


def chip_heuristic_pads(size_x_mm: float, size_y_mm: float) -> tuple[PadRectMM, ...]:
    """Two end pads along X — MDB has no chip land pattern.

    Pad length scales with body (no 0.6 mm cap — that made 0805–1812 look like 0402).
    Pads sit on the terminations (flush with body ends).
    """
    L, W = abs(size_x_mm), abs(size_y_mm)
    if L <= 0 or W <= 0:
        return ()
    pad_w = L * 0.38
    pad_h = W
    cx = (L - pad_w) / 2.0
    return (
        PadRectMM(-cx, 0.0, pad_w, pad_h, 0.0, "1"),
        PadRectMM(cx, 0.0, pad_w, pad_h, 0.0, "2"),
    )


def chip_lead_counts(whole: Mapping[str, Any]) -> tuple[int, int] | None:
    """Left/right lead counts from VISION_CHIP_WHOLE_Det.

    Hanwha chip-lead inspect (TR, TR2, SOD, SOT-23-n) stores two opposite sides:
    EXPARAM15 = left slots, EXPARAM16 = right. A count of 0 is an unused side
    (same idea as a 0×0 second lead). Chip-R/C leave both at 0.
    Both columns must be present; a stale dump with only EXPARAM15 is ignored.
    """
    keys = {str(k).upper() for k in whole}
    if "EXPARAM15" not in keys or "EXPARAM16" not in keys:
        return None
    na = _int(_row_get(whole, "EXPARAM15"))
    nb = _int(_row_get(whole, "EXPARAM16"))
    if na < 0 or nb < 0 or na > 8 or nb > 8:
        return None
    if na == 0 and nb == 0:
        return None
    return na, nb


def _chip_lead_ys(n: int, pitch_mm: float, pad_h: float, body_y: float) -> list[float]:
    """EXPARAM18/19 is first-to-last lead span (equals adjacent pitch when n==2)."""
    if n <= 0:
        return []
    if n == 1:
        return [0.0]
    gaps = n - 1
    if pitch_mm > 1e-9:
        p = pitch_mm / gaps
    else:
        p = max(pad_h * 1.15, body_y * 0.7 / gaps)
    if gaps * p > body_y * 0.98:
        p = body_y * 0.9 / gaps
    mid = gaps / 2.0
    return [(i - mid) * p for i in range(n)]


def chip_lead_pads_from_exparam(
    whole: Mapping[str, Any], size_x_mm: float, size_y_mm: float
) -> tuple[PadRectMM, ...] | None:
    """Pads from chip-lead slots: thickness EXPARAM11/12, length 13/14, pitch 18/19 (µm)."""
    counts = chip_lead_counts(whole)
    if counts is None:
        return None
    na, nb = counts
    L, W = abs(size_x_mm), abs(size_y_mm)
    if L <= 0 or W <= 0:
        return None

    def _dim(key: str, fallback: float) -> float:
        v = um_to_mm(_row_get(whole, key))
        return v if v > 1e-6 else fallback

    pad_h_a = _dim("EXPARAM11", min(0.55, max(0.15, W * 0.35)))
    pad_h_b = _dim("EXPARAM12", pad_h_a)
    pad_w_a = _dim("EXPARAM13", L * 0.28)
    pad_w_b = _dim("EXPARAM14", pad_w_a)
    pitch_a = um_to_mm(_row_get(whole, "EXPARAM18"))
    pitch_b = um_to_mm(_row_get(whole, "EXPARAM19"))
    pads: list[PadRectMM] = []
    n = 1
    cx_a = -(L - pad_w_a) / 2.0
    for y in _chip_lead_ys(na, pitch_a, pad_h_a, W):
        pads.append(PadRectMM(cx_a, y, pad_w_a, pad_h_a, 0.0, str(n)))
        n += 1
    cx_b = (L - pad_w_b) / 2.0
    for y in _chip_lead_ys(nb, pitch_b, pad_h_b, W):
        pads.append(PadRectMM(cx_b, y, pad_w_b, pad_h_b, 0.0, str(n)))
        n += 1
    return tuple(pads) if pads else None


def sot23_heuristic_pads(size_x_mm: float, size_y_mm: float) -> tuple[PadRectMM, ...]:
    """Top-view silhouette: two pads on one side, one on the other (not JEDEC lands)."""
    L, W = abs(size_x_mm), abs(size_y_mm)
    if L <= 0 or W <= 0:
        return ()
    pad_w = min(0.55, max(0.35, L * 0.28))
    pad_h = min(0.55, max(0.35, W * 0.28))
    x = L * 0.32
    y = W * 0.28
    return (
        PadRectMM(-x, y, pad_w, pad_h, 0.0, "1"),
        PadRectMM(-x, -y, pad_w, pad_h, 0.0, "2"),
        PadRectMM(x, 0.0, pad_w, pad_h, 0.0, "3"),
    )


def uses_sot23_pads(
    partgroup_name: str,
    partdesc: str = "",
    profilename: str = "",
    chip_whole: Mapping[str, Any] | None = None,
) -> bool:
    """True only for 3-pin SOT-23-like names — not SOD* and not SOT-23-5/6/8."""
    blob = f"{partgroup_name} {partdesc} {profilename}"
    if _SOD_RE.search(blob) or _SOT23_MORE_PINS_RE.search(blob):
        return False
    rows = _int(_row_get(chip_whole or {}, "EXPARAM15"))
    if rows >= 2:
        return False
    return bool(_SOT23_RE.search(blob))


_POLAR_CHIP_MARKERS = ("LED", "DIODE", "TANT", "POLAR")


def _component_is_nonpolar(snap: UpdProfileSnapshot) -> bool:
    """True when the part has no pin-1 / polarity (typical chip-R / chip-C)."""
    if snap.polarized is False:
        return True
    if snap.pin1_indicator < 0:
        return True
    g = (snap.partgroup_name or "").strip().upper()
    if g in _TR_GROUPS:
        return False
    blob = f"{snap.partgroup_name} {snap.partdesc} {snap.profilename}"
    if _SOD_RE.search(blob) or uses_sot23_pads(
        snap.partgroup_name,
        snap.partdesc,
        snap.profilename,
        snap.chip_whole,
    ):
        return False
    if snap.pin1_indicator > 0:
        return False
    if int(snap.vision_type) != 3:
        return False
    g = (snap.partgroup_name or "").upper()
    return not any(m in g for m in _POLAR_CHIP_MARKERS)


def resolve_pin1(
    snap: UpdProfileSnapshot, outline: FootprintOutlineMM
) -> tuple[float, float, str, str]:
    """Return (x_mm, y_mm, kind, polarity). kind is none | mdb | lead1."""
    if _component_is_nonpolar(snap):
        return 0.0, 0.0, "none", "none"
    if snap.pin1_x_um or snap.pin1_y_um:
        return um_to_mm(snap.pin1_x_um), um_to_mm(snap.pin1_y_um), "mdb", "yes"
    pads = outline.pads
    if pads:
        pad = next((p for p in pads if p.number == "1"), pads[0])
        return pad.cx, pad.cy, "lead1", "yes"
    return 0.0, 0.0, "none", "yes"


def _bbox_from_primitives(
    lines: Sequence[StrokeLineMM],
    circles: Sequence[StrokeCircleMM],
    pads: Sequence[PadRectMM],
    fallback_x: float = 0.0,
    fallback_y: float = 0.0,
) -> BBoxMM:
    boxes: list[BBoxMM] = []
    for ln in lines:
        boxes.append(
            BBoxMM(
                min(ln.x1, ln.x2),
                min(ln.y1, ln.y2),
                max(ln.x1, ln.x2),
                max(ln.y1, ln.y2),
            )
        )
    for c in circles:
        boxes.append(
            BBoxMM(
                c.cx - c.radius_mm,
                c.cy - c.radius_mm,
                c.cx + c.radius_mm,
                c.cy + c.radius_mm,
            )
        )
    for p in pads:
        hx, hy = p.width_mm / 2.0, p.height_mm / 2.0
        boxes.append(BBoxMM(p.cx - hx, p.cy - hy, p.cx + hx, p.cy + hy))
    if boxes:
        return union_bbox(boxes)
    hx, hy = fallback_x / 2.0, fallback_y / 2.0
    return BBoxMM(-hx, -hy, hx, hy)


@dataclass
class UpdProfileSnapshot:
    """Geometry rows for one PROFILENAME (all dimensions still in µm)."""

    profilename: str
    parentprofile: str = ""
    vision_type: int = 0
    partgroup_name: str = ""
    partdesc: str = ""
    size_x_um: int = 0
    size_y_um: int = 0
    size_z_um: int = 0
    pin1_x_um: int = 0
    pin1_y_um: int = 0
    polarized: bool | None = None
    pin1_indicator: int = 0
    chip_whole: Mapping[str, Any] | None = None
    ll_whole: Mapping[str, Any] | None = None
    ll_groups: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    ll_params: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    ll_gaps: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    bga_whole: Mapping[str, Any] | None = None
    bga_params: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    bga_groups: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    bga_gaps: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    poly_whole: Mapping[str, Any] | None = None
    poly_verts: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    flip_whole: Mapping[str, Any] | None = None
    flip_params: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    flip_balls: Sequence[Mapping[str, Any]] = field(default_factory=tuple)


@dataclass(frozen=True)
class FootprintBuildResult:
    outline: FootprintOutlineMM
    vision_type: int
    partgroup_name: str
    partdesc: str
    size_x_mm: float
    size_y_mm: float
    size_z_mm: float
    pin1_x_mm: float
    pin1_y_mm: float
    warnings: tuple[str, ...]
    error: str = ""
    pin1_kind: str = "none"
    polarity: str = "none"


def _empty_result(
    snap: UpdProfileSnapshot, *, error: str, warnings: tuple[str, ...] = ()
) -> FootprintBuildResult:
    px, py, kind, pol = resolve_pin1(snap, FootprintOutlineMM(source="none"))
    return FootprintBuildResult(
        outline=FootprintOutlineMM(source="none"),
        vision_type=snap.vision_type,
        partgroup_name=snap.partgroup_name,
        partdesc=snap.partdesc,
        size_x_mm=um_to_mm(snap.size_x_um),
        size_y_mm=um_to_mm(snap.size_y_um),
        size_z_mm=um_to_mm(snap.size_z_um),
        pin1_x_mm=px,
        pin1_y_mm=py,
        warnings=warnings,
        error=error,
        pin1_kind=kind,
        polarity=pol,
    )


def _ok(
    snap: UpdProfileSnapshot,
    outline: FootprintOutlineMM,
    warnings: list[str],
) -> FootprintBuildResult:
    px, py, kind, pol = resolve_pin1(snap, outline)
    return FootprintBuildResult(
        outline=outline,
        vision_type=snap.vision_type,
        partgroup_name=snap.partgroup_name,
        partdesc=snap.partdesc,
        size_x_mm=um_to_mm(snap.size_x_um),
        size_y_mm=um_to_mm(snap.size_y_um),
        size_z_mm=um_to_mm(snap.size_z_um),
        pin1_x_mm=px,
        pin1_y_mm=py,
        warnings=tuple(warnings),
        error="",
        pin1_kind=kind,
        polarity=pol,
    )


def _ll_param_map(
    params: Sequence[Mapping[str, Any]],
) -> dict[int, Mapping[str, Any]]:
    out: dict[int, Mapping[str, Any]] = {}
    for row in params:
        out[_int(_row_get(row, "INDEX"))] = row
    return out


def _missing_lead_set(
    gaps: Sequence[Mapping[str, Any]], group_index: int
) -> set[int]:
    """1-based lead numbers listed as missing in VISION_LL_GAP_Det."""
    missing: set[int] = set()
    for g in gaps:
        if _int(_row_get(g, "INDEX")) != group_index:
            continue
        start = _int(_row_get(g, "STARTNO"))
        n = _int(_row_get(g, "MISSLEADNUM"))
        for i in range(start, start + n):
            missing.add(i)
    return missing


def _ll_cardinal_side(raw: object) -> str | None:
    """Map lead-group ANGLE 0..3 only. 90 / -90 / 270 are not sides."""
    a = _int(raw)
    return _LL_SIDE.get(a)


def _ll_tan_body_len(side: str, body_x: float, body_y: float) -> tuple[float, float]:
    """Tangent axis length, then the orthogonal (radial) body length."""
    if side in ("pos_x", "neg_x"):
        return abs(body_y), abs(body_x)
    return abs(body_x), abs(body_y)


def _ll_span_overflows_tangent(span_mm: float, tan_len: float, rad_len: float) -> bool:
    """True when the row is stored on the short body axis (FPC 40-pin vs landscape TYPSIZE)."""
    if span_mm <= 0 or tan_len <= 0:
        return False
    if span_mm <= tan_len * 1.25:
        return False
    return span_mm <= rad_len * 1.1 or rad_len > tan_len * 1.5


def _ll_rotate_whole_footprint(
    groups: Sequence[Mapping[str, Any]],
    pmap: dict[int, Mapping[str, Any]],
    body_x_mm: float,
    body_y_mm: float,
) -> bool:
    """Rotate every group 90° only if the densest row (max LEADNUM) overflows TYPSIZE.

    Two-pad mounting groups often have a huge TYPPITCH along the long body axis; those
    must not flip a 4-pin signal row that already fits the short axis.
    """
    best_n = -1
    best_span = 0.0
    best_side: str | None = None
    for grp in groups:
        side = _ll_cardinal_side(_row_get(grp, "ANGLE"))
        lead_n = _int(_row_get(grp, "LEADNUM"))
        pr = pmap.get(_int(_row_get(grp, "LEADPARAMNO")))
        if side is None or pr is None or lead_n < 1:
            continue
        pitch = um_to_mm(_row_get(pr, "TYPPITCH"))
        tan0 = um_to_mm(_row_get(grp, "TANCENTER"))
        half = abs(pitch) * max(lead_n - 1, 0) / 2.0
        # Include TANCENTER: User IC clusters sit off-axis and overflow TYPSIZEY
        # even when (LEADNUM-1)*pitch still fits the short side.
        span = 2.0 * (abs(tan0) + half)
        if lead_n > best_n or (lead_n == best_n and span > best_span):
            best_n, best_span, best_side = lead_n, span, side
    if best_side is None:
        return False
    tan_len, rad_len = _ll_tan_body_len(best_side, body_x_mm, body_y_mm)
    return _ll_span_overflows_tangent(best_span, tan_len, rad_len)


def _ll_flip_tan_for_opposite_sides(groups: Sequence[Mapping[str, Any]]) -> bool:
    """Both of a cardinal pair present (e.g. ANGLE 1 and 3) — negate tan on 2/3."""
    angles = {
        _int(_row_get(g, "ANGLE"))
        for g in groups
        if _ll_cardinal_side(_row_get(g, "ANGLE")) is not None
    }
    return (0 in angles and 2 in angles) or (1 in angles and 3 in angles)


def _ll_pads(
    groups: Sequence[Mapping[str, Any]],
    params: Sequence[Mapping[str, Any]],
    gaps: Sequence[Mapping[str, Any]],
    warnings: list[str],
    *,
    body_x_mm: float = 0.0,
    body_y_mm: float = 0.0,
) -> tuple[PadRectMM, ...]:
    pmap = _ll_param_map(params)
    pads: list[PadRectMM] = []
    n_pad = 0
    rotated = False
    flip_tan = _ll_flip_tan_for_opposite_sides(groups)
    rotate_all = _ll_rotate_whole_footprint(
        groups, pmap, body_x_mm, body_y_mm
    )
    for grp in groups:
        gi = _int(_row_get(grp, "INDEX"))
        angle = _int(_row_get(grp, "ANGLE"))
        side = _ll_cardinal_side(angle)
        if side is None:
            warnings.append(f"unknown LL ANGLE={angle} on group {gi}")
            continue
        rad = um_to_mm(_row_get(grp, "RADCENTER"))
        tan0 = um_to_mm(_row_get(grp, "TANCENTER"))
        lead_n = _int(_row_get(grp, "LEADNUM"))
        pidx = _int(_row_get(grp, "LEADPARAMNO"))
        pr = pmap.get(pidx)
        if pr is None:
            warnings.append(f"missing LL param INDEX={pidx} for group {gi}")
            continue
        pitch = um_to_mm(_row_get(pr, "TYPPITCH"))
        width = um_to_mm(_row_get(pr, "TYPWIDTH"))
        length = um_to_mm(_row_get(pr, "TYPLENGTH"))
        missing = _missing_lead_set(gaps, gi)
        if lead_n < 1:
            continue
        if rotate_all:
            side = _LL_ROTATE_CCW[side]
            rotated = True
        mid = (lead_n - 1) / 2.0
        for i in range(lead_n):
            lead_no = i + 1
            if lead_no in missing:
                continue
            t = tan0 + (i - mid) * pitch
            if flip_tan and angle in (2, 3):
                t = -t
            if side == "pos_x":
                cx, cy, rot = rad, t, 90.0
            elif side == "neg_x":
                cx, cy, rot = -rad, t, 90.0
            elif side == "pos_y":
                cx, cy, rot = t, rad, 0.0
            else:
                cx, cy, rot = t, -rad, 0.0
            n_pad += 1
            pads.append(
                PadRectMM(cx, cy, width, length, rot, str(n_pad))
            )
    if rotated:
        warnings.append(
            "pads: lead row rotated 90° (pitch span vs TYPSIZE)"
        )
    return tuple(pads)


def _poly_lines(verts: Sequence[Mapping[str, Any]]) -> tuple[StrokeLineMM, ...]:
    ordered = sorted(verts, key=lambda r: _int(_row_get(r, "INDEX")))
    lines: list[StrokeLineMM] = []
    contour: list[tuple[float, float]] = []

    def flush() -> None:
        if len(contour) < 2:
            contour.clear()
            return
        for a, b in zip(contour, contour[1:]):
            lines.append(StrokeLineMM(a[0], a[1], b[0], b[1], _LINE_W))
        if len(contour) >= 3:
            a, b = contour[-1], contour[0]
            lines.append(StrokeLineMM(a[0], a[1], b[0], b[1], _LINE_W))
        contour.clear()

    for v in ordered:
        x = um_to_mm(_row_get(v, "VERTEXPOINTX"))
        y = um_to_mm(_row_get(v, "VERTEXPOINTY"))
        bit = _int(_row_get(v, "CONTROLBIT"))
        if bit == 0:
            flush()
            contour.append((x, y))
        else:
            if not contour:
                contour.append((x, y))
            else:
                contour.append((x, y))
    flush()
    return tuple(lines)


def _bga_circles(
    groups: Sequence[Mapping[str, Any]],
    params: Sequence[Mapping[str, Any]],
    gaps: Sequence[Mapping[str, Any]],
    warnings: list[str],
) -> tuple[StrokeCircleMM, ...]:
    pmap = _ll_param_map(params)
    circles: list[StrokeCircleMM] = []
    for grp in groups:
        gi = _int(_row_get(grp, "INDEX"))
        pidx = _int(_row_get(grp, "PARAMINDEX", "LEADPARAMNO"))
        pr = pmap.get(pidx)
        if pr is None and params:
            pr = params[0]
        if pr is None:
            warnings.append(f"missing BGA param for group {gi}")
            continue
        nr = _int(_row_get(grp, "NUMBALLSR"))
        nt = _int(_row_get(grp, "NUMBALLST"))
        pitch_r = um_to_mm(_row_get(pr, "TYPBALLPITCHR"))
        pitch_t = um_to_mm(_row_get(pr, "TYPBALLPITCHT"))
        dia = um_to_mm(_row_get(pr, "TYPBALLDIA"))
        radius = dia / 2.0
        skip: set[tuple[int, int]] = set()
        for g in gaps:
            if _int(_row_get(g, "INDEX")) != gi:
                continue
            r0 = _int(_row_get(g, "MISSBLOCKR"))
            t0 = _int(_row_get(g, "MISSBLOCKT"))
            nr_m = _int(_row_get(g, "NUMMISSINGR"))
            nt_m = _int(_row_get(g, "NUMMISSINGT"))
            for rr in range(r0, r0 + max(nr_m, 0)):
                for tt in range(t0, t0 + max(nt_m, 0)):
                    skip.add((rr, tt))
        if nr < 1 or nt < 1:
            continue
        mid_r = (nr - 1) / 2.0
        mid_t = (nt - 1) / 2.0
        # NUMBALLSR follows TYPSIZEX, NUMBALLST follows TYPSIZEY (see FH82H610 vs _90).
        for ir in range(nr):
            for it in range(nt):
                if (ir, it) in skip:
                    continue
                cx = (ir - mid_r) * pitch_r
                cy = (it - mid_t) * pitch_t
                circles.append(StrokeCircleMM(cx, cy, radius, _LINE_W))
    return tuple(circles)


def build_from_snapshot(snap: UpdProfileSnapshot) -> FootprintBuildResult:
    """Interpret a loaded profile snapshot into millimetre outline + metadata."""
    vt = int(snap.vision_type)
    warnings: list[str] = []
    fx, fy = um_to_mm(snap.size_x_um), um_to_mm(snap.size_y_um)

    if vt == 0:
        return _empty_result(snap, error="VISIONTYPE=0 (no vision geometry)")

    if vt == 3:
        whole = snap.chip_whole or {}
        bx = um_to_mm(_row_get(whole, "TYPSIZEX")) or fx
        by = um_to_mm(_row_get(whole, "TYPSIZEY")) or fy
        if bx <= 0 or by <= 0:
            return _empty_result(snap, error="chip body size is zero")
        if is_chip_circle(snap.partgroup_name):
            circles = chip_circle_body(bx, by)
            outline = FootprintOutlineMM(
                circles=circles,
                bbox=_bbox_from_primitives((), circles, (), bx, by),
                source="hanwha_upd",
            )
            warnings.append("body: circle (CHIP-Circle); no chip lands")
            return _ok(snap, outline, warnings)
        lines = body_rect_lines(bx, by)
        lead_pads = chip_lead_pads_from_exparam(whole, bx, by)
        if lead_pads:
            pads = lead_pads
            warnings.append(
                "pads: chip lead slots (EXPARAM15/16 counts; unused = 0)"
            )
        elif uses_sot23_pads(
            snap.partgroup_name,
            snap.partdesc,
            snap.profilename,
            whole,
        ):
            pads = sot23_heuristic_pads(bx, by)
            warnings.append(
                "pads: SOT-23 heuristic (chip table has no leads)"
            )
        else:
            pads = chip_heuristic_pads(bx, by)
            warnings.append("pads: heuristic (chip lands are not in UPD.MDB)")
        outline = FootprintOutlineMM(
            lines=lines,
            pads=pads,
            bbox=_bbox_from_primitives(lines, (), pads, bx, by),
            source="hanwha_upd",
        )
        return _ok(snap, outline, warnings)

    if vt == 1:
        whole = snap.ll_whole or {}
        bx = um_to_mm(_row_get(whole, "TYPSIZEX")) or fx
        by = um_to_mm(_row_get(whole, "TYPSIZEY")) or fy
        lines = body_rect_lines(bx, by) if bx > 0 and by > 0 else ()
        pads = _ll_pads(
            snap.ll_groups,
            snap.ll_params,
            snap.ll_gaps,
            warnings,
            body_x_mm=bx,
            body_y_mm=by,
        )
        warnings.append("pads: reconstructed from vision leads (not copper lands)")
        if not pads and not lines:
            return _empty_result(snap, error="no LL body or leads", warnings=tuple(warnings))
        outline = FootprintOutlineMM(
            lines=lines,
            pads=pads,
            bbox=_bbox_from_primitives(lines, (), pads, fx or bx, fy or by),
            source="hanwha_upd",
        )
        return _ok(snap, outline, warnings)

    if vt == 2:
        whole = snap.bga_whole or {}
        bx = um_to_mm(_row_get(whole, "TYPSIZEX")) or fx
        by = um_to_mm(_row_get(whole, "TYPSIZEY")) or fy
        lines = body_rect_lines(bx, by) if bx > 0 and by > 0 else ()
        groups = snap.bga_groups
        if not groups and snap.bga_params:
            groups = (
                {
                    "INDEX": 0,
                    "PARAMINDEX": 0,
                    "NUMBALLSR": 0,
                    "NUMBALLST": 0,
                },
            )
        circles = _bga_circles(groups, snap.bga_params, snap.bga_gaps, warnings)
        if not circles:
            appear = um_to_mm(_row_get(whole, "APPEARBALLSIZE"))
            if appear > 0 and bx > 0:
                warnings.append("BGA grid empty; body only")
        outline = FootprintOutlineMM(
            lines=lines,
            circles=circles,
            bbox=_bbox_from_primitives(lines, circles, (), fx or bx, fy or by),
            source="hanwha_upd",
        )
        return _ok(snap, outline, warnings)

    if vt == 5:
        whole = snap.flip_whole or {}
        bx = um_to_mm(_row_get(whole, "TYPSIZEX")) or fx
        by = um_to_mm(_row_get(whole, "TYPSIZEY")) or fy
        lines = body_rect_lines(bx, by) if bx > 0 and by > 0 else ()
        dia = 0.0
        if snap.flip_params:
            dia = um_to_mm(_row_get(snap.flip_params[0], "TYPBALLDIA"))
        radius = dia / 2.0 if dia > 0 else 0.15
        circles = tuple(
            StrokeCircleMM(
                um_to_mm(_row_get(b, "POSITIONX")),
                um_to_mm(_row_get(b, "POSITIONY")),
                radius,
                _LINE_W,
            )
            for b in snap.flip_balls
        )
        outline = FootprintOutlineMM(
            lines=lines,
            circles=circles,
            bbox=_bbox_from_primitives(lines, circles, (), fx or bx, fy or by),
            source="hanwha_upd",
        )
        return _ok(snap, outline, warnings)

    if vt == 6:
        verts = snap.poly_verts
        lines = _poly_lines(verts)
        whole = snap.poly_whole or {}
        bx = um_to_mm(_row_get(whole, "BODYSIZEX")) or fx
        by = um_to_mm(_row_get(whole, "BODYSIZEY")) or fy
        if not lines and bx > 0 and by > 0:
            lines = body_rect_lines(bx, by)
            warnings.append("polygon VERTEXNUM empty; used BODYSIZE rect")
        warnings.append("pads: not stored for polygon / odd-form packages")
        outline = FootprintOutlineMM(
            lines=lines,
            bbox=_bbox_from_primitives(lines, (), (), bx, by),
            source="hanwha_upd",
        )
        return _ok(snap, outline, warnings)

    if vt == 4:
        return _empty_result(
            snap, error="VISIONTYPE=4 Odd Form has no geometry in this library"
        )

    return _empty_result(snap, error=f"unsupported VISIONTYPE={vt}")
