"""Datasheet-pinned regression tests for the four vendor capacitor codecs that had
**only** golden rows.

``src/pn_original/`` carries one codec per vendor, but only some of them have a
dedicated test file. ``darfon_capacitor``, ``eyang_capacitor``,
``fenghua_capacitor`` and ``viiyong_capacitor`` had none: the only thing pinning
them was the 14 / 10 / 10 / 7 sample rows in ``datasheet/<vendor>.md`` that
``tests/test_parser_generated.py`` executes as assertions. A whole lookup table
can therefore be wrong as long as a handful of rows happen to survive - and each
of these four *was* wrong when last checked against its datasheet:

* Darfon decoded **0 of the 632** real part numbers in its own catalogue: the
  old pattern pinned the T.C. field to a literal ``NP`` + three digits, which ate
  the ``0`` of ``NP0`` as the first capacitance digit and then demanded a literal
  ``CG``.
* Eyang could not parse ``X7T`` / ``X7S`` / ``X6T``, and a part carrying the
  ``L`` (15 %) or ``N`` (30 %) tolerance returned ``None`` outright.
* Fenghua read its rated voltage as V/10 although the sheet specifies the EIA
  mantissa-exponent form (``101`` = 100 V, ``202`` = 2 kV), and it had no ``X``
  (X5R) branch at all.
* Viiyong's pattern *required* the sequence ``N...T``, so the manufacturer's own
  ``V226M0402X5R6R3NCT`` and ``V180J0201C0G500NAT`` did not match.

Every ``expected`` value below is transcribed **literally** from the
manufacturer table named in that test's docstring. No assertion reads a codec's
own lookup table and compares it to itself, which would pass even when the table
is wrong. Page numbers are the PDF page of the gitignored local copy under
``datasheet/pdf/``, with the printed page in brackets.

Datasheet sources
-----------------
* Darfon - "MLCC Catalogue / General Purpose", Rev. 202510.
  ``datasheet/pdf/darfon_101 MLCC Catalogue_General Purpose.pdf`` (67 pp.).
* Eyang - "Multilayer Ceramic Chip Capacitors for General Purpose / Model
  selection reference book", SPEC-CAC20260331.
  ``datasheet/pdf/eyang_cap.pdf`` (65 pp.).
* Fenghua - "MLCC - NPO (COG)" and "Multilayer Ceramic Capacitors - X7R".
  ``datasheet/pdf/Fenghua _MLCC-NPO.pdf`` (5 pp.) and
  ``datasheet/pdf/Fenghua _MLCC-X7R.pdf`` (6 pp.).
* Viiyong - "Multi-layer Ceramic Chip Capacitor - Product Specification for
  General Purpose (Reference Sheet)", V2, 2023-11-10
  (``viiyong_v180j0201c0g500nat_new.pdf``, 14 pp.) and the Version A / 2019-08-07
  sheet that prints the code tables (``viiyong_v180j0201c0g500nat.pdf``,
  10 pp.).

One unresolved disagreement with the Darfon datasheet is recorded rather than
asserted - see ``test_darfon_0603_is_eia_0201_not_0603``.
"""

from __future__ import annotations

import pytest

import pn_original
from pn_original import (
    darfon_capacitor,
    eyang_capacitor,
    fenghua_capacitor,
    viiyong_capacitor,
    walsin_mlcc_capacitor,
)

# --------------------------------------------------------------------------
# Cross-vendor part numbers: one real part number per vendor (plus two close
# calls).  Each must be refused by every codec *except* the one that owns it.
# Sources: Murata "GRM"; Walsin "How To Order" ``0805 B 104 K 500 C T``;
# Samsung "Multilayer Ceramic Chip Capacitors" ``CL10B104KB8NNNC``;
# Eyang "Part Number System" ``C 0402 C0G 120 J 500 N T``; Darfon ordering code
# ``C 1005 NP0 101 J G T S``; Viiyong ``V 226 M 0402 X5R 6R3 N C T``;
# Fenghua "How to Order" ``0805 CG 102 J 500 N T``.
# --------------------------------------------------------------------------
MURATA_GRM = "GRM155R61A106ME11D"
WALSIN_B = "0402B104K500CT"
SAMSUNG_CL = "CL10B104KB8NNNC"
EYANG_C0603 = "C0603X5R105MET"
DARFON_C0603 = "C0603X5R101KCT"
VIIYONG_V226 = "V226M0402X5R6R3NCT"
FENGHUA_CG = "0402CG100J500NT"

FOREIGN_CAP_PNS = (
    MURATA_GRM,
    WALSIN_B,
    SAMSUNG_CL,
    EYANG_C0603,
    DARFON_C0603,
    VIIYONG_V226,
    FENGHUA_CG,
)


def _foreign_for(*own: str) -> tuple[str, ...]:
    """The cross-vendor set with the calling codec's own examples removed.

    ``EYANG_C0603`` and ``DARFON_C0603`` are both ``C`` + 4-digit size + T.C. +
    3 digits + 2 letters and are the closest thing the Eyang and Darfon codecs
    have to a collision, so the pair is added back as a *cross* case for both of
    them: each must refuse the other's example.
    """
    return tuple(p for p in FOREIGN_CAP_PNS if p not in own)


def _parse(pn: str, ctype: str = "CAP") -> str | None:
    """Rebuild the vendor registry, then run the arbiter over it."""
    pn_original.CONVERTERS.clear()
    pn_original.load_converters()
    return pn_original.parse_pn(pn, ctype, None)


# ==========================================================================
# Darfon (达方) - "MLCC Catalogue / General Purpose", Rev. 202510
# ==========================================================================

# "VOLTAGE CODE  T: 2.5V  B: 4V  C: 6.3V  D: 10V  E: 16V  F: 25V  N: 35V
#  G: 50V  H: 100V  J: 200V  K: 250V  L: 500V  M: 630V  P: 1KV  Q: 2KV
#  R: 3KV  S: 4KV" - ordering code, PDF p.2 (printed p.4).  The previous codec
# read a *digit* here and then hard-coded 50 V, so 16 of the 17 codes were wrong.
DARFON_VOLTAGE_LETTERS = [
    ("T", "2.5V"),
    ("B", "4V"),
    ("C", "6.3V"),
    ("D", "10V"),
    ("E", "16V"),
    ("F", "25V"),
    ("N", "35V"),
    ("G", "50V"),
    ("H", "100V"),
    ("J", "200V"),
    ("K", "250V"),
    ("L", "500V"),
    ("M", "630V"),
    ("P", "1kV"),
    ("Q", "2kV"),
    ("R", "3kV"),
    ("S", "4kV"),
]

# "TOLERANCE CODE  A: +/-0.05pF  B: +/-0.1pF  C: +/-0.25pF  D: +/-0.5pF
#  F: +/-1%  G: +/-2%  J: +/-5%  K: +/-10%  M: +/-20%" - same page.
DARFON_TOLERANCE_LETTERS = [
    ("A", "0.05pF"),
    ("B", "0.1pF"),
    ("C", "0.25pF"),
    ("D", "0.5pF"),
    ("F", "1%"),
    ("G", "2%"),
    ("J", "5%"),
    ("K", "10%"),
    ("M", "20%"),
]

# "T. C.  X8G: 0 +/- 30ppm/C  X8R: +/-15% ... NP0: 0 +/- 30ppm/C ...
#  X7R: +/-15%  X7S: +/-22%  X7T: +22%/-33%  X7U: +22%/-56% ...
#  X6S: +/-22%  X6T: +22%/-33% ...  X5R: +/-15%" - same page.  Ten codes.
DARFON_TC_CODES = [
    "NP0",
    "X8G",
    "X8R",
    "X7R",
    "X7S",
    "X7T",
    "X7U",
    "X6S",
    "X6T",
    "X5R",
]

