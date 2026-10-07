"""
Walsin MLCC PN parser.

Ordering per the Walsin "MLCC Product Catalog" (retrieved 2026-10-04; local copy
under the gitignored ``datasheet/pdf/``), page "How To Order and Packaging
Dimension/Quantity", which gives **one** scheme for the whole catalogue::

    0805   B    104   K   500   C   T
    size  diel  cap  tol  volt  term  pack

- **Size** (inch code): ``01R5`` 0201 0402 0603 0805 1206 1210 1808 1812 1825
  2220 2225. The metric equivalents are printed alongside in the catalogue
  (0402 = 1005, 0603 = 1608, ...) but the part number uses the inch form.
- **Dielectric**, one letter: ``N``=NP0, ``G``=X8G, ``R``=X8R, ``B``=X7R,
  ``A``=X7S, ``S``=X6S, ``X``=X5R, ``F``=Y5V.
- **Capacitance**: two significant digits plus a zero count, with ``R`` standing
  in for the decimal point — ``R47``=0.47 pF, ``0R5``=0.5 pF, ``1R0``=1 pF,
  ``100``=10 pF, ``101``=100 pF, ``102``=1000 pF, ``103``=0.01 µF, ``104``=0.1 µF,
  ``105``=1 µF, ``106``=10 µF, ``107``=100 µF.
- **Tolerance**: ``A`` ±0.05 pF, ``B`` ±0.1 pF, ``C`` ±0.25 pF, ``D`` ±0.5 pF
  (absolute, class 1) and ``F`` 1 %, ``G`` 2 %, ``J`` 5 %, ``K`` 10 %, ``M`` 20 %,
  ``Z`` −20 %/+80 %.
- **Voltage**: ``4R0``=4 Vdc, ``6R3``=6.3 Vdc, then the 3-digit EIA
  mantissa-exponent form — ``100``=10 V, ``160``=16 V, ``250``=25 V, ``350``=35 V,
  ``500``=50 V, ``101``=100 V, ``201``=200 V, ``251``=250 V, ``401``=400 V,
  ``451``=450 V, ``501``=500 V, ``631``=630 V, ``102``=1 kV, ``152``=1.5 kV,
  ``202``=2 kV, ``252``=2.5 kV, ``302``=3 kV, ``402``=4 kV, ``502``=5 kV,
  ``602``=6 kV. This is **not** the V/10 form the other China-vendor catalogues
  use; see :func:`eia_vol_code_to_v`.
- **Termination + packaging**: ``L`` = Ag/Ni/Sn or ``C`` = Cu/Ni/Sn, then ``T``
  7" reel, ``Q`` 10" reel or ``G`` 13" reel, optionally followed by a
  size-dependent thickness symbol. None of these carry electrical meaning, so
  they are not part of the cleaned value, but they are validated so a foreign
  ending is rejected.

What the previous version got wrong

It carried seven regexes, one per part-number shape seen in the wild, and
covered only part of the catalogue:

- five of the eight dielectric letters were unreachable: ``G``(X8G), ``R``(X8R),
  ``A``(X7S), ``S``(X6S) and ``F``(Y5V) parts returned ``None`` outright.
- the absolute class-1 tolerances ``A``/``B``/``C``/``D`` and the asymmetric
  ``Z`` were not in the table at all, so a part could decode "successfully" while
  silently losing its tolerance.
- a ``CG`` branch existed, but ``CG`` is **not** a Walsin dielectric code - it is
  Fenghua's class-1 spelling. Walsin's own class-1 letter is ``N``. That branch
  was decoding another vendor's part numbers.

Token order is ``size[_capacitance_film]_voltage_tolerance``.

Examples:
- 0805B104K500CT → 0805_100nF_X7R_50V_10%
- 0402N100J500CT → 0402_10pF_C0G_50V_5%
- 0805X475M6R3CT → 0805_4.7uF_X5R_6.3V_20%
- 0402G105K6R3CT → 0402_1uF_X8G_6.3V_10%
"""

