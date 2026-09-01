"""Golden geometry from doc/info/UPD_MDB_Footprint_Geometry_Report.md (no Access)."""

from __future__ import annotations

import pytest

import pcb_preview.upd_footprint_builder as upd_fp


def test_um_to_mm() -> None:
    assert upd_fp.um_to_mm(1000) == 1.0
    assert upd_fp.um_to_mm(500) == 0.5


def test_chip_0402_body() -> None:
    snap = upd_fp.UpdProfileSnapshot(
        profilename="_NewR0402",
        vision_type=3,
        partgroup_name="Chip-R0402",
        size_x_um=400,
        size_y_um=200,
        size_z_um=200,
        chip_whole={"TYPSIZEX": 400, "TYPSIZEY": 200},
    )
    r = upd_fp.build_from_snapshot(snap)
    assert r.error == ""
    assert r.outline.source == "hanwha_upd"
    assert len(r.outline.lines) == 4
    assert r.outline.bbox.width == 0.4
    assert r.outline.bbox.height == 0.2
    assert len(r.outline.pads) == 2
    assert any("heuristic" in w for w in r.warnings)
    assert r.polarity == "none"
    assert r.pin1_kind == "none"


def test_chip_circle_body_not_rect() -> None:
    snap = upd_fp.UpdProfileSnapshot(
        profilename="_NewCircle",
        vision_type=3,
        partgroup_name="CHIP-Circle",
        size_x_um=3000,
        size_y_um=3000,
        size_z_um=500,
        chip_whole={"TYPSIZEX": 3000, "TYPSIZEY": 3000},
    )
    r = upd_fp.build_from_snapshot(snap)
    assert r.error == ""
    assert r.outline.lines == ()
    assert r.outline.pads == ()
    assert len(r.outline.circles) == 1
    assert r.outline.circles[0].radius_mm == pytest.approx(1.5)
    assert any("circle" in w.lower() for w in r.warnings)
    assert not upd_fp.is_chip_circle("Chip-C3216(1206)")
    assert upd_fp.is_chip_circle("CHIP-Circle")


def test_chip_heuristic_pads_scale() -> None:
    p0805 = upd_fp.chip_heuristic_pads(2.0, 1.25)
    assert len(p0805) == 2
    assert p0805[0].width_mm == pytest.approx(0.76)
    assert p0805[0].height_mm == pytest.approx(1.25)
    p0402 = upd_fp.chip_heuristic_pads(0.4, 0.2)
    assert p0402[0].width_mm == pytest.approx(0.152)
    p1812 = upd_fp.chip_heuristic_pads(4.171, 3.078)
    assert p1812[0].width_mm > 1.4
    assert p1812[0].width_mm < 2.0
    assert p1812[0].height_mm == pytest.approx(3.078)


def test_sot23_tr2_three_pads() -> None:
    snap = upd_fp.UpdProfileSnapshot(
        profilename="AP2318GEN",
        vision_type=3,
        partgroup_name="TR2",
        partdesc="SOT23",
        size_x_um=2400,
        size_y_um=2800,
        chip_whole={
            "TYPSIZEX": 2400,
            "TYPSIZEY": 2800,
            "EXPARAM11": 450,
            "EXPARAM12": 450,
            "EXPARAM13": 600,
            "EXPARAM14": 600,
            "EXPARAM15": 1,
            "EXPARAM16": 2,
            "EXPARAM18": 0,
            "EXPARAM19": 1900,
        },
    )
    r = upd_fp.build_from_snapshot(snap)
    assert r.error == ""
    assert len(r.outline.pads) == 3
    assert all(isinstance(p.cx, float) for p in r.outline.pads)
    assert any("chip lead slots" in w for w in r.warnings)
    assert r.polarity == "yes"
    assert r.pin1_kind == "lead1"
    assert len(upd_fp.sot23_heuristic_pads(2.4, 2.8)) == 3


