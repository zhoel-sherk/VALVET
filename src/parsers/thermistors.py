"""
Chip NTC thermistor MPN extraction (Murata NCP*, TDK NTCG*, Panasonic ERTJ*, Sunlord SDNT*).

Pass-through: returns the MPN as it appears in the BOM (no reformatting).
Strict series-specific regexes only — no generic «NTC» substring heuristics.
"""

from __future__ import annotations

from typing import Optional

from parsers.regex_api import I, compile, finditer
from parsers.registry import ParserModuleInfo, register_parser_module

PARSER_GUI_NAME = "Thermistor — NCP / NTCG / ERTJ / SDNT MPN"
PARSER_CLI_NAME = "regex.thermistor"

# Murata chip NTC: NCP + allowed size codes from lineup (03/05/15/18/21) + body.
_NCP_RE = compile(
    r"\b(NCP(?:03|05|15|18|21)[A-Z][A-Z0-9]{5,})\b",
    I,
)
# TDK chip NTC: NTCG + size code (04/06/10/16/18/20/21) + body.
_NTCG_RE = compile(
    r"\b(NTCG(?:04|06|10|16|18|20|21)[A-Z0-9]{6,})\b",
    I,
)
# Panasonic ERTJ series: ERTJ + digit + catalog body (e.g. ERTJ0EP473F).
_ERTJ_RE = compile(
    r"\b(ERTJ\d[A-Z0-9]{5,})\b",
    I,
)
# Sunlord SDNT series: SDNT + size code (0603/1005/1608/2012) + body.
_SDNT_RE = compile(
    r"\b(SDNT\d{4}[A-Z][A-Z0-9]{5,})\b",
    I,
)


def _best_match_in(s: str) -> Optional[str]:
    hits: list[str] = []
    for rx in (_NCP_RE, _NTCG_RE, _ERTJ_RE, _SDNT_RE):
        for m in rx.finditer(s):
            hits.append(m.group(1))
    if not hits:
        return None
    return max(hits, key=len)


def extract_thermistor_mpn(text: str) -> Optional[str]:
    """
    Return the thermistor MPN from a BOM comment if a full series match is found.

    Parenthesized codes are preferred when they alone match a series pattern
    (e.g. ``…(ERTJ0EP473F)``).
    """
    if not text:
        return None
    s = str(text).strip()
    if not s:
        return None
    for m in finditer(r"\(([A-Za-z0-9#./_-]{8,})\)", s):
        inner = m.group(1)
        hit = _best_match_in(inner)
        if hit:
            return hit
    return _best_match_in(s)


register_parser_module(
    ParserModuleInfo(
        module_stem="thermistors",
        role="other",
        gui_name=PARSER_GUI_NAME,
        cli_name=PARSER_CLI_NAME,
        summary="Murata NCP / TDK NTCG / Panasonic ERTJ / Sunlord SDNT chip NTC pass-through MPN.",
    )
)
