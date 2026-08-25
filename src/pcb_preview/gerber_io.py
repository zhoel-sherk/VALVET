"""
Gerber → SVG via pluggable backends (pygerber, then gerbonara).

KiCad GerbView / gerbv are GPL; do not link them in-process. GUI raster is in pcb_preview_tab.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from pcb_preview.engine import load_gerber_layer
from pcb_preview.types import BBoxMM, GerberSvgPayload

GerberUnitMode = Literal["auto", "mm", "mils", "inch"]
MIL_TO_MM = 0.0254
INCH_TO_MM = 25.4

_RS274_MOIN = re.compile(rb"%?MOIN\*?%?", re.IGNORECASE)
_RS274_MOMM = re.compile(rb"%?MOMM\*?%?", re.IGNORECASE)


def peek_rs274x_linear_unit(
    path: str, max_bytes: int = 262144
) -> Literal["inch", "mm", "unknown"]:
    """Best-effort scan of RS-274X header for %MOIN*% vs %MOMM*%."""
    p = Path(path)
    if not p.is_file():
        return "unknown"
    try:
        head = p.read_bytes()[:max_bytes]
    except OSError:
        return "unknown"
    if _RS274_MOMM.search(head):
        return "mm"
    if _RS274_MOIN.search(head):
        return "inch"
    return "unknown"


def gerber_to_scene_mm_scale(
    mode: GerberUnitMode,
    header: Literal["inch", "mm", "unknown"],
    *,
    backend_outputs_mm: bool = True,
) -> tuple[float, str]:
    """
    Map Gerber UI mode onto the shared scene millimetre grid (same as PnP).

    pygerber/gerbonara already emit millimetres; Auto is ×1. mils/inch are
    explicit overrides using the same factors as PnP (0.0254 / 25.4).
    """
    if mode == "mils":
        return MIL_TO_MM, "UI mils→mm ×0.0254"
    if mode == "inch":
        return INCH_TO_MM, "UI inch→mm ×25.4"
    if mode == "mm":
        return 1.0, "UI mm ×1"
    if backend_outputs_mm:
        return 1.0, f"Auto header={header!r}; backend mm ×1"
    if header == "inch":
        return INCH_TO_MM, "Auto %MOIN*% → mm ×25.4"
    return 1.0, f"Auto header={header!r} ×1"


def scale_bbox_mm(bb: BBoxMM, factor: float) -> BBoxMM:
    if factor == 1.0:
        return bb
    return BBoxMM(
        bb.min_x * factor, bb.min_y * factor, bb.max_x * factor, bb.max_y * factor
    )


def load_gerber_svg(path: str) -> GerberSvgPayload:
    """Read one Gerber file; pygerber then gerbonara. Empty svg + errors on failure."""
    return load_gerber_layer(path)
