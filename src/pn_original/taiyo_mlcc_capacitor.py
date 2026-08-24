"""
Taiyo Yuden Capacitor PN Parser

Taiyo Yuden MLCC Part Number Format (subsets UMK / EMK / JMK|TMK):
- UMK + size(105|107|212|…) + dielectric(1) + voltage letter(1) + EIA(3) + tolerance(J|K|F|M|Z) + optional V
- EMK + size + BJ + EIA value + tolerance; or EMK + B + 4-digit block (leading digit = voltage hint)
- JMK|TMK + size + BJ + EIA(3) + optional tolerance → X5R family (fixed 6.3V in branch)

Examples:
- UMK105CH120JV-F → CAP_0402_12pF_C0G_50V_5%
- EMK107B7105KA-T → CAP_0603_1uF_16V_X5R_10%
- JMK212BJ226MG-T → CAP_0805_22uF_6.3V_X5R_20%

Size codes:
105=0402, 107=0603, 212=0805, 315/316=1206, 325=1210, …

Dielectric / temp (UMK first letter):
C=C0G, A/B=X5R/X7R, D=X5R, E/F=X6S

Voltage:
_VOL_UMK and _VOL_EMK_LEAD tables in code

Tolerance:
J=±5%, K=±10%, M=±20%, F=±1%, G=±2%, Z=±20%

Reference:
https://www.yuden.co.jp/ — verify against current ordering guide
"""

from __future__ import annotations

from parsers.regex_api import I, compile, sub

from ._cap_decode import pf_eia_3_to_str

VENDOR_NAME = "TaiyoYuden_MLCC"
COMPONENT_TYPES = ["CAP"]
PARSER_PRIORITY = 65

_SIZE_UMK = {
    "105": "0402",
    "107": "0603",
    "212": "0805",
    "315": "1206",
    "316": "1206",
    "325": "1210",
    "327": "2012",
    "336": "2012",
}

# UMK105CH120JV — value 120, tol J, optional voltage letter V
_RE_UMK = compile(
    r"^UMK(105|107|212|315|316|325|327|336)(.)(.)(\d{3})(J|K|F|M|Z)(V)?$",
    I,
)
_VOL_UMK = {
    "A": "250V",
    "B": "100V",
    "C": "6.3V",
    "D": "10V",
    "E": "16V",
    "F": "25V",
    "G": "50V",
    "H": "50V",
    "J": "6.3V",
    "K": "25V",
    "L": "16V",
    "M": "100V",
    "P": "10V",
    "Q": "6.3V",
}
_DIEL_UMK = {
    "C": "C0G",
    "A": "X5R",
    "B": "X7R",
    "D": "X5R",
    "E": "X6S",
    "F": "X6S",
}

# EMK105BJ105K — BJ + value; EMK105B7223K — B + 4-digit (last 3 = EIA)
_RE_EMK_BJ = compile(
    r"^EMK(105|107|212|316|325)BJ(\d{3,4})(K|J|M|G|Z).*$",
    I,
)
_RE_EMK_Bx = compile(
    r"^EMK(105|107|212|316|325)B(\d{3,4})(K|J|M|G|Z).*$",
    I,
)

_SIZE_EMK = {
    "105": "0402",
    "107": "0603",
    "212": "0805",
    "316": "1206",
    "325": "1210",
}

# JMK/TMK212BJ226MG (BJ + EIA, X5R family)
_RE_JMK_BJ = compile(r"^[JT]MK(105|107|212|315|316|325)BJ(\d{3})(J|K|M)?", I)
_SIZE_JMK = {
    "105": "0402",
    "107": "0603",
    "212": "0805",
    "315": "1206",
    "316": "1206",
    "325": "1210",
}

# Letter after EIA value block (BJ105K / B7105K / …)
_TOL_FROM_LETTER = {"J": "5%", "K": "10%", "M": "20%", "F": "1%", "G": "2%", "Z": "20%"}

# Leading digit of B + 4-digit value block (Taiyo EMK…B7105 = 16V + EIA 105)
_VOL_EMK_LEAD = {
    "3": "6.3V",
    "5": "6.3V",
    "6": "10V",
    "7": "16V",
    "8": "25V",
    "9": "50V",
}


def parse(pn: str, component_type: str) -> str | None:
    if component_type != "CAP":
        return None
    pn0 = sub(r"\s*<[gG]>\s*$", "", str(pn).strip())
    pn0 = sub(r"\s+", "", pn0).strip().upper()
    pni = sub(r"[-].*$", "", pn0)

    mj = _RE_JMK_BJ.match(pni)
    if mj:
        sc, c3, tol_ch = mj.groups()
        sz = _SIZE_JMK.get(sc, "")
        if not sz or len(c3) != 3:
            return None
        cap = pf_eia_3_to_str(c3) or ""
        tol = _TOL_FROM_LETTER.get((tol_ch or "").upper(), "")
        parts = [sz, cap, "6.3V", "X5R"]
        if tol:
            parts.append(tol)
        return "_".join(p for p in parts if p)

    m = _RE_UMK.match(pni)
    if m:
        sc, t1, t2, c3, tol_ch, _v = m.groups()
        sz = _SIZE_UMK.get(sc, "")
        if not sz:
            return None
        cap = pf_eia_3_to_str(c3)
        if not cap:
            return None
        vol = _VOL_UMK.get(t2.upper(), "")
        diel = _DIEL_UMK.get(t1.upper(), t1)
        tol = _TOL_FROM_LETTER.get(tol_ch.upper(), "")
        segs: list[str] = [sz, cap]
        if diel and len(str(diel)) > 1:
            segs.append(str(diel))
        if vol:
            segs.append(vol)
        if tol:
            segs.append(tol)
        return "_".join(segs)

    m_bj = _RE_EMK_BJ.match(pni)
    if m_bj:
        sc, val_block, tol_ch = m_bj.groups()
        sz = _SIZE_EMK.get(sc, "")
        if not sz:
            return None
        tol = _TOL_FROM_LETTER.get(tol_ch.upper(), "")
        if len(val_block) == 3 and pf_eia_3_to_str(val_block):
            cap = pf_eia_3_to_str(val_block)
            parts = [sz, cap or "", "X5R"]
            if tol:
                parts.append(tol)
            return "_".join(p for p in parts if p)
        return None

    m_b = _RE_EMK_Bx.match(pni)
    if m_b:
        sc, vblock, tol_ch = m_b.groups()
        sz = _SIZE_EMK.get(sc, "")
        if not sz or len(vblock) < 3:
            return None
        tol = _TOL_FROM_LETTER.get(tol_ch.upper(), "")
        if len(vblock) == 4:
            vdig, eia3 = vblock[0], vblock[1:4]
            vol = _VOL_EMK_LEAD.get(vdig, "")
        else:
            eia3 = vblock[-3:]
            vol = ""
        cap = pf_eia_3_to_str(eia3)
        if not cap:
            return None
        parts: list[str] = [sz, cap]
        if vol:
            parts.append(vol)
        parts.append("X5R")
        if tol:
            parts.append(tol)
        return "_".join(parts)
    return None
