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

# Datasheet section 3 "Capacitance Tolerance".
_TOL = {"J": "5%", "K": "10%", "M": "20%"}
# Class 1 + the class-2 families named in section 5 of the sheet.
_TC = "X5R|X5S|X7R|X7S|X7T|X6S|X6T|Y5V|Y5U|C0G|COG|NP0|NPO|P7R|P6R"
# (2) capacitance EIA, (3) tolerance, (4) size, (5) TC, (6) voltage as dRd or 3
# digits, then terminal + thickness + control code.
_RE = compile(
    r"^V(\d{3})([JKM])(\d{4})(" + _TC + r")(\dR\d|\d{3})N[A-Z]{0,3}$",
    I,
)


def parse(pn: str, component_type: str) -> str | None:
    if component_type != "CAP":
        return None
    pn2 = "".join(str(pn).strip().upper().split())
    m = _RE.match(pn2)
    if not m:
        return None
    c3, tol_ch, size, film, vraw = m.groups()
    cap = pf_eia_3_to_str(c3)
    if not cap:
        return None
    tol = _TOL.get(str(tol_ch).upper(), "")
    vol = china_mlcc_vol_token(vraw)
    parts = [size, cap, film]
    if tol:
        parts.append(tol)
    if vol:
        parts.append(vol)
    return "_".join(p for p in parts)
