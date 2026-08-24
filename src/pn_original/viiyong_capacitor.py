"""
Viiyong (微容) MLCC PN parser.

Examples:
- V105K0201X5R160NXT → 0201_1uF_X5R_10%_16V
"""

from __future__ import annotations

from parsers.regex_api import I, compile

from ._cap_decode import pf_eia_3_to_str
from ._mlcc_china_vol import china_mlcc_vol_from_digits

VENDOR_NAME = "Viiyong"
COMPONENT_TYPES = ["CAP"]
PARSER_PRIORITY = 87

_TOL = {"J": "5%", "K": "10%", "M": "20%"}
_RE = compile(r"^V(\d{3})([JKM])(\d{4})(X5R|X7R|X6S)(\d{3})N(?:AT|BT|XT)$", I)


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
    vol = china_mlcc_vol_from_digits(vraw)
    parts = [size, cap, film, tol]
    if vol:
        parts.append(vol)
    return "_".join(parts)
