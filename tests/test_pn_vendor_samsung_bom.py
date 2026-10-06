"""Samsung CL MLCCs from the CO1271 (TechOne 27) order vs. their BOM descriptions.

Ground truth is the CO1271 order workbook, sheet ``SKU3``: column D holds the
MPN, column C the human description
``MLCC_<nom>_<dielectric>_<voltage>_<tol>_<size>_...``. The sheet contains 15
Samsung CL rows / 14 unique MPNs (``CL10A106MQ8NNNC`` appears on rows 28 and 41
with the same description); every one is parametrized below and the expected
string is *derived from the BOM description*, never from the parser.

Regression being pinned - the Samsung CL layout is::

    CL + size(2) + temp(1) + capacitance(3) + TOLERANCE(1) + VOLTAGE(1) + thickness(1) + ...

so the tolerance letter sits at index 8 (right after the 3-digit EIA code) and
the rated-voltage letter at index 9. The parser used to read the voltage from
index 8 (the *tolerance* letter: K->10V, M->6.3V) and the tolerance from index
10 (the *thickness* digit: 5->+-20%, 8->+-10%), which produced:

* K parts (+-10%) reported as +-20% whenever the thickness digit was 5,
* M parts (+-20%) reported as +-10% whenever the thickness digit was 8,
* M parts with a letter/digit thickness (Y, 7) reported *no* tolerance at all,
* and the wrong rated voltage on 9 of the 14 parts.
"""

from __future__ import annotations

import re

import pytest

import pn_original
from clean_component import CleanConfig
from pn_original import samsung_capacitor

# (mpn, bom_description) - verbatim from bom.xlsx sheet SKU3, columns D and C.
BOM_SAMSUNG_CL: list[tuple[str, str]] = [
    ("CL05A105KA5NQNC", "MLCC_1uF_X5R_25V_±10%_C0402_0.5±0.1MM_SMD"),
    ("CL10A475KP8NNNC", "MLCC_4.7uF_X5R_10V_+/-10%_C0603_0.8MM+-0.1MM_SMD"),
    ("CL10A106MO8NQNC", "MLCC_10uF_X5R_16V_±20%_C0603_0.8±0.15MM_SMD"),
    ("CL05A475MP5NRNC", "CAP_4.7uF_X5R_10V_+/-20%_C0402_0.5MM+-0.15MM_SMD"),
    ("CL05A105KQ5NNNC", "MLCC_1uF_X5R_6.3V_+/-10%_C0402_0.5MM+-0.05MM_SMD"),
    ("CL10A226MQ8NRNC", "MLCC_22uF_X5R_6.3V_+/-20%_0603_0.8MM+-0.2MM_SMD"),
    ("CL10A106MQ8NNNC", "MLCC_10uF_X5R_6.3V_+/-20%_0603_0.8MM+-0.1MM_SMD"),
    ("CL05A475MQ5NRNC", "MLCC_4.7uF_X5R_6.3V_±20%_C0402_0.5±0.15MM_SMD"),
    ("CL05A225MQ5NSNC", "MLCC_2.2uF_X5R_6.3V_±20%_C0402_0.5MM+-0.07MM_SMD"),
    ("CL05B104KA5NNNC", "MLCC_0.1uF_X7R_25V_+/-10%_0402_0.5MM+-0.05MM_SMD"),
    (
        "CL21A226MAYNNNE",
        "MLCC_22uF_X5R_25V_+/-20%_C0805_1.25MM+/-0.2MM_SMD_CL21A226MAYNNNE",
    ),
    ("CL10B104KB8NNNC", "MLCC_0.1uF_X7R_50V_+/-10%_C0603_0.8MM+/-0.2MM_SMD"),
    ("CL10A226MO7JZNC", "MLCC_22UF_X5R_16V_+/-20%_C0603_0.7±0.1MM_SMD"),
    ("CL05A474KA5NNNC", "MLCC_0.47uF_X5R_25V_+/-10%_C0402_0.5MM+-0.05MM_SMD"),
]

