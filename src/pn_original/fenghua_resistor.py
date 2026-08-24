"""
Fenghua (风华) thick-film chip resistor PN parser.

Part Number Format (General Thick Film / RC series):
RC - Size(2) - TCR - Resistance - Tolerance - Packing

Examples:
- RC-02U3R30FT → 0402_3.3R_1%
- RC-02U2R00FT → 0402_2R_1%
- RC-01W1623FT → 0201_162K_1%  (E96 four-digit)

Size codes:
01=0201, 02=0402, 03=0603, 05=0805, 06=1206, 10=1210, 12=2512, …

Tolerance:
F=±1%, G=±2%, J=±5%, K=±10%, D=±0.5%, M=±20%

Resistance:
E-24 three digits / E-96 four digits / «R» as decimal (3R30 → 3.3R)

Reference:
https://www.fhcomp.com/en/product_page/?code=020101
"""

from __future__ import annotations

from parsers.regex_api import I, compile

VENDOR_NAME = "Fenghua_RES"
COMPONENT_TYPES = ["RES"]
PARSER_PRIORITY = 82

_SIZE = {
    "005": "01005",
    "01": "0201",
    "02": "0402",
    "03": "0603",
    "05": "0805",
    "06": "1206",
    "F": "1210",
    "10": "2010",
    "12": "2512",
}
_TOL = {
    "D": "0.5%",
    "F": "1%",
    "G": "2%",
    "J": "5%",
    "K": "10%",
    "M": "20%",
}

_RE = compile(
    r"^RC-?(?P<size>005|01|02|03|05|06|10|12|F)"
    r"(?P<tcr>[A-Z])"
    r"(?P<res>[0-9R]+)"
    r"(?P<tol>[DFGJKM])"
    r"(?P<pack>[A-Z0-9]*)$",
    I,
)


def _format_ohm(value: float) -> str:
    if value < 0:
        return ""
    if value == 0:
        return "0R"
    if value >= 1_000_000:
        v = value / 1_000_000.0
        return f"{v:.3f}".rstrip("0").rstrip(".") + "M"
    if value >= 1_000:
        v = value / 1_000.0
        return f"{v:.3f}".rstrip("0").rstrip(".") + "K"
    if float(value).is_integer():
        return f"{int(value)}R"
    return f"{value:.3f}".rstrip("0").rstrip(".") + "R"


def _decode_res(code: str) -> str | None:
    s = code.upper().strip()
    if not s:
        return None
    if s in ("000", "0", "0R", "0R0"):
        return "0R"
    if "R" in s:
        # 3R30 → 3.30, 1R0 → 1.0, R100 → 0.100
        if s.startswith("R"):
            frac = s[1:]
            if not frac.isdigit():
                return None
            return _format_ohm(float(f"0.{frac}"))
        left, _, right = s.partition("R")
        if not left.isdigit():
            return None
        if not right:
            return _format_ohm(float(left))
        if not right.isdigit():
            return None
        return _format_ohm(float(f"{left}.{right}"))
    if not s.isdigit():
        return None
    if len(s) == 4:
        return _format_ohm(float(int(s[:3]) * (10 ** int(s[3]))))
    if len(s) == 3:
        return _format_ohm(float(int(s[:2]) * (10 ** int(s[2]))))
    return None


def parse(pn: str, component_type: str) -> str | None:
    if component_type not in COMPONENT_TYPES:
        return None
    s = pn.strip().upper().replace(" ", "")
    m = _RE.match(s)
    if not m:
        return None
    size = _SIZE.get(m.group("size").upper())
    if not size:
        return None
    ohm = _decode_res(m.group("res"))
    if not ohm:
        return None
    tol = _TOL.get(m.group("tol").upper(), "")
    parts = [size, ohm]
    if tol:
        parts.append(tol)
    return "_".join(parts)
