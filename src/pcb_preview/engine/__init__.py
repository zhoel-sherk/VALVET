"""Pluggable Gerber loaders: pygerber first, gerbonara fallback."""

from __future__ import annotations

from pcb_preview.engine.gerbonara_backend import load_via_gerbonara
from pcb_preview.engine.identify import (
    guess_layer_kind,
    layer_default_opacity,
    layer_default_rgb,
    layer_default_z,
)
from pcb_preview.engine.pygerber_backend import load_via_pygerber
from pcb_preview.types import GerberSvgPayload
import logger


def load_gerber_layer(path: str) -> GerberSvgPayload:
    """
    Try pygerber (X3/X2); on empty SVG fall back to gerbonara (CAM350 .art).
    """
    pyg = load_via_pygerber(path)
    if pyg.svg:
        return pyg
    gbn = load_via_gerbonara(path)
    if gbn.svg:
        pyg_err = "; ".join(str(e) for e in pyg.errors if e) or "empty SVG"
        logger.warning(
            "Gerber pygerber failed (%s); using gerbonara for %s",
            pyg_err,
            path,
        )
        return gbn
    errs = tuple(e for e in (pyg.errors + gbn.errors) if e)
    if not errs:
        errs = ("No Gerber backend produced SVG",)
    return GerberSvgPayload(
        source_path=path,
        svg="",
        bbox_mm=gbn.bbox_mm,
        errors=errs,
        backend_name=gbn.backend_name or pyg.backend_name or "",
    )


__all__ = [
    "load_gerber_layer",
    "load_via_gerbonara",
    "load_via_pygerber",
    "guess_layer_kind",
    "layer_default_opacity",
    "layer_default_rgb",
    "layer_default_z",
]
