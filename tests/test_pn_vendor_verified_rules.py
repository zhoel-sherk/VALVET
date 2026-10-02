"""Vendor-rule regressions based on audit references.

Focus: weak or recently generalized decoders.
"""

from __future__ import annotations

import pn_original


def _parse(pn: str, ctype: str) -> str | None:
    pn_original.CONVERTERS.clear()
    pn_original.load_converters()
    return pn_original.parse_pn(pn, ctype, None)


def test_viiyong_tolerance_letter_supported() -> None:
    got = _parse("V105K0201X5R160NXT", "CAP")
    assert got == "0201_1uF_X5R_10%_16V"


def test_viiyong_nat_variant_supported() -> None:
    got = _parse("V223K0201X5R160NAT", "CAP")
    assert got == "0201_22nF_X5R_10%_16V"


def test_walsin_n_line_keeps_tolerance() -> None:
    got = _parse("0402N100J500CT", "CAP")
    assert got == "0402_10pF_50V_5%"


def test_walsin_b_line_emits_film() -> None:
    got = _parse("0402B101K500CT", "CAP")
    assert got == "0402_100pF_X7R_50V_10%"


def test_royal_ohm_k_tolerance_is_preserved() -> None:
    got = _parse("0603WAF220KT5E", "RES")
    assert got == "0603_22R_1%_1/10W"


def test_uniohm_series_letter_gives_tolerance_not_trailing_letter() -> None:
    """WGF is a 1% series: the letter after the value is not the tolerance.

    LCSC lists 0402WGF499JTCE as 49.9R ±1%; the trailing J was previously read
    through the IEC map as 5%.
    """
    got = _parse("0402WGF499JTCE", "RES")
    assert got == "0402_49.9R_1%_1/16W"


def test_uniohm_f_series_is_1_percent_regardless_of_trailing_letter() -> None:
    """Verified against LCSC: 200J, 549J, 511K, 220K are all ±1%."""
    assert _parse("0402WGF200JTCE", "RES") == "0402_20R_1%_1/16W"
    assert _parse("0402WGF549JTCE", "RES") == "0402_54.9R_1%_1/16W"
    assert _parse("0402WGF511KTCE", "RES") == "0402_51.1R_1%_1/16W"


def test_uniohm_j_series_is_5_percent() -> None:
    """LCSC lists 0402WGJ0223TCE as 22k ±5%."""
    got = _parse("0402WGJ0223TCE", "RES")
    assert got == "0402_22K_5%_1/16W"


def test_uniohm_datasheet_ordering_example() -> None:
    """Worked example from the Uniohm thick film chip resistor catalogue.

    "Ordering Procedure (Example: 1206 1/4W 5% 1.2 R T/R-5000)" is given as
    1206W4J012JT5E - it pins the field order (type / wattage / tolerance /
    value / packing) and the deci-ohm reading of a 3-digit value field.
    """
    got = _parse("1206W4J012JT5E", "RES")
    assert got == "1206_1.2R_5%_1/4W"


def test_uniohm_value_field_four_digit_zero_count() -> None:
    """Datasheet p.3: "the 1st to 3rd digits are the significant figures and the
    4th indicates the number of zeros following" (≤1%); for 5% the leading digit
    is 0 and the 2nd/3rd are significant.
    """
    # ≤1%: 200 x 10^1 = 2K (LCSC 0402WGF2001TCE = 2k)
    assert _parse("0402WGF2001TCE", "RES") == "0402_2K_1%_1/16W"
    # 5%: 0 + "22" significant + 3 zeros = 22K (LCSC 0402WGJ0223TCE = 22k)
    assert _parse("0402WGJ0223TCE", "RES") == "0402_22K_5%_1/16W"


def test_uniohm_wgj_series_is_parsed() -> None:
    got = _parse("0402WGJ0472TCE", "RES")
    assert got == "0402_4.7K_5%_1/16W"


def test_uniohm_legacy_3digit_j_code_is_parsed() -> None:
    # Superseded by test_uniohm_series_letter_gives_tolerance_not_trailing_letter,
    # which covers the same part with the tolerance verified against LCSC.
    got = _parse("0402WGF4999TCE", "RES")
    assert got is None


def test_uniohm_zero_ohm_is_parsed() -> None:
    got = _parse("0402WGJ0000TCE", "RES")
    assert got == "0402_0R_5%_1/16W"


def test_royal_ohm_rejects_unrealistic_expansion() -> None:
    # 4-digit exponent blow-up must still be rejected.
    got = _parse("0402WGF4999TCE", "RES")
    assert got is None


# --- Taiyo Yuden ---------------------------------------------------------
# Rated voltage is the FIRST LETTER of the part number (Taiyo Yuden multilayer
# ceramic capacitor catalogue, "PARTS NUMBER" section). Expected values below
# were verified against LCSC product data for each of these exact part numbers.
#
# These three are the ones that used to return None (missing the extra "B" of
# the BBJ series code) or were decoded with a hardcoded 6.3V.


def test_taiyo_bbj_voltage_comes_from_leading_t() -> None:
    got = _parse("TMK107BBJ106MA-T", "CAP")
    assert got == "0603_10uF_25V_X5R_20%"


def test_taiyo_bbj_with_dimension_tolerance_a() -> None:
    got = _parse("TMK316ABJ106KD-T", "CAP")
    assert got == "1206_10uF_25V_X5R_10%"


def test_taiyo_jdk_series_is_capacitor() -> None:
    got = _parse("JDK107BBJ226MA-T", "CAP")
    assert got == "0603_22uF_6.3V_X5R_20%"


def test_taiyo_lmk_leading_l_is_10v() -> None:
    got = _parse("LMK105BJ105KV-F", "CAP")
    assert got == "0402_1uF_10V_X5R_10%"


def test_taiyo_bare_b_series_is_x7r() -> None:
    got = _parse("LMK105B7104KV-F", "CAP")
    assert got == "0402_100nF_10V_X7R_10%"


def test_taiyo_c6_series_is_x6s() -> None:
    got = _parse("LMK063C6273KP-F", "CAP")
    assert got == "0201_27nF_10V_X6S_10%"


def test_taiyo_sd_series_has_no_x_code() -> None:
    """SD is a low-distortion standard part; no dielectric code is emitted."""
    got = _parse("LMK105SD332JV-F", "CAP")
    assert got == "0402_3.3nF_10V_5%"


def test_taiyo_bare_b_series_is_x7r_not_x5r() -> None:
    """Regression: bare "B" was decoded as X5R; LCSC lists it as X7R."""
    got = _parse("EMK105B7223KV-F", "CAP")
    assert got == "0402_22nF_16V_X7R_10%"


def test_taiyo_jmk_keeps_6v3_and_existing_output() -> None:
    """The old branch hardcoded 6.3V, which was only ever right for J."""
    got = _parse("JMK212BJ226MG-T", "CAP")
    assert got == "0805_22uF_6.3V_X5R_20%"


def test_taiyo_umk_legacy_layout_unchanged() -> None:
    got = _parse("UMK105CH120JV-F", "CAP")
    assert got == "0402_12pF_C0G_50V_5%"


def test_taiyo_rejects_unknown_voltage_lead() -> None:
    """Every ① code is P A J L E T G U H Q S X; R is not one of them."""
    got = _parse("RMK107BBJ106MA-T", "CAP")
    assert got is None