# "SIZE in mm (EIA CODE, in inch)" - ordering code, PDF p.2 (printed p.4).  The
# size field is L x W in units of 0.1 mm, which is why ``0603`` (0.6 x 0.3 mm)
# is an EIA **0201**.  The right-hand member of each printed pair is confirmed
# twice more in the package tables: paper tape "PRODUCT SIZE CODE C0603(0201)
# C1005(0402)" (PDF p.53, printed p.55) and embossed tape "PRODUCT SIZE CODE
# 1608(0603) 2012(0805) 3216(1206) 3225(1210) 4520(1808) 4532(1812)"
# (PDF p.54, printed p.56).
DARFON_METRIC_SIZES = [
    ("1005", "0402"),
    ("1608", "0603"),
    ("2012", "0805"),
    ("3216", "1206"),
    ("3225", "1210"),
    ("4520", "1808"),
    ("4532", "1812"),
]


@pytest.mark.parametrize(
    "letter,expected_volts",
    DARFON_VOLTAGE_LETTERS,
    ids=[f"{v}" for _c, v in DARFON_VOLTAGE_LETTERS],
)
def test_darfon_seventeen_voltage_letters(letter: str, expected_volts: str) -> None:
    """Ordering code, VOLTAGE CODE row: all 17 single-letter voltage codes.

    Darfon "MLCC Catalogue / General Purpose" Rev. 202510, PDF p.2 (printed
    p.4).  Part ``C0603NP0101J<x>T`` varies only the voltage field: ``0603`` is
    the size field, ``NP0`` the T.C., ``101`` is 10 x 10^1 pF = 100 pF per the
    CAPACITANCE CODE rule on the same page (the NP0 table prints that part
    number next to "100 pF", PDF p.5 / printed p.7), ``J`` = +/-5 % from the
    TOLERANCE CODE row, and ``T`` = paper tape reel 7" from PACKAGING CODE.
    """
    pn = f"C0603NP0101J{letter}T"
    assert _parse(pn) == f"0201_100pF_C0G_5%_{expected_volts}"


@pytest.mark.parametrize(
    "letter,expected_tol",
    DARFON_TOLERANCE_LETTERS,
    ids=[t for _c, t in DARFON_TOLERANCE_LETTERS],
)
def test_darfon_nine_tolerance_codes(letter: str, expected_tol: str) -> None:
    """Ordering code, TOLERANCE CODE row: 4 absolute-pF + 5 percentage codes.

    Darfon "MLCC Catalogue / General Purpose" Rev. 202510, PDF p.2 (printed p.4),
    repeated per series ("Tolerance Code: A=+/-0.05pF ... K=+/-10%, M=+/-20%",
    PDF p.18 / printed p.20).  The four class-1 absolute codes are the ones the
    old pattern dropped.
    """
    pn = f"C0603NP0101{letter}GT"
    assert _parse(pn) == f"0201_100pF_C0G_{expected_tol}_50V"


@pytest.mark.parametrize(
    "tc,expected_film",
    [(tc, "C0G" if tc == "NP0" else tc) for tc in DARFON_TC_CODES],
    ids=lambda p: p,
)
def test_darfon_ten_temperature_characteristic_codes(
    tc: str, expected_film: str
) -> None:
    """Ordering code, T. C. block: every T.C. code the catalogue prints.

    Darfon "MLCC Catalogue / General Purpose" Rev. 202510, PDF p.2 (printed p.4).
    The old pattern was pinned to a literal ``NP`` + three digits, so nine of
    these ten could never be reached.  The class-1 code ``NP0`` is the only one
    that cleans to a different name (C0G); the nine class-2 codes pass through
    unchanged, which is what the catalogue calls them.
    """
    pn = f"C0603{tc}105KGT"
    assert _parse(pn) == f"0201_1uF_{expected_film}_10%_50V"


def test_darfon_class_one_tc_is_spelled_np0_not_npo() -> None:
    """The class-1 T.C. code is the three characters ``NP0`` with a zero.

    Darfon "MLCC Catalogue / General Purpose" Rev. 202510, PDF p.2 (printed p.4)
    lists ``NP0``; every class-1 part number in the catalogue is ``C<size>NP0<cap>
    <tol><volt><pack>``, e.g. ``C0603NP0240JGTS`` (PDF p.4, printed p.6).
    The old pattern's literal ``NP`` consumed that ``0`` as the first
    capacitance digit, which is why 0 of 632 catalogue part numbers parsed.
    """
    assert _parse("C0603NP0240JGT") == "0201_24pF_C0G_5%_50V"
    assert _parse("C0603NP0201JGT") == "0201_200pF_C0G_5%_50V"
    # ...and the emitted film is the class-1 name, not the literal code.
    assert _parse("C0603NP0240JGT").split("_")[2] == "C0G"


@pytest.mark.parametrize(
    "metric,eia", DARFON_METRIC_SIZES, ids=[m for m, _e in DARFON_METRIC_SIZES]
)
def test_darfon_metric_size_spelling(metric: str, eia: str) -> None:
    """Size field written metric: ``1005`` means a 1.0 x 0.5 mm, i.e. EIA 0402.

    Darfon "MLCC Catalogue / General Purpose" Rev. 202510, PDF p.2 (printed p.4)
    size row, corroborated by the embossed-tape package table
    "PRODUCT SIZE CODE 1608(0603) 2012(0805) 3216(1206) 3225(1210) 4520(1808)
    4532(1812)" (PDF p.54, printed p.56) and by the catalogue's own series
    headings, e.g. "C1005X5R Series (EIA0402)" (PDF p.20, printed p.22).
    """
    pn = f"C{metric}X5R105KGT"
    assert _parse(pn) == f"{eia}_1uF_X5R_10%_50V"


@pytest.mark.parametrize(
    "eia", ["0805", "1206", "1210", "1808", "1812"], ids=lambda v: v
)
def test_darfon_eia_size_spelling_is_refused(eia: str) -> None:
    """The right-hand member of each printed pair is NOT a Darfon size code.

    The catalogue prints each size as ``<mm> (<EIA>)``, which makes it tempting to
    accept the EIA code too - and that is the trap. The two sets overlap:
    ``0603`` is a 0.6 x 0.3 mm body (EIA 0201) while ``1608`` is a 1.6 x 0.8 mm
    body (EIA 0603). Treating the EIA column as a size field reported every
    ``C0603`` part as 0603 instead of 0201, a ~2.7x oversize package. Only the
    metric column is accepted.
    """
    assert _parse(f"C{eia}X5R105KGT") is None


def test_darfon_0603_is_eia_0201_not_0603() -> None:
    """The size field is L x W in units of 0.1 mm, so ``0603`` is EIA **0201**.

    Three places in "MLCC Catalogue / General Purpose" Rev. 202510 say so: the
    paper-tape package table heads its column "PRODUCT SIZE CODE C0603(0201)"
    (PDF p.53, printed p.55), the class-1 series heading reads "C0603NP0 Series
    (EIA0201)" (PDF p.4, printed p.6), and the 0201 tape pocket
    (0.68 x 0.38 mm) cannot take a 1.6 x 0.8 mm body.
    """
    assert _parse("C0603X5R105MET") == "0201_1uF_X5R_20%_16V"
    assert _parse("C0603NP0240JGT") == "0201_24pF_C0G_5%_50V"


