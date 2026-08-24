"""
Yageo Resistor PN Parser

Yageo Thick Film Chip Resistor Part Number Format:
RC|RT + Size(4) + series letters + "-" + optional reel/version + resistance code + L (optional)

Examples:
- RC0402FR-0710KL → RES_0402_1K_1%
- RC0603JR-074R7L → RES_0603_4.7R_5%
- RC0603FR-07680RL → RES_0603_68R_1%

Size codes:
0201, 0402, 0603, 0805, 1206, 1210, 2010, 2512

Tolerance (prefix letter after size, e.g. RC0402``F``R…):
F=±1%, G=±2%, J=±5%, K=±10%

Resistance coding:
Digits after ``-`` — E24 3-digit / E96 4-digit / decimal ``…R…``; see ``_yageo_value_to_str`` (tail after ``-`` only, never size digits).
"""

from __future__ import annotations

from parsers.regex_api import I, compile, match, sub

from ._resistor_decode import decode_ohms_suffix

VENDOR_NAME = "Yageo_RES"
COMPONENT_TYPES = ["RES"]
PARSER_PRIORITY = 100

_SIZE = ("0201", "0402", "0603", "0805", "1206", "1210", "2010", "2512")
_TOL = {"F": "1%", "G": "2%", "J": "5%", "K": "10%"}

_RE_MAIN = compile(
    r"^R([CT])(" + "|".join(_SIZE) + r")([A-Z]{1,2})-([0-9A-Z.]+)L?$",
    I,
)


def _e24_three_to_value_ohm(code3: str) -> int:
    m = int(code3[0:2])
    e = int(code3[2])
    return m * (10**e)


def _yageo_value_to_str(code: str) -> str | None:
    s = code.strip().upper().rstrip("L")
    if not s:
        return None

    # Reel / lot prefix (e.g. 07, 00, 01, 02) when followed by a value token (not "10" which starts 1K/10K codes)
    if len(s) > 2 and s[:2].isdigit() and s[:2] in ("07", "00", "01", "02"):
        rest = s[2:]
        if rest and (rest[0].isdigit() or rest[0] in "R0"):
            s = rest

    if s in ("0", "0R", "0R0", "00"):
        return "0R"

    # 4.75K, 1K2, 4K7
    m = match(r"^(\d)K(\d{2,3})$", s, I)
    if m:
        return f"{m.group(1)}.{m.group(2)}K"
    m = match(r"^(\d{2,3})K(\d)$", s, I)
    if m:
        return f"{m.group(1)}.{m.group(2)}K"
    m = match(r"^(\d)K(\d)$", s, I)
    if m:
        return f"{m.group(1)}.{m.group(2)}K"
    m = match(r"^(\d{2,3})M(\d)$", s, I)
    if m:
        return f"{m.group(1)}.{m.group(2)}M"
    m = match(r"^(\d+(?:\.\d+)?)K$", s, I)
    if m:
        return f"{m.group(1).rstrip('0').rstrip('.') if '.' in m.group(1) else m.group(1)}K"
    m = match(r"^(\d+(?:\.\d+)?)M$", s, I)
    if m:
        return f"{m.group(1)}M"

    # nRn (4R7, 10R0, 0R, 0R0)
    m = match(r"^(\d*)R(\d+)$", s, I)
    if m:
        a, b = m.group(1) or "0", m.group(2)
        if b in ("0", "00", ""):
            return f"{a}R" if a != "0" else "0R"
        if len(b) == 1:
            if a in ("0", ""):
                return f"0.{b}R"
            return f"{a}.{b}R"
        return None

    # 10R, 5R, 12R (literal Ω; not E24 3-digit)
    m = match(r"^([0-9]{1,2})R$", s, I)
    if m:
        return f"{m.group(1)}R"

    # 680R, 1001R, 499R, 124R, …
    m = match(r"^(\d{3,4})R$", s, I)
    if m:
        d = m.group(1)
        if len(d) == 3:
            e24 = _e24_three_to_value_ohm(d)
            if e24 >= 1_000_000:
                return f"{d[0]}{d[1]}.{d[2]}R"
            if d[2] != "0" and e24 >= 1_000:
                return f"{int(d)}R"
            o = decode_ohms_suffix(d)
            if o:
                return o
            return f"{int(d)}R"
        return f"{int(d)}R"

    if s.isdigit() and len(s) in (3, 4):
        return decode_ohms_suffix(s)
    if s.isdigit() and len(s) in (1, 2) and s != "0":
        return f"{s}R"
    if s == "0":
        return "0R"

    return None


def parse(pn: str, component_type: str) -> str | None:
    if component_type != "RES":
        return None
    pn0 = sub(r"\([^)]*\)\s*$", "", str(pn).strip())
    pn0 = sub(r"\s+", "", pn0).strip().upper()
    pn0 = sub(r"^(R[CT](?:0201|0402|0603|0805|1206|1210|2010|2512))-", r"\1", pn0)
    if not (pn0.startswith("RC") or pn0.startswith("RT")):
        return None
    m = _RE_MAIN.match(pn0)
    if not m:
        return None
    rtype, size, ser, tail = m.group(1), m.group(2), m.group(3).upper(), m.group(4)
    if rtype not in ("C", "T"):
        return None
    tol_ch = ""
    for ch in "FGJKM":
        if ch in ser:
            tol_ch = ch
            break
    tol = _TOL.get(tol_ch, "")
    vstr = _yageo_value_to_str(tail)
    if not vstr:
        return None
    parts: list[str] = [size, vstr]
    if tol:
        parts.append(tol)
    return "_".join(parts)
