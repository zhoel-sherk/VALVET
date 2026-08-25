"""Spec-oriented Gerber via pygerber (fails on many CAM350/Allegro .art files)."""

from __future__ import annotations

import warnings
from io import BytesIO
from pathlib import Path

from pcb_preview.engine.svg_bbox import bbox_from_svg_viewbox
from pcb_preview.types import BBoxMM, GerberSvgPayload


def load_via_pygerber(path: str) -> GerberSvgPayload:
    p = Path(path)
    if not p.is_file():
        return GerberSvgPayload(
            source_path=path,
            svg="",
            bbox_mm=BBoxMM(0.0, 0.0, 0.0, 0.0),
            errors=(f"Not a file: {path}",),
            backend_name="pygerber",
        )
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from pygerber.common.rgba import RGBA
            from pygerber.gerberx3.api.v2 import ColorScheme, GerberFile

            parsed = GerberFile.from_file(str(p)).parse()
            buf = BytesIO()
            bg = RGBA(r=0, g=0, b=0, a=0)
            fg = RGBA(r=255, g=255, b=255, a=255)
            scheme = ColorScheme(
                background_color=bg,
                clear_color=bg,
                solid_color=fg,
                clear_region_color=bg,
                solid_region_color=fg,
            )
            parsed.render_svg(buf, color_scheme=scheme)
            svg = buf.getvalue().decode("utf-8", errors="replace")
            info = parsed.get_info()
            info_bbox = BBoxMM(
                float(info.min_x_mm),
                float(info.min_y_mm),
                float(info.max_x_mm),
                float(info.max_y_mm),
            )
    except ImportError as e:
        return GerberSvgPayload(
            source_path=path,
            svg="",
            bbox_mm=BBoxMM(0.0, 0.0, 0.0, 0.0),
            errors=(f"pygerber is not installed: {e}",),
            backend_name="pygerber",
        )
    except Exception as e:
        return GerberSvgPayload(
            source_path=path,
            svg="",
            bbox_mm=BBoxMM(0.0, 0.0, 0.0, 0.0),
            errors=(f"pygerber: {e}",),
            backend_name="pygerber",
        )
    bbox = info_bbox
    if bbox.width <= 0 or bbox.height <= 0:
        bbox = bbox_from_svg_viewbox(svg) or bbox
    if not svg.strip():
        return GerberSvgPayload(
            source_path=path,
            svg="",
            bbox_mm=bbox,
            errors=("pygerber produced empty SVG",),
            backend_name="pygerber",
        )
    return GerberSvgPayload(
        source_path=path,
        svg=svg,
        bbox_mm=bbox,
        backend_name="pygerber",
    )
