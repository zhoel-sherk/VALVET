"""
Eyang (宇阳) MLCC PN parser.

Examples:
- C0402C0G180J500NTB → 0402_18pF_C0G_5%_50V
- C0402X7R221K500NTB → 0402_220pF_X7R_10%_50V
- C0201X5R334M6R3NTJ → 0201_0.33uF_X5R_20%_6.3V
"""

from __future__ import annotations

from parsers.regex_api import I, compile

from ._cap_decode import pf_eia_3_to_str
from ._mlcc_china_vol import china_mlcc_vol_token

VENDOR_NAME = "Eyang"
COMPONENT_TYPES = ["CAP"]
PARSER_PRIORITY = 88

_TOL = {"F": "1%", "G": "2%", "J": "5%", "K": "10%", "M": "20%"}
_RE = compile(
    r"^C(\d{4})(C0G|COG|X7R|X5R|X6S|X8R|NP0|NPO)(\d{3})([FGJKM])"
    r"((?:\d{3})|(?:\dR\d))([A-Z]*)$",
    I,
)


def parse(pn: str, component_type: str) -> str | None:
    if component_type != "CAP":
        return None
    pn2 = "".join(str(pn).strip().upper().split())
    if not pn2.startswith("C") or len(pn2) < 14:
        return None
    m = _RE.match(pn2)
    if not m:
        return None
    size, film_raw, c3, tch, vtok, _tail = m.groups()
    cap = pf_eia_3_to_str(c3)
    if not cap:
        return None
    film = "C0G" if film_raw.upper() in ("C0G", "COG", "NP0", "NPO") else film_raw.upper()
    tol = _TOL.get(tch.upper(), "")
    vol = china_mlcc_vol_token(vtok)
    parts = [size, cap, film]
    if tol:
        parts.append(tol)
    if vol:
        parts.append(vol)
    return "_".join(parts)
