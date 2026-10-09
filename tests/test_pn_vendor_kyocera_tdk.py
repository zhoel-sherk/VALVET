"""Field tables for the Kyocera AVX KAM and TDK CGA automotive MLCC codecs.

Both are transcribed from ``doc/info`` and both share the same shape — a fixed
width part number, a decade-letter voltage code, and absolute class-1 tolerances
that render as a bare pF magnitude — which is why they live in one file.

What is *not* shared is the set of codes each catalogue publishes, and each is
transcribed from its own sheet rather than borrowed:

* ``Kyocera_KAM_Series.pdf`` (KAM, 15 characters) prints 7 dielectrics and 16
  voltages. Its ``0G`` is the 4 V *voltage* code sitting next to ``CG`` in the
  same row, not an eighth dielectric, and it prints no X5R code at all.
* ``TDK_mlcc_automotive_general_en.pdf`` (CGA, 20 characters, **up to 75 V**)
  prints 5 dielectrics, spells them out in full, and prints 8 voltages because
  the document is scoped to 75 V and under. A 100 V+ TDK part is not claimed.

Both real catalogues were used as a corpus, not just as a reference for the
tables: all 100 ``KAM`` part numbers printed in the Kyocera sheet and all 898
``CGA`` part numbers printed in the TDK sheet decode, with nothing refused.
"""

from __future__ import annotations

import pytest

from pn_original import kyocera_capacitor as kyocera, tdk_capacitor as tdk

# --------------------------------------------------------------------------
# Kyocera AVX KAM
# --------------------------------------------------------------------------

KYOCERA_SIZES = [
    ("03", "0201"),
    ("05", "0402"),
    ("15", "0603"),
    ("21", "0805"),
    ("31", "1206"),
    ("32", "1210"),
    ("42", "1808"),
    ("43", "1812"),
    ("55", "2220"),
]

KYOCERA_DIELECTRICS = [
    ("CG", "C0G"),
    ("R7", "X7R"),
    ("S7", "X7S"),
    ("T7", "X7T"),
    ("R8", "X8R"),
    ("L8", "X8L"),
    ("G8", "X8G"),
]

KYOCERA_VOLTAGES = [
    ("0G", "4V"),
    ("0J", "6.3V"),
    ("1A", "10V"),
    ("1C", "16V"),
    ("1E", "25V"),
    ("1H", "50V"),
    ("2A", "100V"),
    ("2D", "200V"),
    ("2E", "250V"),
    ("2H", "500V"),
    ("2J", "630V"),
    ("3A", "1000V"),
    ("3N", "1500V"),
    ("3D", "2000V"),
    ("3E", "2500V"),
    ("3U", "3000V"),
]

KYOCERA_TOLERANCES = [
    ("B", "0.1pF"),
    ("C", "0.25pF"),
    ("D", "0.5pF"),
    ("F", "1%"),
    ("G", "2%"),
    ("J", "5%"),
    ("K", "10%"),
    ("M", "20%"),
]


def _kam(size: str, thickness: str, diel: str, volt: str, cap: str, tol: str) -> str:
    """KAM + size(2) + thickness(1) + diel(2) + volt(2) + cap(3) + tol(1) + pkg(1)."""
    return f"KAM{size}{thickness}{diel}{volt}{cap}{tol}U"


@pytest.mark.parametrize("code,expected", KYOCERA_SIZES, ids=lambda p: p)
def test_kyocera_size_is_the_sheet_code(code: str, expected: str) -> None:
    out = kyocera.parse(_kam(code, "G", "R7", "1H", "475", "K"), "CAP")
    assert out is not None, f"size {code!r} was refused"
    assert out == f"{expected}_4.7uF_50V_X7R_10%"


@pytest.mark.parametrize("code,expected", KYOCERA_DIELECTRICS, ids=lambda p: p)
def test_kyocera_dielectric_is_the_sheet_code(code: str, expected: str) -> None:
    out = kyocera.parse(_kam("31", "G", code, "1H", "475", "K"), "CAP")
    assert out is not None, f"dielectric {code!r} was refused"
    assert out == f"1206_4.7uF_50V_{expected}_10%"


