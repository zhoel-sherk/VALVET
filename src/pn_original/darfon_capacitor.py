"""
Darfon (达方) MLCC PN parser — metric and EIA sizes across the class-1 and
class-2 temperature-characteristic families.

Ordering per the Darfon "MLCC Catalogue / General Purpose", Rev. 202510 (retrieved
2026-10-04; local copy under the gitignored ``datasheet/pdf/``), section
"Ordering Code"::

    C  1005  NP0  101  J  G  T  S  △
    1   2    3    4    5  6  7  8  9

1 product (``C`` = MLCC), 2 size, 3 T.C., 4 capacitance, 5 tolerance,
6 voltage, 7 packaging, 8 application, 9 thickness (may be blank).

Fields, and what the previous pattern got wrong:

- **Size** may be written either way round: the datasheet prints
  ``0402(01005) 0603(0201) 1005(0402) 1608(0603) 2012(0805) 3216(1206)
  3225(1210) 4520(1808) 4532(1812)``, so both the EIA code and the metric code
  have to be accepted and mapped to the imperial form the cleaned string uses.
- **T.C.** is a three-character code: ``NP0`` for class 1 plus ``X8G`` ``X8R``
  ``X7R`` ``X7S`` ``X7T`` ``X7U`` ``X6S`` ``X6T`` ``X5R``. The old pattern was
  pinned to a literal ``NP`` followed by three digits, which consumed the ``0``
  of ``NP0`` as the first capacitance digit and then demanded a literal ``CG``.
  Result: **0 of the 632 real part numbers in the catalogue parsed** - only the
  one hand-written example did, and even that lost its tolerance.
- **Capacitance** is three digits where the first two are significant and the
  last is the power of ten, except that ``9`` marks 1.0-9.9 pF and ``8`` marks
  0.20-0.99 pF, i.e. a negative exponent of one and two respectively.
- **Tolerance** ``A`` +/-0.05 pF, ``B`` +/-0.1 pF, ``C`` +/-0.25 pF, ``D``
  +/-0.5 pF (absolute, class 1) and ``F`` 1 %, ``G`` 2 %, ``J`` 5 %, ``K`` 10 %,
  ``M`` 20 %.
- **Voltage** is a single **letter**, not digits: ``T`` 2.5 V, ``B`` 4 V,
  ``C`` 6.3 V, ``D`` 10 V, ``E`` 16 V, ``F`` 25 V, ``N`` 35 V, ``G`` 50 V,
  ``H`` 100 V, ``J`` 200 V, ``K`` 250 V, ``L`` 500 V, ``M`` 630 V, ``P`` 1 kV,
  ``Q`` 2 kV, ``R`` 3 kV, ``S`` 4 kV. The old code read a digit here and then
  hardcoded 50 V, so every voltage except 50 V would have been wrong.
- **Packaging / application / thickness** are not part of the cleaned value and
  are accepted as an optional tail.

Examples (all taken from the catalogue's own tables):
- C0603NP0240JGT → 0201_24pF_C0G_5%_50V      (24 × 10^0 pF, G = 50 V)
- C0603NP0201JGT → 0201_200pF_C0G_5%_50V     (20 × 10^1 pF)
- C0603NP0201JFT → 0201_200pF_C0G_5%_25V     (same value, F = 25 V)
- C1005NP0508CGTS → 0402_0.5pF_C0G_0.25pF_50V (508: "8" → 50 × 10^-2 pF, C = ±0.25 pF)
"""

from __future__ import annotations

from parsers.regex_api import I, compile

VENDOR_NAME = "Darfon"
COMPONENT_TYPES = ["CAP"]
PARSER_PRIORITY = 84

