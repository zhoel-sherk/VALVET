"""Tests for clean_component CleanConfig and clean_preview."""

from __future__ import annotations

import os
import re
import sys

import pytest

tests_path = os.path.dirname(os.path.realpath(__file__))
_boomer_root = os.path.dirname(tests_path)
sys.path.append(os.path.join(_boomer_root, "src"))

import clean_component
from parsers.bom_text_utils import normalize_for_regex_parsing


def _example6_xlsx_paths() -> tuple[str, str]:
    d = os.path.join(_boomer_root, "examples", "example6")
    return (
        os.path.join(d, "original_gen3_bom.xlsx"),
        os.path.join(d, "bom_final.xlsx"),
    )


def _load_example6_abmq601_comment_map():
    """
    Build ``def`` string (как в колонке ``def`` в bom_final.xlsx) -> Comment как col0+col1
    через '+', по строкам листа abmq601, где метка «插件位置» и список позиций в колонке 5.

    Формат исходного XLSX менялся: раньше позиции были в колонке 9, сейчас — широкая
    таблица с группировкой в col5.
    """
    pd = pytest.importorskip("pandas")
    pytest.importorskip("openpyxl")
    orig_path, _ = _example6_xlsx_paths()
    orig = pd.read_excel(
        orig_path, sheet_name="abmq601", header=None, engine="openpyxl"
    )
    dmap: dict[str, str] = {}
    for i in range(len(orig)):
        row = orig.iloc[i]
        label = row[4]
        placements = row[5]
        if pd.isna(label) or "插件位置" not in str(label):
            continue
        if pd.isna(placements) or not str(placements).strip():
            continue
        key = str(placements).strip()
        parts: list[str] = []
        for x in (row[0], row[1]):
            if x is not None and not (isinstance(x, float) and str(x) == "nan"):
                t = str(x).strip()
                if t:
                    parts.append(t)
        dmap[key] = "+".join(parts)
    return dmap


def _dip_part_anchor_in_comment(part: str, cmt: str) -> bool:
    """
    Heuristic: bom_final 'part' values with a ``DIP_`` prefix are a shop-floor / hand
    label for THT (through-hole) or off-SMD-line assembly—the same idea as marking
    rows «THT» or «DIP» in docs; it is *not* limited to an IC in a DIP package.

    The vendor Comment line may spell MPNs differently; this helper only finds anchors.
    """
    c = re.sub(r"\s+", "", str(cmt))
    body = str(part)[4:].replace(" ", "")
    if body in c or body.replace("_", "") in c.replace("_", ""):
        return True
    for tok in body.split("_"):
        if len(tok) >= 4 and tok in c:
            return True
    if "M2*6" in cmt and "SCREW" in str(part).upper():
        return True
    if "1900-070" in c and "RJ45" in part:
        return True
    return False


def test_resistor_drops_package_when_config():
    cfg = clean_component.CleanConfig(resistor_include_package=False)
    out = clean_component.parse_resistor("100R+1/16W+0402", cfg)
    assert "0402" not in out
    assert "100" in out or "100R" in out


def test_cap_drops_voltage_when_config():
    cfg = clean_component.CleanConfig(
        cap_include_voltage=False, cap_include_package=False
    )
    out = clean_component.parse_capacitor("22PF+50V+0402+±5%(J)+X7R", cfg)
    assert "50V" not in out
    assert "X7R" in out or "22" in out.upper()


def test_clean_preview_five_tuples():
    r = clean_component.clean_preview(["100R+0402", ""], None)
    assert len(r) == 2
    assert len(r[0]) == 6
    assert r[1][2] == ""  # empty comment


def test_classify_murata_like_cap():
    t = clean_component.classify_component_type("10UF+16V+X5R+0603")
    assert t == "CAP"


def test_parse_resistor_space_separated_bom_comment():
    """BOM «Comment» often uses spaces, not '+'; package may appear as (0402) inside a token."""
    cfg = clean_component.CleanConfig()
    out = clean_component.parse_resistor("RES 1K OHM 1/16W(0402)1%", cfg)
    assert out == "0402_1K_1%"
    assert out != "RES 1K OHM 1/16W(0402)1%"


def test_resistor_template_orders_nom_pack_watt_tolerance():
    cfg = clean_component.CleanConfig(
        output_separator="-",
        resistor_template=("nom", "pack", "watt", "%"),
    )
    out = clean_component.parse_resistor("100R+1/16W+0402+5%", cfg)
    assert out == "100R-0402-1/16W-5%"


def test_cap_template_orders_nom_pack_film_tolerance_voltage():
    cfg = clean_component.CleanConfig(
        output_separator="-",
        cap_template=("nom", "pack", "film", "%", "V"),
    )
    out = clean_component.parse_capacitor("0.1UF+16V+0402+X5R+20%", cfg)
    assert out == "0.1uF-0402-X5R-20%-16V"


