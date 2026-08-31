# SPDX-License-Identifier: MIT
"""Build FootprintBuildResult silhouettes for a VSPD package id."""

from __future__ import annotations

import json
from typing import Any

import pcb_preview.upd_footprint_builder as upd_fp
from package_vspd.catalog import iter_seed_packages
from parsers import regex_api as re
from pcb_preview.types import (
    BBoxMM,
    FootprintOutlineMM,
    PadRectMM,
    StrokeCircleMM,
    StrokeLineMM,
    union_bbox,
)

_LINE_W = 0.12


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


def _melf_capsule_body(lx: float, wy: float) -> tuple[StrokeCircleMM, ...]:
    """Cylindrical diode top view: two circular end caps along X."""
    if lx <= 0 or wy <= 0:
        return ()
    r = wy / 2.0
    inset = min(r, lx / 2.0)
    return (
        StrokeCircleMM(-(lx / 2.0 - inset), 0.0, r, _LINE_W),
        StrokeCircleMM(lx / 2.0 - inset, 0.0, r, _LINE_W),
    )


def _melf_end_pads(lx: float, wy: float) -> tuple[PadRectMM, ...]:
    if lx <= 0 or wy <= 0:
        return ()
    pad_w = min(0.45, lx * 0.14)
    pad_h = wy * 0.65
    cx = (lx - pad_w) / 2.0
    return (
        PadRectMM(-cx, 0.0, pad_w, pad_h, 0.0, "1"),
        PadRectMM(cx, 0.0, pad_w, pad_h, 0.0, "2"),
    )


def _cap_alu_pads(lx: float, wy: float) -> tuple[PadRectMM, ...]:
    """Round electrolytic: two pads along the bottom edge."""
    if lx <= 0 or wy <= 0:
        return ()
    pitch = min(lx * 0.42, lx * 0.55)
    pw = min(0.9, lx * 0.22)
    ph = min(0.7, wy * 0.18)
    y = -(wy / 2.0) - ph * 0.25
    return (
        PadRectMM(-pitch / 2.0, y, pw, ph, 0.0, "1"),
        PadRectMM(pitch / 2.0, y, pw, ph, 0.0, "2"),
    )


def _power_sot_pads(vspd_id: str, lx: float, wy: float) -> tuple[PadRectMM, ...]:
    u = (vspd_id or "").upper()
    if u == "SOT-223":
        tab_w, tab_h = min(2.2, lx * 0.38), wy * 0.82
        pw, ph = min(0.75, lx * 0.11), min(0.85, wy * 0.32)
        x_tab = -(lx / 2.0) + tab_w / 2.0 + lx * 0.04
        x_pin = (lx / 2.0) - pw / 2.0 - lx * 0.05
        ys = (-wy * 0.3, 0.0, wy * 0.3)
        pads: list[PadRectMM] = [PadRectMM(x_tab, 0.0, tab_w, tab_h, 0.0, "2")]
        for i, y in enumerate(ys):
            pads.append(PadRectMM(x_pin, y, pw, ph, 0.0, str(1 if i == 0 else i + 2)))
        return tuple(pads)
    if u == "SOT-89":
        pw, ph = min(0.95, lx * 0.2), min(0.9, wy * 0.28)
        return (
            PadRectMM(-lx * 0.28, 0.0, pw, ph, 0.0, "1"),
            PadRectMM(lx * 0.28, wy * 0.28, pw, ph, 0.0, "2"),
            PadRectMM(lx * 0.28, -wy * 0.28, pw, ph, 0.0, "3"),
        )
    if u in {"TO-252", "TO-277"}:
        pw, ph = min(1.0, lx * 0.16), min(0.9, wy * 0.24)
        tab_w, tab_h = lx * 0.42, wy * 0.68
        return (
            PadRectMM(-lx * 0.24, 0.0, pw, ph, 0.0, "1"),
            PadRectMM(lx * 0.26, 0.0, tab_w, tab_h, 0.0, "2"),
            PadRectMM(lx * 0.26, -wy * 0.3, pw, ph, 0.0, "3"),
        )
    if u == "TO-263":
        pw, ph = min(1.1, lx * 0.12), min(1.0, wy * 0.18)
        tab_w, tab_h = lx * 0.4, wy * 0.72
        xs = (-lx * 0.3, lx * 0.26)
        return (
            PadRectMM(xs[0], wy * 0.28, pw, ph, 0.0, "1"),
            PadRectMM(xs[0], -wy * 0.28, pw, ph, 0.0, "3"),
            PadRectMM(xs[1], 0.0, tab_w, tab_h, 0.0, "2"),
            PadRectMM(xs[1], wy * 0.32, pw, ph, 0.0, "4"),
            PadRectMM(xs[1], -wy * 0.32, pw, ph, 0.0, "5"),
        )
    return ()


def _conn_pads(vspd_id: str, lx: float, wy: float) -> tuple[PadRectMM, ...]:
    u = (vspd_id or "").upper()
    n = 0
    m = re.search(r"(\d+)P\b", u)
    if m:
        n = int(m.group(1))
    elif re.search(r"1X(\d+)", u.replace("-", "")):
        n = int(re.search(r"1X(\d+)", u.replace("-", "")).group(1))  # type: ignore[union-attr]
    if n < 1:
        return ()
    pitch = min(1.27, (lx * 0.82) / max(n - 1, 1))
    span = (n - 1) * pitch if n > 1 else 0.0
    pw = min(0.85, pitch * 0.55)
    ph = min(1.2, wy * 0.32)
    y = -(wy / 2.0) - ph * 0.2
    return tuple(
        PadRectMM(-span / 2.0 + i * pitch, y, pw, ph, 0.0, str(i + 1))
        for i in range(n)
    )


