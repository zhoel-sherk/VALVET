"""Tests for multi-vendor-PN handling in Clean BOM.

When a BOM row contains multiple alternative vendor PNs separated by "/" (e.g.,
"C0201C0G100J500NTA/0201CG100J500NT/GRM0335C1H100JA01D/CC0201JRNPO9BN100"),
the vendor parser should try each PN separately and the arbiter should pick
the best one (or first if scores are equal).
"""

from __future__ import annotations

import os
import sys

tests_path = os.path.dirname(os.path.realpath(__file__))
_repo_root = os.path.dirname(tests_path)
sys.path.append(os.path.join(_repo_root, "src"))

import clean_component


def test_multi_vendor_pn_cap_without_description():
    """Multi-vendor-PN CAP without double-comment description.

    Input: 'C0402X7R103K500NTB/C1005X7R103KGTS/GRM155R71H103KA88D/CC0402KRX7R9BB103/0402B103K500NT'
    Expected: ONE cleaned value from the best-matching vendor PN (not last, not concatenation).
    """
    import pn_original

    pn_original.CONVERTERS.clear()
    pn_original.load_converters()

    cfg = clean_component.CleanConfig()
    raw = "C0402X7R103K500NTB/C1005X7R103KGTS/GRM155R71H103KA88D/CC0402KRX7R9BB103/0402B103K500NT"

    cleaned, type_tag, part_code, source = clean_component.clean_one(raw, cfg)

    # Should be a CAP
    assert type_tag == "CAP", f"Expected CAP, got {type_tag}"
    assert part_code == "CAP", f"Expected part_code CAP, got {part_code}"

    # Should come from vendor parser, not regex fallback
    assert source in ("vendor", "pn"), f"Expected vendor/pn source, got {source}"

    # Should contain 10nF (103 = 10 * 10^3 pF = 10nF)
    assert "10nF" in cleaned or "10" in cleaned, f"Expected 10nF in cleaned: {cleaned}"

    # Should contain 0402 package
    assert "0402" in cleaned, f"Expected 0402 package in cleaned: {cleaned}"

    # Should contain X7R dielectric
    assert "X7R" in cleaned, f"Expected X7R dielectric in cleaned: {cleaned}"

    # Should contain 50V voltage
    assert "50V" in cleaned, f"Expected 50V in cleaned: {cleaned}"

    # Should be ONE value, not a concatenation
    assert "|" not in cleaned, f"Expected single value, got concatenation: {cleaned}"


def test_multi_vendor_pn_cap_with_description():
    """Multi-vendor-PN CAP with double-comment description.

    Input: 'C0201C0G100J500NTA/0201CG100J500NT/GRM0335C1H100JA01D/CC0201JRNPO9BN100 | 10PF,50V,J,±5%,C0201,C0G'
    Expected: ONE cleaned value from the best-matching vendor PN.
    """
    import pn_original

    pn_original.CONVERTERS.clear()
    pn_original.load_converters()

    cfg = clean_component.CleanConfig()
    raw = "C0201C0G100J500NTA/0201CG100J500NT/GRM0335C1H100JA01D/CC0201JRNPO9BN100 | 10PF,50V,J,±5%,C0201,C0G"

    cleaned, type_tag, part_code, source = clean_component.clean_one(raw, cfg)

    # Should be a CAP
    assert type_tag == "CAP", f"Expected CAP, got {type_tag}"
    assert part_code == "CAP", f"Expected part_code CAP, got {part_code}"

    # Should come from vendor parser, not regex fallback
    assert source in ("vendor", "pn"), f"Expected vendor/pn source, got {source}"

    # Should contain 10pF (100 = 10 * 10^0 pF = 10pF)
    assert "10pF" in cleaned or "10" in cleaned, f"Expected 10pF in cleaned: {cleaned}"

    # Should contain 0201 package
    assert "0201" in cleaned, f"Expected 0201 package in cleaned: {cleaned}"

    # Should contain C0G (or NPO) dielectric
    assert "C0G" in cleaned or "NPO" in cleaned, (
        f"Expected C0G/NPO dielectric in cleaned: {cleaned}"
    )

    # Should contain 50V voltage
    assert "50V" in cleaned, f"Expected 50V in cleaned: {cleaned}"

    # Should be ONE value, not a concatenation
    assert "|" not in cleaned, f"Expected single value, got concatenation: {cleaned}"


def test_multi_vendor_pn_resistor():
    """Multi-vendor-PN RES with double-comment description.

    Input: 'R0201JXX0000P20LHZ/RTT01000JTH/RC0201JR-070RL/0201WMJ0000TCE/RC-01000JT | 0R,J,±5%,1/20W,R0201'
    Expected: ONE cleaned value for 0R resistor.
    """
    import pn_original

    pn_original.CONVERTERS.clear()
    pn_original.load_converters()

    cfg = clean_component.CleanConfig()
    raw = "R0201JXX0000P20LHZ/RTT01000JTH/RC0201JR-070RL/0201WMJ0000TCE/RC-01000JT | 0R,J,±5%,1/20W,R0201"

    cleaned, type_tag, part_code, source = clean_component.clean_one(raw, cfg)

    # Should be a RESISTOR
    assert type_tag == "RESISTOR", f"Expected RESISTOR, got {type_tag}"
    assert part_code == "RES", f"Expected part_code RES, got {part_code}"

    # Should come from vendor parser, not regex fallback
    assert source in ("vendor", "pn"), f"Expected vendor/pn source, got {source}"

    # Should contain 0R (0 ohm)
    assert "0R" in cleaned or cleaned == "0" or "0.0R" in cleaned, (
        f"Expected 0R in cleaned: {cleaned}"
    )

    # Should contain 0201 package
    assert "0201" in cleaned, f"Expected 0201 package in cleaned: {cleaned}"

    # Should be ONE value, not a concatenation
    assert "|" not in cleaned, f"Expected single value, got concatenation: {cleaned}"