def test_resistor_plain_ohm_r_suffix_toggle():
    base = clean_component.CleanConfig(
        output_separator="-",
        resistor_template=("nom", "pack", "%"),
    )
    assert clean_component.parse_resistor("12.5R+0402+1%", base) == "12.5R-0402-1%"
    assert clean_component.parse_resistor("12.5K+0402+1%", base) == "12.5K-0402-1%"
    no_r = clean_component.CleanConfig(
        output_separator="-",
        resistor_template=("nom", "pack", "%"),
        resistor_include_ohm_r_suffix=False,
    )
    assert clean_component.parse_resistor("12.5R+0402+1%", no_r) == "12.5-0402-1%"
    assert clean_component.parse_resistor("12.5K+0402+1%", no_r) == "12.5K-0402-1%"


def test_cap_ascii_u_replaced_with_micro_when_enabled():
    cfg = clean_component.CleanConfig(
        output_separator="-",
        cap_template=("nom", "pack", "film", "%", "V"),
        cap_uf_micro_sign=True,
    )
    out = clean_component.parse_capacitor("0.1UF+16V+0402+X5R+20%", cfg)
    assert "\u00b5F" in out
    assert "uF" not in out


def test_component_prefix_can_use_or_skip_global_separator():
    with_sep = clean_component.CleanConfig(
        output_separator="-",
        cap_prefix="C",
        resistor_prefix="R",
        inductor_prefix="L",
        prefix_use_separator=True,
    )
    assert clean_component.parse_capacitor("12PF+0402", with_sep) == "C-0402-12pF"
    assert clean_component.parse_resistor("100R+0402", with_sep) == "R-0402-100R"
    assert clean_component.parse_inductor("2.2UH+3015", with_sep) == "L-3015-2.2UH"

    no_sep = clean_component.CleanConfig(
        output_separator="-",
        cap_prefix="C",
        prefix_use_separator=False,
    )
    assert clean_component.parse_capacitor("12PF+0402", no_sep) == "C0402-12pF"


def test_inferit_res_cap_ind_regex_presets():
    cfg = clean_component.CleanConfig()

    res = clean_component.clean_one("RES 0201 10K OHM +/-1% LEAD-FREE - Y01", cfg)
    assert res[2] == "RES"
    assert res[0] == "0201_10K_1%"

    res_zero = clean_component.clean_one("RES 0201 0 OHM +/-5% LEAD-FREE - Y01", cfg)
    assert res_zero[0] == "0201_0R_5%"

    cap = clean_component.clean_one("CAP 0402 10pF/50V +/-5% NPO LEAD-FREE - Y01", cfg)
    assert cap[2] == "CAP"
    assert cap[0] == "0402_10pF_50V_NPO_5%"

    ind = clean_component.clean_one(
        "SMD-INDUCTOR 4.45*4.05*1.2mm 1.0uH ±20% 47mΩMax 4.5A SMD LEAD-FREE - 092(STPI0412-1R0M-T2)",
        cfg,
    )
    assert ind[2] == "IND"
    assert ind[0] == "0412_1.0uH_20%_4.5A_47mΩ"

    bead = clean_component.clean_one(
        "FERRITE-BEAD 0402 120 OHM@100MHz ±25% 700mA LEAD-FREE - 309",
        cfg,
    )
    assert bead[1] == "FERRITE_BEAD"
    assert bead[2] == "FB"
    # No known-series MPN → keep type; must not invent IND ohm@freq slots.
    assert bead[0] != "0402_120R@100MHZ_25%_700MA"
    assert not bead[0].startswith("0402_120R@")


def test_inductor_group_off_uses_other_regex_path():
    cfg = clean_component.CleanConfig(
        parse_inductors=False,
        use_pn_codecs=False,
        use_component_library=False,
    )
    r = clean_component.clean_one(
        "SMD-INDUCTOR 4.45*4.05*1.2mm 1.0uH ±20% 47mΩMax 4.5A (STPI0412-1R0M-T2)", cfg
    )
    assert r[1] == "INDUCTOR"
    assert r[2] == "OTHER"
    assert r[3] in ("regex", "other")


def test_hanwha_mdb_longest_substring_match():
    cfg = clean_component.CleanConfig(
        use_hanwha_mdb=True,
        hanwha_partnames={"STPI0412-1R0M-T2", "STPI0412"},
        use_pn_codecs=False,
        use_component_library=False,
    )
    r = clean_component.clean_one("CONNECTOR BOM rail STPI0412-1R0M-T2 more text", cfg)
    assert r[0] == "STPI0412-1R0M-T2"
    assert r[3] == "hanwha_mdb"