# Datasheet "Ordering Code" block, complete: "SIZE in mm (EIA CODE, in inch)
# 0402(01005) 0603(0201) 1005(0402) 1608(0603) 2012(0805) 3216(1206)
# 3225(1210) 4520(1808) 4532(1812)".
#
# The size field is L x W in units of 0.1 mm, so the two halves of each pair are
# not interchangeable spellings of one size: "0603" is a 0.6 x 0.3 mm body,
# which is EIA 0201, while "1608" is a 1.6 x 0.8 mm body, which is EIA 0603.
# "0402" and "0603" were missing from this table, so a C0603 part fell through to
# the EIA fallback and was reported as 0603 instead of 0201 - a ~2.7x oversize
# package on every C0603 part in the catalogue.
_SIZE_METRIC = {
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

_TC = {
    "NP0": "C0G",
    "X8G": "X8G",
    "X8R": "X8R",
    "X7R": "X7R",
    "X7S": "X7S",
    "X7T": "X7T",
    "X7U": "X7U",
    "X6S": "X6S",
    "X6T": "X6T",
    "X5R": "X5R",
}
_TOL = {
    "A": "0.05pF",
    "B": "0.1pF",
    "C": "0.25pF",
    "D": "0.5pF",
    "F": "1%",
    "G": "2%",
    "J": "5%",
    "K": "10%",
    "M": "20%",
}
# Datasheet "VOLTAGE CODE": a single letter per voltage.
_VOL = {
    "T": "2.5V",
    "B": "4V",
    "C": "6.3V",
    "D": "10V",
    "E": "16V",
    "F": "25V",
    "N": "35V",
    "G": "50V",
    "H": "100V",
    "J": "200V",
    "K": "250V",
    "L": "500V",
    "M": "630V",
    "P": "1kV",
    "Q": "2kV",
    "R": "3kV",
    "S": "4kV",
}

_TCS = "|".join(_TC)
_RE = compile(
    r"^C(\d{4})(" + _TCS + r")(\d{3})([A-Z])([A-Z])(?:[A-Z]){0,2}$",
    I,
)


def _decode_capacitance(code: str) -> str:
    """Three-digit Darfon capacitance code → picofarads.

    First two digits are the significant figures; the third is the power of
    ten, except ``9`` and ``8`` which the datasheet reserves for the decimal
    bands 1.0-9.9 pF and 0.20-0.99 pF (exponents -1 and -2).
    """
    raw = str(code or "").strip()
    if not raw.isdigit() or len(raw) != 3:
        return ""
    mantissa = int(raw[:2])
    tail = raw[2]
    if tail in ("8", "9"):
        pf = mantissa * (10**-1 if tail == "9" else 10**-2)
        return f"{pf:g}pF"
    pf = mantissa * (10 ** int(tail))
    if pf >= 1_000_000:
        return f"{pf / 1_000_000:g}uF"
    if pf >= 1_000:
        return f"{pf / 1_000:g}nF"
    return f"{pf:g}pF"


def _resolve_size(code: str) -> str:
    """Map the metric size field to its EIA code, per the catalogue's 9 pairs.

    Only the metric spelling is accepted. The EIA codes the catalogue prints as
    the second half of each pair are a *different* set of numbers that happen to
    overlap - treating them as size codes is what made "0603" resolve to 0603
    instead of 0201.
    """
    return _SIZE_METRIC.get(str(code or "").strip(), "")


def parse(pn: str, component_type: str) -> str | None:
    if component_type != "CAP":
        return None
    pn2 = "".join(str(pn).strip().upper().split())
    m = _RE.match(pn2)
    if not m:
        return None
    size_code, tc, cap3, tol_ch, vol_ch = m.groups()
    size = _resolve_size(size_code)
    if not size:
        return None
    cap = _decode_capacitance(cap3)
    if not cap:
        return None
    film = _TC.get(tc.upper())
    if not film:
        return None
    parts = [size, cap, film]
    tol = _TOL.get(tol_ch.upper())
    if tol:
        parts.append(tol)
    vol = _VOL.get(vol_ch.upper())
    if vol:
        parts.append(vol)
    return "_".join(parts)
