"""
Walsin WW Resistor PN Parser

Walsin WW Low-Ohm / Current-Sense Chip Resistor Part Number Format:
WW + Size(06|08|12|20|25) + R + Rxxx (milliohm code) + Tolerance + suffix

Examples:
- WW06RR050FTL → RES_0603_0.05R_1%
- WW08RR100JTL → RES_0805_0.1R_5%

Size codes:
06=0603, 08=0805, 12=1206, 20=2010, 25=2512

Tolerance:
F=±1%, J=±5%

Resistance:
Rxxx → xxx / 1000 Ω (see ``_low_ohm``)
"""

from __future__ import annotations

from parsers.regex_api import I, compile, match, sub

VENDOR_NAME = "Walsin_WW"
COMPONENT_TYPES = ["RES"]
PARSER_PRIORITY = 75

_SIZE = {
    "06": "0603",
    "08": "0805",
    "12": "1206",
    "20": "2010",
    "25": "2512",
}
_TOL = {"F": "1%", "J": "5%"}

_RE_WW = compile(r"^WW(06|08|12|20|25)R(R[0-9]{3})(F|J)([A-Z]+)$", I)


def _low_ohm(token: str) -> str | None:
    m = match(r"^R([0-9]{3})$", token.strip().upper())
    if not m:
        return None
    milli = int(m.group(1))
    if milli == 0:
        return "0R"
    return f"{milli / 1000.0:.3f}".rstrip("0").rstrip(".") + "R"


def parse(pn: str, component_type: str) -> str | None:
    if component_type != "RES":
        return None
    pn0 = sub(r"\s+", "", str(pn).strip()).upper()
    m = _RE_WW.match(pn0)
    if not m:
        return None
    size_code, raw, tol_code, _tail = m.groups()
    size = _SIZE.get(size_code)
    ohm = _low_ohm(raw)
    tol = _TOL.get(tol_code.upper(), "")
    if not size or not ohm:
        return None
    return "_".join(p for p in (size, ohm, tol) if p)
