"""
OTHER family: strip IC/MOSFET/diode/crystal prose down to a representative MPN token.

Runs when classifier yields OTHER or when inductor regex is disabled.

Catalog labels for Debug settings:
"""

from __future__ import annotations

from parsers.regex_api import I, finditer, match, search, split, sub
from parsers.registry import ParserModuleInfo, register_parser_module

PARSER_GUI_NAME = "OTHER — MPN / preset prose extractor"
PARSER_CLI_NAME = "regex.other"

PACKAGE_PREFIXES = [
    "SOT",
    "TSSOP",
    "DFN",
    "QFN",
    "BGA",
    "LGA",
    "QFP",
    "SOP",
    "SOIC",
    "DIP",
    "TO-",
    "SC",
    "SMA",
    "SMB",
    "SMC",
    "DO",
    "2PAD",
    "MLP",
    "WDFN",
    "UDFN",
]

# English adjectives / package prose that must never be treated as an MPN.
_MPN_STOPWORDS = frozenset(
    {
        "LOW",
        "HIGH",
        "ULTRA",
        "BIDIRECTIONAL",
        "UNIDIRECTIONAL",
        "CONTACT",
        "AIR",
        "ARRAY",
        "PROTECTION",
        "SWITCH",
        "LOAD",
        "RON",
        "SMD",
        "LEAD",
        "FREE",
        "ROHS",
        "SINGLE",
        "DUAL",
        "N-CHANNEL",
        "P-CHANNEL",
    }
)


def _looks_like_mpn(token: str) -> bool:
    t = str(token or "").strip()
    if not t or len(t) < 3 or len(t) > 48:
        return False
    if " " in t or "\t" in t:
        return False
    up = t.upper()
    if up in _MPN_STOPWORDS:
        return False
    if not search(r"\d", t):
        return False
    if match(r"^[A-Z]{2,}$", up):
        return False
    return True


def clean_other(spec: str) -> str:
    """Clean other component types — extract main part number."""
    spec = spec.strip()

    if not spec:
        return ""

    def _restore(text: str) -> str:
        return sub(r"__PM__", "+/-", text)

    # Keep «+/-» / «+-» intact so XTAL «20PF/+-20PPM» is not truncated at «+».
    protected = sub(r"\+/-", "__PM__", spec)
    protected = sub(r"\+-", "__PM__", protected)

    preset_patterns = [
        r"\bPOWER-IC(?:\s+(?:SWITCH|LINEAR))?\s+(?P<mpn>[A-Z0-9][A-Z0-9#./_-]{2,})",
        r"\bTYPEC\s+IC\s+(?P<mpn>[A-Z0-9][A-Z0-9#./_-]{2,})",
        r"\bPCIE\s+[\d.]+\s+QUICK\s+SWITCH\s+IC\s+(?P<mpn>[A-Z0-9][A-Z0-9#./_-]{2,})",
        # Require a digit in IC MPN so «IC Low RON … KTS1677…» skips «Low».
        r"\bIC\s+(?P<mpn>[A-Z0-9]*\d[A-Z0-9#./_-]{1,})",
        r"\bMOSFET(?:\s+(?:N-CHANNEL|P-CHANNEL|SINGLE\s+P-CHANNEL))?\s+(?P<mpn>[A-Z0-9][A-Z0-9#./_-]{2,})",
        r"\b(?:SMD-)?(?:RECTIFIER-|SCHOTTKY-)?DIODE[S]?\s+(?:SCHOTTKY\s+BARRIER\s+DIODE\s+)?(?P<mpn>[A-Z0-9][A-Z0-9#./_-]{2,})",
        r"\bESD\s+(?:PROTECTION\s+)?(?:DIODES?\s+)?(?:(?:BIDIRECTIONAL|UNIDIRECTIONAL|ULTRA(?:\s+LOW)?(?:\s+CAPACITANCE)?(?:\s+ARRAY)?(?:\s+FOR\s+ESD\s+PROTECTION)?)\s+)*(?P<mpn>[A-Z0-9][A-Z0-9#./_-]{2,})",
        r"\bCRYSTAL\s+(?P<mpn>[0-9]+(?:\.[0-9]+)?\s*(?:MHZ|KHZ))",
        r"\((?P<mpn>[A-Z0-9][A-Z0-9#./_-]{3,})\)",
    ]
    for pat in preset_patterns:
        m = search(pat, protected, I)
        if m:
            cand = sub(r"\s+", "", m.group("mpn")).upper()
            if _looks_like_mpn(cand):
                return _restore(cand)

    parts = [p.strip() for p in split(r"[+]", protected)]
    parts = [p for p in parts if p]

    for part in parts:
        part = part.strip()
        if not part:
            continue
        is_pkg = any(
            part.upper().startswith(pkg)
            or part.upper() in [p.upper() for p in PACKAGE_PREFIXES]
            for pkg in PACKAGE_PREFIXES
        )
        if is_pkg:
            continue
        if match(r"^[A-Z][A-Z0-9]{2,}[A-Z0-9-]*[A-Z0-9]$", part) and _looks_like_mpn(
            part
        ):
            return _restore(part)
        if (
            match(r"^[A-Z]+[0-9]+[A-Z]*", part)
            and len(part) > 4
            and _looks_like_mpn(part)
        ):
            return _restore(part)

    if parts:
        for part in reversed(parts):
            part = part.strip()
            if not part:
                continue
            is_pkg = any(part.upper().startswith(pkg) for pkg in PACKAGE_PREFIXES)
            if (
                not is_pkg
                and len(part) > 2
                and match(r"^[A-Z0-9]", part)
                and _looks_like_mpn(part)
            ):
                return _restore(part)

    # Mid-prose MPN scan (IC/ESD when adjective precedes the catalog code).
    best = ""
    for m in finditer(r"\b([A-Z]{1,6}\d[A-Z0-9#./_-]{2,})\b", protected, I):
        cand = m.group(1).upper()
        if _looks_like_mpn(cand) and len(cand) > len(best):
            best = cand
    if best:
        return _restore(best)

    if parts:
        return _restore(parts[-1])
    return _restore(protected)


register_parser_module(
    ParserModuleInfo(
        module_stem="other_pars",
        role="other",
        gui_name=PARSER_GUI_NAME,
        cli_name=PARSER_CLI_NAME,
        summary="Heuristic MPN extraction for non-R/C/L rows.",
    )
)