@pytest.mark.parametrize("code,expected", KYOCERA_VOLTAGES, ids=lambda p: p)
def test_kyocera_voltage_is_the_sheet_code(code: str, expected: str) -> None:
    out = kyocera.parse(_kam("31", "G", "R7", code, "475", "K"), "CAP")
    assert out is not None, f"voltage {code!r} was refused"
    assert out == f"1206_4.7uF_{expected}_X7R_10%"


@pytest.mark.parametrize("code,expected", KYOCERA_TOLERANCES, ids=lambda p: p)
def test_kyocera_tolerance_is_the_sheet_code(code: str, expected: str) -> None:
    out = kyocera.parse(_kam("31", "G", "R7", "1H", "475", code), "CAP")
    assert out is not None, f"tolerance {code!r} was refused"
    assert out == f"1206_4.7uF_50V_X7R_{expected}"


def test_kyocera_sheet_worked_example() -> None:
    """``KAM 31 G R7 1H 475 K U`` — the sheet's own order block example."""
    assert kyocera.parse("KAM31GR71H475KU", "CAP") == "1206_4.7uF_50V_X7R_10%"


def test_kyocera_size_15_is_0603_not_an_eia_reading() -> None:
    """Kyocera writes 0603 as ``15`` (the 1608 JIS code).

    The size table prints both forms, and the repo vocabulary is the inch name,
    so ``15`` has to be mapped rather than pattern-matched on its digits.
    """
    assert kyocera.parse(_kam("15", "G", "R7", "1H", "475", "K"), "CAP").startswith(
        "0603_"
    )


def test_kyocera_zero_g_is_a_voltage_not_a_dielectric() -> None:
    """``0G`` is the 4 V entry of the voltage column, next to ``CG`` in the same row."""
    assert kyocera.parse(_kam("31", "G", "0G", "1H", "475", "K"), "CAP") is None
    assert kyocera.parse(_kam("31", "G", "CG", "0G", "475", "K"), "CAP") == (
        "1206_4.7uF_4V_C0G_10%"
    )


def test_kyocera_publishes_no_x5r_code() -> None:
    """``R5`` is not in the sheet, so it is not accepted."""
    assert kyocera.parse(_kam("31", "G", "R5", "1H", "475", "K"), "CAP") is None


def test_kyocera_c0g_normalises() -> None:
    assert kyocera.parse(_kam("31", "L", "CG", "2J", "103", "J"), "CAP") == (
        "1206_10nF_630V_C0G_5%"
    )


@pytest.mark.parametrize(
    ("cap", "expected"),
    [("1R5", "1.5pF"), ("0R5", "0.5pF"), ("2R2", "2.2pF")],
    ids=lambda p: p,
)
def test_kyocera_r_decimal_capacitance(cap: str, expected: str) -> None:
    out = kyocera.parse(_kam("31", "L", "CG", "1H", cap, "J"), "CAP")
    assert out is not None
    assert out == f"1206_{expected}_50V_C0G_5%"


@pytest.mark.parametrize(
    "pn",
    [
        "KAF31GR71H475KU",  # FLEXITERM: a different catalogue
        "KAM31GR71H475",  # one char short
        "KAM31GR71H475KUX",  # one char long
        "KAM99GR71H475KU",  # undocumented size
        "KAM31WR91H475KU",  # undocumented dielectric
        "KAM31GR7ZH475KU",  # undocumented voltage
        "KAM31GR71H475ZU",  # undocumented tolerance
    ],
    ids=lambda p: p,
)
def test_kyocera_refuses_what_it_cannot_read(pn: str) -> None:
    assert kyocera.parse(pn, "CAP") is None


# --------------------------------------------------------------------------
# TDK CGA
# --------------------------------------------------------------------------

TDK_SIZES = [
    ("CGA1", "0201"),
    ("CGA2", "0402"),
    ("CGA3", "0603"),
    ("CGA4", "0805"),
    ("CGA5", "1206"),
    ("CGA6", "1210"),
    ("CGA8", "1812"),
    ("CGA9", "2220"),
]

