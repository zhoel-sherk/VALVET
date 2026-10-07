"""Ralec chip-resistor codec.

There was no Ralec codec at all before this one, so every Ralec part number in a
BOM fell through the vendor phase untouched. The expectations here come from the
manufacturer's own "Explanation Of Part Numbers" sections in the SMD Resistor
Components catalogue 2022 and from product specification IE-SP-010.

The tests are mostly about *which* series claims a part number and *which size
table* it uses, because that is where a generic pattern would silently attach the
wrong imperial size.
"""

from __future__ import annotations

import pn_original
from pn_original import ralec_resistor


def _parse(pn: str, ctype: str) -> str | None:
    pn_original.CONVERTERS.clear()
    pn_original.load_converters()
    return pn_original.parse_pn(pn, ctype, None)


# --- size tables are per-series, not shared ---------------------------------


def test_same_body_different_size_by_series() -> None:
    """``06`` is 1206 on the standard series and 0612 on the wide-terminal one.

    This is the reason every prefix carries its own table. A shared table would
    report 1206 for a wide-terminal part.
    """
    assert ralec_resistor.parse("RTT06100JTH", "RES") == "1206_10R_5%"
    assert ralec_resistor.parse("RTW06100JTP", "RES") == "0612_10R_5%"


def test_size_codes_are_ralec_own_not_inch() -> None:
    """The catalogue prints ``02``=0402 and ``06``=1206, opposite to the usual
    inch reading where 06 would be 0603."""
    assert ralec_resistor.parse("RTT02100JTH", "RES") == "0402_10R_5%"
    assert ralec_resistor.parse("RTT06100JTH", "RES") == "1206_10R_5%"
    assert ralec_resistor.parse("RTT03100JTH", "RES") == "0603_10R_5%"


def test_every_wide_terminal_series_uses_the_wide_table() -> None:
    """RAW and RTW both print 05=0508, 18=1218, 20=1020, 25=1225."""
    for prefix in ("RAW", "RTW"):
        assert ralec_resistor.parse(f"{prefix}05100JTP", "RES") == "0508_10R_5%", prefix
        assert ralec_resistor.parse(f"{prefix}18100JTP", "RES") == "1218_10R_5%", prefix
        assert ralec_resistor.parse(f"{prefix}20100JTP", "RES") == "1020_10R_5%", prefix
        assert ralec_resistor.parse(f"{prefix}25100JTP", "RES") == "1225_10R_5%", prefix


def test_a_size_outside_a_series_range_is_refused() -> None:
    """ARST starts at 01 and RAR at 03; a code outside the printed table is not
    a part that series makes."""
    assert ralec_resistor.parse("RAR02100JTP", "RES") is None
    assert ralec_resistor.parse("ARST00100JTP", "RES") is None
    assert ralec_resistor.parse("RTW02100JTP", "RES") is None


# --- resistance spellings the catalogue states ------------------------------


def test_resistance_forms_from_the_catalogue() -> None:
    """3-digit, R-decimal, 4-digit and jumper forms, with the catalogue's values."""
    assert ralec_resistor.parse("RTT02100JTH", "RES") == "0402_10R_5%"  # 100 = 10 ohm
    assert ralec_resistor.parse("RTT024R7FTH", "RES") == "0402_4.7R_1%"  # 4R7 = 4.7
    assert ralec_resistor.parse("RTT021002FTH", "RES") == "0402_10K_1%"  # 1002 = 10 k
    assert ralec_resistor.parse("RTT0210R2FTH", "RES") == "0402_10.2R_1%"  # 10R2
    assert ralec_resistor.parse("RTT02000JTH", "RES") == "0402_0R_5%"  # JUMPER = 000


def test_sub_ohm_codes_put_r_at_the_decimal_point() -> None:
    """The low-resistance pages print R050=0.05, R100=0.1, R240=0.24."""
    assert ralec_resistor.parse("AHH03R050JTP", "RES") == "0603_0.05R_5%"
    assert ralec_resistor.parse("RTW06R240FTP", "RES") == "0612_0.24R_1%"
    assert ralec_resistor.parse("RTG25R100FTE", "RES") == "2512_0.1R_1%"
    assert ralec_resistor.parse("RTR06R150FTH", "RES") == "1206_0.15R_1%"


def test_r100_is_not_read_as_a_bare_100() -> None:
    """R100 is 0.1 ohm. Read as plain digits it would be 10 ohm, a 100x error."""
    assert ralec_resistor.parse("RTT02R100FTH", "RES") == "0402_0.1R_1%"
    assert ralec_resistor.parse("RTT02100FTH", "RES") == "0402_10R_1%"


