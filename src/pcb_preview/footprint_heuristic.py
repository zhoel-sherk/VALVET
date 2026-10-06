"""Tier A: footprint silhouette from name tokens (no KiCad library)."""

from __future__ import annotations

import re
from typing import Optional

from pcb_preview.types import BBoxMM, FootprintOutlineMM, StrokeLineMM
from pcb_preview.upd_footprint_builder import chip_heuristic_pads

# Body size (mm) approximations for common SMD codes (length x width of rectangle).
_CHIP_MM: dict[str, tuple[float, float]] = {
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


def _find_imperial_code(name: str) -> Optional[str]:
    u = (name or "").upper().replace("_", "").replace("-", "").replace(" ", "")
    if not u:
        return None
    # Pick the code that starts earliest in the name, breaking ties by taking
    # the longer one. Scanning the codes in table order instead made the result
    # depend on dict insertion order, which has two consequences:
    #   - "x-2010-1210" resolved to 1210 although 2010 comes first in the name;
    #   - "C_1210_2010" resolved to 0201, a code that exists only as the four
    #     characters straddling the boundary between the two real codes.
    best: Optional[tuple[int, int, str]] = None
    for code in _CHIP_MM:
        idx = u.find(code)
        if idx < 0:
            continue
        candidate = (idx, -len(code), code)
        if best is None or candidate < best:
            best = candidate
    if best is not None:
        return best[2]
    m = re.search(r"\b(\d{4,5})\b", name or "")
    if m and m.group(1) in _CHIP_MM:
        return m.group(1)
    return None


def heuristic_footprint_outline(footprint_name: str) -> Optional[FootprintOutlineMM]:
    """
    Return a simple chip body + two pad hints if footprint name suggests imperial SMD size.
    Coordinates centered on origin (placement centroid at 0,0 in local space).
    """
    code = _find_imperial_code(footprint_name or "")
    if not code:
        return None
    L, W = _CHIP_MM[code]
    half_l, half_w = L / 2.0, W / 2.0
    lines = (
        StrokeLineMM(-half_l, -half_w, half_l, -half_w, 0.1),
        StrokeLineMM(half_l, -half_w, half_l, half_w, 0.1),
        StrokeLineMM(half_l, half_w, -half_l, half_w, 0.1),
        StrokeLineMM(-half_l, half_w, -half_l, -half_w, 0.1),
    )
    pads = chip_heuristic_pads(L, W)
    bbox = BBoxMM(-half_l, -half_w, half_l, half_w)
    return FootprintOutlineMM(lines=lines, pads=pads, bbox=bbox, source="heuristic")
