"""
Viiyong (Guangdong Viiyong Electronic Technology) MLCC PN parser.

Ordering per the "Product Specification for General Purpose" sheet (V2 dated
2023-11-10, retrieved 2026-10-04; local copy under the gitignored
``datasheet/pdf/``), section 2 "Part Number System"::

    (1) Series  (2) Capacitance  (3) Capacitance Tolerance
    (4) Dimension  (5) Temperature Characteristic  (6) Rated Voltage
    (7) Terminal Electrodes  (8) Thickness  (9) Control Code

    V  226  M  0402  X5R  6R3  N  C  T
    1  22uF  20%  0402  X5R  6.3V  Ni-Sn

What the previous pattern got wrong:

- It ended at ``N(?:AT|BT|XT)$``, so the two part numbers printed in the
  datasheet itself - ``V226M0402X5R6R3NCT`` and ``V180J0201C0G500NAT`` - did not
  match at all. The datasheet puts the thickness code (8) and control code (9)
  after the terminal, so ``NC``+``T`` is the ordinary ending, not a variant.
- Rated voltage accepts both forms the sheet uses: the ``dRd`` decimal
  (``6R3`` -> 6.3 V) and a 3-digit block. The 3-digit form is V/10 like the other
  China-vendor catalogues (``160`` -> 16 V), not the EIA exponent form.
- Temperature characteristics cover the class-2 families the sheet lists
  alongside X5R/X7R/X6S, plus class 1. Only the first three were accepted, so
  X7S/X6T/Y5V/Y5U/C0G parts returned ``None``.
- All fourteen tolerance codes of section 3 are accepted, and the class-1
  spellings (C0G / COG / C0H / NP0 / NPO) all clean to ``C0G`` instead of
  leaking the vendor's own spelling into the cleaned string.

Examples:
- V226M0402X5R6R3NCT → 0402_22uF_X5R_20%_6.3V   (datasheet part number)
- V180J0201C0G500NAT → 0201_18pF_C0G_5%_50V    (datasheet part number)
- V105K0201X5R160NXT → 0201_1uF_X5R_10%_16V
"""

from __future__ import annotations

from parsers.regex_api import I, compile

from ._cap_decode import pf_eia_3_to_str
from ._mlcc_china_vol import china_mlcc_vol_token

VENDOR_NAME = "Viiyong"
COMPONENT_TYPES = ["CAP"]
PARSER_PRIORITY = 87

# Datasheet section 3 "Capacitance Tolerance", PDF p.2: "A: +/-0.05pF B: +/-0.1pF
# C: +/-0.25pF D: +/-0.5pF F: +/-1% G: +/-2% J: +/-5% K: +/-10% L: +/-15% M:
# +/-20% N: +/-30% X: +/-40% Z: +80/-20% Y: +150/-20%".
#
# Only J/K/M were decoded, and because the pattern *required* a tolerance letter
# the other nine made the whole part unparseable - size, capacitance, dielectric
# and voltage all thrown away. The absolute codes render as a bare ``0.25pF``
# magnitude and the asymmetric ones as the sheet spells them, which is what
# ``fenghua``/``darfon``/``walsin`` already do for the same two classes.
_TOL = {
    "A": "0.05pF",
    "B": "0.1pF",
    "C": "0.25pF",
    "D": "0.5pF",
    "F": "1%",
    "G": "2%",
    "J": "5%",
    "K": "10%",
    "L": "15%",
    "M": "20%",
    "N": "30%",
    "X": "40%",
    "Z": "+80/-20%",
    "Y": "+150/-20%",
}
# Class 1 + the class-2 families named in section 5 of the sheet. Section 1.3
# lists the class-1 group as "C0G/C0H(NP0)", so C0H is a real spelling here.
_TC = "X5R|X5S|X7R|X7S|X7T|X6S|X6T|Y5V|Y5U|C0G|COG|C0H|NP0|NPO|P7R|P6R"
# Every class-1 spelling collapses to C0G, as darfon/eyang/fenghua/tcc/walsin
# already do: the same class-1 dielectric must clean to the same string whichever
# vendor marked it.
_CLASS1 = {"C0G", "COG", "C0H", "NP0", "NPO"}
# (2) capacitance EIA, (3) tolerance, (4) size, (5) TC, (6) voltage as dRd or 3
# digits, then terminal + thickness + control code.
_RE = compile(
    r"^V(\d{3})(["
    + "".join(sorted(_TOL))
    + r"])(\d{4})("
    + _TC
    + r")(\dR\d|\d{3})N[A-Z]{0,3}$",
    I,
)


def parse(pn: str, component_type: str) -> str | None:
    if component_type != "CAP":
        return None
    pn2 = "".join(str(pn).strip().upper().split())
    m = _RE.match(pn2)
    if not m:
        return None
    c3, tol_ch, size, film_raw, vraw = m.groups()
    cap = pf_eia_3_to_str(c3)
    if not cap:
        return None
    film_raw = str(film_raw).upper()
    film = "C0G" if film_raw in _CLASS1 else film_raw
    tol = _TOL.get(str(tol_ch).upper(), "")
    vol = china_mlcc_vol_token(vraw)
    parts = [size, cap, film]
    if tol:
        parts.append(tol)
    if vol:
        parts.append(vol)
    return "_".join(p for p in parts)
