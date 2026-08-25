"""Parse SVG viewBox to BBoxMM so pixmap pose matches gerbonara/pygerber output."""

from __future__ import annotations

import re

from pcb_preview.types import BBoxMM

_VIEWBOX = re.compile(
    r"viewBox\s*=\s*[\"']\s*([^\s\"']+)\s+([^\s\"']+)\s+([^\s\"']+)\s+([^\s\"']+)\s*[\"']",
    re.IGNORECASE,
)


def bbox_from_svg_viewbox(svg: str) -> BBoxMM | None:
    if not svg:
        return None
    m = _VIEWBOX.search(svg)
    if m is None:
        return None
    try:
        x, y, w, h = (float(m.group(i)) for i in range(1, 5))
    except (TypeError, ValueError):
        return None
    return BBoxMM(x, y, x + w, y + h)