TDK_DIELECTRICS = [
    ("C0G", "C0G"),
    ("X5R", "X5R"),
    ("X7R", "X7R"),
    ("X7S", "X7S"),
    ("X7T", "X7T"),
]

# Only what the sub-75 V document prints.
TDK_VOLTAGES = [
    ("0G", "4V"),
    ("0J", "6.3V"),
    ("1A", "10V"),
    ("1C", "16V"),
    ("1E", "25V"),
    ("1H", "50V"),
    ("1V", "35V"),
    ("1N", "75V"),
]

TDK_TOLERANCES = [
    ("C", "0.25pF"),
    ("D", "0.5pF"),
    ("J", "5%"),
    ("K", "10%"),
    ("M", "20%"),
]


def _cga(
    size: str,
    thickness: str,
    diel: str,
    volt: str,
    cap: str,
    tol: str,
) -> str:
    """CGA+size(4) + thick(1) + undecoded(1) + diel(3) + volt(2) + cap(3) + tol(1) + dim(3) + pack(2)."""
    return f"{size}{thickness}2{diel}{volt}{cap}{tol}030BA"


@pytest.mark.parametrize("code,expected", TDK_SIZES, ids=lambda p: p)
def test_tdk_size_is_the_sheet_code(code: str, expected: str) -> None:
    out = tdk.parse(_cga(code, "A", "X7R", "1H", "104", "K"), "CAP")
    assert out is not None, f"size {code!r} was refused"
    assert out == f"{expected}_100nF_50V_X7R_10%"


@pytest.mark.parametrize("code,expected", TDK_DIELECTRICS, ids=lambda p: p)
def test_tdk_dielectric_is_the_sheet_code(code: str, expected: str) -> None:
    out = tdk.parse(_cga("CGA5", "L", code, "1H", "104", "K"), "CAP")
    assert out is not None, f"dielectric {code!r} was refused"
    assert out == f"1206_100nF_50V_{expected}_10%"


@pytest.mark.parametrize("code,expected", TDK_VOLTAGES, ids=lambda p: p)
def test_tdk_voltage_is_the_sheet_code(code: str, expected: str) -> None:
    out = tdk.parse(_cga("CGA5", "L", "X7R", code, "104", "K"), "CAP")
    assert out is not None, f"voltage {code!r} was refused"
    assert out == f"1206_100nF_{expected}_X7R_10%"


@pytest.mark.parametrize("code,expected", TDK_TOLERANCES, ids=lambda p: p)
def test_tdk_tolerance_is_the_sheet_code(code: str, expected: str) -> None:
    out = tdk.parse(_cga("CGA5", "L", "X7R", "1H", "104", code), "CAP")
    assert out is not None, f"tolerance {code!r} was refused"
    assert out == f"1206_100nF_50V_X7R_{expected}"


def test_tdk_real_catalogue_parts_decode() -> None:
    """Real part numbers printed in the TDK sheet, spanning the field spread."""
    for pn, expected in (
        ("CGA1A2C0G1H010C030BA", "0201_1pF_50V_C0G_0.25pF"),
        ("CGA1A2C0G1H1R5C030BA", "0201_1.5pF_50V_C0G_0.25pF"),
        ("CGA3E3X5R0J335K080AB", "0603_3.3uF_6.3V_X5R_10%"),
        ("CGA6P1X7R1N106M250AC", "1210_10uF_75V_X7R_20%"),
        ("CGA9P3X7R1H226M250KB", "2220_22uF_50V_X7R_20%"),
        ("CGA3E1X7T0G106M080AC", "0603_10uF_4V_X7T_20%"),
    ):
        assert tdk.parse(pn, "CAP") == expected, pn


def test_tdk_does_not_claim_parts_above_its_75v_scope() -> None:
    """The document is capped at 75 V, so a 2A (100 V) code is not accepted.

    Claiming it would mean guessing at a table this sheet does not print; the
    full-range TDK sheet is needed instead.
    """
    assert tdk.parse(_cga("CGA5", "L", "X7R", "2A", "104", "K"), "CAP") is None


