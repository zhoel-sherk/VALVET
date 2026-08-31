"""Chip footprint prefixes, IEC-60062 compact ohms, default watt-by-size."""

from __future__ import annotations

from parsers.constants import PACKAGE_PATTERN
from parsers.regex_api import I, match

# UniOhm omit-watt table (regex/inferit only when CleanConfig flag is on).
PACKAGE_DEFAULT_WATT: dict[str, str] = {
    "0201": "1/20W",
    "0402": "1/16W",
    "0603": "1/10W",
    "0805": "1/8W",
    "1206": "1/4W",
    "1210": "1/2W",
    "2010": "3/4W",
    "2512": "1W",
}

_PACK_EXACT = rf"^([RC])?({PACKAGE_PATTERN})$"
_PACK_COMPOUND = (
    rf"^([RC])?({PACKAGE_PATTERN})-(?:8P4R|\d+P\d+R|[A-Za-z0-9]+)$"
)
_PACK_IN_STRING = rf"(?<![A-Za-z0-9])[RC]?({PACKAGE_PATTERN})(?![A-Za-z0-9])"


def match_package_token(part: str) -> str:
    """Bare ``0402`` or prefixed ``R0402`` / ``C0603`` → size code, else ``""``."""
    p = str(part).strip()
    if not p:
        return ""
    m = match(_PACK_EXACT, p, I)
    if m:
        return m.group(2)
    m = match(_PACK_COMPOUND, p, I)
    if m:
        return m.group(2)
    return ""


def find_package_in_text(text: str) -> str:
    """First chip size in a prose line, allowing R/C prefixes."""
    m = match(_PACK_EXACT, str(text).strip(), I)
    if m:
        return m.group(2)
    from parsers.regex_api import search

    mm = search(_PACK_IN_STRING, str(text), I)
    return mm.group(1) if mm else ""


def watt_for_package(pack: str) -> str:
    return PACKAGE_DEFAULT_WATT.get(str(pack).strip(), "")


def _format_decimal_prefix(left: str, right: str, suffix: str) -> str:
    body = f"{left}.{right}".rstrip("0").rstrip(".")
    if not body or body == ".":
        body = "0"
    return f"{body}{suffix}"


def expand_compact_rkm(token: str) -> str | None:
    """
    IEC 60062-style compact ohms: ``4K7`` → ``4.7K``, ``39K2`` → ``39.2K``,
    ``2K49`` → ``2.49K``, ``49R9`` → ``49.9R``. Returns None if not compact.
    """
    compact = str(token).strip()
    if not compact:
        return None
    m = match(r"^([0-9]+)([RrKkM])([0-9]+)$", compact)
    if not m:
        return None
    left, letter, right = m.group(1), m.group(2), m.group(3)
    if letter in "rR":
        out = _format_decimal_prefix(left, right, "R")
    elif letter in "kK":
        out = _format_decimal_prefix(left, right, "K")
    elif letter == "M":
        out = _format_decimal_prefix(left, right, "M")
    else:
        return None
    return out


def canonical_voltage_token(num: str, unit: str) -> str:
    """``3`` + ``kV``/``KV``/``V`` → ``3KV`` or ``3V``."""
    n = str(num).strip()
    u = str(unit).strip().upper()
    if u in ("KV",):
        return f"{n}KV"
    return f"{n}V"
