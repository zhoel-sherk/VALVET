"""
Fenghua (风华) MLCC PN parser — ``0402CG…NT`` C0G and ``0402B…NT`` X7R/X5R lines.

Examples:
- 0402CG101J500NT → 0402_100pF_C0G_5%_50V
- 0402B223K250NT → 0402_22nF_X7R_10%_25V
"""

from __future__ import annotations

from parsers.regex_api import I, compile

from ._cap_decode import pf_eia_3_to_str
from ._mlcc_china_vol import china_mlcc_vol_from_digits

VENDOR_NAME = "Fenghua"
COMPONENT_TYPES = ["CAP"]
PARSER_PRIORITY = 86

_TOL = {"F": "1%", "G": "2%", "J": "5%", "K": "10%", "M": "20%"}
_RE_CG = compile(r"^(\d{4})CG(\d{3})([FGJKM])(\d{3})NT$", I)
_RE_B = compile(r"^(\d{4})B(\d{3})([FGJKM])(\d{3})NT$", I)


def _parse_line(m, film: str) -> str | None:
    size, c3, tch, vraw = m.groups()
    cap = pf_eia_3_to_str(c3)
    if not cap:
        return None
    tol = _TOL.get(tch.upper(), "")
    vol = china_mlcc_vol_from_digits(vraw)
    parts = [size, cap, film]
    if tol:
        parts.append(tol)
    if vol:
        parts.append(vol)
    return "_".join(parts)


def parse(pn: str, component_type: str) -> str | None:
    if component_type != "CAP":
        return None
    pn2 = "".join(str(pn).strip().upper().split())
    mc = _RE_CG.match(pn2)
    if mc:
        return _parse_line(mc, "C0G")
    mb = _RE_B.match(pn2)
    if mb:
        return _parse_line(mb, "X7R")
    return None
