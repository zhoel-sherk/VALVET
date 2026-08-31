"""Qt-free VSPD parser, store, and .kicad_mod import."""

from __future__ import annotations

from pathlib import Path

from package_vspd.catalog import load_tree, normalize_package_key
from package_vspd.import_machine import import_machine_packages
from package_vspd.kicad_mod import parse_kicad_mod_file, parse_kicad_mod_text
from package_vspd.outline import build_result_for_package, outline_to_json
from package_vspd.parse import classify_electrical, parse_package
from package_vspd.store import PackageStore

_KICAD_A = """
(footprint "SOIC-8_3.9x4.9mm_P1.27mm"
  (layer F.Cu)
  (pad "1" smd rect (at -1.905 2.2) (size 0.6 1.55) (layers F.Cu))
  (pad "8" smd rect (at -1.905 -2.2) (size 0.6 1.55) (layers F.Cu))
  (fp_line (start -2.45 -1.95) (end 2.45 -1.95) (layer F.Fab) (width 0.1))
  (fp_line (start 2.45 -1.95) (end 2.45 1.95) (layer F.Fab) (width 0.1))
)
"""

_KICAD_B = """
(footprint "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm_N"
  (pad "1" smd rect (at -1.9 2.15) (size 0.55 1.4) (layers F.Cu))
  (fp_line (start -2.4 -1.9) (end 2.4 -1.9) (layer F.Fab) (width 0.1))
)
"""


def test_tree_has_seven_classes() -> None:
    classes = load_tree()["classes"]
    assert len(classes) == 7


def test_parse_package_goldens() -> None:
    assert parse_package("SOIC127P600X175-8N").vspd_id == "SOIC-8"
    assert parse_package("MS-012").vspd_id == "SOIC-8"
    sop = parse_package("SOP-8")
    assert sop.vspd_id == "SOIC-8"
    assert sop.warnings
    assert parse_package("4301.8-1").vspd_id == "SOIC-8"
    assert parse_package("014T01").vspd_id == "SOIC-8"
    assert parse_package("NE555D").vspd_id == "SOIC-8"
    assert parse_package("D0008A").vspd_id == "SOIC-8"
    assert parse_package("OP07CS8").vspd_id == "SOIC-8"
    assert parse_package("PIC16F877-I/SN").vspd_id == "SOIC-8"
    assert parse_package("PIC16F877-I/SM").vspd_id == "SOIC-16W"
    assert parse_package("SOT23").vspd_id == "SOT-23"
    assert parse_package("SOT_23").vspd_id == "SOT-23"
    assert parse_package("SOT-23").vspd_id == "SOT-23"
    assert parse_package("Chip-SOT23").vspd_id == "SOT-23"
    assert parse_package("Chip-R1005(0402)").vspd_id == "CHIP-0402"
    assert parse_package("Chip-R0603(0201)").vspd_id == "CHIP-0201"
    assert parse_package("Chip-Tantal").vspd_id == "TANT-A"
    assert parse_package("TR2").vspd_id == "SOT-23"
    assert parse_package("SOP").vspd_id == "OTHER"
    assert parse_package("103020015").vspd_id == "OTHER"
    assert parse_package("CAPC1005").vspd_id == "CHIP-0402"
    klc = parse_package("SOIC-8_3.9x4.9mm_P1.27mm")
    assert klc.vspd_id == "SOIC-8"
    assert parse_package("Package_SO:SOIC-8_3.9x4.9mm_P1.27mm").vspd_id == "SOIC-8"
    assert parse_package("no-such-pkg-zzzz").vspd_id == "OTHER"


def test_classify_electrical() -> None:
    assert classify_electrical("Chip-R0402 10k") == "res"
    assert classify_electrical("MLCC 100nF") == "cap"
    assert classify_electrical("ferrite bead") == "ind"
    assert classify_electrical("SOIC-8") == "other"


def test_sqlite_roundtrip(tmp_path: Path) -> None:
    store = PackageStore(tmp_path / "vspd.sqlite")
    try:
        store.add_alias("custom-so8", "SOIC-8", "user")
        store.add_link("mpn", "NE555D", "SOIC-8")
        row = store.get_package("SOIC-8")
        assert row is not None
        aliases = [a["raw"] for a in store.aliases_for("SOIC-8")]
        assert any("custom-so8" == a for a in aliases)
        links = [lk["value"] for lk in store.links_for("SOIC-8")]
        assert "NE555D" in links
        assert store.lookup_vspd("custom-so8") == "SOIC-8"
        assert store.lookup_vspd("ne555d") == "SOIC-8"
        assert store.lookup_vspd("no-such-alias-zzz") is None
        store.add_alias("junk-sku", "OTHER", "hanwha")
        store.add_link("partgroup", "junk-sku", "OTHER")
        n = import_machine_packages(
            store, part_groups=["Chip-R0402", "FAKEPART", "SOT23", "SOT_23", "SOT-23"]
        )
        assert n.mapped == 2
        assert store.aliases_for("OTHER") == []
        assert n.skipped == 1
        assert store.get_package("CHIP-0402") is not None
        assert any(
            a["norm_key"] == normalize_package_key("SOT23")
            for a in store.aliases_for("SOT-23")
        )
    finally:
        store.close()


def test_two_kicad_mod_files_one_vspd(tmp_path: Path) -> None:
    a = tmp_path / "SOIC-8_3.9x4.9mm_P1.27mm.kicad_mod"
    b = tmp_path / "SOIC-8_3.9x4.9mm_P1.27mm_N.kicad_mod"
    a.write_text(_KICAD_A, encoding="utf-8")
    b.write_text(_KICAD_B, encoding="utf-8")
    ia = parse_kicad_mod_file(a)
    ib = parse_kicad_mod_file(b)
    assert ia.vspd_id == ib.vspd_id == "SOIC-8"
    assert ia.outline.source == "kicad_mod"
    assert ia.outline.pads
    store = PackageStore(tmp_path / "vspd.sqlite")
    try:
        store.add_alias(ia.name, ia.vspd_id, "kicad_mod")
        store.add_alias(ib.name, ib.vspd_id, "kicad_mod")
        store.set_outline_json(ia.vspd_id, outline_to_json(ia.outline))
        store.set_outline_json(ib.vspd_id, outline_to_json(ib.outline))
        pkg = store.get_package("SOIC-8")
        assert pkg is not None
        assert pkg["outline_json"]
        als = store.aliases_for("SOIC-8")
        names = {a["raw"] for a in als}
        assert ia.name in names and ib.name in names
    finally:
        store.close()
    text_hit = parse_kicad_mod_text(_KICAD_A)
    assert text_hit.vspd_id == "SOIC-8"


def test_sot_punctuation_same_key() -> None:
    assert (
        normalize_package_key("SOT23")
        == normalize_package_key("SOT_23")
        == normalize_package_key("SOT-23")
        == "sot23"
    )


def test_chip0402_heuristic_outline() -> None:
    result = build_result_for_package("CHIP-0402")
    assert result.error == ""
    assert result.outline.source == "vspd_heuristic"
    assert result.size_x_mm > 0
    assert result.outline.pads


def test_sod523_heuristic_has_two_pads() -> None:
    result = build_result_for_package("SOD-523")
    assert result.error == ""
    assert len(result.outline.pads) == 2
    assert result.outline.lines