# --- the extra field exists only where the catalogue documents one ----------


def test_thin_film_series_require_their_tcr_letter() -> None:
    """RTX021002BDTH is tolerance B then TCR D; the letter cannot be dropped."""
    assert ralec_resistor.parse("RTX021002BDTH", "RES") == "0402_10K_0.1%"
    assert ralec_resistor.parse("RTX021002BTH", "RES") is None


def test_fos_series_require_their_fos_letter() -> None:
    """RST02100JATH is tolerance J then FoS A (60 C)."""
    assert ralec_resistor.parse("RST02100JATH", "RES") == "0402_10R_5%"
    assert ralec_resistor.parse("RST02100JTH", "RES") is None


def test_series_without_an_extra_field_reject_one() -> None:
    """RTT has no TCR or FoS field, so a spare letter means a different part."""
    assert ralec_resistor.parse("RTT02100JTH", "RES") == "0402_10R_5%"
    assert ralec_resistor.parse("RTT02100JBTH", "RES") is None


# --- per-series tolerance and packing lists ---------------------------------


def test_tolerance_list_is_per_series() -> None:
    """RTR's page prints B/D/F only; RTG's prints D/F/J; neither has G."""
    assert ralec_resistor.parse("RTR02100FTH", "RES") == "0402_10R_1%"
    assert ralec_resistor.parse("RTR02100JTH", "RES") is None
    assert ralec_resistor.parse("RTG02100JTH", "RES") == "0402_10R_5%"
    assert ralec_resistor.parse("RTG02100GTH", "RES") is None


def test_packing_list_is_per_series() -> None:
    """AHH's page lists TP only."""
    assert ralec_resistor.parse("AHH03100JTP", "RES") == "0603_10R_5%"
    assert ralec_resistor.parse("AHH03100JTH", "RES") is None
    assert ralec_resistor.parse("RTT02100JZZ", "RES") is None


def test_catalog_example_uses_th_although_its_table_omits_it() -> None:
    """FTT page 80 lists TP and TE but its own printed example is FTT02100JTH.

    The example is part of the datasheet, so TH has to be accepted; the table on
    that page is incomplete rather than the example wrong.
    """
    assert ralec_resistor.parse("FTT02100JTH", "RES") == "0402_10R_5%"


# --- series the catalogue does not let us resolve ---------------------------


def test_rhw_is_refused_because_the_catalogue_contradicts_itself() -> None:
    """Page 62 prints 06=1206 for RHW, page 64 prints 06=0612 for the same
    prefix, and the part number cannot say which product it belongs to."""
    for pn in ("RHW06100JTP", "RHW02100JTH", "RHW06100FTE", "RHW05100FTP"):
        assert ralec_resistor.parse(pn, "RES") is None, pn


def test_arrays_are_refused_because_they_are_a_different_structure() -> None:
    """RAA02-4D100JTH inserts a circuit count and a terminal-type field."""
    for pn in (
        "RAA02-4D100JTH",
        "RTA02-4D100JTH",
        "RSA02-2D100JATH",
        "RTN02-10T100JTP",
    ):
        assert ralec_resistor.parse(pn, "RES") is None, pn


# --- no collision with other vendors ----------------------------------------


def test_ralec_does_not_claim_other_vendors_resistors() -> None:
    assert ralec_resistor.parse("GRM188R61A106MA73D", "RES") is None
    assert ralec_resistor.parse("WR04X1001FTL", "RES") is None
    assert ralec_resistor.parse("WW25NR005JT", "RES") is None
    assert ralec_resistor.parse("RC0603FR-0710KL", "RES") is None
    assert ralec_resistor.parse("ARG03C1002DT", "RES") is None


def test_ralec_parts_still_reach_the_vendor_phase() -> None:
    """Through the arbiter the accepted Ralec parts decode, the refused ones
    fall through as ``None`` rather than being guessed elsewhere."""
    assert _parse("RTT02100JTH", "RES") == "0402_10R_5%"
    assert _parse("RTW06100JTP", "RES") == "0612_10R_5%"
    assert _parse("RTX021002BDTH", "RES") == "0402_10K_0.1%"
    assert _parse("RHW06100JTP", "RES") is None
    assert _parse("RAA02-4D100JTH", "RES") is None


def test_ralec_is_wired_for_resistors_only() -> None:
    assert ralec_resistor.parse("RTT02100JTH", "CAP") is None
    assert ralec_resistor.parse("RTT02100JTH", "IND") is None
