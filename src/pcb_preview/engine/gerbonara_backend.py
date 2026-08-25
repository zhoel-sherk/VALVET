"""CAM toolkit backend; implicit D01 patch for CAM350/Allegro .art."""

from __future__ import annotations

import warnings
from pathlib import Path

from pcb_preview.engine.svg_bbox import bbox_from_svg_viewbox
from pcb_preview.types import BBoxMM, GerberSvgPayload

_GERBONARA_IMPLICIT_PATCHED = False


def _relax_gerbonara_implicit_coords() -> None:
    global _GERBONARA_IMPLICIT_PATCHED
    if _GERBONARA_IMPLICIT_PATCHED:
        return
    try:
        from gerbonara.rs274x import GerberParser  # type: ignore[import-untyped]
    except ImportError:
        return
    orig = GerberParser._parse_coord

    def _parse_coord(self, match):  # type: ignore[no-untyped-def]
        interp, x_s, x, y_s, y, i_s, i, j_s, j, op = match.groups()
        has_coord = x or y or i or j
        if (not op) and has_coord and self.last_operation not in ("1",):
            self.last_operation = "1"
        return orig(self, match)

    GerberParser._parse_coord = _parse_coord
    _GERBONARA_IMPLICIT_PATCHED = True


def load_via_gerbonara(path: str) -> GerberSvgPayload:
    p = Path(path)
    if not p.is_file():
        return GerberSvgPayload(
            source_path=path,
            svg="",
            bbox_mm=BBoxMM(0.0, 0.0, 0.0, 0.0),
            errors=(f"Not a file: {path}",),
            backend_name="gerbonara",
        )
    try:
        from gerbonara import GerberFile  # type: ignore[import-untyped]
    except ImportError as e:
        return GerberSvgPayload(
            source_path=path,
            svg="",
            bbox_mm=BBoxMM(0.0, 0.0, 0.0, 0.0),
            errors=(f"gerbonara not installed: {e}",),
            backend_name="gerbonara",
        )
    _relax_gerbonara_implicit_coords()
    notes: list[str] = []
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", SyntaxWarning)
            warnings.simplefilter("always", DeprecationWarning)
            gbr = GerberFile.open(str(p))
        n_syntax = sum(
            1
            for w in caught
            if issubclass(w.category, SyntaxWarning)
            and "operation" in str(w.message).lower()
        )
        if n_syntax:
            notes.append(
                f"Gerber uses implicit D01 coordinates ({n_syntax} times; "
                "common in CAM350/Allegro .art). Parsed anyway."
            )
    except Exception as e:
        return GerberSvgPayload(
            source_path=path,
            svg="",
            bbox_mm=BBoxMM(0.0, 0.0, 0.0, 0.0),
            errors=(f"Gerber open failed: {e}",),
            backend_name="gerbonara",
        )
    try:
        bb = gbr.bounding_box()
        (x0, y0), (x1, y1) = bb
        bbox = BBoxMM(float(x0), float(y0), float(x1), float(y1))
        svg = str(gbr.to_svg())
    except Exception as e:
        notes.append(f"Gerber SVG/bbox failed: {e}")
        return GerberSvgPayload(
            source_path=path,
            svg="",
            bbox_mm=BBoxMM(0.0, 0.0, 0.0, 0.0),
            errors=tuple(notes),
            backend_name="gerbonara",
        )
    vb = bbox_from_svg_viewbox(svg)
    if vb is not None:
        bbox = vb
    return GerberSvgPayload(
        source_path=path,
        svg=svg,
        bbox_mm=bbox,
        errors=tuple(notes),
        backend_name="gerbonara",
    )
