"""CO1271 SKU3 production BOM: TCC capacitors and Walsin ``0402CG*`` capacitors.

Ground truth is column C of the SKU3 sheet (column D holds the MPN): the
description states nominal, dielectric, voltage and tolerance for every row below.
Each ``expected`` value is the literal string the parser returned when the row was
executed — nothing here is predicted. The BOM description sits next to each case
as the evidence the value was derived from.

Two production defects are pinned here:

* **TCC** (``TCC0402…``) had no vendor parser at all. Rows classified ``CAP`` but
  fell through to the generic regex phase, which returned the MPN unchanged.
* **Walsin CG decimal-pF** (``0402CG0R5C500NT`` …) was classified ``OTHER``, so no
  capacitor parser was ever consulted: the classifier only knew the 3-digit EIA
  value form (``100`` → 10pF), not the decimal form (``0R5`` → 0.5pF).

Regression guards keep the already-working siblings honest: the 3-digit
``0402CG…`` C0G line and the real ``WR0x…`` resistors of the same BOM.
"""

from __future__ import annotations

import pytest
from tools.clean_corpus_lib import load_corpus_profile

import clean_component
import pn_original
from pn_original import tcc_capacitor

# SKU3 rows: (row, mpn, BOM description (column C), expected parser output)
TCC_ROWS = [
    (
        8,
        "TCC0402X5R104K250AT",
        "MLCC_0.1uF_X5R_25V_+/-10%_C0402_0.5MM+-0.05MM_SMD",
        "0402_100nF_X5R_10%_25V",
    ),
    (
        13,
        "TCC0402X7R224K250AT",
        "MLCC_0.22uF_X7R_25V_+/-10%_C0402_0.5MM+-0.1MM_SMD",
        "0402_220nF_X7R_10%_25V",
    ),
    (
        23,
        "TCC0402C0G820J500AT",
        "MLCC_82pF_C0G_50V_+/-5%_C0402_0.5MM+/-0.1MM_SMD",
        "0402_82pF_C0G_5%_50V",
    ),
    (
        26,
        "TCC0402X7R104K160AT",
        "MLCC_0.1uF_X7R_16V_+/-10%_C0402_0.5MM+-0.05MM_SMD",
        "0402_100nF_X7R_10%_16V",
    ),
    (
        30,
        "TCC0402X5R106M6R3ATR",
        "MLCC_10uF_X5R_6.3V_+/-20%_0402_0.5mm-0.05/+0.25mm_SMD",
        "0402_10uF_X5R_20%_6.3V",
    ),
    (
        32,
        "TCC0402C0G101J500AT",
        "MLCC_100pF_C0G_50V_+/-5%_C0402_0.5MM+/-0.1MM_SMD",
        "0402_100pF_C0G_5%_50V",
    ),
    (
        37,
        "TCC0402COG331J500AT",
        "MLCC_330pF_C0G_50V_+/-5%_C0402_0.5+/-0.1mm_SMD",
        "0402_330pF_C0G_5%_50V",
    ),
    (
        38,
        "TCC0402X7R473K500AT",
        "MLCC_47nF_X7R_50V_+/-10%_C0402_0.5MM+-0.2MM_SMD",
        "0402_47nF_X7R_10%_50V",
    ),
    (
        44,
        "TCC0402X5R225M6R3AT",
        "MLCC_2.2uF_X5R_6.3V_+/-20%_0402_0.5MM+-0.1MM_SMD",
        "0402_2.2uF_X5R_20%_6.3V",
    ),
    # Second SKU3 row carrying the same MPN as row 26 (44 more placements).
    (
        49,
        "TCC0402X7R104K160AT",
        "MLCC_0.1uF_X7R_16V_+/-10%_C0402_0.5MM+-0.05MM_SMD",
        "0402_100nF_X7R_10%_16V",
    ),
]

# Decimal "R is the decimal point" value form of the Walsin CG line.
CG_DECIMAL_ROWS = [
    (
        18,
        "0402CG0R5C500NT",
        "MLCC_0.5pF_C0G_50V_+/-0.25pF_C0402_0.50±0.05mm_SMD",
        "0402_0.5pF_C0G_0.25pF_50V",
    ),
    (
        59,
        "0402CG5R6C500NT",
        "MLCC_5.6pF_NP0_50V_+/-0.25pF_C0402_0.5MM+-0.05MM_SMD",
        "0402_5.6pF_C0G_0.25pF_50V",
    ),
    (
        57,
        "0402CG8R2C500NT",
        "MLCC_8.2pF_C0G_50V_+/-0.25pF_C0402_0.5MM+/-0.05MM_SMD",
        "0402_8.2pF_C0G_0.25pF_50V",
    ),
]