def test_darfon_all_nine_size_pairs_resolve_as_printed() -> None:
    """Every pair of the catalogue's Ordering Code block, verbatim.

    The block prints all nine in one run: 0402(01005) 0603(0201) 1005(0402)
    1608(0603) 2012(0805) 3216(1206) 3225(1210) 4520(1808) 4532(1812).
    """
    expected = {
        "0402": "01005",
        "0603": "0201",
        "1005": "0402",
        "1608": "0603",
        "2012": "0805",
        "3216": "1206",
        "3225": "1210",
        "4520": "1808",
        "4532": "1812",
    }
    for mm, eia in expected.items():
        assert _parse(f"C{mm}NP0101JGT") == f"{eia}_100pF_C0G_5%_50V", mm


@pytest.mark.parametrize(
    "pn,expected",
    [
        # NP0 series table, PDF p.4 (printed p.6). The last digit is the power of
        # ten except 8 (0.20-0.99 pF) and 9 (1.0-9.9 pF). Size 0603 = EIA 0201.
        ("C0603NP0108GTS", "0201_0.1pF_C0G_2%_2.5V"),
        ("C0603NP0208GTS", "0201_0.2pF_C0G_2%_2.5V"),
        ("C0603NP0758GTS", "0201_0.75pF_C0G_2%_2.5V"),
        ("C0603NP0908GTS", "0201_0.9pF_C0G_2%_2.5V"),
        ("C0603NP0109GTS", "0201_1pF_C0G_2%_2.5V"),
        ("C0603NP0229GTS", "0201_2.2pF_C0G_2%_2.5V"),
        ("C0603NP0249GTS", "0201_2.4pF_C0G_2%_2.5V"),
        ("C0603NP0919GTS", "0201_9.1pF_C0G_2%_2.5V"),
        ("C0603NP0100GTS", "0201_10pF_C0G_2%_2.5V"),
        ("C0603NP0180GTS", "0201_18pF_C0G_2%_2.5V"),
        ("C0603NP0220GTS", "0201_22pF_C0G_2%_2.5V"),
        ("C0603NP0680GTS", "0201_68pF_C0G_2%_2.5V"),
    ],
)
def test_darfon_capacitance_code_third_digit(pn: str, expected: str) -> None:
    """Third capacitance digit is the power of ten, except 8 and 9.

    Darfon "MLCC Catalogue / General Purpose" Rev. 202510, ordering code PDF p.2
    (printed p.4): "Expressed in pico-farads and identified by a three-digit
    number.  First two digits represent significant figures.  Last digit
    specifies the number of zeros.  (Use 9 for 1.0 through 9.9pF; Use 8 for
    0.20 through 0.99pF)".  Every expected value is the pF figure the NP0
    table prints next to that part number (PDF p.4, printed p.6).
    """
    assert _parse(pn) == expected


@pytest.mark.parametrize(
    "pn,expected",
    [
        # C1005X5R series table, PDF p.20 (printed p.22): the N block is 35 V.
        ("C1005X5R224KNT", "0402_220nF_X5R_10%_35V"),
        ("C1005X5R104MNT", "0402_100nF_X5R_20%_35V"),
        # C0603X5R series table, PDF p.18 (printed p.20): 331 nF at E = 16 V and
        # 1.0 uF +/-20 % at E = 16 V.
        ("C0603X5R331KET", "0201_330pF_X5R_10%_16V"),
        ("C0603X5R105MET", "0201_1uF_X5R_20%_16V"),
        ("C1005X5R475MFT", "0402_4.7uF_X5R_20%_25V"),
        # NP0 series table, PDF p.4 (printed p.6): 0.50 pF, tolerance C.
        ("C1005NP0508CGTS", "0402_0.5pF_C0G_0.25pF_50V"),
    ],
)
def test_darfon_catalogue_part_numbers(pn: str, expected: str) -> None:
    """Part numbers printed in the Darfon catalogue, with the RV of each block.

    Darfon "MLCC Catalogue / General Purpose" Rev. 202510, NP0 / X5R series
    tables (PDF p.4 printed p.6 and PDF p.18 / p.20 printed p.22).  ``G`` =
    50 V, ``N`` = 35 V, ``E`` = 16 V, ``F`` = 25 V, ``T`` = 2.5 V, ``B`` = 4 V,
    ``C`` = 6.3 V, ``D`` = 10 V, per the VOLTAGE CODE row on PDF p.2.
    """
    assert _parse(pn) == expected


@pytest.mark.parametrize(
    "pn",
    [
        # No C product code: field 1 of the ordering code is mandatory.
        "0603X5R105KGT",
        # Y5V is not a T.C. in this catalogue (PDF p.2 lists ten, none is Y5V).
        "C0603Y5V105KGT",
        # Size codes outside the printed size row.
        "C0903X5R105KGT",
        "C01005X5R105KGT",
        "C0201X5R105KGT",
        # Voltage field is mandatory, so it may not be dropped.
        "C0603X5R105K",
        # T.C. must be three characters.
        "C0603NP101JGT",
    ],
    ids=lambda p: p,
)
def test_darfon_rejects_malformed_part_numbers(pn: str) -> None:
    """Every mandatory ordering-code field has to be present and in the table.

    Darfon "MLCC Catalogue / General Purpose" Rev. 202510, PDF p.2 (printed p.4):
    ``C 1005 NP0 101 J G T S`` - product code, size, three-character T.C.,
    three-digit capacitance, tolerance, voltage.  A size outside the printed
    size row, or a T.C. that is not one of the ten printed codes, is not a
    Darfon part number.
    """
    assert darfon_capacitor.parse(pn, "CAP") is None


@pytest.mark.parametrize("pn", _foreign_for(DARFON_C0603, EYANG_C0603), ids=lambda p: p)
def test_darfon_does_not_claim_other_vendors_part_numbers(pn: str) -> None:
    """A Darfon codec must return ``None`` for every other vendor's format."""
    assert darfon_capacitor.parse(pn, "CAP") is None, pn


def test_darfon_rejects_non_capacitor_component_types() -> None:
    """Field 1 ``C`` is the MLCC product code; the codec is CAP-only."""
    assert darfon_capacitor.parse("C0603NP0240JGT", "RES") is None
    assert darfon_capacitor.parse("C0603NP0240JGT", "IND") is None


# ==========================================================================
# Eyang (宇阳) - "Multilayer Ceramic Chip Capacitors for General Purpose"
# ==========================================================================

# "1.1 Temperature Characteristics:  Class1 ... C0G  Class2 ... X7R\X7T\X7S\
# X6S\X6T\X5R" - PDF p.2 (printed p.2).  X7T, X7S and X6T were missing from the
# old table, so those parts returned ``None`` and lost size, capacitance,
# dielectric *and* voltage.
EYANG_DIELECTRICS = ["C0G", "X7R", "X7T", "X7S", "X6S", "X6T", "X5R"]

# "5 Capacitance Tolerance ... A +/-0.05pF  B +/-0.1pF  C +/-0.25pF  D +/-0.5pF
#  P +/-0.02pF  F +/-1%  G +/-2%  J +/-5%  K +/-10%  L +/-15%  M +/-20%
#  N +/-30%  S +50%/-20%  X +22%/-33%  Y +150%/-20%  Z +80%/-20%" - PDF p.4.
# The seven percentage codes below are all of them.
EYANG_TOLERANCES = [
    ("F", "1%"),
    ("G", "2%"),
    ("J", "5%"),
    ("K", "10%"),
    ("L", "15%"),
    ("M", "20%"),
    ("N", "30%"),
]