def test_sod923_tr2_two_pads_not_sot23() -> None:
    snap = upd_fp.UpdProfileSnapshot(
        profilename="RB521CS_30",
        vision_type=3,
        partgroup_name="TR2",
        partdesc="SOD923-25-CDZ6",
        chip_whole={
            "TYPSIZEX": 1100,
            "TYPSIZEY": 550,
            "EXPARAM11": 200,
            "EXPARAM12": 200,
            "EXPARAM13": 150,
            "EXPARAM14": 150,
            "EXPARAM15": 1,
            "EXPARAM16": 1,
            "EXPARAM18": 0,
            "EXPARAM19": 0,
        },
    )
    r = upd_fp.build_from_snapshot(snap)
    assert len(r.outline.pads) == 2
    assert any("chip lead slots" in w for w in r.warnings)
    assert not any("SOT-23" in w for w in r.warnings)
    assert r.polarity == "yes"
    xs = sorted(p.cx for p in r.outline.pads)
    assert xs[0] < 0 < xs[1]


def test_tr_sot223_tab_and_three_leads() -> None:
    snap = upd_fp.UpdProfileSnapshot(
        profilename="SOT223",
        vision_type=3,
        partgroup_name="TR",
        partdesc="SOT-223",
        chip_whole={
            "TYPSIZEX": 8300,
            "TYPSIZEY": 10000,
            "EXPARAM11": 10000,
            "EXPARAM12": 1000,
            "EXPARAM13": 1200,
            "EXPARAM14": 1900,
            "EXPARAM15": 1,
            "EXPARAM16": 3,
            "EXPARAM18": 0,
            "EXPARAM19": 5100,
        },
    )
    r = upd_fp.build_from_snapshot(snap)
    assert len(r.outline.pads) == 4
    assert any("chip lead slots" in w for w in r.warnings)
    left = [p for p in r.outline.pads if p.cx < 0]
    right = [p for p in r.outline.pads if p.cx > 0]
    assert len(left) == 1
    assert len(right) == 3
    assert left[0].height_mm == pytest.approx(10.0)


def test_tr_small_sop_span_not_adjacent_pitch() -> None:
    """EXPARAM18=3.85 mm is first-to-last span for 4 leads, not 3.85 mm pitch."""
    snap = upd_fp.UpdProfileSnapshot(
        profilename="_NewSmallSOP",
        vision_type=3,
        partgroup_name="TR",
        chip_whole={
            "TYPSIZEX": 5000,
            "TYPSIZEY": 6000,
            "EXPARAM11": 400,
            "EXPARAM12": 400,
            "EXPARAM13": 450,
            "EXPARAM14": 450,
            "EXPARAM15": 4,
            "EXPARAM16": 4,
            "EXPARAM18": 3850,
            "EXPARAM19": 3850,
        },
    )
    r = upd_fp.build_from_snapshot(snap)
    assert len(r.outline.pads) == 8
    ys = sorted({round(p.cy, 4) for p in r.outline.pads})
    assert len(ys) == 4
    assert max(ys) - min(ys) == pytest.approx(3.85, abs=0.05)


def test_sot23_6_six_pads_from_exparam() -> None:
    snap = upd_fp.UpdProfileSnapshot(
        profilename="CS0816",
        vision_type=3,
        partgroup_name="TR2",
        partdesc="SOT-23-6",
        chip_whole={
            "TYPSIZEX": 2800,
            "TYPSIZEY": 2800,
            "EXPARAM11": 400,
            "EXPARAM12": 400,
            "EXPARAM13": 700,
            "EXPARAM14": 700,
            "EXPARAM15": 3,
            "EXPARAM16": 3,
            "EXPARAM18": 1900,
            "EXPARAM19": 1900,
        },
    )
    r = upd_fp.build_from_snapshot(snap)
    assert len(r.outline.pads) == 6


def test_tr2_without_sot23_name_two_pads() -> None:
    snap = upd_fp.UpdProfileSnapshot(
        profilename="IRLML6402",
        vision_type=3,
        partgroup_name="TR2",
        partdesc="",
        chip_whole={"TYPSIZEX": 2400, "TYPSIZEY": 2100},
    )
    r = upd_fp.build_from_snapshot(snap)
    assert len(r.outline.pads) == 2


def test_sot23_from_partdesc_not_chip_r() -> None:
    snap = upd_fp.UpdProfileSnapshot(
        profilename="foo",
        vision_type=3,
        partgroup_name="Chip-R0402",
        partdesc="resistor",
        chip_whole={"TYPSIZEX": 400, "TYPSIZEY": 200},
    )
    r = upd_fp.build_from_snapshot(snap)
    assert len(r.outline.pads) == 2

    snap2 = upd_fp.UpdProfileSnapshot(
        profilename="x",
        vision_type=3,
        partgroup_name="Chip",
        partdesc="SOT-23-3",
        chip_whole={"TYPSIZEX": 2400, "TYPSIZEY": 2800},
    )
    r2 = upd_fp.build_from_snapshot(snap2)
    assert len(r2.outline.pads) == 3


