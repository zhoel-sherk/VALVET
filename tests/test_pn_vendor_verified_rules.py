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
    assert got == "0603_22R_10%_1/10W"


def test_uniohm_wgj_series_is_parsed() -> None:
    got = _parse("0402WGJ0472TCE", "RES")
    assert got == "0402_4.7K_5%_1/16W"


def test_uniohm_legacy_3digit_j_code_is_parsed() -> None:
    got = _parse("0402WGF499JTCE", "RES")
    assert got == "0402_49.9R_5%_1/16W"


def test_uniohm_zero_ohm_is_parsed() -> None:
    got = _parse("0402WGJ0000TCE", "RES")
    assert got == "0402_0R_5%_1/16W"


def test_royal_ohm_rejects_unrealistic_expansion() -> None:
    # 4-digit exponent blow-up must still be rejected.
    got = _parse("0402WGF4999TCE", "RES")
    assert got is None