# "6 Rated Voltage ... 100 10V  160 16V  4R0 4.0V  6R3 6.3V  2R5 2.5V  630 63V
#  350 35V  500 50V  250 25V" - PDF p.5 (printed p.5).  "1.4 Rated Voltage:
# DC 2.5V to 63V" - PDF p.2.  A plain V/10 scaling, not the EIA exponent form
# Fenghua uses.
EYANG_VOLTAGES = [
    ("2R5", "2.5V"),
    ("4R0", "4.0V"),
    ("6R3", "6.3V"),
    ("100", "10V"),
    ("160", "16V"),
    ("250", "25V"),
    ("350", "35V"),
    ("500", "50V"),
    ("630", "63V"),
]

# "1.2 Size Code: A8A4(008004)\0105(01005)\0201\0402\0603\0805\1206\1210"
# - PDF p.2.  The list below is every code in that row that is four digits wide;
# ``A8A4`` (and its alias ``008004``) is not, so it is not exercised here.
EYANG_SIZES = ["0105", "0201", "0402", "0603", "0805", "1206", "1210"]


@pytest.mark.parametrize("diel", EYANG_DIELECTRICS)
def test_eyang_seven_dielectric_codes(diel: str) -> None:
    """Temperature-characteristic field, all seven codes of section 1.1.

    Eyang "Multilayer Ceramic Chip Capacitors for General Purpose",
    PDF p.2, section 1.1: "Class1 (Temperature Compensating Type): C0G /
    Class2 (High dielectric constant type): X7R\\X7T\\X7S\\X6S\\X6T\\X5R".
    The per-dielectric change figures are repeated in the section-2 table
    (X7T +22%/-33%, X7S +/-22%, X6S +/-22%, X6T +22%/-33%, X7R +/-15%,
    X5R +/-15%, C0G 0 +/-30 ppm/C), PDF p.4.
    """
    pn = f"C0402{diel}105M500NTB"
    assert _parse(pn) == f"0402_1uF_{diel}_20%_50V"


@pytest.mark.parametrize(
    "letter,expected_tol", EYANG_TOLERANCES, ids=[t for _c, t in EYANG_TOLERANCES]
)
def test_eyang_seven_percentage_tolerance_codes(letter: str, expected_tol: str) -> None:
    """Capacitance-tolerance field, section 5, including ``L`` and ``N``.

    Eyang "Multilayer Ceramic Chip Capacitors for General Purpose",
    PDF p.4, section 5: F +/-1%, G +/-2%, J +/-5%, K +/-10%, L +/-15%,
    M +/-20%, N +/-30%.  ``L`` and ``N`` were absent from the old table, and
    because the pattern *required* a tolerance letter that made the whole part
    unparseable instead of merely dropping a field.
    """
    pn = f"C0402X7R221{letter}500NTB"
    assert _parse(pn) == f"0402_220pF_X7R_{expected_tol}_50V"


@pytest.mark.parametrize("code,expected_volts", EYANG_VOLTAGES, ids=lambda p: p)
def test_eyang_rated_voltage_codes(code: str, expected_volts: str) -> None:
    """Rated-voltage field: V/10 for the digit forms, ``dRd`` for the decimals.

    Eyang "Multilayer Ceramic Chip Capacitors for General Purpose", PDF p.5,
    section 6: ``100`` 10 V, ``160`` 16 V, ``250`` 25 V, ``350`` 35 V,
    ``500`` 50 V, ``630`` 63 V, ``4R0`` 4.0 V, ``6R3`` 6.3 V, ``2R5`` 2.5 V.
    Section 1.4 on PDF p.2 caps the range at "DC 2.5V to 63V", so the whole
    table is covered and no code above 63 V may appear.
    """
    pn = f"C0402X7R221J{code}NTB"
    assert _parse(pn) == f"0402_220pF_X7R_5%_{expected_volts}"


def test_eyang_voltage_is_tenths_not_eia_exponent() -> None:
    """Eyang's digit codes are a plain division by ten.

    Eyang "Multilayer Ceramic Chip Capacitors for General Purpose", PDF p.5,
    section 6: ``630`` = 63 V.  Fenghua's identical-looking code ``101`` means
    100 V because *its* sheet (NPO, PDF p.1) specifies the EIA mantissa-exponent
    form; the two conventions must not be shared.  Eyang never publishes a
    three-digit code whose last digit is non-zero, so every code it does
    publish lands on the same value under either reading - which is exactly why
    the two sheets have to be kept apart.
    """
    assert _parse("C0402X7R221J630NTB") == "0402_220pF_X7R_5%_63V"
    assert _parse("C0402X7R221J500NTB") == "0402_220pF_X7R_5%_50V"
    # Fenghua's 101 is 100 V, not 10.1 V - assert the contrast through Fenghua.
    assert _parse("0402B101J101NT") == "0402_100pF_X7R_5%_100V"


@pytest.mark.parametrize("size", EYANG_SIZES, ids=lambda s: s)
def test_eyang_size_codes(size: str) -> None:
    """Size-code field, section 1.2, every four-digit code it publishes.

    Eyang "Multilayer Ceramic Chip Capacitors for General Purpose", PDF p.2,
    section 1.2: "A8A4(008004)\\0105(01005)\\0201\\0402\\0603\\0805\\1206\\
    1210".  The dimension table on PDF p.2/3 pairs ``0105`` with 0.40 x 0.20 mm
    and ``0201`` with 0.60 x 0.30 mm.
    """
    pn = f"C{size}X7R221J500NTB"
    assert _parse(pn) == f"{size}_220pF_X7R_5%_50V"


@pytest.mark.parametrize(
    "pn,expected",
    [
        # Section 2 "Part Number System", PDF p.2/3, worked example
        # "C 0402 C0G 120 J 500 N T": 0402 / C0G / 12 pF / 5 % / 50 V.
        ("C0402C0G120J500NTB", "0402_12pF_C0G_5%_50V"),
        # "4 Nominal Capacitance (Unit: pF) ... Example: 120=12x100=12pF,
        # 104=10x104=100000 pF=100 nF" - PDF p.4.
        ("C0402C0G104J500NTB", "0402_100nF_C0G_5%_50V"),
        ("C0402C0G105M500NTB", "0402_1uF_C0G_20%_50V"),
        # Section 1.1 lists X7T / X6T / X7S; the old table had only X7R and X5R.
        ("C0402X7T120L250NTB", "0402_12pF_X7T_15%_25V"),
        ("C0402X7S330K100NTB", "0402_33pF_X7S_10%_10V"),
        ("C0402X6T105M630NTB", "0402_1uF_X6T_20%_63V"),
        ("C0402X6S105M630NTB", "0402_1uF_X6S_20%_63V"),
        # Section 5 tolerance N = +/-30 %.
        ("C0402C0G120N500NTB", "0402_12pF_C0G_30%_50V"),
        # Section 6 decimals.
        ("C0201X5R334M6R3NTJ", "0201_330nF_X5R_20%_6.3V"),
        ("C0402C0G120J2R5NTB", "0402_12pF_C0G_5%_2.5V"),
    ],
)
def test_eyang_part_number_system_fields(pn: str, expected: str) -> None:
    """Every field of section 2's nine-position part-number system, in order.

    Eyang "Multilayer Ceramic Chip Capacitors for General Purpose", PDF p.2
    section 2 (field order 1-9: series C, size, T.C., capacitance, tolerance,
    rated voltage, termination, packaging, thickness), PDF p.4 section 4 for the
    capacitance examples, PDF p.4 section 5 for the tolerance letters, and
    PDF p.5 section 6 for the voltage codes.
    """
    assert _parse(pn) == expected


