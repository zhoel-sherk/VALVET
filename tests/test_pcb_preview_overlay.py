"""PCB Preview overlay: no auto-draw, side filter, centroid, outline defaults."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from pcb_preview.engine.identify import layer_default_rgb
from pcb_preview.outline_resolve import footprint_name_keys, resolve_named_outlines
from pcb_preview.types import BBoxMM, FootprintOutlineMM, PlacementRecord


def test_layer_default_rgb_yellowish() -> None:
    assert layer_default_rgb("copper") == (218, 176, 72)
    assert layer_default_rgb("other") == (218, 176, 72)


def test_resolve_named_outlines_unique_vspd() -> None:
    out = resolve_named_outlines(["CHIP-0402", "Chip-R1005(0402)", "mystery-xyz"])
    a = out["CHIP-0402"]
    b = out["Chip-R1005(0402)"]
    assert a.source != "none"
    assert a is b
    assert out["mystery-xyz"].source == "none"


def test_footprint_name_keys_path_and_kicad() -> None:
    path_keys = footprint_name_keys(r"lib\CHIP-0402")
    assert path_keys[0] == r"lib\CHIP-0402"
    assert "CHIP-0402" in path_keys
    lib_keys = footprint_name_keys("Resistor_SMD:CHIP-0402")
    assert "Resistor_SMD:CHIP-0402" in lib_keys
    assert "CHIP-0402" in lib_keys


def test_resolve_named_outlines_path_and_lib_alias() -> None:
    out = resolve_named_outlines(["foo/bar/CHIP-0402"])
    body = out["foo/bar/CHIP-0402"]
    assert body.source != "none"
    assert out["CHIP-0402"] is body
    lib = resolve_named_outlines(["Lib:CHIP-0402"])
    assert lib["Lib:CHIP-0402"].source != "none"
    assert lib["CHIP-0402"] is lib["Lib:CHIP-0402"]
    assert lib["CHIP-0402"].source == body.source


def _qapp():
    pytest.importorskip("PySide6")
    from PySide6 import QtWidgets

    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def _tab(tmp_path: Path):
    from PySide6 import QtCore

    from pcb_preview_tab import PcbPreviewTab

    settings = QtCore.QSettings(
        str(tmp_path / "pcb.ini"), QtCore.QSettings.Format.IniFormat
    )
    return PcbPreviewTab(settings=settings)


def test_no_placements_until_show_and_outline_default_off(tmp_path: Path) -> None:
    _qapp()
    tab = _tab(tmp_path)
    try:
        assert tab._items == {}
        assert tab._show_footprints is False
        assert tab._chk_show_footprints.isChecked() is False
        assert tab._chk_show_top.isChecked() is True
        assert tab._chk_show_bot.isChecked() is True
        df = pd.DataFrame(
            {
                "REF": ["U1"],
                "X": [1.0],
                "Y": [2.0],
                "Layer": ["TOP"],
                "Footprint": ["CHIP-0402"],
            }
        )
        tab.set_placements_from_dataframe(
            df,
            force=True,
            designator_col="REF",
            x_col="X",
            y_col="Y",
            rot_col=None,
            layer_col="Layer",
            footprint_col="Footprint",
            coord_unit_mm=True,
        )
        assert "U1" in tab._items
        assert tab._items["U1"].path_item().isVisible() is False
    finally:
        tab.close()


def test_stale_outline_epoch_ignored(tmp_path: Path) -> None:
    _qapp()
    tab = _tab(tmp_path)
    try:
        df = pd.DataFrame(
            {
                "REF": ["U1"],
                "X": [1.0],
                "Y": [2.0],
                "Footprint": ["CHIP-0402"],
            }
        )
        tab.set_placements_from_dataframe(
            df,
            force=True,
            designator_col="REF",
            x_col="X",
            y_col="Y",
            rot_col=None,
            footprint_col="Footprint",
            coord_unit_mm=True,
        )
        tab._outline_cache.clear()
        stale = FootprintOutlineMM(source="heuristic")
        tab._on_outlines_ready((tab._outline_epoch - 1, {"CHIP-0402": stale}))
        assert "CHIP-0402" not in tab._outline_cache
        tab._on_outlines_ready((tab._outline_epoch, {"CHIP-0402": stale}))
        assert tab._outline_cache["CHIP-0402"] is stale
        tab.append_log("ok")
    finally:
        tab.close()


def test_side_filter_hides_bottom(tmp_path: Path) -> None:
    _qapp()
    tab = _tab(tmp_path)
    try:
        df = pd.DataFrame(
            {
                "REF": ["T1", "B1", "U0"],
                "X": [0.0, 1.0, 2.0],
                "Y": [0.0, 0.0, 0.0],
                "Layer": ["TOP", "BOT", ""],
            }
        )
        tab.set_placements_from_dataframe(
            df,
            force=True,
            designator_col="REF",
            x_col="X",
            y_col="Y",
            rot_col=None,
            layer_col="Layer",
            coord_unit_mm=True,
        )
        assert tab._items["T1"].isVisible()
        assert tab._items["B1"].isVisible()
        assert tab._items["U0"].isVisible()
        tab._chk_show_bot.setChecked(False)
        assert tab._items["T1"].isVisible()
        assert not tab._items["B1"].isVisible()
        assert tab._items["U0"].isVisible()
        tab._chk_show_top.setChecked(False)
        assert not tab._items["T1"].isVisible()
        assert not tab._items["U0"].isVisible()
    finally:
        tab.close()


def test_side_filter_m_is_bottom_empty_is_top(tmp_path: Path) -> None:
    _qapp()
    tab = _tab(tmp_path)
    try:
        df = pd.DataFrame(
            {
                "REF": ["T1", "B1", "U0"],
                "X": [0.0, 1.0, 2.0],
                "Y": [0.0, 0.0, 0.0],
                "Layer": ["t", "m", ""],
            }
        )
        tab.set_placements_from_dataframe(
            df,
            force=True,
            designator_col="REF",
            x_col="X",
            y_col="Y",
            rot_col=None,
            layer_col="Layer",
            coord_unit_mm=True,
        )
        assert tab._items["T1"]._placement.side == "top"
        assert tab._items["B1"]._placement.side == "bottom"
        assert tab._items["U0"]._placement.side == "top"
        tab._chk_show_bot.setChecked(False)
        assert tab._items["T1"].isVisible()
        assert not tab._items["B1"].isVisible()
        assert tab._items["U0"].isVisible()
        tab._chk_show_bot.setChecked(True)
        tab._chk_show_top.setChecked(False)
        assert not tab._items["T1"].isVisible()
        assert tab._items["B1"].isVisible()
        assert not tab._items["U0"].isVisible()
    finally:
        tab.close()


def test_centroid_translates_overlay(tmp_path: Path) -> None:
    _qapp()
    from PySide6 import QtGui, QtWidgets

    from pcb_preview_tab import _GerberLayerRow

    tab = _tab(tmp_path)
    try:
        df = pd.DataFrame(
            {
                "REF": ["A", "B"],
                "X": [0.0, 10.0],
                "Y": [0.0, 0.0],
            }
        )
        tab.set_placements_from_dataframe(
            df,
            force=True,
            designator_col="REF",
            x_col="X",
            y_col="Y",
            rot_col=None,
            coord_unit_mm=True,
        )
        pm = QtGui.QPixmap(100, 100)
        pm.fill(QtGui.QColor(218, 176, 72))
        item = QtWidgets.QGraphicsPixmapItem(pm)
        tab._scene.addItem(item)
        bb = BBoxMM(0.0, 0.0, 100.0, 100.0)
        tab._layers.append(
            _GerberLayerRow(
                path="dummy.gbr",
                display_name="dummy",
                pixmap_item=item,
                bbox_mm=bb,
                native_bbox_mm=bb,
                s_raster=1.0,
            )
        )
        tab._align_centroids_coarse()
        assert tab._preview_sim.tx == pytest.approx(45.0)
        assert tab._preview_sim.ty == pytest.approx(50.0)
        assert tab._preview_sim.scale == pytest.approx(1.0)
    finally:
        tab.close()


def test_lang_pcb_overlay_keys() -> None:
    import json

    keys = (
        "pcb.show_from_pnp",
        "pcb.show_from_merge",
        "pcb.centroid",
        "pcb.layer_top",
        "pcb.layer_bot",
        "pcb.show_footprints",
        "pcb.overlay",
        "pcb.show_circles",
        "pcb.show_crosses",
        "pcb.centroid_radius",
        "pcb.cross_size",
        "pcb.mdb_fallback",
        "pcb.gerber_units_help_title",
        "pcb.gerber_units_help_body",
    )
    root = Path(__file__).resolve().parents[1] / "lang"
    for path in root.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        for k in keys:
            assert k in data, f"{path.name} missing {k}"


def test_placement_record_side_unknown_allowed() -> None:
    pl = PlacementRecord(ref="X", x_mm=0.0, y_mm=0.0, rotation_deg=0.0, side="unknown")
    assert pl.side == "unknown"


def test_overlay_group_between_gerber_and_pnp(tmp_path: Path) -> None:
    _qapp()
    tab = _tab(tmp_path)
    try:
        grid = tab._pcb_settings_panel.layout()
        assert grid.itemAtPosition(0, 0).widget() is tab._grp_gunit
        assert grid.itemAtPosition(0, 1).widget() is tab._grp_overlay
        assert tab._btn_gunit_help.text() == "?"
        assert tab._chk_show_circles.isChecked() is True
        assert tab._chk_show_crosses.isChecked() is True
        assert tab._chk_mdb_fallback.isChecked() is False
        assert tab._spin_centroid_r.value() == pytest.approx(0.45)
        assert tab._spin_cross_h.value() == pytest.approx(0.9)
    finally:
        tab.close()


def test_circles_and_crosses_toggle(tmp_path: Path) -> None:
    _qapp()
    tab = _tab(tmp_path)
    try:
        df = pd.DataFrame({"REF": ["U1"], "X": [1.0], "Y": [2.0]})
        tab.set_placements_from_dataframe(
            df,
            force=True,
            designator_col="REF",
            x_col="X",
            y_col="Y",
            rot_col=None,
            coord_unit_mm=True,
        )
        item = tab._items["U1"]
        assert item._dot.isVisible()
        assert item._cross1.isVisible()
        tab._chk_show_circles.setChecked(False)
        tab._chk_show_crosses.setChecked(False)
        assert not item._dot.isVisible()
        assert not item._cross1.isVisible()
        tab._spin_centroid_r.setValue(0.8)
        assert item._centroid_r == pytest.approx(0.8)
    finally:
        tab.close()


def test_export_apply_overlay_prefs_roundtrip(tmp_path: Path) -> None:
    _qapp()
    tab = _tab(tmp_path)
    try:
        tab._chk_show_circles.setChecked(False)
        tab._chk_show_crosses.setChecked(False)
        tab._chk_mdb_fallback.setChecked(True)
        tab._spin_centroid_r.setValue(0.7)
        tab._spin_cross_h.setValue(1.5)
        prefs = tab.export_ui_prefs()
        assert prefs["show_circles"] is False
        assert prefs["mdb_fallback"] is True
        tab._chk_show_circles.setChecked(True)
        tab._chk_mdb_fallback.setChecked(False)
        tab._spin_centroid_r.setValue(0.45)
        tab.apply_ui_prefs(prefs)
        assert tab._show_circles is False
        assert tab._show_crosses is False
        assert tab._mdb_fallback is True
        assert tab._centroid_radius == pytest.approx(0.7)
        assert tab._cross_half == pytest.approx(1.5)
    finally:
        tab.close()


def test_resolve_mdb_fallback_logs_info(mocker: pytest.MockFixture) -> None:
    import logger
    from pcb_preview.types import BBoxMM, StrokeLineMM

    fake = FootprintOutlineMM(
        lines=(StrokeLineMM(0.0, 0.0, 1.0, 0.0),),
        bbox=BBoxMM(0.0, 0.0, 1.0, 0.0),
        source="hanwha_upd",
    )

    class _Built:
        error = ""
        outline = fake

    class _SqlitePath:
        def is_file(self) -> bool:
            return True

    mocker.patch(
        "machine_library.hanwha_sqlite_cache.sqlite_path",
        return_value=_SqlitePath(),
    )
    mocker.patch(
        "machine_library.hanwha_sqlite_cache.build_outline_from_sqlite",
        return_value=_Built(),
    )
    info_spy = mocker.spy(logger, "info")
    out = resolve_named_outlines(
        ["mystery-xyz"],
        mdb_cache_dir="C:/fake-hanwha-cache",
    )
    assert out["mystery-xyz"].source == "hanwha_upd"
    assert info_spy.called
    msg = str(info_spy.call_args.args[0]).lower()
    assert "vspd" in msg
    assert "hanwha" in msg


def test_resolve_mdb_fallback_missing_cache_logs_warning(
    mocker: pytest.MockFixture,
) -> None:
    import logger

    class _SqlitePath:
        def is_file(self) -> bool:
            return False

    mocker.patch(
        "machine_library.hanwha_sqlite_cache.sqlite_path",
        return_value=_SqlitePath(),
    )
    warn_spy = mocker.spy(logger, "warning")
    out = resolve_named_outlines(
        ["mystery-xyz"],
        mdb_cache_dir="C:/missing-cache",
    )
    assert out["mystery-xyz"].source == "none"
    assert warn_spy.called
    msg = str(warn_spy.call_args.args[0]).lower()
    assert "vspd" in msg
    assert "sqlite" in msg or "hanwha" in msg