def test_inferit_other_regex_presets_extract_mpn():
    assert (
        clean_component.clean_one("POWER-IC RT8120AZSP ONE-PHASE SOP-8 LEAD-FREE")[0]
        == "RT8120AZSP"
    )
    assert (
        clean_component.clean_one("TYPEC IC IT8851FN-128/HX V0.2.8 USB Type-C")[0]
        == "IT8851FN-128/HX"
    )
    assert (
        clean_component.clean_one("MOSFET N-CHANNEL MDU1514URH 30V DFN-56 RoHS")[0]
        == "MDU1514URH"
    )
    assert (
        clean_component.clean_one("SMD-RECTIFIER-DIODES 1N4148WS 75V 200mA SOD323")[0]
        == "1N4148WS"
    )
    assert (
        clean_component.clean_one("CRYSTAL 25.000MHz 12pF ±10PPM ESR<50 OHM")[0]
        == "25.000MHZ"
    )


def test_vendor_pn_uses_component_template_order():
    cfg = clean_component.CleanConfig(
        output_separator="-",
        cap_template=("nom", "pack", "film", "%", "V"),
    )
    row = clean_component.clean_one("YAGEO/CC0402KRX7R9BB102", cfg)
    assert row[3] == "pn"
    assert row[0] == "1nF-0402-X7R-10%-50V"


def test_example6_bom_golden_def_bijection():
    """
    example6: supplier BOM (abmq601) and hand-export bom_final list the same designator
    groups (def); Comment is reconstructed as 品名規格+规格 (col2+col3) with '+'.
    """
    pd = pytest.importorskip("pandas")
    pytest.importorskip("openpyxl")
    orig_path, final_path = _example6_xlsx_paths()
    if not (os.path.isfile(orig_path) and os.path.isfile(final_path)):
        pytest.skip("example6 xlsx not in tree (expected under examples/example6/)")

    dmap = _load_example6_abmq601_comment_map()
    gf = pd.read_excel(final_path, engine="openpyxl")
    assert "def" in gf.columns and "part" in gf.columns
    defs_golden = {str(x).strip() for x in gf["def"].tolist() if str(x).strip()}
    defs_orig = set(dmap.keys())
    assert len(defs_golden) == len(gf), "unique def per row in bom_final"
    assert defs_golden == defs_orig
    for d, cmt in dmap.items():
        assert cmt, f"non-empty comment for {d!r}"


def test_example6_bom_dip_mpn_anchors_in_vendor_comment():
    """
    Where bom_final 'part' uses a ``DIP_`` prefix, at least one stable token from the
    part string appears in the vendor Comment line (join key: ``def`` in abmq601).

    ``DIP_`` here means THT / not pick-and-place line, not «must be a DIP package»;
    the test checks substring anchors only, not package type.
    """
    pd = pytest.importorskip("pandas")
    pytest.importorskip("openpyxl")
    orig_path, final_path = _example6_xlsx_paths()
    if not (os.path.isfile(orig_path) and os.path.isfile(final_path)):
        pytest.skip("example6 xlsx not in tree (expected under examples/example6/)")

    dmap = _load_example6_abmq601_comment_map()
    gf = pd.read_excel(final_path, engine="openpyxl")
    for _, row in gf.iterrows():
        part = str(row["part"])
        sdef = str(row["def"]).strip()
        cmt = dmap[sdef]
        if not part.startswith("DIP_"):
            continue
        assert _dip_part_anchor_in_comment(part, cmt), (
            f"no anchor for {part!r} in comment for {sdef!r}:\n{cmt!r}"
        )


def test_mlcc_one_line_various_spacing():
    cfg = clean_component.CleanConfig()
    for raw in (
        "MLCC 15PF/50V (0402) NPO 5%",
        "MLCC 47PF/50V(0402)NPO 5%",
        "MLCC 0.1UF/16V(0402)X7R 10%",
    ):
        out = clean_component.parse_capacitor(raw, cfg)
        assert out != raw
        assert "0402" in out
        assert "50V" in out or "16V" in out


def test_normalize_for_regex_keeps_cap_voltage_slash():
    assert normalize_for_regex_parsing(
        "MLCC 15PF/50V (0402) NPO 5%"
    ) == ("MLCC 15PF/50V (0402) NPO 5%")
    assert normalize_for_regex_parsing("MFR/RC0603JR-1KL") == "RC0603JR-1KL"


def test_normalize_for_regex_keeps_fractional_wattage():
    assert normalize_for_regex_parsing("100R+1/16W+0402") == "100R+1/16W+0402"


def test_classify_tai_mpn_strips_space_after_slash():
    assert clean_component.classify_component_type("TA-I/RM04JTN100") == "RESISTOR"
    assert clean_component.classify_component_type("TA-I/ RM04JTN100") == "RESISTOR"


def test_classify_bare_cl_and_yageo_rc():
    assert clean_component.classify_component_type("CL05B102KB5NNNC") == "CAP"
    assert clean_component.classify_component_type("RC0402JR-0710RL") == "RESISTOR"


def test_yageo_cc_includes_voltage_tolerance():
    import pn_original

    pn_original.CONVERTERS.clear()
    pn_original.load_converters()
    cfg = clean_component.CleanConfig()
    out = pn_original.parse_pn("CC0402KRX7R9BB102", "CAP", cfg)
    assert out
    assert "50V" in out
    assert "10%" in out
    assert "X7R" in out


