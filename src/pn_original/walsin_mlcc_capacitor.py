"""
Walsin Capacitor PN Parser

Walsin MLCC Part Number Format (several families — see regexes in code):
- ``0402N…`` / ``0603N…``: package + N + EIA(3) or 5R0-style + tolerance + voltage digits + tape
- ``0402B…CT``, ``0805X…CT``, ``1206X…CT``: B/X line + value + tolerance + voltage encoding

Packaging suffix (last two letters of the B/X lines):
- ``CT`` — 7" paper tape; ``NT`` — 7" plastic tape (same reel code family)

Examples:
- 0402N100J500CT → CAP_0402_10pF_50V_5%
- 0402B102K500CT → CAP_0402_1nF_50V_10%
- 0805X475M6R3CT → CAP_0805_4.7uF_6.3V_20%
- 0201X104K6R3NT → CAP_0201_100nF_6.3V_X5R_10%

Size codes:
0201, 0402, 0603, 0805, 1206, 1210 (leading 4 digits in PN)

Tolerance:
F=±1%, G=±2%, J=±5%, K=±10%, M=±20%

Voltage:
Numeric blocks (e.g. 500→50V) via ``walsin_vol_code_to_v``; X-line ``dRd`` = d.V (e.g. 6R3 → 6.3V)

Reference:
https://www.passivecomponent.com/ — Walsin Tech ordering guides
"""

from __future__ import annotations

from parsers.regex_api import I, compile, match, search, sub

from ._cap_decode import pf_eia_3_to_str, walsin_vol_code_to_v

VENDOR_NAME = "Walsin_MLCC"
COMPONENT_TYPES = ["CAP"]
PARSER_PRIORITY = 65

_SIZE = {
    "0201": "0201",
    "0402": "0402",
    "0603": "0603",
    "0805": "0805",
    "1206": "1206",
    "1210": "1210",
}

# N100 J 500: 3-digit pF, tolerance J, 500 → 50V; N5R0 C 500: 5.0pF, C0G, 50V
_RE_N3 = compile(
    r"^(\d{4})N([0-9]{3})([FGJKM])([0-9]{2,3})([A-Z]{1,3})$",
    I,
)
_RE_N5R = compile(
    r"^(\d{4})N(5R[0-9])(.)([0-9]{2,3})([A-Z]{1,3})$",
    I,
)
# 0402B102K500CT / 0402B102K500NT — B line, 102 EIA, K tol, 500 = 50V
_RE_BCT = compile(r"^(\d{4})B(\d{3})([A-Z])(\d{3,4})(?:CT|NT)$", I)
# 0805X475M6R3CT — 475 EIA, 6R3 = 6.3V; leading M = 20% (optional)
_RE_X6R3 = compile(r"^(\d{4})X(\d{3,4})([A-Z]?)(\d)R(\d)(?:CT|NT)$", I)
# 1206X106K250CT — 106 value, K tol, 250 = 25V
_RE_XKV = compile(r"^(\d{4})X(\d{3,4})([A-Z])(\d{3,4})(?:CT|NT)$", I)
_TOL = {"F": "1%", "G": "2%", "J": "5%", "K": "10%", "M": "20%"}
_FILM_BY_SERIES = {
    "B": "X7R",
    "X": "X5R",
}


def parse(pn: str, component_type: str) -> str | None:
    if component_type != "CAP":
        return None
    pn0 = sub(r"\s*<[gG]>\s*$", "", str(pn).strip())
    pn2 = sub(r"\s+", "", pn0).strip().upper()

    mb = _RE_BCT.match(pn2)
    if mb:
        pz, c3, tch, vraw = mb.groups()
        if pz not in _SIZE:
            return None
        cap = pf_eia_3_to_str(c3) if len(c3) == 3 and c3.isdigit() else None
        if not cap:
            return None
        vol = walsin_vol_code_to_v(vraw)
        tol = _TOL.get(tch.upper(), "")
        film = _FILM_BY_SERIES.get("B", "")
        parts2 = [_SIZE[pz], cap]
        if film:
            parts2.append(film)
        if vol:
            parts2.append(vol)
        if tol:
            parts2.append(tol)
        return "_".join(parts2)

    m6r = _RE_X6R3.match(pn2)
    if m6r:
        pz, cblock, tch, _a, _b = m6r.groups()
        if pz not in _SIZE:
            return None
        c3 = cblock if len(cblock) == 3 else cblock[-3:]
        cap = pf_eia_3_to_str(c3) if len(c3) == 3 and c3.isdigit() else None
        if not cap:
            return None
        tol = _TOL.get(tch.upper(), "") if tch else ""
        film = _FILM_BY_SERIES.get("X", "")
        return "_".join(p for p in (_SIZE[pz], cap, film, "6.3V", tol) if p)

    mxk = _RE_XKV.match(pn2)
    # Guard: the dRd voltage encoding (…6R3CT / …6R3NT) belongs to _RE_X6R3, so
    # the optional packaging letters after it must be tolerated here as well.
    if mxk and not search(r"[0-9]R[0-9][A-Z]{0,2}$", pn2, I):
        pz, cblock, tch, vraw = mxk.groups()
        if pz not in _SIZE:
            return None
        c3 = cblock if len(cblock) == 3 and cblock.isdigit() else cblock[-3:]
        cap = pf_eia_3_to_str(c3) if len(c3) == 3 and c3.isdigit() else None
        if not cap:
            return None
        vol = walsin_vol_code_to_v(vraw)
        tol = _TOL.get(tch.upper(), "")
        film = _FILM_BY_SERIES.get("X", "")
        parts3 = [_SIZE[pz], cap]
        if film:
            parts3.append(film)
        if vol:
            parts3.append(vol)
        if tol:
            parts3.append(tol)
        return "_".join(parts3)

    m5 = _RE_N5R.match(pn2)
    if m5:
        psize, pval, diel, vcode, _pack = m5.groups()
        if psize not in _SIZE:
            return None
        mr = match(r"^5R([0-9])$", pval, I)
        if not mr:
            return None
        cap_s = f"5.{mr.group(1)}pF"
        vol = walsin_vol_code_to_v(vcode)
        d = "C0G" if diel.upper() == "C" else diel
        segs = [_SIZE[psize], cap_s, d]
        if vol:
            segs.append(vol)
        return "_".join(segs)

    m = _RE_N3.match(pn2)
    if not m:
        return None
    psize, cap3, tol_ch, vcode, _pack = m.groups()
    if psize not in _SIZE:
        return None
    cap = pf_eia_3_to_str(cap3)
    if not cap:
        return None
    vol = walsin_vol_code_to_v(vcode)
    tol = _TOL.get(str(tol_ch).upper(), "")
    parts = [_SIZE[psize], cap]
    if vol:
        parts.append(vol)
    if tol:
        parts.append(tol)
    return "_".join(parts)