# Already-working 3-digit CG siblings of the same BOM (fenghua owns them today;
# the Walsin CG branch would return the identical string).
CG_EIA_ROWS = [
    (
        36,
        "0402CG100J500NT",
        "CAP_10pF_C0G_50V_+/-5%_C0402_0.5MM+-0.05MM_SMD",
        "0402_10pF_C0G_5%_50V",
    ),
    (
        31,
        "0402CG150J500NT",
        "MLCC_15pF_COG_50V_±5%_C0402_0.5±0.05MM_SMD",
        "0402_15pF_C0G_5%_50V",
    ),
    (
        35,
        "0402CG220J500NT",
        "MLCC_22pF_COG_50V_+/-5%_C0402_0.5MM±0.05MM_SMD",
        "0402_22pF_C0G_5%_50V",
    ),
    (
        52,
        "0402CG330J500NT",
        "MLCC_33pF_COG_50V_+/-5%_C0402_0.5MM+/-0.05MM_SMD",
        "0402_33pF_C0G_5%_50V",
    ),
]

# Every WR0x… resistor row of the same sheet — these must stay untouched.
WR_ROWS = [
    (143, "WR04X5113FTL", "RES_511K_+/-1%_1/16W_R0402_SMD", "0402_511K_1%"),
    (163, "WR04X8871FTL", "RES_8K87_+/-1%_1/16W_R0402_SMD", "0402_8.87K_1%"),
    (169, "WR04W2R00FTL", "RES_2R_+/-1%_1/16W_R0402_SMD", "0402_2R_1%"),
    (183, "WR04X4641FTL", "RES_4K64_+/-1%_1/16W_R0402_SMD", "0402_4.64K_1%"),
    (
        184,
        "WR04X1651FTL",
        "RES_1K65_+/-1%_1/16W_R0402_WR04X1651FTL_SMD_RoHS",
        "0402_1.65K_1%",
    ),
    (205, "WR04X2742FTL", "RES_27K4_+/-1%_1/16W_R0402_SMD", "0402_27.4K_1%"),
    (244, "WR04X24R0FTL", "RES_24R_+/-1%_1/16W_R0402_SMD", "0402_24R_1%"),
]


@pytest.fixture(scope="module")
def cfg():
    pn_original.CONVERTERS.clear()
    pn_original.load_converters()
    return load_corpus_profile()


# --- Defect A: TCC capacitors -------------------------------------------------


@pytest.mark.parametrize(
    "row,mpn,desc,expected",
    TCC_ROWS,
    ids=[f"row{r}-{m}" for r, m, _, _ in TCC_ROWS],
)
def test_tcc_mpn_parses_to_bom_value(cfg, row, mpn, desc, expected) -> None:
    assert pn_original.parse_pn(mpn, "CAP", cfg) == expected, (row, desc)


@pytest.mark.parametrize(
    "row,mpn,desc,expected",
    TCC_ROWS,
    ids=[f"row{r}-{m}" for r, m, _, _ in TCC_ROWS],
)
def test_tcc_mpn_only_row_is_vendor_cleaned(cfg, row, mpn, desc, expected) -> None:
    """MPN-only input: typed CAP, normalized by the vendor codec, not left alone."""
    cleaned, typ, _pc, src = clean_component.clean_one(mpn, cfg)
    assert typ == "CAP"
    assert cleaned == expected, (row, desc, cleaned)
    assert src == "vendor"


def test_tcc_join_row_keeps_the_bom_description_tokens(cfg) -> None:
    """A prose+MPN row still decodes every field the description states."""
    desc, mpn, expected = (
        TCC_ROWS[0][2],
        TCC_ROWS[0][1],
        "0402_0.1uF_X5R_10%_25V",
    )
    cleaned, typ, _pc, _src = clean_component.clean_one(f"{desc} | {mpn}", cfg)
    assert typ == "CAP"
    assert cleaned == expected


def test_tcc_module_only_claims_tcc_part_numbers() -> None:
    """The ^TCC anchor: no other vendor's MPN can be shadowed by this module."""
    for other in (
        "0402CG100J500NT",
        "0402B223K250NT",
        "CC0402KRX7R9BB102",
        "CL05A105KA5NQNC",
        "GRM155R61A106ME11D",
        "0402N100J500CT",
        "WR04X2742FTL",
    ):
        assert tcc_capacitor.parse(other, "CAP") is None, other
    assert tcc_capacitor.parse("TCC0402X5R104K250AT", "RES") is None


