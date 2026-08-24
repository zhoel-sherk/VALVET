"""
Ferrite bead MPN extraction (pass-through, like thermistors).

Goal:
- extract only the bead MPN from noisy BOM prose;
- do not normalize to R/L values (these are not resistors/inductors);
- keep the original catalog code so downstream tooling can map datasheets cleanly.
"""

from __future__ import annotations

from typing import Optional

from parsers.regex_api import I, compile, finditer
from parsers.registry import ParserModuleInfo, register_parser_module

PARSER_GUI_NAME = "Ferrite bead — MPN pass-through"
PARSER_CLI_NAME = "regex.ferrite_bead"

# Tai-Tech / common high-current beads:
# HCB1608KF-800T30, HCB1608KF-121T20, ...
_HCB_RE = compile(
    r"(HCB\d{4}K[A-Z]-\d{3}T\d{2})(?=(?:HCB|$|[^A-Z0-9]))",
    I,
)

# Generic p/n style found in curated corpus:
# PBY100505T-121Y-N
_PBY_RE = compile(
    r"(PBY\d{6}T-\d{3}[A-Z]-[A-Z])(?=(?:$|[^A-Z0-9-]))",
    I,
)

# Sporton style:
# LCB1608K-300T50, LCB2012K-300T60, GCB1608K-121T06, ...
_LCB_GCB_RE = compile(
    r"([LG]CB\d{4}K-\d{3}T\d{2})(?=(?:$|[^A-Z0-9-]))",
    I,
)

# Murata ferrite bead style:
# BLM18PG121SN1D, BLM15AG121SN1D, ...
_BLM_RE = compile(
    r"(BLM\d{2}[A-Z]{2}\d{3}[A-Z]{2}\d[A-Z])(?=(?:$|[^A-Z0-9]))",
    I,
)

# Maxecho styles:
# ACMS160808A121, BCMS160808A300RDC01, EBMS100505A121, ...
_CMS_RE = compile(
    r"((?:ACMS|BCMS|EBMS)\d{6}A\d{3}(?:\s*RDC\d{1,2})?)(?=(?:$|[^A-Z0-9]))",
    I,
)


def _best_match_in(s: str) -> Optional[str]:
    hits: list[str] = []
    for rx in (_HCB_RE, _PBY_RE, _LCB_GCB_RE, _BLM_RE, _CMS_RE):
        for m in rx.finditer(s):
            hits.append(m.group(1).replace(" ", ""))
    if not hits:
        return None
    return max(hits, key=len)


def extract_ferrite_bead_mpn(text: str) -> Optional[str]:
    """
    Return ferrite-bead MPN from a noisy BOM field.

    Parenthesized candidates are checked first (common in imported BOM lines).
    """
    if not text:
        return None
    s = str(text).strip()
    if not s:
        return None
    for m in finditer(r"\(([A-Za-z0-9#./_-]{6,})\)", s):
        inner = m.group(1)
        hit = _best_match_in(inner)
        if hit:
            return hit
    return _best_match_in(s)


register_parser_module(
    ParserModuleInfo(
        module_stem="ferrite_beads",
        role="other",
        gui_name=PARSER_GUI_NAME,
        cli_name=PARSER_CLI_NAME,
        summary="Ferrite-bead MPN extraction pass-through for noisy BOM text.",
    )
)