_DESC_RE = re.compile(
    r"^(?:MLCC|CAP)_([0-9.]+)([uUnNpP][fF])_([A-Za-z0-9]+)_([0-9.]+)V_"
    r"(?:\+/-|±)([0-9.]+)%_"
)
_SIZE_RE = re.compile(r"_(?:C)?(0201|0402|0603|0805|1206|1210)_")
_TOL_LETTER = {"F": "1%", "G": "2%", "J": "5%", "K": "10%", "M": "20%"}


def _to_pf(nominal: str) -> float:
    """``0.47uF`` -> 470000.0; the BOM spells what the parser prints as 470nF."""
    text = nominal.strip().lower().replace("µ", "u").replace("μ", "u")
    for suffix, factor in (("uf", 1e6), ("nf", 1e3), ("pf", 1.0), ("f", 1e9)):
        if text.endswith(suffix):
            return float(text[: -len(suffix)]) * factor
    raise AssertionError(f"unparsable nominal {nominal!r}")


def _fmt_pf(pf: float) -> str:
    """Normalize pF the way the parser prints it (100nF / 470nF / 10uF ...)."""
    for limit, factor, unit in ((1e6, 1e6, "uF"), (1e3, 1e3, "nF")):
        if pf >= limit:
            return f"{pf / factor:.3f}".rstrip("0").rstrip(".") + unit
    return f"{pf:.3f}".rstrip("0").rstrip(".") + "pF"


def expected_from_bom(desc: str) -> str:
    """Build the canonical parse output out of the human BOM description."""
    m = _DESC_RE.match(desc)
    assert m, f"unparsable BOM description: {desc!r}"
    size = _SIZE_RE.search(desc)
    assert size, f"no package size in BOM description: {desc!r}"
    nominal = _fmt_pf(_to_pf(f"{m.group(1)}{m.group(2)}"))
    return f"{size.group(1)}_{nominal}_{m.group(4)}V_{m.group(3)}_{m.group(5)}%"


@pytest.mark.parametrize(
    "mpn,bom_desc",
    BOM_SAMSUNG_CL,
    ids=[mpn for mpn, _ in BOM_SAMSUNG_CL],
)
def test_samsung_cl_matches_bom_description(mpn: str, bom_desc: str) -> None:
    expected = expected_from_bom(bom_desc)

    assert samsung_capacitor.parse(mpn, "CAP") == expected

    # Same part through the arbiter, the way the BOM pipeline calls it.
    assert pn_original.parse_pn(mpn, "CAP", CleanConfig()) == expected


@pytest.mark.parametrize(
    "mpn,bom_desc",
    BOM_SAMSUNG_CL,
    ids=[mpn for mpn, _ in BOM_SAMSUNG_CL],
)
def test_samsung_cl_tolerance_letter_drives_tolerance(mpn: str, bom_desc: str) -> None:
    """The tolerance letter is the character right after the EIA code (index 8)."""
    tolerance = expected_from_bom(bom_desc).rsplit("_", 1)[1]
    assert _TOL_LETTER[mpn[8]] == tolerance


def test_samsung_cl_same_capacitance_different_voltage_keeps_tolerance() -> None:
    """``...A106M...`` parts differ only in the voltage letter (O vs Q).

    ``CL10A106MO8NQNC`` is 10uF/16V and ``CL10A106MQ8NNNC`` is 10uF/6.3V; both
    carry the same M tolerance letter, so both are +-20%. Before the fix the
    parser swapped the roles of index 8 and index 9 and reported +-10% for both.
    """
    for mpn, bom_desc in (
        ("CL10A106MO8NQNC", "MLCC_10uF_X5R_16V_±20%_C0603_0.8±0.15MM_SMD"),
        ("CL10A106MQ8NNNC", "MLCC_10uF_X5R_6.3V_+/-20%_0603_0.8MM+-0.1MM_SMD"),
    ):
        out = samsung_capacitor.parse(mpn, "CAP")
        assert out == expected_from_bom(bom_desc)
        assert out.endswith("_20%")
        assert mpn[8] == "M"