@pytest.mark.parametrize(
    "pn",
    [
        # Y5V is not in section 1.1 (C0G, X7R, X7T, X7S, X6S, X6T, X5R).
        "C0402Y5V105M500NTB",
        # Section 5 tolerance letter is mandatory - an omitted tolerance is not
        # an Eyang part number.
        "C0402X7R221500NTB",
        # Section 1 series code C is mandatory.
        "0402X7R221J500NTB",
        # Section 6 voltage field is mandatory and is either dRd or 3 digits.
        "C0402X7R221JNTB",
        # ``4R0`` / ``6R3`` belong only in the rated-voltage field, never in the
        # temperature-characteristic slot.
        "C0402X6R0105M500NTB",
    ],
    ids=lambda p: p,
)
def test_eyang_rejects_malformed_part_numbers(pn: str) -> None:
    """Fields the section-2 system requires, but which this codec refuses.

    Eyang "Multilayer Ceramic Chip Capacitors for General Purpose", PDF p.2
    (series / size / T.C. / capacitance / tolerance / rated voltage) and PDF p.4
    section 1.1 (the closed list of temperature characteristics).  ``Y5V`` is
    deliberately not one of them.
    """
    assert eyang_capacitor.parse(pn, "CAP") is None


@pytest.mark.parametrize("pn", _foreign_for(EYANG_C0603, DARFON_C0603), ids=lambda p: p)
def test_eyang_does_not_claim_other_vendors_part_numbers(pn: str) -> None:
    """An Eyang codec must return ``None`` for every other vendor's format.

    The two Darfon examples are the close calls: both are ``C`` + 4-digit size
    + 3-character T.C. + 3 digits + letter, but Eyang's rated-voltage field
    (PDF p.5) is ``dRd`` or three digits, never a single letter, so the Darfon
    ``C0603X5R105MET`` / ``C0603X5R101KCT`` endings cannot satisfy it.
    """
    assert eyang_capacitor.parse(pn, "CAP") is None, pn


def test_eyang_rejects_non_capacitor_component_types() -> None:
    """Field 1 ``C`` is the MLCC series code; the codec is CAP-only."""
    assert eyang_capacitor.parse("C0402X7R221J500NTB", "RES") is None
    assert eyang_capacitor.parse("C0402X7R221J500NTB", "OTHER") is None


# ==========================================================================
# Fenghua (风华) - "MLCC - NPO (COG)" + "Multilayer Ceramic Capacitors - X7R"
# ==========================================================================

# "Rated Voltage 160 16x10^0  250 25x10^0  500 50x10^0  630 63x10^0
#  101 10x10^1  201 20x10^1  501 50x10^1  102 10x10^2  202 20x10^2" - X7R
# "How to Order", PDF p.1; the NPO sheet prints the same nine codes on its
# PDF p.1.  Mantissa-exponent, *not* the V/10 form Eyang/Darfon/Viiyong use.
FENGHUA_VOLTAGES = [
    ("160", "16V"),
    ("250", "25V"),
    ("500", "50V"),
    ("630", "63V"),
    ("101", "100V"),
    ("201", "200V"),
    ("501", "500V"),
    ("102", "1000V"),
    ("202", "2000V"),
]


@pytest.mark.parametrize("code,expected_volts", FENGHUA_VOLTAGES, ids=lambda p: p)
def test_fenghua_rated_voltage_is_eia_mantissa_exponent(
    code: str, expected_volts: str
) -> None:
    """Rated-voltage field: the mantissa-exponent code, never divided by ten.

    Fenghua "Multilayer Ceramic Capacitors - X7R", "How to Order", PDF p.1,
    section E: ``160`` 16x10^0, ``250`` 25x10^0, ``500`` 50x10^0,
    ``630`` 63x10^0, ``101`` 10x10^1, ``201`` 20x10^1, ``501`` 50x10^1,
    ``102`` 10x10^2, ``202`` 20x10^2.  The identical table appears on the NPO
    sheet, PDF p.1.  Reading ``101`` as V/10 reported 10.1 V for a 100 V part
    and ``202`` as 20.2 V for a 2 kV part; the two conventions only coincide on
    codes ending in 0, which is why the error survived on 16/25/50/63 V parts.
    """
    pn = f"0402B101J{code}NT"
    assert _parse(pn) == f"0402_100pF_X7R_5%_{expected_volts}"


def test_fenghua_high_voltage_codes_are_not_div_ten() -> None:
    """The four codes a V/10 reading gets wrong outright: 101, 501, 102, 202.

    Fenghua "MLCC - NPO (COG)", "HOW TO ORDER", PDF p.1, section E lists
    ``101`` 100 V, ``501`` 500 V, ``102`` 1000 V and ``202`` 2000 V; the X7R
    sheet, PDF p.1, gives them as 10x10^1, 50x10^1, 10x10^2 and 20x10^2.
    ``0402X104M101NT`` (``X`` = X5R, ``104`` = 100 nF, ``101`` = 100 V) must
    therefore read 100 V, not 10.1 V.
    """
    assert _parse("0402X104M101NT") == "0402_100nF_X5R_20%_100V"
    assert _parse("0805CG102M501NT") == "0805_1nF_C0G_20%_500V"
    assert _parse("0805CG102M202NT") == "0805_1nF_C0G_20%_2000V"


@pytest.mark.parametrize(
    "code,expected_film",
    [("B", "X7R"), ("X", "X5R")],
    ids=["B-X7R", "X-X5R"],
)
def test_fenghua_class_two_dielectric_codes(code: str, expected_film: str) -> None:
    """Dielectric field: ``B`` is X7R and ``X`` is X5R.

    Fenghua "Multilayer Ceramic Capacitors - X7R", "How to Order", PDF p.1,
    section B: "Dielectric  B  X7R / X  X5R".  The previous pattern hard-wired
    ``B`` to X7R and had no ``X`` branch at all, so every X5R part returned
    ``None`` and lost its size, capacitance, tolerance and voltage with it.
    """
    pn = f"0402{code}104M101NT"
    assert _parse(pn) == f"0402_100nF_{expected_film}_20%_100V"


@pytest.mark.parametrize("code", ["CG", "COG"])
def test_fenghua_class_one_dielectric_codes(code: str) -> None:
    """Class-1 dielectric field: ``CG`` and ``COG`` are both printed.

    Fenghua "MLCC - NPO (COG)", "HOW TO ORDER", PDF p.1, section B prints
    "CG  COG  (NPO)" as the two accepted spellings of the class-1 dielectric,
    and the worked example is ``0805 CG 102 J 500 N T``.  Both clean to C0G.
    """
    pn = f"0805{code}102J630SB"
    assert _parse(pn) == "0805_1nF_C0G_5%_63V"


@pytest.mark.parametrize(
    "code,expected_cap",
    [
        ("0R5", "0.5pF"),
        ("1R0", "1pF"),
        ("2R2", "2.2pF"),
        ("5R6", "5.6pF"),
        ("8R2", "8.2pF"),
    ],
    ids=lambda p: p,
)
def test_fenghua_r_decimal_capacitance(code: str, expected_cap: str) -> None:
    """Capacitance field: an ``R`` stands in for the decimal point.

    Fenghua "MLCC - NPO (COG)", "HOW TO ORDER", PDF p.1, section C prints
    ``1R0`` = 1 pF next to ``100`` = 10 pF; PDF p.2 then uses ``0R5`` throughout
    the capacitance-range tables ("0R5~471" for 0402 at 16 V).  The X7R sheet,
    PDF p.1, states the rule: "If there is a decimal place it is represented by
    a 'R'.  In this scenario all figures are significant digit."  A bare
    three-digit field cannot match these, so they used to return ``None``.
    """
    pn = f"0402CG{code}C500NT"
    assert _parse(pn) == f"0402_{expected_cap}_C0G_0.25pF_50V"