def test_murata_grm1555_c1h_uses_vendor_pn():
    import pn_original

    pn_original.CONVERTERS.clear()
    pn_original.load_converters()
    cfg = clean_component.CleanConfig()
    row = clean_component.clean_one("MURATA/GRM1555C1H270JA01D <G>", cfg)
    assert row[3] in ("pn", "vendor")
    assert "27pF" in row[0] or "27" in row[0]
    assert "C0G" in row[0] or "5%" in row[0]
    assert row[2] == "CAP"


def test_new_vendor_pn_regressions():
    import pn_original

    pn_original.CONVERTERS.clear()
    pn_original.load_converters()
    cfg = clean_component.CleanConfig()

    murata = clean_component.clean_one("MURATA/GRM155R71H681KA01D", cfg)
    assert murata[2] == "CAP" and murata[3] == "pn"
    assert "680pF" in murata[0] and "50V" in murata[0] and "X7R" in murata[0]

    yageo = clean_component.clean_one("YAGEO/RC0402FR-0749K9L", cfg)
    assert yageo[2] == "RES" and yageo[3] == "pn"
    assert "49.9K" in yageo[0] and "0402" in yageo[0]

    walsin = clean_component.clean_one("WALSIN/WW25RR001FTL", cfg)
    assert walsin[2] == "RES" and walsin[3] == "pn"
    assert "2512" in walsin[0] and "0.001R" in walsin[0]


def test_vendor_pn_list_does_not_fall_back_to_regex():
    import pn_original

    pn_original.CONVERTERS.clear()
    pn_original.load_converters()
    cfg = clean_component.CleanConfig()
    cases = {
        "RC0402-JR-07510RL": ("RES", "51R"),
        "WR04W2R20FTL": ("RES", "2.20R"),
        "RC0402FR-076K49L (PC335)": ("RES", "6.49K"),
        "RC0402-JR-0775RL": ("RES", "75R"),
        "RM06JTN-2R2": ("RES", "2.2R"),
        "GRM155R61E104K": ("CAP", "100nF"),
        "GRM155R61A104KA01D": ("CAP", "100nF"),
        "GRM155R61C105KA12D": ("CAP", "1uF"),
        "0402X105K6R3CT": ("CAP", "1uF"),
        "GRM155R60J105KE19D": ("CAP", "1uF"),
        "TAIYO/TMK107BJ105KA-T": ("CAP", "1uF"),
    }
    for raw, (part_code, expected) in cases.items():
        cleaned, _typ, code, source = clean_component.clean_one(raw, cfg)
        assert code == part_code, raw
        assert source == "pn", raw
        assert expected in cleaned, raw


def test_component_library_plain_and_structured(tmp_path, monkeypatch):
    import component_library

    lib = tmp_path / "components.txt"
    lib.write_text("SN74LVC2G17DCKR\n", encoding="utf-8")
    monkeypatch.setenv("BOOMER_COMPONENTS_TXT", str(lib))

    row = clean_component.clean_one(
        "MFR/SN74LVC2G17DCKR", clean_component.CleanConfig()
    )
    assert row == ("SN74LVC2G17DCKR", "OTHER", "OTHER", "library")

    disabled = clean_component.clean_one(
        "MFR/SN74LVC2G17DCKR",
        clean_component.CleanConfig(use_component_library=False),
    )
    assert disabled[3] != "library"

    ok = component_library.append_component(
        "Vendor/FANCY-IC-1 <G>", "FANCY-IC-1", "OTHER", "SOT-23", lib
    )
    assert ok
    assert not component_library.append_component(
        "FANCY-IC-1", "FANCY-IC-1", "OTHER", "", lib
    )
    got = component_library.lookup_component("FANCY-IC-1", lib)
    assert got is not None
    assert got.cleaned == "FANCY-IC-1"
    assert got.footprint == "SOT-23"


def test_parse_capacitors_false_returns_unchanged():
    cfg = clean_component.CleanConfig(parse_capacitors=False)
    raw = "MLCC 15PF/50V (0402) NPO 5%"
    assert clean_component.parse_capacitor(raw, cfg) == raw


def test_clean_one_respects_master_switches():
    c_off = clean_component.CleanConfig(parse_capacitors=False)
    t = clean_component.clean_one("MLCC 10PF/50V(0402)NPO 5%", c_off)
    assert t[0] == "MLCC 10PF/50V(0402)NPO 5%" and t[3] == "off"

    c_on = clean_component.CleanConfig(parse_capacitors=True, use_vendor_pn=False)
    t2 = clean_component.clean_one("MFR/RM10K", c_on)
    assert t2[1] == "RESISTOR" and t2[3] == "regex"


