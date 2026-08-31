"""
PCB preview core: Gerber via pygerber then gerbonara, PnP alignment math, footprint cache (heuristic + legacy DB).

No PySide6 or pandas in this package; GUI lives in `pcb_preview_tab.py`.
"""

from pcb_preview.alignment import Similarity2D, similarity_from_two_point_pairs
from pcb_preview.footprint_db import (
    FootprintStore,
    default_data_dir,
    normalize_footprint_key,
)
from pcb_preview.gerber_io import (
    gerber_to_scene_mm_scale,
    load_gerber_svg,
    peek_rs274x_linear_unit,
    scale_bbox_mm,
)
from pcb_preview.types import (
    BBoxMM,
    FootprintOutlineMM,
    GerberSvgPayload,
    PadRectMM,
    PlacementRecord,
    StrokeCircleMM,
    StrokeLineMM,
)

__all__ = [
    "Similarity2D",
    "similarity_from_two_point_pairs",
    "FootprintStore",
    "default_data_dir",
    "normalize_footprint_key",
    "load_gerber_svg",
    "peek_rs274x_linear_unit",
    "scale_bbox_mm",
    "gerber_to_scene_mm_scale",
    "BBoxMM",
    "FootprintOutlineMM",
    "GerberSvgPayload",
    "PadRectMM",
    "PlacementRecord",
    "StrokeCircleMM",
    "StrokeLineMM",
]