@pytest.mark.parametrize(
    "letter,expected_tol",
    [
        # NPO sheet PDF p.1, section D.
        ("B", "0.1pF"),
        ("C", "0.25pF"),
        ("D", "0.5pF"),
        ("F", "1%"),
        ("G", "2%"),
        ("J", "5%"),
        ("K", "10%"),
        ("M", "20%"),
        # X7R sheet PDF p.2, Table 1 "Capacitance Tolerance K=+/-10% M=+/-20%
        # S=+/-50%/-20%".
        ("S", "+50%/-20%"),
    ],
    ids=lambda p: p,
)
def test_fenghua_tolerance_codes(letter: str, expected_tol: str) -> None:
    """Capacitance-tolerance field, both sheets, including the three absolute.

    Fenghua "MLCC - NPO (COG)" PDF p.1, section D: ``B`` +/-0.10 pF,
    ``C`` +/-0.25 pF, ``D`` +/-0.5 pF (absolute, class 1), ``F`` +/-1.0 %,
    ``G`` +/-2.0 %, ``J`` +/-5.0 %, ``K`` +/-10 %, ``M`` +/-20 %.
    "Multilayer Ceramic Capacitors - X7R" PDF p.2, Table 1 adds
    ``S`` = +50 %/-20 %.  The absolute codes and ``S`` were missing, and since
    the pattern *required* a tolerance letter each of them made the whole part
    unparseable rather than merely dropping a field.
    """
    pn = f"0402CG101{letter}500NT"
    assert _parse(pn) == f"0402_100pF_C0G_{expected_tol}_50V"


@pytest.mark.parametrize(
    "tail",
    ["NT", "ST", "NB", "SB"],
    ids=lambda t: t,
)
def test_fenghua_termination_and_packaging_pairs(tail: str) -> None:
    """Termination (F) x packaging (G): S/N x T/B, and nothing else.

    Fenghua "MLCC - NPO (COG)", "HOW TO ORDER", PDF p.1: F = "S Silver No Mark /
    N Nickel Barrier Tin Plating", G = "T Tape & Reel / B Bulk Package"; the X7R
    sheet PDF p.1 prints the same four codes.  The pairs are therefore exactly
    ST, NT, SB and NB - enumerating them is what stops this codec claiming
    Walsin's parts, which reuse the same ``B``/``X``/``CG`` bodies with a
    ``CT`` tape suffix.
    """
    pn = f"0402CG101J500{tail}"
    assert _parse(pn) == "0402_100pF_C0G_5%_50V"
    assert fenghua_capacitor.parse(pn, "CAP") == "0402_100pF_C0G_5%_50V"


@pytest.mark.parametrize(
    "pn,expected",
    [
        # NPO sheet PDF p.1 worked example and its table rows.
        ("0402CG101J500NT", "0402_100pF_C0G_5%_50V"),
        ("0805COG102J630SB", "0805_1nF_C0G_5%_63V"),
        ("0402CG1R0B160SB", "0402_1pF_C0G_0.1pF_16V"),
        ("0805CG102M501NT", "0805_1nF_C0G_20%_500V"),
        ("0805CG102M202NT", "0805_1nF_C0G_20%_2000V"),
        # X7R sheet: "0805 B 104 K 500 N T" (PDF p.1) and the tolerance/voltage
        # tables on PDF p.2.
        ("0402B223K250NT", "0402_22nF_X7R_10%_25V"),
        ("0805B104K500NT", "0805_100nF_X7R_10%_50V"),
        ("0805B201M101NT", "0805_200pF_X7R_20%_100V"),
        ("0402B101S630NT", "0402_100pF_X7R_+50%/-20%_63V"),
        # The X5R (dielectric X) line, which the previous pattern had no branch for.
        ("0402X104M101NT", "0402_100nF_X5R_20%_100V"),
    ],
)
def test_fenghua_datasheet_part_numbers(pn: str, expected: str) -> None:
    """The seven ordering fields, both sheets, at the values each sheet prints.

    Fenghua "MLCC - NPO (COG)" PDF p.1 ("HOW TO ORDER": size / dielectric /
    capacitance / tolerance / rated voltage / termination / packaging) and
    "Multilayer Ceramic Capacitors - X7R" PDF p.1 ("How to Order":
    ``0805 B 104 K 500 N T``) with its Table 1 tolerance and rated-voltage
    lists on PDF p.2.
    """
    assert _parse(pn) == expected


@pytest.mark.parametrize(
    "tail",
    ["NA", "TT", "NTB", "NNT", "N", "CT"],
    ids=lambda t: t,
)
def test_fenghua_rejects_wrong_packaging_suffix(tail: str) -> None:
    """Only S/N termination x T/B packaging is a Fenghua part number.

    Fenghua "MLCC - NPO (COG)", PDF p.1, columns F and G: termination is
    S (silver, no mark) or N (nickel barrier, tin plating); packaging is
    T (tape & reel) or B (bulk package).  No other pair exists, so a tail with
    a third character, or ``CT``, is either malformed or another vendor's
    (``CT`` is the Walsin ``C`` = Cu/Ni/Sn termination with ``T`` = 7" reel,
    Walsin "MLCC Product Catalog", "How To Order").
    """
    pn = f"0402CG101J500{tail}"
    assert _parse(pn) is None
    assert fenghua_capacitor.parse(pn, "CAP") is None


@pytest.mark.parametrize(
    "pn",
    [
        # No dielectric code at all.
        "0402101J500NT",
        # Y5V is not one of CG / COG / B / X.
        "0402Y5V101J500NT",
        # 15 % (L) is not in either Fenghua tolerance table (NPO p.1 has
        # B C D F G J K M; X7R p.2 adds S).
        "0402B101L500NT",
        # ``0R5`` is a valid capacitance, but the tolerance letter after it is not.
        "0402CG0R500NT",
    ],
    ids=lambda p: p,
)
def test_fenghua_rejects_malformed_part_numbers(pn: str) -> None:
    """Fields the ordering code requires, in the codes the sheets actually print.

    Fenghua "MLCC - NPO (COG)" PDF p.1 (sections A-G) and "Multilayer Ceramic
    Capacitors - X7R" PDF p.1 (sections A-G): dielectric is one of
    CG / COG / B / X, capacitance is three EIA digits *or* ``dRd``, and the
    tolerance letter must come from the sheet's own table.
    """
    assert fenghua_capacitor.parse(pn, "CAP") is None


@pytest.mark.parametrize("pn", _foreign_for(FENGHUA_CG, WALSIN_B), ids=lambda p: p)
def test_fenghua_does_not_claim_other_vendors_part_numbers(pn: str) -> None:
    """A Fenghua codec must return ``None`` for every other vendor's format."""
    assert fenghua_capacitor.parse(pn, "CAP") is None, pn