def test_thermistor_extract_classify_clean_and_no_vendor_pn():
    from parsers.thermistors import extract_thermistor_mpn

    assert extract_thermistor_mpn("NCP15WF104F03RC") == "NCP15WF104F03RC"
    assert extract_thermistor_mpn("NTCG103JF103FT1") == "NTCG103JF103FT1"
    assert extract_thermistor_mpn("ALT (ERTJ0EP473F) tail") == "ERTJ0EP473F"
    assert clean_component.classify_component_type("47K OHM NCP15WF104F03RC") == "OTHER"
    cfg = clean_component.CleanConfig(use_pn_codecs=True, regex_master_enabled=False)
    row = clean_component.clean_one("NCP15WF104F03RC", cfg)
    assert row[0] == "NCP15WF104F03RC" and row[3] == "thermistor"
    import pn_original

    pn_original.CONVERTERS.clear()
    pn_original.load_converters()
    from pn_original import parse_pn

    assert parse_pn("NCP15WF104F03RC", "RES", cfg) is None
    assert parse_pn("NTCG103JF103FT1", "CAP", cfg) is None


def test_inferit_cap_tolerance_pf_snaps_to_percent_bucket():
    from parsers.inferit_pars import parse_inferit_capacitor_fields

    cfg = clean_component.CleanConfig()
    s = "CAP 0402 22PF / 50V +/-0.50pF NPO"
    d = parse_inferit_capacitor_fields(s, cfg)
    assert d is not None
    raw, formatted = d
    assert raw["%"] == "5%"


def test_cap_token_pf_tolerance_snaps():
    from parsers.cap_pars import parse_capacitor_token_fields

    cfg = clean_component.CleanConfig()
    slots, out = parse_capacitor_token_fields("15PF+50V+±0.25PF+0402+C0G", cfg)
    assert slots.get("%") == "5%"


def test_mlcc_prose_pf_tolerance_snaps():
    from parsers.cap_pars import try_parse_mlcc_bom_line_slots

    cfg = clean_component.CleanConfig()
    s = "MLCC 15PF/50V (0402) NPO ±0.50pF"
    t = try_parse_mlcc_bom_line_slots(s, cfg)
    assert t is not None
    assert t[0].get("%") == "5%"


def test_mlcc_prose_absolute_pf_tolerance_kept():
    from parsers.cap_pars import try_parse_mlcc_bom_line_slots

    cfg = clean_component.CleanConfig(
        cap_template=("pack", "nom", "film", "%", "V"),
    )
    s = "MLCC 5PF/50V (0402) NPO 0.25PF"
    t = try_parse_mlcc_bom_line_slots(s, cfg)
    assert t is not None
    _slots, out = t
    assert out == "0402_5pF_C0G_0.25pF_50V"


def test_vendor_merge_mlcc_5pf_absolute_tol_over_vendor_pct():
    from tools.clean_corpus_lib import load_corpus_profile

    cfg = load_corpus_profile()
    exp = "0402_5pF_C0G_0.25pF_50V"
    for suffix in (
        "YAGEO/CC0402CRNPO9BN5R0",
        "WALSIN/0402N5R0C500LT",
        "SAMSUNG/CL05C050CB5NNNC",
        "MURATA/GRM1555C1H5R0CA01D",
    ):
        s = f"MLCC 5PF/50V (0402) NPO 0.25PF | {suffix}"
        assert clean_component.clean_one(s, cfg)[0] == exp


def test_clean_other_power_ic_skips_switch_keyword():
    from parsers.other_pars import clean_other

    s = "POWER-IC Switch JW7115S-2SOTA#TRPBF SOT23"
    assert clean_other(s) == "JW7115S-2SOTA#TRPBF"


def test_match_hanwha_normalized_full_and_partial():
    names = {"JW7115S-2SOTA#TRPBF", "OTHERPART"}
    full = clean_component.match_hanwha_mdb_partname(
        "JW7115S2SOTATRPBF", names, partial_match=False
    )
    assert full == ("JW7115S-2SOTA#TRPBF", "hanwha_mdb")
    spacer_partial = clean_component.match_hanwha_mdb_partname(
        "JW7115S2SOTATRPBF", names, partial_match=True
    )
    assert spacer_partial == ("JW7115S-2SOTA#TRPBF", "PARTIAL hanwha_mdb")
    frag = clean_component.match_hanwha_mdb_partname(
        "JW7115S2SOTA", {"JW7115S-2SOTA#TRPBF"}, partial_match=False
    )
    assert frag is None
    partial = clean_component.match_hanwha_mdb_partname(
        "JW7115S2SOTA", {"JW7115S-2SOTA#TRPBF"}, partial_match=True
    )
    assert partial == ("JW7115S-2SOTA#TRPBF", "PARTIAL hanwha_mdb")


def test_match_hanwha_footprint_and_part_group_bonus():
    names = {"IC_QFN_STM", "IC_SOP_STM"}
    hit = clean_component.match_hanwha_mdb_partname(
        "line IC_QFN_STM and IC_SOP_STM",
        names,
        footprint="QFN",
    )
    assert hit is not None
    assert hit[0] == "IC_QFN_STM"
    grouped = clean_component.match_hanwha_mdb_partname(
        "JST_HEADER and JST_SOCKET",
        {"JST_HEADER", "JST_SOCKET"},
        footprint="HEADER",
        part_groups={"JST_HEADER": "Connector", "JST_SOCKET": "Connector"},
    )
    assert grouped is not None
    assert grouped[0] == "JST_HEADER"


