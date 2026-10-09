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

#: Above this, a "resistance" is a mis-split field, not a value. 100 MΩ is
#: already past the top of the SMD range (the WR catalogue stops at 10 MΩ), so a
#: four-digit code with a high exponent means the pattern cut in the wrong place.
#: The vendor codecs that predate this helper already refuse such expansions;
#: without it here they disagreed on what ``4999`` means.
_MAX_OHMS = 100_000_000


def _scaled(value: float, unit: int, suffix: str) -> str:
    """Render ``value`` in steps of ``unit``, e.g. 4750000 -> ``4.75M``.

    The K and M branches must agree on this, otherwise ``4751`` reads as
    ``4.75K`` while ``4754`` (the same 4.75 in megaohms) falls through to a raw
    ``4750000R``.
    """
    text = f"{value / unit:.3f}".rstrip("0").rstrip(".")
    return f"{text}{suffix}"


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
        # ``R`` stands for the decimal point, so the fractional digits are
        # significant as written: ``4R7`` and ``4R70`` are the same 4.7 ohm and
        # must normalise identically, or equality-based dedup sees two parts.
        frac = b.rstrip("0")
        if not frac:
            return f"{a}R"
        return f"{a}.{frac}R"
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
    if value > _MAX_OHMS:
        return None
    if value >= 1_000_000:
        if value % 1_000_000 == 0:
            return f"{value // 1_000_000}M"
        return _scaled(value, 1_000_000, "M")
    if value >= 1000:
        if value % 1000 == 0:
            return f"{value // 1000}K"
        return _scaled(value, 1000, "K")
    return f"{value}R"