from __future__ import annotations

from parsers.regex_api import I, compile, match, sub

from ._cap_decode import eia_vol_code_to_v, pf_eia_3_to_str

VENDOR_NAME = "Walsin_MLCC"
COMPONENT_TYPES = ["CAP"]
PARSER_PRIORITY = 65

_SIZE = {
    "01R5": "0402",
    "0201": "0201",
    "0402": "0402",
    "0603": "0603",
    "0612": "0612",
    "0805": "0805",
    "1206": "1206",
    "1210": "1210",
    "1808": "1808",
    "1812": "1812",
    "1825": "1825",
    "2220": "2220",
    "2225": "2225",
}

# Dielectric letter -> catalogue name.
_DIEL = {
    "N": "C0G",  # NP0
    "G": "X8G",
    "R": "X8R",
    "B": "X7R",
    "A": "X7S",
    "S": "X6S",
    "X": "X5R",
    "F": "Y5V",
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
    "Z": "-20%/+80%",
}

_SIZES = "|".join(sorted(_SIZE, key=len, reverse=True))
_DIELS = "|".join(_DIEL)
_TOLS = "|".join(_TOL)

# size, dielectric, capacitance (EIA-3 or R-decimal), tolerance,
# voltage (EIA-3 or dRd), termination + packaging (+ optional thickness symbol).
#
# The tail is enumerated from the catalog rather than left as ``[A-Z]{2}``.
# Termination is ``L`` = Ag/Ni/Sn or ``C`` = Cu/Ni/Sn (plus ``P`` = Cu/polymer on
# particular series), and packaging is ``T`` 7" reel, ``Q`` 10" reel, ``G`` 13"
# reel; a size-dependent thickness symbol may follow, which is why the catalogue
# prints both ``0805B104K500CT`` and ``0805B104K500CTG``. A permissive tail
# accepted anything and let foreign endings such as ``…6R3PT`` decode.
_RE = compile(
    r"^(" + _SIZES + r")(" + _DIELS + r")"
    r"(\d{3}|\dR\d)(" + _TOLS + r")"
    r"(\d{3}|\dR\d)[LC][TQG][A-Z]?$",
    I,
)


def _capacitance(code: str) -> str:
    """``0R5`` → ``0.5pF`` (R is the decimal point); otherwise the EIA-3 form."""
    raw = str(code or "").strip().upper()
    mr = match(r"^(\d)R(\d)$", raw)
    if mr:
        value = float(f"{mr.group(1)}.{mr.group(2)}")
        return f"{value:g}pF"
    return pf_eia_3_to_str(raw) or ""


def _voltage(code: str) -> str:
    """``6R3`` → ``6.3V``; a 3-digit block is EIA mantissa-exponent."""
    raw = str(code or "").strip().upper()
    mr = match(r"^(\d)R(\d)$", raw)
    if mr:
        value = float(f"{mr.group(1)}.{mr.group(2)}")
        return f"{value:g}V"
    return eia_vol_code_to_v(raw)


def parse(pn: str, component_type: str) -> str | None:
    if component_type != "CAP":
        return None
    pn0 = sub(r"\s*<[gG]>\s*$", "", str(pn).strip())
    pn2 = sub(r"\s+", "", pn0).strip().upper()

    m = _RE.match(pn2)
    if not m:
        return None
    size_code, diel, cap_code, tol_ch, vol_code = m.groups()

    size = _SIZE.get(size_code)
    film = _DIEL.get(diel)
    if not size or not film:
        return None
    cap = _capacitance(cap_code)
    if not cap:
        return None
    vol = _voltage(vol_code)
    tol = _TOL.get(tol_ch.upper())
    # ``N`` is NP0 (class 1); every other letter is a distinct dielectric, so the
    # film is only omitted when the codec cannot name it.
    parts = [size, cap, film]
    if vol:
        parts.append(vol)
    if tol:
        parts.append(tol)
    return "_".join(p for p in parts if p)
