"""
Walsin WR Resistor PN Parser

Walsin Thick Film Chip Resistor Part Number Format:
WR + Size(02|04|…) + X|W + resistance token + Tolerance(F|J) + tape suffix (TL|FTL|…)

Examples:
- WR04X1001FTL → RES_0402_1K_1%
- WR06X472JTL → RES_0603_4.7K_5%
- WR04X000PTL → RES_0402_0R (zero-ohm branch)

Size codes:
02=0201, 04=0402, 06=0603, 08=0805, 10=0805, 12=1210, 20=2010, 25=2512

Tolerance:
F=±1%, J=±5%

Resistance:
``10R…``, decimal R forms, or E24/E96 digits — via ``decode_ohms_suffix``

Reference:
https://www.passivecomponent.com/ — Walsin Tech WR/WF guides
"""

from __future__ import annotations

from parsers.regex_api import I, compile, sub

from ._resistor_decode import decode_ohms_suffix

VENDOR_NAME = "Walsin_WR"
COMPONENT_TYPES = ["RES"]
PARSER_PRIORITY = 70

_RE_ZERO = compile(
    r"^WR(02|04|06|08|10|12|20|25)X(0+)(P)(AL|TL|PTL|FTL|JTL|L)$",
    I,
)
_RE_VAL = compile(
    r"^WR(02|04|06|08|10|12|20|25)[XW](10R[0-9]|[0-9]{1,4}R[0-9]{1,2}|[0-9]{1,4})(F|J)([A-Z]{2,5})$",
    I,
)
_SIZE = {
    "02": "0201",
    "04": "0402",
    "06": "0603",
    "08": "0805",
    "10": "0805",
    "12": "1210",
    "20": "2010",
    "25": "2512",
}
_TOL = {"F": "1%", "J": "5%"}


def parse(pn: str, component_type: str) -> str | None:
    if component_type != "RES":
        return None
    pn2 = sub(r"\s+", "", pn).strip().upper()

    z = _RE_ZERO.match(pn2)
    if z:
        s = _SIZE.get(z.group(1))
        if not s:
            return None
        return f"{s}_0R_5%"

    m = _RE_VAL.match(pn2)
    if not m:
        return None
    size = _SIZE.get(m.group(1))
    if not size:
        return None
    val_raw, tol_c, _tape = m.group(2), m.group(3).upper(), m.group(4)
    tol = _TOL.get(tol_c, "")
    ohm = decode_ohms_suffix(val_raw)
    if ohm is None:
        return None
    parts = [size, ohm]
    if tol:
        parts.append(tol)
    return "_".join(parts)