def test_soic_ll_two_sides() -> None:
    snap = upd_fp.UpdProfileSnapshot(
        profilename="AT45DB161E-SSHF-T",
        vision_type=1,
        partgroup_name="SOP",
        size_x_um=4900,
        size_y_um=6100,
        size_z_um=1400,
        ll_whole={
            "TYPSIZEX": 4900,
            "TYPSIZEY": 3900,
            "LEADTYPE": 0,
            "LEADGROUPNUM": 2,
            "LEADPARAMNUM": 1,
        },
        ll_groups=(
            {
                "INDEX": 0,
                "ANGLE": 3,
                "RADCENTER": 2500,
                "TANCENTER": 0,
                "LEADNUM": 4,
                "LEADPARAMNO": 0,
            },
            {
                "INDEX": 1,
                "ANGLE": 1,
                "RADCENTER": 2500,
                "TANCENTER": 0,
                "LEADNUM": 4,
                "LEADPARAMNO": 0,
            },
        ),
        ll_params=(
            {
                "INDEX": 0,
                "TYPWIDTH": 400,
                "TYPLENGTH": 1100,
                "TYPPITCH": 1270,
                "TYPFOOT": 500,
            },
        ),
    )
    r = upd_fp.build_from_snapshot(snap)
    assert r.error == ""
    assert len(r.outline.pads) == 8
    xs = [p.cx for p in r.outline.pads]
    assert min(xs) < 0 < max(xs)
    assert r.size_z_mm == 1.4
    assert r.polarity == "yes"
    assert r.pin1_kind == "lead1"


def test_qfp48_four_sides() -> None:
    groups = []
    for i, ang in enumerate((0, 3, 2, 1)):
        groups.append(
            {
                "INDEX": i,
                "ANGLE": ang,
                "RADCENTER": 4000,
                "TANCENTER": 0,
                "LEADNUM": 12,
                "LEADPARAMNO": 0,
            }
        )
    snap = upd_fp.UpdProfileSnapshot(
        profilename="QFP-48",
        vision_type=1,
        partgroup_name="QFP",
        size_x_um=9000,
        size_y_um=9000,
        size_z_um=1400,
        ll_whole={"TYPSIZEX": 7000, "TYPSIZEY": 7000, "LEADGROUPNUM": 4},
        ll_groups=tuple(groups),
        ll_params=(
            {
                "INDEX": 0,
                "TYPWIDTH": 200,
                "TYPLENGTH": 1000,
                "TYPPITCH": 500,
                "TYPFOOT": 400,
            },
        ),
    )
    r = upd_fp.build_from_snapshot(snap)
    assert r.error == ""
    assert len(r.outline.pads) == 48
    assert r.outline.bbox.width >= 7.0


def test_user_ic_asymmetric_leads() -> None:
    snap = upd_fp.UpdProfileSnapshot(
        profilename="_NewUserIC",
        vision_type=1,
        partgroup_name="User IC",
        size_x_um=9800,
        size_y_um=5600,
        size_z_um=6000,
        ll_whole={"TYPSIZEX": 9800, "TYPSIZEY": 5000, "LEADGROUPNUM": 4},
        ll_groups=(
            {
                "INDEX": 0,
                "ANGLE": 3,
                "RADCENTER": 2380,
                "TANCENTER": -2450,
                "LEADNUM": 2,
                "LEADPARAMNO": 1,
            },
            {
                "INDEX": 1,
                "ANGLE": 1,
                "RADCENTER": 2380,
                "TANCENTER": -2450,
                "LEADNUM": 3,
                "LEADPARAMNO": 0,
            },
            {
                "INDEX": 2,
                "ANGLE": 1,
                "RADCENTER": 2380,
                "TANCENTER": 2450,
                "LEADNUM": 3,
                "LEADPARAMNO": 0,
            },
            {
                "INDEX": 3,
                "ANGLE": 3,
                "RADCENTER": 2380,
                "TANCENTER": 2450,
                "LEADNUM": 2,
                "LEADPARAMNO": 1,
            },
        ),
        ll_params=(
            {
                "INDEX": 0,
                "TYPWIDTH": 350,
                "TYPLENGTH": 1300,
                "TYPPITCH": 1650,
                "TYPFOOT": 600,
            },
            {
                "INDEX": 1,
                "TYPWIDTH": 350,
                "TYPLENGTH": 1250,
                "TYPPITCH": 3300,
                "TYPFOOT": 600,
            },
        ),
    )
    r = upd_fp.build_from_snapshot(snap)
    assert r.error == ""
    assert len(r.outline.pads) == 10
    assert r.size_z_mm == 6.0
    assert any("rotated 90" in w for w in r.warnings)
    xs = [p.cx for p in r.outline.pads]
    ys = [p.cy for p in r.outline.pads]
    assert max(xs) - min(xs) > max(ys) - min(ys)
    assert max(abs(y) for y in ys) < 3.2
    assert max(abs(x) for x in xs) > 3.0


