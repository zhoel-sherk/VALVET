# SPDX-License-Identifier: MIT
"""Best-effort Yamaha ``.Tou`` footprint silhouette (name codes + placement metadata).

``.Tou`` bytes 40–319 do not store body size (job XY/rotation/comment only).
Package millimetres come from imperial/metric tokens in the component name.
"""

from __future__ import annotations

import re
from typing import Literal

from machine_library.yamaha_tou import TouRecord
from pcb_preview.types import BBoxMM, FootprintOutlineMM, StrokeLineMM
from pcb_preview.upd_footprint_builder import (
    FootprintBuildResult,
    body_rect_lines,
    chip_heuristic_pads,
)

YamahaOutlineSource = Literal["yamaha_tou", "yamaha_heuristic"]

_IMPERIAL_MM: dict[str, tuple[float, float]] = {
    "01005": (0.4, 0.2),
    "0201": (0.6, 0.3),
    "0402": (1.0, 0.5),
    "0603": (1.6, 0.8),
    "0805": (2.0, 1.25),
    "1206": (3.2, 1.6),
    "1210": (3.2, 2.5),
    "2010": (5.0, 2.5),
    "2512": (6.4, 3.2),
}
_IMPERIAL_CODES: tuple[str, ...] = tuple(
    sorted(_IMPERIAL_MM.keys(), key=len, reverse=True)
)

_METRIC_EIA = re.compile(r"(?:CAPC|RESC|INDC)(\d{4})", re.IGNORECASE)


def package_size_mm(name: str) -> tuple[float, float] | None:
    """Body L×W mm from Yamaha-style part names, or ``None``."""
    if not name:
        return None
    compact = name.upper().replace("_", "").replace("-", "").replace(" ", "")
    for code in _IMPERIAL_CODES:
        if code in compact:
            return _IMPERIAL_MM[code]
    m = _METRIC_EIA.search(name)
    if m:
        d = m.group(1)
        lx, wy = int(d[:2]) / 10.0, int(d[2:]) / 10.0
        if 0.2 <= lx <= 12.0 and 0.1 <= wy <= 8.0:
            return lx, wy
    return None


def _rect_outline(
    size_x_mm: float, size_y_mm: float, *, source: YamahaOutlineSource
) -> FootprintOutlineMM:
    lines: tuple[StrokeLineMM, ...] = body_rect_lines(size_x_mm, size_y_mm)
    hx, hy = size_x_mm / 2.0, size_y_mm / 2.0
    pads = chip_heuristic_pads(size_x_mm, size_y_mm)
    return FootprintOutlineMM(
        lines=lines,
        pads=pads,
        bbox=BBoxMM(-hx, -hy, hx, hy),
        source=source,
    )


def _result(
    *,
    size: tuple[float, float] | None,
    source: YamahaOutlineSource,
    extra: tuple[str, ...] = (),
    partdesc: str = "",
    kind: str = "",
) -> FootprintBuildResult:
    warnings = list(extra)
    if size is None:
        warnings.append("yamaha payload has no body size; name has no package code")
        outline = FootprintOutlineMM(source="none")
        sx = sy = 0.0
        err = "No Yamaha package size in name or .Tou payload"
    else:
        sx, sy = size
        outline = _rect_outline(sx, sy, source=source)
        err = ""
        if source == "yamaha_heuristic":
            warnings.append("body from package code in name (not binary size)")
        else:
            warnings.append("body from package code in name; .Tou has placement only")
    return FootprintBuildResult(
        outline=outline,
        vision_type=0,
        partgroup_name=kind or "Yamaha",
        partdesc=partdesc,
        size_x_mm=sx,
        size_y_mm=sy,
        size_z_mm=0.0,
        pin1_x_mm=0.0,
        pin1_y_mm=0.0,
        warnings=tuple(warnings),
        error=err,
        pin1_kind="none",
        polarity="none",
    )


def build_outline_from_name(
    name: str,
    *,
    kind: str = "",
    basename: str = "",
) -> FootprintBuildResult:
    """Lib / name-only silhouette (``yamaha_heuristic``)."""
    extra: list[str] = []
    if basename:
        extra.append(f"basename={basename}")
    desc = basename or ""
    return _result(
        size=package_size_mm(name) or package_size_mm(basename),
        source="yamaha_heuristic",
        extra=tuple(extra),
        partdesc=desc,
        kind=kind or "Lib",
    )


def build_outline_from_tou_record(rec: TouRecord) -> FootprintBuildResult:
    extra: list[str] = []
    if rec.refdes:
        extra.append(f"ref={rec.refdes}")
    if rec.x_mm is not None and rec.y_mm is not None:
        extra.append(f"XY {rec.x_mm:.3f}, {rec.y_mm:.3f} mm")
    if rec.rotation_deg is not None:
        extra.append(f"rot {rec.rotation_deg:.3f}°")
    return _result(
        size=package_size_mm(rec.name),
        source="yamaha_tou",
        extra=tuple(extra),
        partdesc=rec.comment,
        kind="Tou",
    )
