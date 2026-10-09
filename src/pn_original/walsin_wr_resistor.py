"""
Walsin WR Resistor PN Parser

Walsin Thick Film Chip Resistor Part Number Format:
WR + Size(02|04|06|08|10|12|18|20|25) + X|W + resistance token + Tolerance(F|J)
+ tape suffix (TL|FTL|…)

Examples:
- WR04X1001FTL → RES_0402_1K_1%
- WR06X472JTL → RES_0603_4.7K_5%
- WR04X000PTL → RES_0402_0R (zero-ohm branch)

Size codes, read off the "Size code" row of each catalogue's own table (the
two series numbers are *not* ordered by size, which is why 10 is a 1210 and 12
is a 1206):

- ``ASC_WR_TR_V07`` (WR10 / WR12 / WR08 / WR06 / WR04):
  ``WR10: 1210, WR12: 1206, WR08: 0805, WR06: 0603, WR04: 0402``
- ``WR18-20-25X(W)_V14``: ``WR18: 1218, WR20: 2010, WR25: 2512``

``02`` is in neither sheet, but it is not a guess: the CO1271 production corpus
carries two real rows for it - ``WR02X3301FTL`` described as
``RES_3K3 ±1%_1/20W_R0201_SMD`` and the jumper ``WR02X000 PAL`` described as
``RES 0 OHM 1/20W (0201) 1%`` - so ``02`` = 0201 on production evidence. A
0201-specific sheet simply is not in the local set.

Tolerance:
F=±1%, J=±5%. A jumper is ``P`` and carries no percentage at all.

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
    r"^WR(02|04|06|08|10|12|18|20|25)X(0+)(P)(AL|TL|PTL|FTL|JTL|L)$",
    I,
)
_RE_VAL = compile(
    r"^WR(02|04|06|08|10|12|18|20|25)[XW](10R[0-9]|[0-9]{1,4}R[0-9]{1,2}|[0-9]{1,4})(F|J)([A-Z]{2,5})$",
    I,
)
_SIZE = {
    "02": "0201",
    "04": "0402",
    "06": "0603",
    "08": "0805",
    "10": "1210",
    "12": "1206",
    "18": "1218",
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
        # "P : Jumper" - a jumper is not a tolerance, so no percentage is
        # emitted. Appending one invents a spec the part number never states.
        return f"{s}_0R"

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