def test_bga_grid() -> None:
    snap = upd_fp.UpdProfileSnapshot(
        profilename="_NewBGA",
        vision_type=2,
        partgroup_name="BGA",
        size_x_um=27000,
        size_y_um=27000,
        size_z_um=2120,
        bga_whole={"TYPSIZEX": 27000, "TYPSIZEY": 27000, "APPEARBALLSIZE": 500},
        bga_params=(
            {
                "INDEX": 0,
                "TYPBALLDIA": 800,
                "TYPBALLPITCHR": 1270,
                "TYPBALLPITCHT": 1270,
            },
        ),
        bga_groups=(
            {
                "INDEX": 0,
                "PARAMINDEX": 0,
                "NUMBALLSR": 20,
                "NUMBALLST": 20,
                "NUMMISSING": 4,
            },
        ),
        bga_gaps=(
            {
                "INDEX": 0,
                "MISSBLOCKR": 0,
                "MISSBLOCKT": 0,
                "NUMMISSINGR": 1,
                "NUMMISSINGT": 1,
            },
        ),
    )
    r = upd_fp.build_from_snapshot(snap)
    assert r.error == ""
    assert len(r.outline.circles) == 399


def test_ps7101_bga_grid_follows_body_xy() -> None:
    """NUMBALLSR=11 along X (8 mm), NUMBALLST=7 along Y (5 mm) — not swapped."""
    snap = upd_fp.UpdProfileSnapshot(
        profilename="PS7101-51",
        vision_type=2,
        partgroup_name="BGA",
        size_x_um=8000,
        size_y_um=5000,
        bga_whole={"TYPSIZEX": 8000, "TYPSIZEY": 5000, "APPEARBALLSIZE": 500},
        bga_params=(
            {
                "INDEX": 0,
                "TYPBALLDIA": 350,
                "TYPBALLPITCHR": 650,
                "TYPBALLPITCHT": 650,
            },
        ),
        bga_groups=(
            {
                "INDEX": 0,
                "PARAMINDEX": 0,
                "NUMBALLSR": 11,
                "NUMBALLST": 7,
                "GRIDANGLE": 0,
            },
        ),
    )
    r = upd_fp.build_from_snapshot(snap)
    assert r.error == ""
    assert len(r.outline.circles) == 77
    xs = [c.cx for c in r.outline.circles]
    ys = [c.cy for c in r.outline.circles]
    assert max(xs) - min(xs) > max(ys) - min(ys)
    assert max(xs) - min(xs) == pytest.approx(6.5)
    assert max(ys) - min(ys) == pytest.approx(3.9)
    assert max(abs(x) for x in xs) < 4.0
    assert max(abs(y) for y in ys) < 2.6


def test_polygon_contours() -> None:
    verts = (
        {
            "INDEX": 0,
            "VERTEXPOINTX": -7335,
            "VERTEXPOINTY": 8180,
            "CONTROLBIT": 0,
        },
        {
            "INDEX": 1,
            "VERTEXPOINTX": -4335,
            "VERTEXPOINTY": 8180,
            "CONTROLBIT": 5,
        },
        {
            "INDEX": 2,
            "VERTEXPOINTX": -4335,
            "VERTEXPOINTY": 5180,
            "CONTROLBIT": 5,
        },
        {
            "INDEX": 3,
            "VERTEXPOINTX": -7335,
            "VERTEXPOINTY": 5180,
            "CONTROLBIT": 5,
        },
    )
    snap = upd_fp.UpdProfileSnapshot(
        profilename="_NewShieldCan",
        vision_type=6,
        partgroup_name="Polygon",
        poly_whole={"VERTEXNUM": 4, "BODYSIZEX": 18000, "BODYSIZEY": 18000},
        poly_verts=verts,
    )
    r = upd_fp.build_from_snapshot(snap)
    assert r.error == ""
    assert len(r.outline.lines) >= 3
    assert r.outline.pads == ()


