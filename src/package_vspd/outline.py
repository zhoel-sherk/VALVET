# SPDX-License-Identifier: MIT
"""Build FootprintBuildResult silhouettes for a VSPD package id."""

from __future__ import annotations

import json
from typing import Any

from package_vspd.catalog import iter_seed_packages
from pcb_preview.types import (
    BBoxMM,
    FootprintOutlineMM,
    PadRectMM,
    StrokeCircleMM,
    StrokeLineMM,
    union_bbox,
)
from pcb_preview.upd_footprint_builder import (
    FootprintBuildResult,
    body_rect_lines,
    chip_heuristic_pads,
)


def _body_for(vspd_id: str) -> tuple[float, float, float]:
    for row in iter_seed_packages():
        if row["vspd_id"] == vspd_id:
            return row["body_l"], row["body_w"], row["body_h"]
    return 0.0, 0.0, 0.0


def outline_to_json(outline: FootprintOutlineMM) -> str:
    def line(x: StrokeLineMM) -> dict[str, Any]:
        return {
            "x1": x.x1,
            "y1": x.y1,
            "x2": x.x2,
            "y2": x.y2,
            "width_mm": x.width_mm,
        }

    def circ(c: StrokeCircleMM) -> dict[str, Any]:
        return {
            "cx": c.cx,
            "cy": c.cy,
            "radius_mm": c.radius_mm,
            "width_mm": c.width_mm,
        }

    def pad(p: PadRectMM) -> dict[str, Any]:
        return {
            "cx": p.cx,
            "cy": p.cy,
            "width_mm": p.width_mm,
            "height_mm": p.height_mm,
            "rotation_deg": p.rotation_deg,
            "number": p.number,
        }

    bb = outline.bbox
    return json.dumps(
        {
            "lines": [line(x) for x in outline.lines],
            "circles": [circ(c) for c in outline.circles],
            "pads": [pad(p) for p in outline.pads],
            "bbox": {
                "min_x": bb.min_x,
                "min_y": bb.min_y,
                "max_x": bb.max_x,
                "max_y": bb.max_y,
            },
            "source": outline.source,
        }
    )


def outline_from_json(raw: str) -> FootprintOutlineMM:
    d = json.loads(raw)
    bb = d.get("bbox") or {}
    return FootprintOutlineMM(
        lines=tuple(StrokeLineMM(**x) for x in d.get("lines") or []),
        circles=tuple(StrokeCircleMM(**x) for x in d.get("circles") or []),
        pads=tuple(PadRectMM(**x) for x in d.get("pads") or []),
        bbox=BBoxMM(
            float(bb.get("min_x") or 0.0),
            float(bb.get("min_y") or 0.0),
            float(bb.get("max_x") or 0.0),
            float(bb.get("max_y") or 0.0),
        ),
        source=d.get("source") or "none",  # type: ignore[arg-type]
    )


def _pads_for(vspd_id: str, lx: float, wy: float) -> tuple[PadRectMM, ...]:
    u = (vspd_id or "").upper()
    if u.startswith("CHIP-") or u.startswith("TANT-") or u.startswith("SOD-") or u.startswith("LED-"):
        return chip_heuristic_pads(lx, wy)
    if u in {"SMA", "SMB", "SMC", "MINIMELF"}:
        return chip_heuristic_pads(lx, wy)
    if u.startswith("SOT-23-"):
        n = 5
        tail = u.split("SOT-23-", 1)[1]
        if tail[:1].isdigit():
            n = int(tail[0])
        return _sot23_more_pads(lx, wy, n)
    if u.startswith("SOT-23") or u == "SOT-323":
        return _sot23_pads(lx, wy)
    if u.startswith("SOT-363") or u.startswith("SOT-563"):
        return _sot23_more_pads(lx, wy, 6)
    if u.startswith(("SOIC-", "SSOP-", "TSSOP-", "MSOP-")):
        n = _digits_after_dash(u)
        pitch = 1.27 if u.startswith("SOIC-") else 0.65
        return _dual_row_pads(n, lx, wy, pitch)
    if u.startswith(("LQFP-", "TQFP-", "QFN-", "DFN-", "LGA-")):
        n = _digits_after_dash(u)
        return _quad_pads(n, lx, wy)
    return ()