def test_match_hanwha_equal_length_is_ambiguous():
    names = {"PART-A", "PART_A"}
    hit = clean_component.match_hanwha_mdb_partname("xxPARTAxx", names)
    assert hit is not None
    assert hit[1] == "AMBIGUOUS hanwha_mdb"


def test_hanwha_norm_keeps_dot_between_digits():
    assert clean_component._norm_hanwha("4.7K") != clean_component._norm_hanwha("47K")


def test_thermistor_line_beats_hanwha_mdb_lookalike_res():
    s = "Thermistor-SMD 0402 47K OHM +/-1% NTC RoHS-715(ERTJ0EP473F)"
    cfg = clean_component.CleanConfig(
        regex_master_enabled=True,
        parse_resistors=True,
        use_hanwha_mdb=True,
        hanwha_partnames={"0402_4.7K"},
    )
    row = clean_component.clean_one(s, cfg)
    assert row[0] == "ERTJ0EP473F" and row[3] == "thermistor"


def test_ferrite_bead_extract_and_clean_pass_through():
    from parsers.ferrite_beads import extract_ferrite_bead_mpn

    assert (
        extract_ferrite_bead_mpn(
            "FERRITE-BEAD 0603 80 OHM@100MHz ±25% 3000mA RoHS - 699(HCB1608KF-800T30)"
        )
        == "HCB1608KF-800T30"
    )
    assert (
        extract_ferrite_bead_mpn(
            "FERRITE BEAD(0603)120OHM/2A | MURATA/BLM18PG121SN1D"
        )
        == "BLM18PG121SN1D"
    )
    assert (
        extract_ferrite_bead_mpn(
            "FERRITE BEAD (0603)60OHM/1A | MAXECHO/ACMS160808A600 1A"
        )
        == "ACMS160808A600"
    )
    assert (
        extract_ferrite_bead_mpn(
            "FERRITE BEAD(0603)120OHM/600mA | MAXECHO/EBMS160808A121 0.6A"
        )
        == "EBMS160808A121"
    )
    assert (
        extract_ferrite_bead_mpn(
            "FERRITE BEAD SMD(0603)600OHM | MAXECHO/EBMS160808A601 RDC3"
        )
        == "EBMS160808A601RDC3"
    )
    assert (
        clean_component.classify_component_type(
            "FERRITE-BEAD 0603 ... (HCB1608KF-800T30)"
        )
        == "FERRITE_BEAD"
    )
    cfg = clean_component.CleanConfig(use_pn_codecs=True, regex_master_enabled=False)
    row = clean_component.clean_one(
        "FERRITE-BEAD 0603 80 OHM@100MHz ±25% 3000mA RoHS - 699(HCB1608KF-800T30)",
        cfg,
    )
    assert row[0] == "HCB1608KF-800T30"
    assert row[1] == "FERRITE_BEAD"
    assert row[2] == "FB"
    assert row[3] == "ferrite_bead"


def test_ferrite_bead_hcb_analog_family_is_covered():
    from parsers.ferrite_beads import extract_ferrite_bead_mpn

    analogs = [
        "HCB1608KF-300T30",
        "HCB1608KF-300T60",
        "HCB1608KF-800T30",
        "HCB1608KF-121T30",
        "HCB1608KF-151T20",
        "HCB1608KF-221T25",
        "HCB1608KF-301T20",
        "HCB1608KF-471T10",
        "HCB1608KF-601T10",
        "HCB1608KF-102T10",
    ]
    for mpn in analogs:
        s = f"FERRITE BEAD junk {mpn} noise"
        assert extract_ferrite_bead_mpn(s) == mpn


def test_power_ic_spacer_only_hanwha_is_partial_when_flag_on():
    mdb = "JW7115S_2SOTA_TRPBF"
    bom = (
        "POWER-IC Switch JW7115S-2SOTA#TRPBF Input voltage range2.7-5.5V "
        "2.2A High Enable SOT23-5 LEAD-FREE - 00Y"
    )
    names = {mdb}
    hit = clean_component.match_hanwha_mdb_partname(bom, names, partial_match=True)
    assert hit == (mdb, "PARTIAL hanwha_mdb")


def test_hanwha_partial_fuzzy_typo_when_substring_primary_misses():
    """O vs 0 in BOM key: primary substring fails, fuzzy partial_ratio still matches."""
    mpn = "JW7115S-2SOTA#TRPBF"
    names = {mpn, "OTHERPART"}
    hit = clean_component.match_hanwha_mdb_partname(
        "JW7115S2S0TA", names, partial_match=True
    )
    assert hit == (mpn, "PARTIAL hanwha_mdb")