@pytest.mark.parametrize(
    "pn",
    [
        "CGA1A2C0G1H010C030B",  # one char short
        "CGA1A2C0G1H010C030BAA",  # one char long
        "CGA7A2C0G1H010C030BA",  # no CGA7 exists
        "CGA1A2XX7R1H010C030BA",  # undocumented dielectric
        "CGA1A2C0G3A010C030BA",  # 100V: outside this document's scope
        "CGA1A2C0G1H010G030BA",  # undocumented tolerance
        "CGA1A2C0G1H010C030",  # tail truncated
    ],
    ids=lambda p: p,
)
def test_tdk_refuses_what_it_cannot_read(pn: str) -> None:
    assert tdk.parse(pn, "CAP") is None


def test_the_three_mlcc_codecs_do_not_collide() -> None:
    """No part may be readable by two of these codecs.

    The arbiter picks between vendor codecs, so an overlap would make the winner
    depend on priority rather than on whose pattern is right.
    """
    from pn_original import samsung_capacitor

    kam, cga = "KAM31GR71H475KU", "CGA1A2C0G1H010C030BA"
    assert kyocera.parse(cga, "CAP") is None
    assert tdk.parse(kam, "CAP") is None
    assert samsung_capacitor.parse(kam, "CAP") is None
    assert samsung_capacitor.parse(cga, "CAP") is None


def test_neither_new_codec_claims_a_resistor() -> None:
    assert kyocera.parse("KAM31GR71H475KU", "RES") is None
    assert tdk.parse("CGA1A2C0G1H010C030BA", "RES") is None


@pytest.mark.parametrize(
    "pn",
    [
        "XAM31GR71H475KU",  # right shape, wrong series
        "KA331GR71H475KU",
        "AKM31GR71H475KU",
        "XGA1A2C0G1H010C030BA",  # TDK
        "CGB1A2C0G1H010C030BA",
        "AGA1A2C0G1H010C030BA",
    ],
    ids=lambda p: p,
)
def test_the_series_prefix_is_required_and_exact(pn: str) -> None:
    """``KAM`` and ``CGA`` must match exactly, not merely be a prefix.

    Every other field in each of these is a published code, so a codec that
    loosened the series check would decode them and nothing else would fail.
    That matters for the arbiter: a CL-shaped or KAM-shaped string belonging to
    a different vendor has to be refused here, not picked up on priority.
    """
    assert kyocera.parse(pn, "CAP") is None
    assert tdk.parse(pn, "CAP") is None


@pytest.mark.parametrize(
    ("code", "expected"),
    [("1R5", "1.5pF"), ("0R5", "0.5pF")],
    ids=lambda p: p,
)
def test_single_digit_r_decimal_is_the_published_form(code: str, expected: str) -> None:
    """Every sheet prints ``dRd`` with one digit each side of the ``R``."""
    assert tdk.parse(_cga("CGA1", "A", "C0G", "1H", code, "C"), "CAP") is not None
    assert kyocera.parse(_kam("31", "L", "CG", "1H", code, "C"), "CAP") is not None


@pytest.mark.parametrize("code", ["1R00", "0R50", "1R05", "12R3"])
def test_multi_digit_r_decimal_is_refused(code: str) -> None:
    """A two-digit fraction is refused, deliberately and unlike the resistors.

    ``decode_ohms_suffix`` collapses ``4R70`` to ``4.7`` because a chip-resistor
    sheet prints trailing zeros, but no capacitor sheet here prints a
    two-digit fraction - so these four codes are pinned as refused rather than
    left as an untested asymmetry between the two decoders. See doc/TODO.md.
    """
    assert tdk.parse(_cga("CGA1", "A", "C0G", "1H", code, "C"), "CAP") is None
    assert kyocera.parse(_kam("31", "L", "CG", "1H", code, "C"), "CAP") is None
