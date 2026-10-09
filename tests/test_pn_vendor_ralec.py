"""Ralec chip-resistor codec.

There was no Ralec codec at all before this one, so every Ralec part number in a
BOM fell through the vendor phase untouched. The expectations here come from the
manufacturer's own "Explanation Of Part Numbers" sections in the SMD Resistor
Components catalogue 2022 and from product specification IE-SP-010.

The tests are mostly about *which* series claims a part number and *which size
table* it uses, because that is where a generic pattern would silently attach the
wrong imperial size.

Why the tables are pinned *independently*

A mutation experiment injected two real defects into the codec - RAW's ``06``
changed from 0612 to 1206, and ARST's ``02`` from 0402 to 0201 - and the whole
suite stayed green, because the wide-terminal table was only ever asserted
through ``RTW`` and the standard table only through ``RTT``. Of the 147 size
codes in the 23 series, 119 had no assertion anywhere.

So the tables below are transcribed from the catalogue pages named beside each
row (page numbers are the catalogue's own printed page numbers, which match the
PDF page order), and the codec is compared against that transcription rather
than against itself. A test that walked ``_SERIES`` and asserted the codec
agreed with itself would still pass with either mutation in place, because
``parse()`` returns whatever the table says.
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


# --- the two size tables, transcribed from the catalogue --------------------
#
# Ralec's size code is its own, not the inch code. Two tables are in use and
# they disagree about the same codes, which is the entire reason every prefix
# carries its own size table:

STANDARD_TABLE = {
    # printed on every standard series page, e.g. RTT p.51, ARST p.34, RAT p.18
    "01": "0201",
    "02": "0402",
    "03": "0603",
    "05": "0805",
    "06": "1206",
    "12": "1210",
    "18": "1812",
    "20": "2010",
    "25": "2512",
}

WIDE_TERMINAL_TABLE = {
    # printed on the wide-terminal pages: RAW p.21+22, RTW p.55+56, AHW p.28
    "05": "0508",
    "06": "0612",
    "18": "1218",
    "20": "1020",
    "25": "1225",
}

# The three series whose own feature list reads "Wide terminal" (RAW p.21,
# RTW p.55, AHW p.28). AHW prints the single code ``25``=1225.
WIDE_TERMINAL_SERIES = {"AHW", "RAW", "RTW"}

# Every decoded series, transcribed from its "Explanation Of Part Numbers"
# block: the catalogue pages it is printed on, its size codes, its tolerance
# letters, its packing codes and its optional extra field. Nothing below is
# derived from the codec - that is the point. If a codec entry is wrong, the
# comparison fails here instead of passing unnoticed.
_CATALOG = {
    "AHH": {
        # p.27, AHH Series Low-Resistance Thick Film Chip Resistors
        "pages": (27,),
        "sizes": {"03": "0603", "05": "0805", "06": "1206"},
        "tolerances": {"F": "1%", "J": "5%"},
        "packing": {"TP"},
        "extra": "",
        "extra_letters": "",
    },
    "AHW": {
        # p.28, AHW Series High Power Low Resistance Thick Film Chip Resistors
        "pages": (28,),
        "sizes": {"25": "1225"},
        "tolerances": {"F": "1%", "J": "5%"},
        "packing": {"TE"},
        "extra": "",
        "extra_letters": "",
    },
    "ARST": {
        # p.34, ARST Series Thick Film Chip Resistors. No ``18``: this series
        # stops at 2010/2512, unlike RTT which prints 18(1812) on p.51.
        "pages": (34,),
        "sizes": {
            "01": "0201",
            "02": "0402",
            "03": "0603",
            "05": "0805",
            "06": "1206",
            "12": "1210",
            "20": "2010",
            "25": "2512",
        },
        "tolerances": {"D": "0.5%", "F": "1%", "J": "5%"},
        "packing": {"TE", "TH", "TP"},
        "extra": "",
        "extra_letters": "",
    },
    "ARTX": {
        # p.17, ARTX Series Thin Film Chip Resistors. TCR B/C/D only, and the
        # packing table lists TP and TH but no TE.
        "pages": (17,),
        "sizes": {"02": "0402", "03": "0603", "05": "0805", "06": "1206"},
        "tolerances": {"B": "0.1%", "C": "0.25%", "D": "0.5%"},
        "packing": {"TH", "TP"},
        "extra": "TCR",
        "extra_letters": "BCD",
    },
    "FTG": {
        # p.86 anti-surge prints J/K/M, p.88 pulse-proof prints D/F; the two
        # pages together give D/F/J.
        "pages": (86, 88),
        "sizes": {"06": "1206", "12": "1210", "20": "2010", "25": "2512"},
        "tolerances": {"D": "0.5%", "F": "1%", "J": "5%"},
        "packing": {"TE", "TP"},
        "extra": "",
        "extra_letters": "",
    },
    "FTH": {
        # p.89, FTH Series Thick Film Chip Resistors
        "pages": (89,),
        "sizes": {
            "01": "0201",
            "02": "0402",
            "03": "0603",
            "05": "0805",
            "06": "1206",
            "12": "1210",
            "20": "2010",
            "25": "2512",
        },
        "tolerances": {"F": "1%", "J": "5%"},
        "packing": {"TE", "TH", "TP"},
        "extra": "",
        "extra_letters": "",
    },
    "FTT": {
        # p.80 thick film prints TP and TE as packing, but its own printed
        # example is FTT 02 100 J TH, so TH is accepted; p.82 adds the
        # low-resistance form. See the test below for the TH/TE conflict.
        "pages": (80, 82),
        "sizes": {
            "01": "0201",
            "02": "0402",
            "03": "0603",
            "05": "0805",
            "06": "1206",
            "12": "1210",
            "20": "2010",
            "25": "2512",
        },
        "tolerances": {"B": "0.1%", "D": "0.5%", "F": "1%", "J": "5%"},
        "packing": {"TE", "TH", "TP"},
        "extra": "",
        "extra_letters": "",
    },
    "RAG": {
        # p.29 anti-surge prints J only, p.31 pulse-proof prints D/F; together
        # D/F/J.
        "pages": (29, 31),
        "sizes": {
            "02": "0402",
            "03": "0603",
            "05": "0805",
            "06": "1206",
            "12": "1210",
            "20": "2010",
            "25": "2512",
        },
        "tolerances": {"D": "0.5%", "F": "1%", "J": "5%"},
        "packing": {"TE", "TH", "TP"},
        "extra": "",
        "extra_letters": "",
    },
    "RAH": {
        # p.25 thick film, p.26 low-resistance. High power, starts at 0402.
        "pages": (25, 26),
        "sizes": {
            "02": "0402",
            "03": "0603",
            "05": "0805",
            "06": "1206",
            "12": "1210",
            "20": "2010",
            "25": "2512",
        },
        "tolerances": {"B": "0.1%", "D": "0.5%", "F": "1%", "J": "5%"},
        "packing": {"TE", "TH", "TP"},
        "extra": "",
        "extra_letters": "",
    },
    "RAR": {
        # p.23 thick film, p.24 low-resistance. High precision, no 0201.
        "pages": (23, 24),
        "sizes": {
            "03": "0603",
            "05": "0805",
            "06": "1206",
            "12": "1210",
            "20": "2010",
            "25": "2512",
        },
        "tolerances": {"D": "0.5%", "F": "1%"},
        "packing": {"TE", "TH", "TP"},
        "extra": "",
        "extra_letters": "",
    },
    "RAT": {
        # p.18 thick film, p.20 low-resistance. p.18 also prints 005(01005);
        # see test_catalog_01005_code_is_not_decoded_yet.
        "pages": (18, 20),
        "sizes": {
            "01": "0201",
            "02": "0402",
            "03": "0603",
            "05": "0805",
            "06": "1206",
            "12": "1210",
            "20": "2010",
            "25": "2512",
        },
        "tolerances": {"B": "0.1%", "D": "0.5%", "F": "1%", "G": "2%", "J": "5%"},
        "packing": {"TE", "TH", "TP"},
        "extra": "",
        "extra_letters": "",
    },
    "RAV": {
        # p.33, RAV Series Thick Film Chip Resistors (high voltage)
        "pages": (33,),
        "sizes": {
            "03": "0603",
            "05": "0805",
            "06": "1206",
            "12": "1210",
            "20": "2010",
            "25": "2512",
        },
        "tolerances": {"D": "0.5%", "F": "1%", "J": "5%"},
        "packing": {"TE", "TH", "TP"},
        "extra": "",
        "extra_letters": "",
    },
    "RAW": {
        # p.21 thick film, p.22 low-resistance. Wide terminal: 05=0508,
        # 06=0612, 18=1218, 20=1020, 25=1225, and no 2 mm tape.
        "pages": (21, 22),
        "sizes": {"05": "0508", "06": "0612", "18": "1218", "20": "1020", "25": "1225"},
        "tolerances": {"D": "0.5%", "F": "1%", "J": "5%"},
        "packing": {"TE", "TP"},
        "extra": "",
        "extra_letters": "",
    },
    "RSR": {
        # p.78, RSR Series Thick Film Chip Resistors
        "pages": (78,),
        "sizes": {
            "01": "0201",
            "02": "0402",
            "03": "0603",
            "05": "0805",
            "06": "1206",
            "12": "1210",
            "20": "2010",
            "25": "2512",
        },
        "tolerances": {"D": "0.5%", "F": "1%"},
        "packing": {"TE", "TH", "TP"},
        "extra": "",
        "extra_letters": "",
    },
    "RST": {
        # p.72, RST Series Thick Film Chip Resistors. FoS test field: A=60 C,
        # B=105 C (printed as "A : 60 C" / "B :105 C").
        "pages": (72,),
        "sizes": {
            "01": "0201",
            "02": "0402",
            "03": "0603",
            "05": "0805",
            "06": "1206",
            "12": "1210",
            "20": "2010",
            "25": "2512",
        },
        "tolerances": {"B": "0.1%", "D": "0.5%", "F": "1%", "J": "5%"},
        "packing": {"TE", "TH", "TP"},
        "extra": "FOS",
        "extra_letters": "AB",
    },
    "RSV": {
        # p.79, RSV Series Thick Film Chip Resistors
        "pages": (79,),
        "sizes": {
            "03": "0603",
            "05": "0805",
            "06": "1206",
            "12": "1210",
            "20": "2010",
            "25": "2512",
        },
        "tolerances": {"D": "0.5%", "F": "1%", "J": "5%"},
        "packing": {"TE", "TP"},
        "extra": "",
        "extra_letters": "",
    },
    "RTG": {
        # p.67 anti-surge prints J/K/M, p.69 pulse-proof D/F, p.70 low
        # resistance F/J; together D/F/J.
        "pages": (67, 69, 70),
        "sizes": {
            "02": "0402",
            "03": "0603",
            "05": "0805",
            "06": "1206",
            "20": "2010",
            "25": "2512",
        },
        "tolerances": {"D": "0.5%", "F": "1%", "J": "5%"},
        "packing": {"TE", "TH", "TP"},
        "extra": "",
        "extra_letters": "",
    },
    "RTH": {
        # p.60, RTH Series Thick Film Chip Resistors
        "pages": (60,),
        "sizes": {
            "01": "0201",
            "02": "0402",
            "03": "0603",
            "05": "0805",
            "06": "1206",
            "12": "1210",
            "20": "2010",
            "25": "2512",
        },
        "tolerances": {"B": "0.1%", "D": "0.5%", "F": "1%", "J": "5%"},
        "packing": {"TE", "TH", "TP"},
        "extra": "",
        "extra_letters": "",
    },
    "RTR": {
        # p.57 thick film, p.59 low-resistance. No J on either page.
        "pages": (57, 59),
        "sizes": {
            "01": "0201",
            "02": "0402",
            "03": "0603",
            "05": "0805",
            "06": "1206",
            "12": "1210",
            "20": "2010",
            "25": "2512",
        },
        "tolerances": {"B": "0.1%", "D": "0.5%", "F": "1%"},
        "packing": {"TE", "TH", "TP"},
        "extra": "",
        "extra_letters": "",
    },
    "RTT": {
        # p.51 thick film, p.53 low-resistance. The only decoded series that
        # prints 18(1812).
        "pages": (51, 53),
        "sizes": {
            "01": "0201",
            "02": "0402",
            "03": "0603",
            "05": "0805",
            "06": "1206",
            "12": "1210",
            "18": "1812",
            "20": "2010",
            "25": "2512",
        },
        "tolerances": {"B": "0.1%", "D": "0.5%", "F": "1%", "G": "2%", "J": "5%"},
        "packing": {"TE", "TH", "TP"},
        "extra": "",
        "extra_letters": "",
    },
    "RTV": {
        # p.65, RTV Series Thick Film Chip Resistors
        "pages": (65,),
        "sizes": {
            "03": "0603",
            "05": "0805",
            "06": "1206",
            "12": "1210",
            "20": "2010",
            "25": "2512",
        },
        "tolerances": {"D": "0.5%", "F": "1%", "J": "5%"},
        "packing": {"TE", "TP"},
        "extra": "",
        "extra_letters": "",
    },
    "RTW": {
        # p.55 thick film, p.56 low-resistance. Wide terminal, same five codes
        # as RAW.
        "pages": (55, 56),
        "sizes": {"05": "0508", "06": "0612", "18": "1218", "20": "1020", "25": "1225"},
        "tolerances": {"D": "0.5%", "F": "1%", "J": "5%"},
        "packing": {"TE", "TP"},
        "extra": "",
        "extra_letters": "",
    },
    "RTX": {
        # p.49, RTX Thin Film Chip Resistors. TCR B/C/D/E.
        #
        # The catalogue prints F on this page as "+- 1.0%", where all 22 other
        # series print "1%". Transcribed verbatim it made the *same* electrical
        # part clean to two different strings depending only on the prefix
        # (RTX021002FTH -> 0402_10K_1.0% vs RTT021002FTH -> 0402_10K_1%), which
        # breaks equality-based dedup and cross-series matching. The table below
        # therefore records the normalised token; the value is unchanged.
        "pages": (49,),
        "sizes": {
            "01": "0201",
            "02": "0402",
            "03": "0603",
            "05": "0805",
            "06": "1206",
            "12": "1210",
            "20": "2010",
            "25": "2512",
        },
        "tolerances": {"B": "0.1%", "C": "0.25%", "D": "0.5%", "F": "1%"},
        "packing": {"TE", "TH", "TP"},
        "extra": "TCR",
        "extra_letters": "BCDE",
    },
}

# The catalogue's own printed example part numbers, one or two per series, each
# with the body the same page's size table gives it. These are the datasheet's
# own statements, so they cannot drift with the codec.
_PRINTED_EXAMPLES = [
    (17, "ARTX021002BDTH", "0402_10K_0.1%"),
    (18, "RAT02100JTH", "0402_10R_5%"),
    (20, "RAT05R100FTP", "0805_0.1R_1%"),
    (21, "RAW18100JTP", "1218_10R_5%"),
    (22, "RAW18R100FTP", "1218_0.1R_1%"),
    (23, "RAR051002FTP", "0805_10K_1%"),
    (24, "RAR05R100FTP", "0805_0.1R_1%"),
    (25, "RAH06103JTP", "1206_10K_5%"),
    (26, "RAH06R150FTP", "1206_0.15R_1%"),
    (27, "AHH03R050JTP", "0603_0.05R_5%"),
    (28, "AHW25R200FTE", "1225_0.2R_1%"),
    (29, "RAG06100JTP", "1206_10R_5%"),
    (31, "RAG061000FTP", "1206_100R_1%"),
    (33, "RAV05100JTP", "0805_10R_5%"),
    (34, "ARST051002FTP", "0805_10K_1%"),
    (49, "RTX021002BDTH", "0402_10K_0.1%"),
    (51, "RTT02100JTH", "0402_10R_5%"),
    (53, "RTT02R100FTH", "0402_0.1R_1%"),
    (55, "RTW06100JTP", "0612_10R_5%"),
    (56, "RTW06R240FTP", "0612_0.24R_1%"),
    (57, "RTR011002DTH", "0201_10K_0.5%"),
    (59, "RTR06R150FTH", "1206_0.15R_1%"),
    (60, "RTH02100JTH", "0402_10R_5%"),
    (65, "RTV03100JTP", "0603_10R_5%"),
    (67, "RTG05100JTP", "0805_10R_5%"),
    (69, "RTG05100FTP", "0805_10R_1%"),
    (70, "RTG25R100FTE", "2512_0.1R_1%"),
    (72, "RST02100JATH", "0402_10R_5%"),
    (74, "RST05R100FATP", "0805_0.1R_1%"),
    (78, "RSR051002FTP", "0805_10K_1%"),
    (79, "RSV03100JTP", "0603_10R_5%"),
    (80, "FTT02100JTH", "0402_10R_5%"),
    (82, "FTT02R100FTH", "0402_0.1R_1%"),
    (86, "FTG06100JTP", "1206_10R_5%"),
    (88, "FTG061002FTP", "1206_10K_1%"),
    (89, "FTH06100JTP", "1206_10R_5%"),
]


def _probe(row: dict) -> tuple[str, str, str, str]:
    """Build the tail of a probe part number from one catalogue row.

    The first tolerance letter the page prints, the first extra-field letter the
    page prints (nothing when the series has no such field) and the
    alphabetically first packing code. So the probe is itself a statement about
    what the catalogue lists.
    """
    tols = row["tolerances"]
    letter = next(iter(tols))
    return letter, tols[letter], row["extra_letters"][:1], sorted(row["packing"])[0]


def _page(row: dict) -> str:
    return "catalog p." + ", p.".join(str(n) for n in row["pages"])


def _prefix_of(pn: str) -> str:
    """The alphabetic prefix of a part number (``RAW18100JTP`` -> ``RAW``)."""
    out = ""
    for ch in pn:
        if not ch.isalpha():
            break
        out += ch
    return out


# --- the tables agree with the pages, entry by entry ------------------------


def test_every_series_and_no_other_one_is_decoded() -> None:
    """The catalogue documents 23 chip-resistor series and all 23 are here.

    A 24th series cannot be added without saying which catalogue page its table
    was read from, and a series cannot be dropped silently.
    """
    assert sorted(ralec_resistor._SERIES) == sorted(_CATALOG)


def test_size_tables_match_the_catalogue_page_by_page() -> None:
    """Each series' code -> body map is exactly what its own page prints.

    Compared against the transcription above, not against the codec: editing
    RAW's ``06`` to 1206 or ARST's ``02`` to 0201 fails here.
    """
    for prefix, row in _CATALOG.items():
        assert ralec_resistor._SERIES[prefix]["sizes"] == row["sizes"], (
            f"{prefix} ({_page(row)})"
        )


def test_each_series_accepts_exactly_its_printed_size_codes() -> None:
    """The set of codes a series accepts, as a list, so an added or dropped code
    is reported as a changed list of codes rather than as a changed mapping."""
    for prefix, row in _CATALOG.items():
        sizes = ralec_resistor._SERIES[prefix]["sizes"]
        assert sorted(sizes) == sorted(row["sizes"]), f"{prefix} ({_page(row)})"
        assert all(len(code) == 2 for code in sizes), prefix
        assert all(len(metric) == 4 for metric in sizes.values()), prefix


def test_tolerance_lists_match_the_catalogue() -> None:
    """Each series keeps its own tolerance letters and their printed values.

    e.g. RTR's pages print B/D/F and no J (p.57, p.59); RTX's print F as 1.0 %
    (p.49); RAT is the only decoded series with G (p.18).
    """
    for prefix, row in _CATALOG.items():
        assert ralec_resistor._SERIES[prefix]["tolerances"] == row["tolerances"], (
            f"{prefix} ({_page(row)})"
        )


def test_packing_lists_match_the_catalogue() -> None:
    """Packing is per series too: AHH p.27 lists TP only, AHW p.28 lists TE only.

    The wide-terminal series are packed on TP/TE and never on the 2 mm TH.
    """
    for prefix, row in _CATALOG.items():
        assert set(ralec_resistor._SERIES[prefix]["packing"]) == row["packing"], (
            f"{prefix} ({_page(row)})"
        )


def test_extra_field_letters_match_the_catalogue() -> None:
    """Only ARTX p.17 and RTX p.49 print a TCR field; only RST p.72 prints FoS.

    Everything else must not grow one, which is what keeps ``RTT02100JBTH`` a
    different part rather than a tolerated spelling.
    """
    for prefix, row in _CATALOG.items():
        spec = ralec_resistor._SERIES[prefix]
        assert spec["extra"] == row["extra"], f"{prefix} ({_page(row)})"
        assert spec["extra_letters"] == row["extra_letters"], f"{prefix} ({_page(row)})"


def test_refused_prefixes_are_exactly_the_documented_six() -> None:
    """RHW plus the five arrays, and nothing else, is refused.

    RHW is refused because p.62 prints 06=1206 (high power low resistance) and
    p.64 prints 06=0612 (wide terminal) under the same prefix.
    """
    assert set(ralec_resistor._REFUSED) == {"FTA", "RAA", "RHW", "RSA", "RTA", "RTN"}


# --- the two tables never bleed into each other -----------------------------


def test_wide_terminal_series_print_the_wide_terminal_table() -> None:
    """RAW (p.21+22) and RTW (p.55+56) print five codes, AHW (p.28) prints one.

    06 is 0612 here and 1206 on the standard pages, and 20 is 1020 here against
    2010 on the standard pages. This is the assertion the surviving mutation
    RAW 06 -> 1206 had no way to trip.
    """
    assert ralec_resistor._SERIES["RAW"]["sizes"] == {
        "05": "0508",
        "06": "0612",
        "18": "1218",
        "20": "1020",
        "25": "1225",
    }
    assert ralec_resistor._SERIES["RTW"]["sizes"] == {
        "05": "0508",
        "06": "0612",
        "18": "1218",
        "20": "1020",
        "25": "1225",
    }
    assert ralec_resistor._SERIES["AHW"]["sizes"] == {"25": "1225"}


def test_wide_terminal_series_print_no_standard_body() -> None:
    """No body from the standard table may appear in a wide-terminal series."""
    for prefix in sorted(WIDE_TERMINAL_SERIES):
        bodies = set(ralec_resistor._SERIES[prefix]["sizes"].values())
        assert not bodies & set(STANDARD_TABLE.values()), prefix


def test_standard_series_print_no_wide_terminal_body() -> None:
    """The other direction, and the one that catches a leaked wide-terminal row."""
    for prefix in sorted(set(_CATALOG) - WIDE_TERMINAL_SERIES):
        bodies = set(ralec_resistor._SERIES[prefix]["sizes"].values())
        assert not bodies & set(WIDE_TERMINAL_TABLE.values()), prefix


def test_no_series_maps_a_code_onto_the_other_table() -> None:
    """Every code a series prints must mean the same body its table gives it.

    Checks code *and* body at once against the table the series belongs to, so a
    single wrong value anywhere in the 147 entries fails.
    """
    for prefix, row in _CATALOG.items():
        table = (
            WIDE_TERMINAL_TABLE if prefix in WIDE_TERMINAL_SERIES else STANDARD_TABLE
        )
        for code, metric in ralec_resistor._SERIES[prefix]["sizes"].items():
            assert table.get(code) == metric, f"{prefix}{code} ({_page(row)})"


def test_no_body_the_codec_can_print_belongs_to_both_tables() -> None:
    """The two tables share no body, so "which table is this series on" is
    answerable from the decoded size alone."""
    assert not set(STANDARD_TABLE.values()) & set(WIDE_TERMINAL_TABLE.values())
    printed = {
        metric
        for spec in ralec_resistor._SERIES.values()
        for metric in spec["sizes"].values()
    }
    assert printed <= set(STANDARD_TABLE.values()) | set(WIDE_TERMINAL_TABLE.values())


# --- round trips through the public parser ----------------------------------


def test_the_size_field_is_exactly_what_the_catalogue_prints() -> None:
    """Every series against every code in either table: the printed body, or a
    refusal.

    This is the whole size field at once - 23 series x 9 codes - asserted
    through ``parse()``, so the tables cannot be right in the dict and wrong in
    the compiled pattern.
    """
    for prefix, row in _CATALOG.items():
        tol, tol_value, extra, pack = _probe(row)
        for code in sorted(set(STANDARD_TABLE) | set(WIDE_TERMINAL_TABLE)):
            pn = f"{prefix}{code}100{tol}{extra}{pack}"
            if code in row["sizes"]:
                expected = f"{row['sizes'][code]}_10R_{tol_value}"
                assert ralec_resistor.parse(pn, "RES") == expected, f"{pn} {_page(row)}"
            else:
                assert ralec_resistor.parse(pn, "RES") is None, f"{pn} {_page(row)}"


def test_every_tolerance_letter_a_series_prints_round_trips() -> None:
    """Each printed tolerance letter is accepted and carries its printed value.

    The second half is the other direction: a letter Ralec prints for a *different*
    series is refused here, because this page does not print it. e.g. RAV p.33
    prints D/F/J, so ``RAV05100GTH`` is a different part, not a 2 % RAV.
    """
    every_letter = set().union(*(row["tolerances"] for row in _CATALOG.values()))
    for prefix, row in _CATALOG.items():
        _, _, extra, pack = _probe(row)
        code = next(iter(row["sizes"]))
        for letter, value in row["tolerances"].items():
            pn = f"{prefix}{code}100{letter}{extra}{pack}"
            assert ralec_resistor.parse(pn, "RES") == (
                f"{row['sizes'][code]}_10R_{value}"
            ), f"{pn} {_page(row)}"
        for letter in sorted(every_letter - set(row["tolerances"])):
            pn = f"{prefix}{code}100{letter}{extra}{pack}"
            assert ralec_resistor.parse(pn, "RES") is None, f"{pn} {_page(row)}"


def test_every_packing_code_a_series_prints_round_trips() -> None:
    """Each printed packing code is accepted; a code the page omits is not."""
    for prefix, row in _CATALOG.items():
        tol, tol_value, extra, _ = _probe(row)
        code = next(iter(row["sizes"]))
        for pack in sorted(row["packing"]):
            pn = f"{prefix}{code}100{tol}{extra}{pack}"
            assert ralec_resistor.parse(pn, "RES") == (
                f"{row['sizes'][code]}_10R_{tol_value}"
            ), f"{pn} {_page(row)}"
        for pack in ("TH", "TP", "TE"):
            if pack in row["packing"]:
                continue
            pn = f"{prefix}{code}100{tol}{extra}{pack}"
            assert ralec_resistor.parse(pn, "RES") is None, f"{pn} {_page(row)}"


def test_every_printed_catalogue_example_decodes() -> None:
    """The catalogue's own example part numbers, from its own pages.

    One or two per series, each printed immediately above the size table used to
    decode it, so a whole series is pinned end to end rather than one code at a
    time. Every one of the 23 decoded series appears.
    """
    covered = set()
    for page, pn, expected in _PRINTED_EXAMPLES:
        assert ralec_resistor.parse(pn, "RES") == expected, f"{pn} (catalog p.{page})"
        covered.add(_prefix_of(pn))
    assert covered == set(_CATALOG)


# --- the two mutations that used to survive ----------------------------------


def test_raw06_is_0612_and_arst02_is_0402() -> None:
    """The two defects a mutation experiment injected, now pinned.

    ``RAW``'s ``06`` changed 0612 -> 1206 and ``ARST``'s ``02`` changed
    0402 -> 0201 in the codec while the whole suite stayed green, because the
    wide-terminal table was only reachable through RTW and the standard one
    through RTT. RAW p.21/22 and ARST p.34 decide both.
    """
    assert ralec_resistor._SERIES["RAW"]["sizes"]["06"] == "0612"
    assert ralec_resistor.parse("RAW06100JTP", "RES") == "0612_10R_5%"
    assert ralec_resistor.parse("RAW061002FTP", "RES") == "0612_10K_1%"
    assert ralec_resistor.parse("RAW06R240FTP", "RES") == "0612_0.24R_1%"
    assert ralec_resistor.parse("RAW06100JTE", "RES") == "0612_10R_5%"

    assert ralec_resistor._SERIES["ARST"]["sizes"]["02"] == "0402"
    assert ralec_resistor.parse("ARST02100JTP", "RES") == "0402_10R_5%"
    assert ralec_resistor.parse("ARST02100JTH", "RES") == "0402_10R_5%"
    assert ralec_resistor.parse("ARST02100JTE", "RES") == "0402_10R_5%"
    assert ralec_resistor.parse("ARST02R100FTP", "RES") == "0402_0.1R_1%"


def test_a_wide_terminal_and_a_standard_part_differ_only_in_the_prefix() -> None:
    """Same six characters, same packing code, different body - the reason the
    two tables exist at all. RAW p.21 prints 0612 where RTT p.51 prints 1206."""
    assert ralec_resistor.parse("RAW06100JTP", "RES") != ralec_resistor.parse(
        "RTT06100JTP", "RES"
    )
    assert ralec_resistor.parse("RAW20100JTP", "RES") == "1020_10R_5%"
    assert ralec_resistor.parse("RTW20100JTP", "RES") == "1020_10R_5%"
    assert ralec_resistor.parse("RTT20100JTP", "RES") == "2010_10R_5%"


# --- codes the catalogue prints that this codec does not decode yet ----------
#
# Both of these are open questions about the catalogue, pinned here so they are
# visible rather than forgotten. If the codec is extended to cover them, these
# two tests are what should change.


def test_catalog_01005_code_is_not_decoded_yet() -> None:
    """``005``=01005 is printed on RAT p.18, RTT p.51 and FTT p.80.

    On RTT p.51 and FTT p.80 it comes with its own packing code, H1 (2 mm pitch
    carrier tape, 20000 pcs), which the codec does not list either. Nothing
    below decodes today; that is recorded, not endorsed.
    """
    assert ralec_resistor.parse("RAT005100JTH", "RES") is None  # RAT p.18
    assert ralec_resistor.parse("RTT005100FH1", "RES") is None  # RTT p.51, H1
    assert ralec_resistor.parse("FTT005100FH1", "RES") is None  # FTT p.80, H1


def test_anti_surge_k_and_m_letters_are_not_decoded() -> None:
    """RTG p.67 and FTG p.86 print K=+-10 % and M=+-20 % beside J=+-5 %.

    Those two letters are outside Ralec's own tolerance alphabet
    (B/C/D/F/G/J), so the codec stops at J. Whether they should be decoded is
    open; today they are refused.
    """
    assert ralec_resistor.parse("RTG05100KTP", "RES") is None  # RTG p.67
    assert ralec_resistor.parse("RTG05100MTP", "RES") is None  # RTG p.67
    assert ralec_resistor.parse("FTG06100KTP", "RES") is None  # FTG p.86
    assert ralec_resistor.parse("FTG06100MTP", "RES") is None  # FTG p.86