def test_inferit_res_k_suffix_beats_tol_only_regex_master():
    cfg = clean_component.CleanConfig(
        regex_master_enabled=True,
        parse_resistors=True,
        use_hanwha_mdb=True,
        hanwha_partnames={"Y01", "LEADFREE"},
    )
    row = clean_component.clean_one("RES 0201 150K +/-1% LEAD-FREE - Y01", cfg)
    assert "150" in row[0] and "K" in row[0].upper()
    assert row[1] == "RESISTOR"


def test_hanwha_skipped_for_cap_even_if_mdb_has_package_like_partname():
    cfg = clean_component.CleanConfig(
        regex_master_enabled=True,
        parse_capacitors=True,
        use_hanwha_mdb=True,
        hanwha_partnames={"0201_100", "CAP0201JUNK"},
    )
    row = clean_component.clean_one("CAP 0201 100pF/25V +/-5% COG LEAD-FREE - Y01", cfg)
    assert row[2] == "CAP"
    assert row[3] not in ("hanwha_mdb", "PARTIAL hanwha_mdb")
    assert "100" in row[0] or "pF" in row[0].lower()


def test_legacy_cap_template_w_migrates_to_v_in_default_clean_config():
    from clean_types import CleanConfig, default_clean_config

    cfg = CleanConfig(cap_template=("nom", "pack", "film", "%", "W"))
    norm = default_clean_config(cfg)
    assert norm.cap_template == ("nom", "pack", "film", "%", "V")


def test_legacy_cap_template_volt_label_migrates_to_v_slot():
    from clean_types import CleanConfig, default_clean_config

    cfg = CleanConfig(cap_template=("pack", "nom", "V (volt)", "film", "%"))
    norm = default_clean_config(cfg)
    assert norm.cap_template == ("pack", "nom", "V", "film", "%")


def test_device_style_cap_slash_uf_voltage_splits_for_tokens():
    from parsers.cap_pars import parse_capacitor_token_fields

    cfg = clean_component.CleanConfig()
    s = "C_C0402_DISCRETE_0.22UF/6.3V/0.22UF/6.3V"
    raw, out = parse_capacitor_token_fields(s, cfg)
    assert raw.get("V") == "6.3V"
    assert "0.22" in (raw.get("nom") or "").lower()


def test_tokenize_plus_minus_does_not_trigger_plus_split():
    from parsers.bom_text_utils import tokenize_bom_spec
    from parsers.res_pars import parse_resistor_token_fields

    toks = tokenize_bom_spec("RES 0402 330 OHM +/-1% LEAD-FREE - Y01")
    assert "330" in toks
    assert any("1%" in t for t in toks)
    cfg = clean_component.CleanConfig(
        parse_resistors=True,
        resistor_template=("pack", "nom", "%"),
    )
    raw, out = parse_resistor_token_fields(
        "RES 0402 330 OHM +/-1% LEAD-FREE - Y01", cfg
    )
    assert raw.get("pack") == "0402"
    assert "330" in (raw.get("nom") or "")
    assert raw.get("%") == "1%"


def test_mlcc_prose_with_mfr_suffix_parse_slots_before_preprocess():
    """Slash→+ preprocess must not run before MLCC slot parse (needs UF/V slash)."""
    from parsers.cap_pars import parse_capacitor_token_fields

    cfg = clean_component.CleanConfig()
    s = "MLCC 1UF/16V(0402)X5R 10%2SAMSUNG/CL05A105KO5NNNC"
    raw, _out = parse_capacitor_token_fields(s, cfg)
    assert raw.get("V") == "16V"
    assert raw.get("film") == "X5R"
    assert raw.get("%") == "10%"


def test_enrich_vendor_cap_overwrites_wrong_voltage_when_bom_has_value_voltage_slash():
    """No «MLCC» keyword required — slash ``UF/V`` anchors BOM-derived regex."""
    from parsers.vendor_context_merge import enrich_vendor_cleaned_from_bom

    cfg = clean_component.CleanConfig(
        parse_capacitors=True,
        cap_template=("nom", "pack", "film", "%", "V"),
    )
    orig = "CHIP CAP 1UF/16V(0402)X5R 10% CL05A105KO5NNNC"
    vendor = "0402_1UF_10V_X5R_10%"
    out = enrich_vendor_cleaned_from_bom(orig, vendor, "CAP", cfg)
    assert "16V" in out
    assert "10V" not in out


def test_enrich_vendor_cap_keeps_vendor_voltage_when_bom_regex_not_anchored():
    """Stray ``25V`` without nominal/slash must not override MPN-derived voltage."""
    from parsers.vendor_context_merge import enrich_vendor_cleaned_from_bom

    cfg = clean_component.CleanConfig(
        parse_capacitors=True,
        cap_template=("nom", "pack", "film", "%", "V"),
    )
    orig = "SAMSUNG CL05A105KO5NNNC max 25V"
    vendor = "0402_1UF_10V_X5R_10%"
    out = enrich_vendor_cleaned_from_bom(orig, vendor, "CAP", cfg)
    assert "10V" in out
    assert "25V" not in out