def test_flipchip_balls() -> None:
    snap = upd_fp.UpdProfileSnapshot(
        profilename="_NewFlipChip",
        vision_type=5,
        partgroup_name="Flip Chip",
        size_x_um=5000,
        size_y_um=5000,
        flip_whole={"TYPSIZEX": 5000, "TYPSIZEY": 5000},
        flip_params=({"INDEX": 0, "TYPBALLDIA": 300},),
        flip_balls=(
            {"POSITIONX": -1000, "POSITIONY": 0},
            {"POSITIONX": 1000, "POSITIONY": 0},
        ),
    )
    r = upd_fp.build_from_snapshot(snap)
    assert r.error == ""
    assert len(r.outline.circles) == 2
    assert r.outline.circles[0].radius_mm == 0.15


def test_ll_gap_skips_leads() -> None:
    snap = upd_fp.UpdProfileSnapshot(
        profilename="gap",
        vision_type=1,
        ll_whole={"TYPSIZEX": 4000, "TYPSIZEY": 4000},
        ll_groups=(
            {
                "INDEX": 0,
                "ANGLE": 1,
                "RADCENTER": 2000,
                "TANCENTER": 0,
                "LEADNUM": 4,
                "LEADPARAMNO": 0,
            },
        ),
        ll_params=(
            {
                "INDEX": 0,
                "TYPWIDTH": 200,
                "TYPLENGTH": 800,
                "TYPPITCH": 500,
            },
        ),
        ll_gaps=({"INDEX": 0, "STARTNO": 2, "MISSLEADNUM": 1},),
    )
    r = upd_fp.build_from_snapshot(snap)
    assert len(r.outline.pads) == 3


def test_fpc_connector_row_follows_long_body_axis() -> None:
    """ANGLE=1 would put a 0.5 mm × 40 row on TYPSIZEY; rotate onto TYPSIZEX."""
    snap = upd_fp.UpdProfileSnapshot(
        profilename="FPC0518-40B2-G1R-C",
        vision_type=1,
        partgroup_name="Connector",
        size_x_um=24000,
        size_y_um=5462,
        size_z_um=2000,
        ll_whole={"TYPSIZEX": 24000, "TYPSIZEY": 5462, "LEADGROUPNUM": 2},
        ll_groups=(
            {
                "INDEX": 0,
                "ANGLE": 1,
                "RADCENTER": 2126,
                "TANCENTER": 0,
                "LEADNUM": 40,
                "LEADPARAMNO": 0,
            },
            {
                "INDEX": 1,
                "ANGLE": 1,
                "RADCENTER": -500,
                "TANCENTER": 0,
                "LEADNUM": 2,
                "LEADPARAMNO": 1,
            },
        ),
        ll_params=(
            {
                "INDEX": 0,
                "TYPWIDTH": 200,
                "TYPLENGTH": 1125,
                "TYPPITCH": 500,
            },
            {
                "INDEX": 1,
                "TYPWIDTH": 1000,
                "TYPLENGTH": 1700,
                "TYPPITCH": 23000,
            },
        ),
    )
    r = upd_fp.build_from_snapshot(snap)
    assert r.error == ""
    assert len(r.outline.pads) == 42
    xs = [p.cx for p in r.outline.pads]
    ys = [p.cy for p in r.outline.pads]
    assert max(xs) - min(xs) > max(ys) - min(ys)
    assert max(xs) - min(xs) > 18.0
    assert r.outline.bbox.width >= 23.0
    assert r.outline.bbox.height < 12.0
    assert any("rotated 90" in w for w in r.warnings)


