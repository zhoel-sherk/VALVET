"""
Taiyo Yuden Capacitor PN Parser

Decoding follows the Taiyo Yuden multilayer ceramic capacitor catalogue, the
"PARTS NUMBER" section of the 2018 product catalogue (26 pages; not committed
here - see ``doc/info`` and ``.gitignore``). Its layout is:

    J  M  K  3 1 6  △  B J 1 0 6  M  L  -  T
    ①  ②  ③   ④    ⑤  ⑥ ⑦     ⑧  ⑨  ⑩ ⑪

① Rated voltage        P=2.5 A=4 J=6.3 L=10 E=16 T=25 G=35 U=50
                       H=100 Q=250 S=630 X=2000
② Series name          M=MLC, V=high frequency, W=LW reverse
③ End termination      K=plated, S=Cu internal electrodes
④ Dimension (L×W)      063=0201 105=0402 107=0603 212=0805
                       316=1206 325=1210 432=1812 (021/042 are 008004/01005)
⑤ Dimension tolerance  blank (standard) or A
⑥ Series code          BJ/BBJ=X5R, B7=X7R, B=X7R, C6=X6S, C7=X7S,
                       LD=X5R, SD=standard (no X-code)
⑦ Nominal capacitance  EIA 3-digit: 104=0.1uF 105=1uF 106=10uF 107=100uF.
                       Older stock uses a 4-digit block whose first digit is a
                       voltage hint; the last three digits are still the EIA code.
⑧ Capacitance tolerance F=±1% G=±2% J=±5% K=±10% M=±20% Z=+80/-20%
⑨ Thickness / ⑩ special code / ⑪ packaging — parsed but not emitted.

The rated voltage is the FIRST LETTER of the part number, not a per-series
constant: TMK107BBJ106MA-T is 25V because of the leading ``T``.

Older UMK/EMK stock predates this layout and keeps its own branches below.

Examples:
- UMK105CH120JV-F  -> 0402_12pF_C0G_50V_5%
- TMK107BBJ106MA-T -> 0603_10uF_25V_X5R_20%
- TMK316ABJ106KD-T -> 1206_10uF_25V_X5R_10%
- JDK107BBJ226MA-T -> 0603_22uF_6.3V_X5R_20%
- LMK105BJ105KV-F  -> 0402_1uF_10V_X5R_10%
- EMK105B7223KV-F  -> 0402_22nF_16V_X7R_10%

Series-code -> dielectric values were verified against LCSC product data
(TMK107BBJ106MA-T, TMK316ABJ106KD-T, LMK105BJ105KV-F, LMK105B7104KV-F,
LMK063C6273KP-F, LMK105SD332JV-F, EMK105B7223KV-F).
"""

from __future__ import annotations

from parsers.regex_api import I, compile, sub

from ._cap_decode import pf_eia_3_to_str

VENDOR_NAME = "TaiyoYuden_MLCC"
COMPONENT_TYPES = ["CAP"]
PARSER_PRIORITY = 65

# ① Rated voltage, keyed by the first character of the part number.
_VOL_BY_LEAD = {
    "P": "2.5V",
    "A": "4V",
    "J": "6.3V",
    "L": "10V",
    "E": "16V",
    "T": "25V",
    "G": "35V",
    "U": "50V",
    "H": "100V",
    "Q": "250V",
    "S": "630V",
    "X": "2000V",
}

# ② + ③, two characters after the voltage lead: M/V/W is the series and K/S the
# end termination. JDK uses D as its series letter (absent from the 2018
# catalogue table but a real, current series).
_SERIES = r"(?:[MWVD][KS])"

# ④ Dimension code -> EIA inch size.
_SIZE_GENERAL = {
    "021": "008004",
    "042": "01005",
    "063": "0201",
    "105": "0402",
    "107": "0603",
    "212": "0805",
    "316": "1206",
    "325": "1210",
    "432": "1812",
}

# ⑥ Series code -> dielectric. SD is a low-distortion standard part and carries
# no X-code, so it maps to an empty string and the field is dropped.
_DIEL_SERIES = {
    "BBJ": "X5R",
    "BJ": "X5R",
    "LD": "X5R",
    "B7": "X7R",
    "B": "X7R",
    "C6": "X6S",
    "C7": "X7S",
    "SD": "",
}

# ⑧ Capacitance tolerance. A/B/C/D are the pF-class codes used with the
# temperature-compensating UMK stock and carry no percent value here.
_TOL_FROM_LETTER = {"F": "1%", "G": "2%", "J": "5%", "K": "10%", "M": "20%", "Z": "20%"}

# Modern stock: [voltage lead][series][size][dim tol A?][series code][EIA][tol].
# The tail (thickness, special code, packaging) is intentionally not anchored.
# Alternation order matters only for readability: "B7" and "B" both read a
# 4-digit block as lead+EIA, which yields the same capacitance either way.
_RE_GENERAL = compile(
    r"^([PAJLE TGUHQSX])"
    + _SERIES
    + r"(\d{3})(A)?(BBJ|BJ|B7|C6|C7|LD|SD|B)(\d{3,4})([JKMFGZ])",
    I,
)

# ---------------------------------------------------------------- older stock

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

# UMK105CH120JV - value 120, tol J, optional voltage letter V
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


def _parse_general(pni: str) -> str | None:
    """Decode the modern [lead][series][size][code][EIA][tol] layout."""
    m = _RE_GENERAL.match(pni)
    if not m:
        return None
    lead, sc, _dim_tol, series_code, value, tol_ch = m.groups()
    size = _SIZE_GENERAL.get(sc, "")
    if not size:
        return None
    eia3 = value[-3:]
    cap = pf_eia_3_to_str(eia3)
    if not cap:
        return None
    parts = [
        size,
        cap,
        _VOL_BY_LEAD.get(lead.upper(), ""),
        _DIEL_SERIES.get(series_code.upper(), ""),
        _TOL_FROM_LETTER.get(tol_ch.upper(), ""),
    ]
    return "_".join(p for p in parts if p)


def _parse_umk(pni: str) -> str | None:
    """Decode the pre-2018 UMK layout (voltage in a later letter, not the lead)."""
    m = _RE_UMK.match(pni)
    if not m:
        return None
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


def parse(pn: str, component_type: str) -> str | None:
    if component_type != "CAP":
        return None
    pn0 = sub(r"\s*<[gG]>\s*$", "", str(pn).strip())
    pn0 = sub(r"\s+", "", pn0).strip().upper()
    pni = sub(r"[-].*$", "", pn0)

    return _parse_general(pni) or _parse_umk(pni)