def test_multi_vendor_pn_picks_best_not_last():
    """Verify that the arbiter picks the best-matching PN, not just the last one.

    This test ensures that when multiple vendor PNs are provided, the system
    tries each one and picks the best result based on arbiter scoring.
    """
    import pn_original

    pn_original.CONVERTERS.clear()
    pn_original.load_converters()

    cfg = clean_component.CleanConfig()

    # This row has 5 alternative PNs. The last one (0402B103K500NT) is a Fenghua part.
    # But the arbiter should try all of them and pick the best match.
    raw = "C0402X7R103K500NTB/C1005X7R103KGTS/GRM155R71H103KA88D/CC0402KRX7R9BB103/0402B103K500NT"

    cleaned, type_tag, part_code, source = clean_component.clean_one(raw, cfg)

    # All 5 PNs are 10nF 50V X7R 0402 caps, so they should all parse to the same value
    # The important thing is that we get ONE valid result, not the last PN as-is
    assert type_tag == "CAP"
    assert source in ("vendor", "pn")
    assert "10" in cleaned  # 10nF
    assert "0402" in cleaned
    assert "|" not in cleaned


def test_single_vendor_pn_still_works():
    """Ensure that single-vendor-PN rows (no "/" separator) still work correctly."""
    import pn_original

    pn_original.CONVERTERS.clear()
    pn_original.load_converters()

    cfg = clean_component.CleanConfig()

    # Single PN (no "/" separator)
    raw = "GRM155R71H103KA88D"
    cleaned, type_tag, part_code, source = clean_component.clean_one(raw, cfg)

    assert type_tag == "CAP"
    assert source in ("vendor", "pn")
    assert "10nF" in cleaned or "10" in cleaned
    assert "0402" in cleaned


def test_multi_vendor_pn_with_regex_master_enabled():
    """Test multi-vendor-PN with regex_master_enabled=True (arbiter path)."""
    import pn_original

    pn_original.CONVERTERS.clear()
    pn_original.load_converters()

    cfg = clean_component.CleanConfig(regex_master_enabled=True)
    raw = "C0402X7R103K500NTB/C1005X7R103KGTS/GRM155R71H103KA88D/CC0402KRX7R9BB103/0402B103K500NT"

    cleaned, type_tag, part_code, source = clean_component.clean_one(raw, cfg)

    assert type_tag == "CAP"
    assert source in ("vendor", "pn")
    assert "10" in cleaned
    assert "0402" in cleaned
    assert "|" not in cleaned


def test_value_with_slash_does_not_hide_the_resistor_mpn():
    """``10K/1% | RC0603FR-0710KL`` must clean the MPN, not return it raw.

    RC0603FR-0710KL is 0603, 10 kOhm, +/-1% (Yageo RC series), so the only
    correct cleaned value is ``0603_10K_1%``. Before the fix the leading
    description was taken as the PN list, every alternative failed, and the row
    fell through to ``OTHER`` with the raw MPN as its value.
    """
    cfg = clean_component.CleanConfig()

    cleaned, type_tag, part_code, source = clean_component.clean_one(
        "10K/1% | RC0603FR-0710KL", cfg
    )

    assert (cleaned, type_tag, part_code) == ("0603_10K_1%", "RESISTOR", "RES")
    assert source in ("pn", "vendor")


def test_value_with_slash_does_not_hide_the_capacitor_mpn():
    """``0.1uF/50V | GRM155R71H104KA88D`` is 0402 100nF 50V X7R +/-10%."""
    cfg = clean_component.CleanConfig()

    cleaned, type_tag, part_code, source = clean_component.clean_one(
        "0.1uF/50V | GRM155R71H104KA88D", cfg
    )

    assert (cleaned, type_tag, part_code) == (
        "0402_100nF_50V_X7R_10%",
        "CAP",
        "CAP",
    )
    assert source in ("pn", "vendor")


def test_five_alternatives_agree_on_one_cleaned_value():
    """Every listed alternative is a 0402 10nF 50V X7R cap; the row must say so."""
    cfg = clean_component.CleanConfig()

    cleaned, type_tag, part_code, source = clean_component.clean_one(
        "C0402X7R103K500NTB/C1005X7R103KGTS/GRM155R71H103KA88D"
        "/CC0402KRX7R9BB103/0402B103K500NT",
        cfg,
    )

    assert (cleaned, type_tag, part_code) == (
        "0402_10nF_50V_X7R_10%",
        "CAP",
        "CAP",
    )
    assert source in ("pn", "vendor")