def test_four_pin_connector_does_not_follow_mount_pitch() -> None:
    """4×0.8 mm fits TYPSIZEY; 2-pad 4.6 mm pitch must not rotate the signal row."""
    snap = upd_fp.UpdProfileSnapshot(
        profilename="0.8T-W-04-00",
        vision_type=1,
        partgroup_name="Connector",
        size_x_um=5300,
        size_y_um=2600,
        ll_whole={"TYPSIZEX": 5300, "TYPSIZEY": 2600, "LEADGROUPNUM": 2},
        ll_groups=(
            {
                "INDEX": 0,
                "ANGLE": 1,
                "RADCENTER": 1200,
                "TANCENTER": 0,
                "LEADNUM": 4,
                "LEADPARAMNO": 0,
            },
            {
                "INDEX": 1,
                "ANGLE": 1,
                "RADCENTER": -700,
                "TANCENTER": 0,
                "LEADNUM": 2,
                "LEADPARAMNO": 1,
            },
        ),
        ll_params=(
            {
                "INDEX": 0,
                "TYPWIDTH": 200,
                "TYPLENGTH": 400,
                "TYPPITCH": 800,
            },
            {
                "INDEX": 1,
                "TYPWIDTH": 200,
                "TYPLENGTH": 800,
                "TYPPITCH": 4600,
            },
        ),
    )
    r = upd_fp.build_from_snapshot(snap)
    assert r.error == ""
    assert len(r.outline.pads) == 6
    assert not any("rotated 90" in w for w in r.warnings)
    sig = [p for p in r.outline.pads if abs(p.height_mm - 0.4) < 0.01]
    assert len(sig) == 4
    assert max(p.cy for p in sig) - min(p.cy for p in sig) > 2.0
    assert max(p.cx for p in sig) - min(p.cx for p in sig) < 0.05


def test_hdmi_connector_does_not_rotate_lead_row() -> None:
    snap = upd_fp.UpdProfileSnapshot(
        profilename="HDMI_CON_24",
        vision_type=1,
        partgroup_name="Connector",
        size_x_um=15000,
        size_y_um=12500,
        ll_whole={"TYPSIZEX": 15000, "TYPSIZEY": 12500, "LEADGROUPNUM": 5},
        ll_groups=(
            {
                "INDEX": 0,
                "ANGLE": 3,
                "RADCENTER": -4100,
                "TANCENTER": -100,
                "LEADNUM": 6,
                "LEADPARAMNO": 0,
            },
            {
                "INDEX": 1,
                "ANGLE": 3,
                "RADCENTER": -2600,
                "TANCENTER": 450,
                "LEADNUM": 6,
                "LEADPARAMNO": 0,
            },
        ),
        ll_params=(
            {
                "INDEX": 0,
                "TYPWIDTH": 300,
                "TYPLENGTH": 300,
                "TYPPITCH": 1500,
            },
        ),
    )
    r = upd_fp.build_from_snapshot(snap)
    assert r.error == ""
    assert len(r.outline.pads) == 12
    assert not any("rotated 90" in w for w in r.warnings)
    xs = [p.cx for p in r.outline.pads]
    ys = [p.cy for p in r.outline.pads]
    assert max(ys) - min(ys) > max(xs) - min(xs)


def test_pcie_x16_key_aligns_on_both_rows() -> None:
    snap = upd_fp.UpdProfileSnapshot(
        profilename="PCIEx16_164P_180R",
        vision_type=1,
        partgroup_name="PCI",
        size_x_um=35000,
        size_y_um=7000,
        ll_whole={"TYPSIZEX": 35000, "TYPSIZEY": 7000, "LEADGROUPNUM": 4},
        ll_groups=(
            {
                "INDEX": 0,
                "ANGLE": 3,
                "RADCENTER": 3400,
                "TANCENTER": 6500,
                "LEADNUM": 71,
                "LEADPARAMNO": 0,
            },
            {
                "INDEX": 1,
                "ANGLE": 1,
                "RADCENTER": 3400,
                "TANCENTER": 36500,
                "LEADNUM": 11,
                "LEADPARAMNO": 0,
            },
            {
                "INDEX": 2,
                "ANGLE": 1,
                "RADCENTER": 3400,
                "TANCENTER": -6500,
                "LEADNUM": 71,
                "LEADPARAMNO": 0,
            },
            {
                "INDEX": 3,
                "ANGLE": 3,
                "RADCENTER": 3400,
                "TANCENTER": -36500,
                "LEADNUM": 11,
                "LEADPARAMNO": 0,
            },
        ),
        ll_params=(
            {
                "INDEX": 0,
                "TYPWIDTH": 450,
                "TYPLENGTH": 1400,
                "TYPPITCH": 1000,
            },
        ),
    )
    r = upd_fp.build_from_snapshot(snap)
    assert r.error == ""
    assert len(r.outline.pads) == 164
    top = [p.cx for p in r.outline.pads if p.cy > 0]
    bot = [p.cx for p in r.outline.pads if p.cy < 0]
    assert any(x > 30 for x in top) and any(x > 30 for x in bot)
    assert any(x < 0 for x in top) and any(x < 0 for x in bot)
    top_key = min(x for x in top if x > 30)
    bot_key = min(x for x in bot if x > 30)
    assert abs(top_key - bot_key) < 1.0


