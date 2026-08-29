import os
import sys
import warnings

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pcb_preview.engine.identify import guess_layer_kind
from pcb_preview.gerber_io import load_gerber_svg
from pcb_preview.types import FootprintOutlineMM, PlacementRecord


def test_gerber_missing_file_returns_errors(tmp_path) -> None:
    missing = tmp_path / "missing.gbr"
    payload = load_gerber_svg(str(missing))
    assert not payload.svg
    assert payload.errors
    assert any("not found" in str(e).lower() for e in payload.errors)


def test_minimal_gerber_roundtrip(tmp_path) -> None:
    g = """G04 Test*
%FSLAX26Y26*%
%MOMM*%
%ADD10C,0.5*%
D10*
X0Y0D02*
X1000000Y0D01*
X1000000Y1000000D01*
X0Y1000000D01*
X0Y0D01*
M02*
"""
    p = tmp_path / "t.gbr"
    p.write_text(g, encoding="ascii")
    payload = load_gerber_svg(str(p))
    assert not payload.errors, payload.errors
    assert payload.backend_name == "pygerber"
    assert "svg" in payload.svg.lower() or payload.svg.startswith("<?xml")
    assert payload.bbox_mm.max_x > payload.bbox_mm.min_x


def test_cam350_silk_implicit_d01_does_not_fail() -> None:
    root = os.path.join(os.path.dirname(__file__), "..", "examples", "gerber_example3")
    path = os.path.join(root, "SILKSCREENTOP.art")
    if not os.path.isfile(path):
        pytest.skip("example Gerber not present")
    with warnings.catch_warnings():
        warnings.simplefilter("error", SyntaxWarning)
        payload = load_gerber_svg(path)
    assert payload.svg
    assert payload.backend_name == "gerbonara"
    assert payload.bbox_mm.width > 0 or payload.bbox_mm.height > 0


def test_label_scale_reverts() -> None:
    pytest.importorskip("PySide6")
    from PySide6 import QtWidgets

    from pcb_preview_tab import PlacementGroupItem

    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    pl = PlacementRecord(ref="R1", x_mm=0.0, y_mm=0.0, rotation_deg=0.0)
    item = PlacementGroupItem(pl, FootprintOutlineMM())
    item.set_label_scale(0.55)
    item.set_label_scale(0.12)
    t = item._label.transform()
    assert t.m11() == pytest.approx(0.12, rel=1e-6)
    assert t.m22() == pytest.approx(0.12, rel=1e-6)
    assert item._label.scale() == pytest.approx(1.0)


def test_guess_layer_kind_from_filename() -> None:
    assert guess_layer_kind("SILKSCREENTOP.art") == "silk"
    assert guess_layer_kind("board.GTO") == "silk"
    assert guess_layer_kind("PASTEMASKTOP.art") == "paste"
    assert guess_layer_kind("SOLDERMASKTOP.art") == "mask"
    assert guess_layer_kind("layer.GTL") == "copper"
    assert guess_layer_kind("PANEL.art") == "other"


def test_rasterize_gerber_svg_worker_image(tmp_path) -> None:
    pytest.importorskip("PySide6")
    from PySide6 import QtWidgets

    from pcb_preview_load_thread import rasterize_gerber_svg

    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    g = """G04 Test*
%FSLAX26Y26*%
%MOMM*%
%ADD10C,0.5*%
D10*
X0Y0D02*
X1000000Y0D01*
X1000000Y1000000D01*
X0Y1000000D01*
X0Y0D01*
M02*
"""
    p = tmp_path / "r.gbr"
    p.write_text(g, encoding="ascii")
    payload = load_gerber_svg(str(p))
    img, vb = rasterize_gerber_svg(payload.svg, px_per_mm=8.0)
    assert img is not None
    assert img.width() > 1 and img.height() > 1
def test_gerber_to_scene_mm_scale_matches_pnp_factors() -> None:
    from pcb_preview.gerber_io import gerber_to_scene_mm_scale

    s, _ = gerber_to_scene_mm_scale("mils", "inch")
    assert s == pytest.approx(0.0254)
    s, _ = gerber_to_scene_mm_scale("inch", "inch")
    assert s == pytest.approx(25.4)
    s, _ = gerber_to_scene_mm_scale("auto", "inch")
    assert s == pytest.approx(1.0)
    s, _ = gerber_to_scene_mm_scale("mm", "mm")
    assert s == pytest.approx(1.0)


def test_pygerber_keeps_manufacturing_origin(tmp_path) -> None:
    g = """G04 Test*
%FSLAX26Y26*%
%MOMM*%
%ADD10C,1.0*%
D10*
X5000000Y-3000000D03*
M02*
"""
    p = tmp_path / "off.gbr"
    p.write_text(g, encoding="ascii")
    payload = load_gerber_svg(str(p))
    assert payload.backend_name == "pygerber"
    assert payload.bbox_mm.min_x == pytest.approx(4.5, abs=0.05)
    assert payload.bbox_mm.min_y == pytest.approx(-3.5, abs=0.05)


def test_moin_backend_bbox_is_millimetres() -> None:
    path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "examples",
        "example9",
        "gerber",
        "PASTEMASKTOP.art",
    )
    if not os.path.isfile(path):
        pytest.skip("example9 Gerber not present")
    payload = load_gerber_svg(path)
    assert payload.svg
    # %MOIN*% file; gerbonara already converted — a ~280 mm panel, not ~11 inch.
    assert payload.bbox_mm.width > 50.0
    assert payload.bbox_mm.width < 2000.0
