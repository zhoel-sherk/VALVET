"""
Resistance decode helpers (pn_original)

Shared thick-film / chip resistance decoding for vendor resistor parsers.

Part Number Format (conceptual):
Suffix token after series prefix — digits (E24 3 / E96 4) or decimal ``nRm`` ohms notation

Examples:
- decode_ohms_suffix("4751") → "4.75K"
- decode_ohms_suffix("10R0") → "10R"

Tolerance / size live in each vendor module — this file only normalizes Ω strings.
"""

from __future__ import annotations

from parsers.regex_api import match


def decode_ohms_suffix(s: str) -> str | None:
    """
    Decode a resistance token after a series prefix (e.g. 100, 10R0, 1001, 0).
    Returns a normalized value string (..R, ..K, ..M) or None.
    """
    t = s.strip().upper()
    if not t:
        return None
    if t in ("0", "00", "000", "0000"):
        return "0R"
    if match(r"^([0-9]+)R([0-9]+)$", t):
        m = match(r"^([0-9]+)R([0-9]+)$", t)
        assert m
        a, b = m.group(1), m.group(2)
        if b == "0" or b == "00":
            return f"{a}R"
        return f"{a}.{b}R"
    if not t.isdigit():
        return None
    if len(t) == 3:
        mantissa = int(t[:2])
        exp = int(t[2])
        value = mantissa * (10**exp)
    elif len(t) == 4:
        mantissa = int(t[:3])
        exp = int(t[3])
        value = mantissa * (10**exp)
    else:
        return None
    if value == 0:
        return "0R"
    if value < 1_000_000:
        if 1000 <= value < 1_000_000:
            if value % 1000 == 0:
                return f"{value // 1000}K"
            s_k = f"{value / 1000.0:.3f}".rstrip("0").rstrip(".")
            return f"{s_k}K"
        if value < 1000:
            return f"{value}R"
    if value >= 1_000_000 and value % 1_000_000 == 0:
        return f"{value // 1_000_000}M"
    return f"{value}R"