def test_fenghua_nt_bodies_are_claimed_by_fenghua_not_walsin() -> None:
    """``…NT`` is Fenghua's; ``…CT`` is Walsin's, and neither codec steals it.

    Fenghua's termination (NPO p.1, column F) is S or N, so its part numbers end
    in ``NT`` / ``ST`` / ``NB`` / ``SB``.  Walsin's "MLCC Product Catalog",
    "How To Order and Packaging Dimension/Quantity", prints
    ``0805 B 104 K 500 C T`` - termination ``L`` (Ag/Ni/Sn) or ``C`` (Cu/Ni/Sn),
    packaging ``T`` / ``Q`` / ``G`` - so a Walsin part never ends in ``NT``.
    (``datasheet/fenghua_capacitor.md`` states that Walsin has the higher
    ``PARSER_PRIORITY`` and wins the tie; the priorities actually registered are
    Fenghua 86 and Walsin_MLCC 65, so Fenghua is consulted first.  Either way
    the observable result is the one asserted here.)
    """
    fenghua_pn = "0402B104K500NT"
    assert fenghua_capacitor.parse(fenghua_pn, "CAP") == "0402_100nF_X7R_10%_50V"
    assert walsin_mlcc_capacitor.parse(fenghua_pn, "CAP") is None
    assert _parse(fenghua_pn) == "0402_100nF_X7R_10%_50V"
    assert _parse(fenghua_pn) == fenghua_capacitor.parse(fenghua_pn, "CAP")

    walsin_pn = "0402B104K500CT"
    assert walsin_mlcc_capacitor.parse(walsin_pn, "CAP") == "0402_100nF_X7R_50V_10%"
    assert fenghua_capacitor.parse(walsin_pn, "CAP") is None
    assert _parse(walsin_pn) == walsin_mlcc_capacitor.parse(walsin_pn, "CAP")


def test_fenghua_rejects_non_capacitor_component_types() -> None:
    """The ordering code carries no ``C`` series marker; the codec is CAP-only."""
    assert fenghua_capacitor.parse("0402CG101J500NT", "RES") is None
    assert fenghua_capacitor.parse("0402CG101J500NT", "IND") is None


# ==========================================================================
# Viiyong (Guangdong Viiyong Electronic Technology) - general-purpose MLCC sheet
# ==========================================================================

# 2019 Version A sheet, PDF p.2, section 2 "Part Number System"
# "V 103 K 0201 X5R 250 N A *" with the legend "Rated Capacitance For example:
# 103=10nF  474=470nF" and "Rated Voltage 6R3=6.3V;100=10V 160=16V; 250=25V
# 500=50V".
VIIYONG_VOLTAGES = [
    ("6R3", "6.3V"),
    ("100", "10V"),
    ("160", "16V"),
    ("250", "25V"),
    ("500", "50V"),
]

# 2019 sheet PDF p.3, Table 2 "Type of dielectrics": NP0, C0G, C0H, X7R, X5R,
# X5S, Y5V.  Section 1.3 on PDF p.2 names C0G, X7R, X5R, X5S, Y5V.
VIIYONG_DIELECTRICS = ["C0G", "X7R", "X5R", "X5S", "Y5V"]

# 2019 sheet PDF p.2, "Capacitance Tolerance A: +/-0.05pF  B: +/-0.1pF
# C: +/-0.25pF  D: +/-0.5pF  F: +/-1%  G: +/-2%  J: +/-5%  K: +/-10%
# L: +/-15%  M: +/-20%  Z: +80/-20%  N: +/-30%  X: +/-40%  Y: +150/-20%".
VIIYONG_TOLERANCES = [("J", "5%"), ("K", "10%"), ("M", "20%")]

# 2019 sheet PDF p.2, "Size Code (EIA size) 0105(01005) 0201(0201)" with
# Table 1 dimensions (01005 = 0.40 x 0.20 mm, 0201 = 0.60 x 0.30 mm); the
# 2023 sheet PDF p.2 uses 0402 (1.00 x 0.50 mm, PDF p.2/5).
VIIYONG_SIZES = ["0105", "0201", "0402"]


def test_viiyong_datasheet_nct_part_number() -> None:
    """The sheet's own title part number, field by field.

    Viiyong "Multi-layer Ceramic Chip Capacitor - Product Specification for
    General Purpose (Reference Sheet)" V2 / 2023-11-10, PDF p.1:
    ``V226M0402X5R6R3NCT (0402, X5R, 22uF, +/-20%, 6.3V)``.  PDF p.2 spells the
    nine positions out: "V 226 M 0402 X5R 6R3 N C T" with (7) Terminal
    Electrodes Ni-Sn Plating, (8) Thickness, (9) VIIYONG Control Code.
    """
    pn = "V226M0402X5R6R3NCT"
    assert _parse(pn) == "0402_22uF_X5R_20%_6.3V"
    assert viiyong_capacitor.parse(pn, "CAP") == "0402_22uF_X5R_20%_6.3V"


def test_viiyong_datasheet_nat_part_number() -> None:
    """The other datasheet form, ending ``NAT`` rather than ``NCT``.

    Viiyong Version A / 2019-08-07 sheet, PDF p.1 title block:
    ``V224M0201X5R160NJ*``, and PDF p.2 section 2:
    ``V 103 K 0201 X5R 250 N A *`` - position (7) is the ``N`` Ni-Sn terminal,
    (8) the thickness letter, (9) the control code.  ``V180J0201C0G500NAT``
    is the same shape with thickness ``A`` and control code ``T``; ``180`` is a
    three-digit capacitance field, so this part is 18 pF, C0G, +/-5 %, 50 V.
    """
    pn = "V180J0201C0G500NAT"
    assert _parse(pn) == "0201_18pF_C0G_5%_50V"
    assert viiyong_capacitor.parse(pn, "CAP") == "0201_18pF_C0G_5%_50V"


@pytest.mark.parametrize(
    "tail",
    ["NCT", "NAT", "NXT", "NAJ", "NCZ"],
    ids=lambda t: t,
)
def test_viiyong_terminal_thickness_control_forms(tail: str) -> None:
    """Fields 7-9: terminal ``N``, then a thickness letter, then a control code.

    Viiyong 2023 sheet, PDF p.2, annotates (7) "Terminal Electrodes: Ni-Sn
    Plating" and prints ``...6R3 N C T``, i.e. terminal ``N``, thickness ``C``,
    control code ``T``.  The 2019 sheet, PDF p.2, prints
    ``V 103 K 0201 X5R 250 N A *`` with Table 1 thickness codes Z (01005) and
    A / J / X (0201).  So ``NCT`` and ``NAT`` are the ordinary endings, not
    variants: the previous pattern ended at ``N(?:AT|BT|XT)$`` and therefore
    matched neither of the manufacturer's own printed examples.
    """
    pn = f"V226M0402X5R6R3{tail}"
    assert _parse(pn) == "0402_22uF_X5R_20%_6.3V"


@pytest.mark.parametrize("diel", VIIYONG_DIELECTRICS)
def test_viiyong_dielectric_codes(diel: str) -> None:
    """Temperature-characteristic field: the five codes the sheet names.

    Viiyong Version A sheet, PDF p.2 section 1.3 "Type of Dielectrics:
    C0G, X7R, X5R, X5S, Y5V", and PDF p.3 Table 2 "Type of dielectrics" adds
    the class-1 aliases NP0 and C0H.  The old pattern accepted only the first
    three entries, so X5S and Y5V parts returned ``None``.
    """
    pn = f"V226M0402{diel}6R3NCT"
    assert _parse(pn) == f"0402_22uF_{diel}_20%_6.3V"


@pytest.mark.parametrize("code,expected_volts", VIIYONG_VOLTAGES, ids=lambda p: p)
def test_viiyong_rated_voltage_codes(code: str, expected_volts: str) -> None:
    """Rated-voltage field: the ``dRd`` decimal plus the V/10 digit block.

    Viiyong Version A sheet, PDF p.2, "Rated Voltage 6R3=6.3V;100=10V
    160=16V; 250=25V 500=50V".  V/10 like Eyang / TCC / Darfon - *not* the EIA
    exponent form Fenghua and Walsin publish.
    """
    pn = f"V226M0402X5R{code}NCT"
    assert _parse(pn) == f"0402_22uF_X5R_20%_{expected_volts}"