def _array_pads(vspd_id: str, lx: float, wy: float) -> tuple[PadRectMM, ...]:
    m = re.search(r"X(\d+)\s*$", (vspd_id or "").upper())
    if not m:
        return ()
    n = int(m.group(1))
    if n == 2:
        cols, rows = 2, 1
    elif n == 4:
        cols, rows = 2, 2
    else:
        cols, rows = n, 1
    gap_x = lx * 0.72 / max(cols - 1, 1) if cols > 1 else 0.0
    gap_y = wy * 0.72 / max(rows - 1, 1) if rows > 1 else 0.0
    pw = min(0.55, gap_x * 0.75 if cols > 1 else lx * 0.35)
    ph = min(0.55, gap_y * 0.75 if rows > 1 else wy * 0.35)
    ox = -gap_x * (cols - 1) / 2.0
    oy = -gap_y * (rows - 1) / 2.0
    pads: list[PadRectMM] = []
    num = 1
    for row in range(rows):
        for col in range(cols):
            pads.append(
                PadRectMM(ox + col * gap_x, oy + row * gap_y, pw, ph, 0.0, str(num))
            )
            num += 1
    return tuple(pads)


def _xtal_pads(lx: float, wy: float) -> tuple[PadRectMM, ...]:
    if lx <= 0 or wy <= 0:
        return ()
    pw, ph = lx * 0.22, wy * 0.35
    ox, oy = lx * 0.32, wy * 0.32
    return (
        PadRectMM(-ox, -oy, pw, ph, 0.0, "1"),
        PadRectMM(ox, -oy, pw, ph, 0.0, "2"),
        PadRectMM(ox, oy, pw, ph, 0.0, "3"),
        PadRectMM(-ox, oy, pw, ph, 0.0, "4"),
    )


def _pads_for(vspd_id: str, lx: float, wy: float) -> tuple[PadRectMM, ...]:
    u = (vspd_id or "").upper()
    if u.startswith("CHIP-") or u.startswith("TANT-") or u.startswith("SOD-") or u.startswith("LED-"):
        return upd_fp.chip_heuristic_pads(lx, wy)
    if u.startswith("FUSE-") or u.startswith("IND-SMD-"):
        return upd_fp.chip_heuristic_pads(lx, wy)
    if u in {"SMA", "SMB", "SMC"}:
        return upd_fp.chip_heuristic_pads(lx, wy)
    if u in {"MINIMELF", "MELF"}:
        return _melf_end_pads(lx, wy)
    if u.startswith("CAP-ALU-"):
        return _cap_alu_pads(lx, wy)
    if u.startswith("ARRAY-"):
        return _array_pads(vspd_id, lx, wy)
    if u.startswith("CONN-"):
        return _conn_pads(vspd_id, lx, wy)
    if u.startswith("XTAL-"):
        return _xtal_pads(lx, wy)
    if u.startswith("SOT-23-"):
        n = 5
        tail = u.split("SOT-23-", 1)[1]
        if tail[:1].isdigit():
            n = int(tail[0])
        return _sot23_more_pads(lx, wy, n)
    if u.startswith("TSOT-23-"):
        tail = u.split("TSOT-23-", 1)[1]
        n = int(tail[0]) if tail[:1].isdigit() else 6
        return _sot23_more_pads(lx, wy, n)
    if u.startswith("SOT-23") or u in {"SOT-323", "SOT-353", "SOT-523", "SOT-723", "SOT-143"}:
        return _sot23_pads(lx, wy)
    if u.startswith("SOT-363") or u.startswith("SOT-563"):
        return _sot23_more_pads(lx, wy, 6)
    if u in {"SOT-223", "SOT-89", "TO-252", "TO-263", "TO-277"}:
        return _power_sot_pads(vspd_id, lx, wy)
    if u.startswith(("SOIC-", "SSOP-", "TSSOP-", "MSOP-", "ESOP-", "SOJ-")):
        n = _digits_after_dash(u)
        pitch = 1.27 if u.startswith(("SOIC-", "SOJ-")) else 0.65
        return _dual_row_pads(n, lx, wy, pitch)
    if u.startswith(("LQFP-", "TQFP-", "PLCC-", "QFN-", "DFN-", "LGA-", "WSON-")):
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


def _body_lines_and_circles(
    vspd_id: str, lx: float, wy: float
) -> tuple[tuple[StrokeLineMM, ...], tuple[StrokeCircleMM, ...]]:
    u = (vspd_id or "").upper()
    if u.startswith("CIRCLE-") or u.startswith("CAP-ALU-"):
        return (), upd_fp.chip_circle_body(lx, wy)
    if u in {"MELF", "MINIMELF"}:
        return (), _melf_capsule_body(lx, wy)
    return upd_fp.body_rect_lines(lx, wy), ()


def heuristic_outline(vspd_id: str) -> FootprintOutlineMM | None:
    lx, wy, _h = _body_for(vspd_id)
    if lx <= 0 or wy <= 0:
        return None
    u = (vspd_id or "").upper()
    pads = _pads_for(vspd_id, lx, wy)
    lines, body_circ = _body_lines_and_circles(vspd_id, lx, wy)
    circ = body_circ + _ball_circles(vspd_id, lx, wy)
    if u.startswith("CIRCLE-"):
        pads = ()
    return FootprintOutlineMM(
        lines=lines,
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
) -> upd_fp.FootprintBuildResult:
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
        return upd_fp.FootprintBuildResult(
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
    return upd_fp.FootprintBuildResult(
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