# --- Defect B: Walsin CG decimal-pF values ------------------------------------


@pytest.mark.parametrize(
    "row,mpn,desc,expected",
    CG_DECIMAL_ROWS,
    ids=[f"row{r}-{m}" for r, m, _, _ in CG_DECIMAL_ROWS],
)
def test_cg_decimal_part_classifies_as_cap(cfg, row, mpn, desc, expected) -> None:
    assert clean_component.classify_component_type(mpn) == "CAP", (row, desc)


@pytest.mark.parametrize(
    "row,mpn,desc,expected",
    CG_DECIMAL_ROWS,
    ids=[f"row{r}-{m}" for r, m, _, _ in CG_DECIMAL_ROWS],
)
def test_cg_decimal_part_parses_to_bom_value(cfg, row, mpn, desc, expected) -> None:
    assert pn_original.parse_pn(mpn, "CAP", cfg) == expected, (row, desc)
    cleaned, typ, _pc, src = clean_component.clean_one(mpn, cfg)
    assert typ == "CAP"
    assert cleaned == expected, (row, desc, cleaned)
    assert src == "vendor"


@pytest.mark.parametrize(
    "row,mpn,desc,expected",
    CG_EIA_ROWS,
    ids=[f"row{r}-{m}" for r, m, _, _ in CG_EIA_ROWS],
)
def test_cg_eia_siblings_still_parse(cfg, row, mpn, desc, expected) -> None:
    """The 3-digit CG line of the same BOM must not move an inch."""
    assert pn_original.parse_pn(mpn, "CAP", cfg) == expected, (row, desc)
    cleaned, typ, _pc, src = clean_component.clean_one(mpn, cfg)
    assert typ == "CAP"
    assert cleaned == expected, (row, desc, cleaned)
    assert src == "vendor"


def test_cg_sibling_regression_anchor(cfg) -> None:
    """Explicit anchor asked for by the audit: 0402CG100J500NT → 10pF/50V/C0G/5%."""
    assert (
        clean_component.clean_one("0402CG100J500NT", cfg)[0] == "0402_10pF_C0G_5%_50V"
    )
    assert pn_original.parse_pn("0402CG100J500NT", "CAP", cfg) == (
        "0402_10pF_C0G_5%_50V"
    )


def test_cg_join_row_output_is_unchanged_by_the_vendor_branch(cfg) -> None:
    """Prose+MPN rows produced this string before the fix; it must not move."""
    desc, mpn = CG_DECIMAL_ROWS[0][2], CG_DECIMAL_ROWS[0][1]
    cleaned, typ, _pc, _src = clean_component.clean_one(f"{desc} | {mpn}", cfg)
    assert typ == "CAP"
    assert cleaned == "0402_0.5pF_C0G_0.25pF_50V"


# --- Regression: the WR0x resistors of the same sheet -------------------------


@pytest.mark.parametrize(
    "row,mpn,desc,expected",
    WR_ROWS,
    ids=[f"row{r}-{m}" for r, m, _, _ in WR_ROWS],
)
def test_wr_resistor_rows_are_untouched(cfg, row, mpn, desc, expected) -> None:
    assert clean_component.classify_component_type(mpn) == "RESISTOR", (row, desc)
    assert pn_original.parse_pn(mpn, "RES", cfg) == expected, (row, desc)
    cleaned, typ, _pc, src = clean_component.clean_one(mpn, cfg)
    assert typ == "RESISTOR"
    assert cleaned == expected, (row, desc, cleaned)
    assert src == "vendor"


def test_wr04x2742ftl_spot_check(cfg) -> None:
    assert clean_component.clean_one("WR04X2742FTL", cfg)[0] == "0402_27.4K_1%"


# --- Classifier stays narrow ---------------------------------------------------


@pytest.mark.parametrize(
    "mpn,expected_type",
    [
        ("WR04X2742FTL", "RESISTOR"),
        ("RC0402FR-0756KL", "RESISTOR"),
        ("HCB2012KF-121T40", "FERRITE_BEAD"),
        ("ALC897-VA2-CG", "OTHER"),
        ("NCP15XH103F03RC", "OTHER"),
        ("TCC0402X7R104K160AT", "CAP"),
        ("0402CG100J500NT", "CAP"),
    ],
)
def test_classifier_unaffected_outside_the_cg_decimal_fix(mpn, expected_type) -> None:
    assert clean_component.classify_component_type(mpn) == expected_type, mpn