def test_ddr4_connector_pads_span_body() -> None:
    snap = upd_fp.UpdProfileSnapshot(
        profilename="ADDR0110_P055A_",
        vision_type=1,
        partgroup_name="DDR",
        size_x_um=40000,
        size_y_um=7200,
        ll_whole={"TYPSIZEX": 40000, "TYPSIZEY": 7200, "LEADGROUPNUM": 4},
        ll_groups=(
            {
                "INDEX": 0,
                "ANGLE": 3,
                "RADCENTER": -4000,
                "TANCENTER": -10600,
                "LEADNUM": 52,
                "LEADPARAMNO": 0,
            },
            {
                "INDEX": 1,
                "ANGLE": 1,
                "RADCENTER": -4000,
                "TANCENTER": -14150,
                "LEADNUM": 38,
                "LEADPARAMNO": 0,
            },
            {
                "INDEX": 2,
                "ANGLE": 3,
                "RADCENTER": 4000,
                "TANCENTER": -10350,
                "LEADNUM": 52,
                "LEADPARAMNO": 0,
            },
            {
                "INDEX": 3,
                "ANGLE": 1,
                "RADCENTER": 4000,
                "TANCENTER": -13900,
                "LEADNUM": 38,
                "LEADPARAMNO": 0,
            },
        ),
        ll_params=(
            {
                "INDEX": 0,
                "TYPWIDTH": 150,
                "TYPLENGTH": 1000,
                "TYPPITCH": 500,
            },
        ),
    )
    r = upd_fp.build_from_snapshot(snap)
    assert r.error == ""
    assert len(r.outline.pads) == 180
    xs = [p.cx for p in r.outline.pads]
    assert min(xs) < -15.0
    assert max(xs) > 15.0
    top = [p.cx for p in r.outline.pads if p.cy > 0]
    bot = [p.cx for p in r.outline.pads if p.cy < 0]
    assert min(top) < -10 and max(top) > 10
    assert min(bot) < -10 and max(bot) > 10


def test_pin1_mdb_coords_override_pads() -> None:
    snap = upd_fp.UpdProfileSnapshot(
        profilename="ic",
        vision_type=1,
        partgroup_name="SOP",
        pin1_x_um=1200,
        pin1_y_um=-800,
        ll_whole={"TYPSIZEX": 4000, "TYPSIZEY": 3000},
        ll_groups=(
            {
                "INDEX": 0,
                "ANGLE": 1,
                "RADCENTER": 2000,
                "TANCENTER": 0,
                "LEADNUM": 2,
                "LEADPARAMNO": 0,
            },
        ),
        ll_params=(
            {
                "INDEX": 0,
                "TYPWIDTH": 200,
                "TYPLENGTH": 800,
                "TYPPITCH": 500,
            },
        ),
    )
    r = upd_fp.build_from_snapshot(snap)
    assert r.pin1_kind == "mdb"
    assert r.polarity == "yes"
    assert r.pin1_x_mm == pytest.approx(1.2)
    assert r.pin1_y_mm == pytest.approx(-0.8)


def test_pin1_hidden_when_indicator_negative() -> None:
    snap = upd_fp.UpdProfileSnapshot(
        profilename="R",
        vision_type=3,
        partgroup_name="Chip-R0402",
        pin1_indicator=-1,
        chip_whole={"TYPSIZEX": 400, "TYPSIZEY": 200},
    )
    r = upd_fp.build_from_snapshot(snap)
    assert r.polarity == "none"
    assert r.pin1_kind == "none"