def test_enrich_vendor_resistor_fills_watt_from_bom_prose():
    from parsers.vendor_context_merge import enrich_vendor_cleaned_from_bom

    cfg = clean_component.CleanConfig(
        parse_resistors=True,
        resistor_template=("pack", "nom", "watt", "%"),
    )
    orig = "RC0402JR-0710KL+1/10W+5%"
    vendor = "0402_10K_5%"
    out = enrich_vendor_cleaned_from_bom(orig, vendor, "RESISTOR", cfg)
    assert "1/10W" in out


def test_milliohm_not_mega_on_sense_resistor_prose():
    cfg = clean_component.CleanConfig(
        use_pn_codecs=True,
        use_hanwha_mdb=False,
        use_component_library=False,
        regex_master_enabled=False,
        resistor_include_ohm_r_suffix=True,
        resistor_template=("pack", "nom", "watt", "%"),
    )
    row = clean_component.clean_one(
        "RES 1m OHM 2W (2512) 1% | YAGEO/PA2512FKF7W0R001E", cfg
    )
    assert "0.001R" in row[0] or "0.001" in row[0]
    assert "1M" not in row[0]
    row2 = clean_component.clean_one(
        "RES 2m OHM 2W (2512) 1% | TA-I/RLM25FEER002", cfg
    )
    assert "0.002R" in row2[0] or "0.002" in row2[0]
    mega = clean_component.clean_one("RES 0402 1M +/-1%", cfg)
    assert "1M" in mega[0]


def test_clean_other_skips_adjectives_and_keeps_xtal_plus_minus():
    from parsers.other_pars import clean_other

    assert clean_other(
        "IC Low RON Load Switch KTS1677BEVH-TR VIN=3V to 23V 5A WLCSP-15"
    ).startswith("KTS1677")
    assert "TT0501SB" in clean_other(
        "ESD protection diodes Bidirectional TT0501SB +/-25KV(air) +/-20KV(contact)"
    )
    assert "TT0504SP" in clean_other(
        "ESD Ultra Low Capacitance Array for ESD Protection TT0504SP +/-25KV"
    )
    xtal = clean_other("XTAL 25MHZ SMD 20PF/+-20PPM")
    assert "20PPM" in xtal.upper() or "+/-" in xtal
    assert not xtal.rstrip().endswith("20PF/")


def test_ic_line_not_classified_resistor_from_r_code():
    assert (
        clean_component.classify_component_type(
            "IC WS05-4R2P 4-Line Uni-directional Ultra-low Capacitance Transient"
        )
        == "OTHER"
    )
    row = clean_component.clean_one(
        "IC WS05-4R2P 4-Line Uni-directional Ultra-low Capacitance "
        "Transient Voltage Suppressors DFN10 - 276"
    )
    assert row[1] == "OTHER"
    assert "WS05" in row[0]


def test_uniohm_spaced_mpn_and_fenghua_rc_resistor():
    cfg = clean_component.CleanConfig(
        use_pn_codecs=True,
        use_hanwha_mdb=False,
        use_component_library=False,
        regex_master_enabled=False,
        resistor_template=("pack", "nom", "watt", "%"),
    )
    uni = clean_component.clean_one(
        "RES_75K_+/-1%_1/20W_R0201_SMD | UniOhm | 0201 F7502TCE", cfg
    )
    assert uni[1] == "RESISTOR"
    assert "75K" in uni[0]
    assert uni[3] in ("vendor", "pn")
    fh = clean_component.clean_one(
        "RES_3R3_+/-1%_1/16W_R0402_SMD | Fenghua | RC-02U3R30FT", cfg
    )
    assert fh[1] == "RESISTOR"
    assert "3.3R" in fh[0] or "3R3" in fh[0]
    assert fh[3] in ("vendor", "pn")


def test_clean_one_preview_classify_parity_joined_comment():
    cfg = clean_component.CleanConfig(
        use_pn_codecs=True,
        use_hanwha_mdb=False,
        use_component_library=False,
        regex_master_enabled=False,
    )
    s = "FERRITE BEAD(0603)120OHM/2A | MURATA/BLM18PG121SN1D"
    one = clean_component.clean_one(s, cfg)
    prev = clean_component.clean_preview([s], cfg)[0]
    assert one[0] == prev[2]
    assert one[1] == prev[3]
    assert one[3] == prev[4]


def test_res_nominal_gets_r_suffix_in_regex_path():
    cfg = clean_component.CleanConfig(
        use_pn_codecs=False,
        use_hanwha_mdb=False,
        use_component_library=False,
        regex_master_enabled=False,
        resistor_include_ohm_r_suffix=True,
        resistor_template=("pack", "nom", "watt", "%"),
    )
    row = clean_component.clean_one("RES 3 OHM 1W (2512) 5%", cfg)
    assert "3R" in row[0]
    from clean_alerts import analyze_token_alert

    alert = analyze_token_alert(row[0], "RESISTOR", separator="_").as_text()
    assert "missing=nominal" not in alert