def _digits_after_dash(vspd_id: str) -> int:
    parts = vspd_id.split("-")
    if len(parts) < 2:
        return 0
    head = parts[1].split("_")[0]
    digits = ""
    for ch in head:
        if ch.isdigit():
            digits += ch
        else:
            break
    return int(digits) if digits else 0


def _sot23_pads(lx: float, wy: float) -> tuple[PadRectMM, ...]:
    pw, ph = min(0.55, lx * 0.32), min(0.5, wy * 0.5)
    xoff = lx * 0.32
    yoff = wy / 2.0 + ph * 0.22
    return (
        PadRectMM(-xoff, -yoff, pw, ph, 0.0, "1"),
        PadRectMM(xoff, -yoff, pw, ph, 0.0, "2"),
        PadRectMM(0.0, yoff, pw, ph, 0.0, "3"),
    )


def _sot23_more_pads(lx: float, wy: float, n: int) -> tuple[PadRectMM, ...]:
    per = (n + 1) // 2
    return _dual_row_pads(max(n, per * 2), lx, wy, max(0.45, lx / max(per, 1) * 0.7))


def _dual_row_pads(
    n: int, lx: float, wy: float, pitch: float
) -> tuple[PadRectMM, ...]:
    per = max(n // 2, 1)
    if per < 1 or lx <= 0 or wy <= 0:
        return ()
    if per > 1:
        span = (per - 1) * pitch
        if span > lx * 0.92:
            pitch = (lx * 0.85) / (per - 1)
            span = (per - 1) * pitch
    else:
        span = 0.0
    xs = [-span / 2.0 + i * pitch for i in range(per)]
    pw = min(0.6, max(0.28, pitch * 0.45))
    ph = min(0.95, max(0.35, wy * 0.32))
    y = wy / 2.0 + ph * 0.18
    pads: list[PadRectMM] = []
    for i, x in enumerate(xs):
        pads.append(PadRectMM(x, -y, pw, ph, 0.0, str(i + 1)))
    for i, x in enumerate(reversed(xs)):
        pads.append(PadRectMM(x, y, pw, ph, 0.0, str(per + i + 1)))
    return tuple(pads)


def _quad_pads(n: int, lx: float, wy: float) -> tuple[PadRectMM, ...]:
    per = max(n // 4, 1)
    if lx <= 0 or wy <= 0:
        return ()
    pitch_x = (lx * 0.72) / max(per - 1, 1) if per > 1 else 0.0
    pitch_y = (wy * 0.72) / max(per - 1, 1) if per > 1 else 0.0
    pw = min(0.45, max(0.22, min(lx, wy) * 0.08))
    ph = pw * 1.6
    pads: list[PadRectMM] = []
    num = 1
    xs = [-pitch_x * (per - 1) / 2.0 + i * pitch_x for i in range(per)]
    ys = [-pitch_y * (per - 1) / 2.0 + i * pitch_y for i in range(per)]
    yb, yt = -wy / 2.0 - ph * 0.15, wy / 2.0 + ph * 0.15
    xl, xr = -lx / 2.0 - pw * 0.15, lx / 2.0 + pw * 0.15
    for x in xs:
        pads.append(PadRectMM(x, yb, pw, ph, 0.0, str(num)))
        num += 1
    for y in ys:
        pads.append(PadRectMM(xr, y, ph, pw, 0.0, str(num)))
        num += 1
    for x in reversed(xs):
        pads.append(PadRectMM(x, yt, pw, ph, 0.0, str(num)))
        num += 1
    for y in reversed(ys):
        pads.append(PadRectMM(xl, y, ph, pw, 0.0, str(num)))
        num += 1
    return tuple(pads)


def _ball_circles(vspd_id: str, lx: float, wy: float) -> tuple[StrokeCircleMM, ...]:
    u = (vspd_id or "").upper()
    n = 0
    if u.startswith("WLCSP-"):
        n = _digits_after_dash(u)
    elif u.startswith("BGA-") or u.startswith("FBGA-") or u.startswith("VFBGA-"):
        parts = u.split("-")
        if parts[-1].isdigit():
            n = int(parts[-1])
    side = int(n**0.5) if n else 0
    if side < 2 or side * side != n:
        return ()
    r = min(lx, wy) / side * 0.18
    xs = [(-side + 1) / 2.0 * (lx / side) + i * (lx / side) for i in range(side)]
    ys = [(-side + 1) / 2.0 * (wy / side) + j * (wy / side) for j in range(side)]
    return tuple(
        StrokeCircleMM(x, y, r, 0.08) for y in ys for x in xs
    )


def _outline_bbox(
    lx: float, wy: float, pads: tuple[PadRectMM, ...], circ: tuple[StrokeCircleMM, ...]
) -> BBoxMM:
    boxes = [BBoxMM(-lx / 2.0, -wy / 2.0, lx / 2.0, wy / 2.0)]
    for p in pads:
        hx, hy = p.width_mm / 2.0, p.height_mm / 2.0
        boxes.append(BBoxMM(p.cx - hx, p.cy - hy, p.cx + hx, p.cy + hy))
    for c in circ:
        boxes.append(
            BBoxMM(c.cx - c.radius_mm, c.cy - c.radius_mm, c.cx + c.radius_mm, c.cy + c.radius_mm)
        )
    return union_bbox(boxes)


def heuristic_outline(vspd_id: str) -> FootprintOutlineMM | None:
    lx, wy, _h = _body_for(vspd_id)
    if lx <= 0 or wy <= 0:
        return None
    pads = _pads_for(vspd_id, lx, wy)
    circ = _ball_circles(vspd_id, lx, wy)
    return FootprintOutlineMM(
        lines=body_rect_lines(lx, wy),
        circles=circ,
        pads=pads,
        bbox=_outline_bbox(lx, wy, pads, circ),
        source="vspd_heuristic",
    )


def build_result_for_package(
    vspd_id: str,
    *,
    outline_json: str | None = None,
    family: str = "",
    notes: str = "",
) -> FootprintBuildResult:
    warnings: list[str] = []
    outline: FootprintOutlineMM | None = None
    if outline_json:
        try:
            outline = outline_from_json(outline_json)
        except (json.JSONDecodeError, TypeError, KeyError, ValueError):
            warnings.append("stored outline_json unreadable")
    if outline is None or outline.source == "none":
        outline = heuristic_outline(vspd_id)
    if outline is None:
        return FootprintBuildResult(
            outline=FootprintOutlineMM(source="none"),
            vision_type=0,
            partgroup_name=family or "Package",
            partdesc=notes,
            size_x_mm=0.0,
            size_y_mm=0.0,
            size_z_mm=0.0,
            pin1_x_mm=0.0,
            pin1_y_mm=0.0,
            warnings=tuple(warnings),
            error="No outline for this package",
            pin1_kind="none",
            polarity="none",
        )
    lx, wy, hz = _body_for(vspd_id)
    if lx <= 0:
        lx = outline.bbox.width
        wy = outline.bbox.height
    return FootprintBuildResult(
        outline=outline,
        vision_type=0,
        partgroup_name=family or "Package",
        partdesc=notes,
        size_x_mm=lx,
        size_y_mm=wy,
        size_z_mm=hz,
        pin1_x_mm=0.0,
        pin1_y_mm=0.0,
        warnings=tuple(warnings),
        error="",
        pin1_kind="none",
        polarity="none",
    )