@pytest.mark.parametrize(
    "letter,expected_tol", VIIYONG_TOLERANCES, ids=[t for _c, t in VIIYONG_TOLERANCES]
)
def test_viiyong_tolerance_codes(letter: str, expected_tol: str) -> None:
    """Capacitance-tolerance field, section 3 of the ordering code.

    Viiyong Version A sheet, PDF p.2, "Capacitance Tolerance ... F: +/-1%
    G: +/-2%  J: +/-5%  K: +/-10%  L: +/-15%  M: +/-20%  Z: +80/-20%
    N: +/-30%  X: +/-40%  Y: +150/-20%" plus the four absolute class-1 codes
    A / B / C / D.  J, K and M are the ones the codec decodes.
    """
    pn = f"V226{letter}0402X5R6R3NCT"
    assert _parse(pn) == f"0402_22uF_X5R_{expected_tol}_6.3V"


@pytest.mark.parametrize("size", VIIYONG_SIZES, ids=lambda s: s)
def test_viiyong_size_codes(size: str) -> None:
    """Size field: 01005 / 0201 on the 2019 sheet, 0402 on the 2023 sheet.

    Viiyong Version A sheet, PDF p.2, "Size Code (EIA size) 0105(01005)
    0201(0201)" with Table 1 dimensions 0.40 x 0.20 mm and 0.60 x 0.30 mm;
    the 2023 sheet, PDF p.2 and PDF p.5, uses 0402 (1.00 x 0.50 mm).
    """
    pn = f"V226M{size}X5R6R3NCT"
    assert _parse(pn) == f"{size}_22uF_X5R_20%_6.3V"


@pytest.mark.parametrize(
    "code,expected_cap",
    [("103", "10nF"), ("104", "100nF"), ("105", "1uF"), ("474", "470nF")],
    ids=lambda p: p,
)
def test_viiyong_capacitance_is_eia_three_digit(code: str, expected_cap: str) -> None:
    """Capacitance field: three EIA digits, first two significant.

    Viiyong Version A sheet, PDF p.2, "Rated Capacitance For example:
    103=10nF  474=470nF" - i.e. ``XY x 10^Z`` pF, exactly the EIA convention.
    ``474`` is therefore 470 nF, not 4.7 uF.
    """
    pn = f"V{code}M0402X5R6R3NCT"
    assert _parse(pn) == f"0402_{expected_cap}_X5R_20%_6.3V"


@pytest.mark.parametrize(
    "pn,expected",
    [
        ("V226M0402X5R6R3NCT", "0402_22uF_X5R_20%_6.3V"),  # 2023 sheet, PDF p.1
        ("V180J0201C0G500NAT", "0201_18pF_C0G_5%_50V"),  # 2019 sheet shape
        ("V105K0201X5R160NXT", "0201_1uF_X5R_10%_16V"),  # 2019 sheet, PDF p.2
        ("V475M0805X7R6R3NCT", "0805_4.7uF_X7R_20%_6.3V"),
        ("V104K0402Y5V6R3NCT", "0402_100nF_Y5V_10%_6.3V"),
    ],
)
def test_viiyong_part_number_system_fields(pn: str, expected: str) -> None:
    """All nine positions of section 2's part-number system, at the sheet values.

    Viiyong 2023 sheet PDF p.2, "2.Part Number System ... V 226 M 0402 X5R 6R3
    N C T", and Version A sheet PDF p.2, "V 103 K 0201 X5R 250 N A *" with the
    capacitance / tolerance / rated-voltage / terminal legends that follow it.
    """
    assert _parse(pn) == expected


@pytest.mark.parametrize(
    "pn",
    [
        # Section 1 series code V is mandatory.
        "226M0402X5R6R3NCT",
        # Section 3 tolerance letter is mandatory and is one of the printed set.
        "V226X0402X5R6R3NCT",
        "V226A0402X5R6R3NCT",
        # Section 6 rated voltage is mandatory and is dRd or a 3-digit block.
        "V226M0402X5RNCT",
        "V226M0402X5R6NC",
        # Field (7) terminal: the sheet gives exactly one type, N (Ni-Sn / Cu-Ni-Sn).
        "V226M0402X5R6R3JAT",
        # Size field is four digits.
        "V226M402X5R6R3NCT",
    ],
    ids=lambda p: p,
)
def test_viiyong_rejects_malformed_part_numbers(pn: str) -> None:
    """Fields the nine-position system requires, but which this codec refuses.

    Viiyong 2023 sheet PDF p.2 (positions 1-9) and Version A sheet PDF p.2,
    section 1.3 "Capacitance Tolerance" and the "Rated Voltage" and "Terminal
    Type" legends.  ``X`` (+/-40 %) and ``A`` (+/-0.05 pF) *are* printed in the
    sheet's tolerance table but are not decoded; the list above only pins the
    structural rejections.
    """
    assert viiyong_capacitor.parse(pn, "CAP") is None


@pytest.mark.parametrize("pn", _foreign_for(VIIYONG_V226), ids=lambda p: p)
def test_viiyong_does_not_claim_other_vendors_part_numbers(pn: str) -> None:
    """A Viiyong codec must return ``None`` for every other vendor's format.

    Field (1) is the single letter ``V`` and field (4) a 4-digit size, which is
    what keeps the ``C…`` and bare-``0402…`` bodies of the other three out.
    """
    assert viiyong_capacitor.parse(pn, "CAP") is None, pn


def test_viiyong_rejects_non_capacitor_component_types() -> None:
    """Field 1 ``V`` is the Viiyong series marker; the codec is CAP-only."""
    assert viiyong_capacitor.parse("V226M0402X5R6R3NCT", "RES") is None
    assert viiyong_capacitor.parse("V226M0402X5R6R3NCT", "IND") is None


# ==========================================================================
# Arbiter reachability: the vendor phase must actually claim these parts
# ==========================================================================


@pytest.mark.parametrize(
    "pn,expected",
    [
        ("C0603NP0240JGT", "0201_24pF_C0G_5%_50V"),
        ("C0603X5R105MET", "0201_1uF_X5R_20%_16V"),
        ("C1005X5R224KNT", "0402_220nF_X5R_10%_35V"),
        ("C0402X7T120L250NTB", "0402_12pF_X7T_15%_25V"),
        ("C0402X6S105M630NTB", "0402_1uF_X6S_20%_63V"),
        ("0805CG102M202NT", "0805_1nF_C0G_20%_2000V"),
        ("0402X104M101NT", "0402_100nF_X5R_20%_100V"),
        ("0402B101S630NT", "0402_100pF_X7R_+50%/-20%_63V"),
        ("V226M0402X5R6R3NCT", "0402_22uF_X5R_20%_6.3V"),
        ("V180J0201C0G500NAT", "0201_18pF_C0G_5%_50V"),
    ],
)
def test_arbiter_reaches_the_four_vendor_capacitor_codecs(
    pn: str, expected: str
) -> None:
    """``parse_pn`` must return each codec's value, not a rival vendor's.

    ``pn_original.parse_pn`` consults the converters in ``PARSER_PRIORITY``
    order and returns the first non-empty result, so a codec that only works
    when called directly is invisible to the pipeline.  These ten parts cover
    one datasheet row per vendor plus the previously unreachable codes
    (Darfon letter voltages, Eyang X7T/X6S, Fenghua 2 kV and ``S`` tolerance,
    Viiyong ``NCT``/``NAT``); each expected string is the literal datasheet
    value from the vendor test that sits above it.
    """
    assert _parse(pn) == expected


def test_arbiter_returns_none_for_nonsense_capacitor_input() -> None:
    """Sanity floor: the arbiter still declines input no vendor publishes."""
    for junk in ("", "NOT-A-PN", "MLCC_1uF_X7R_50V_10%", "????????"):
        assert _parse(junk) is None, junk
