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

_END = r"(?=(?:$|[^A-Z0-9]))"

# Tai-Tech / common high-current beads:
# HCB1608KF-800T30, HCB1608KF_221T30, ...
_HCB_RE = compile(
    r"(HCB\d{4}K[A-Z][-_]\d{3}T\d{2})(?=(?:HCB|$|[^A-Z0-9]))",
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

# Sunlord PZ large-current: PZ1005E121-R70TF, PZ1608U300-3R0TF, PZ1005E121_R70TF
_PZ_RE = compile(
    rf"(PZ(?:0603|1005|1608|2012|3216|4516)[DEU]\d{{3}}[-_][0-9]*R?[0-9]+TF(?:A99)?){_END}",
    I,
)

# Microgate MGLB: MGLB1005M121T0R7-LF, MGLB1608M300T3R0-LF
_MGLB_RE = compile(
    rf"(MGLB(?:1005|1608|2012|3216)[EMQ]\d{{3}}[TB][0-9]+R[0-9]+(?:-?LF)?){_END}",
    I,
)

# Sunlord GZ (impedance in MPN, no current suffix): GZ1005U601TF
_GZ_RE = compile(
    rf"(GZ(?:0603|1005|1608|2012|3216|4516)[DEU]\d{{3}}TF){_END}",
    I,
)

# Fenghua CBG/CBW/CBM: CBG100505U121T
_FENGHUA_CB_RE = compile(
    rf"(CB[GWM]\d{{6}}[A-Z]\d{{3}}T){_END}",
    I,
)

# Samsung CIM/CIB: CIM05J121NC
_SAMSUNG_CI_RE = compile(
    rf"(CI[MB]\d{{2}}[A-Z]\d{{3}}[NAB][CE]){_END}",
    I,
)

# TDK MMZ/MPZ (not MLZ inductors): MMZ1608B121C, MPZ2012S300AT000
_TDK_MZ_RE = compile(
    rf"(M[MP]Z(?:0603|1005|1608|2012|3216)[A-Z]\d{{3}}[A-Z0-9]{{0,8}}){_END}",
    I,
)

# Microgate MGGB: MGGB1005M121HT-LF
_MGGB_RE = compile(
    rf"(MGGB(?:1005|1608|2012|3216)[EMQ]\d{{3}}[A-Z]{{1,3}}(?:-LF)?){_END}",
    I,
)

# Taiyo Yuden BK: BK1608HS121-T
_BK_RE = compile(
    rf"(BK(?:0603|1005|1608|2012|3216)[A-Z]{{2}}\d{{3}}-T){_END}",
    I,
)

_SERIES_RES = (
    _HCB_RE,
    _PBY_RE,
    _LCB_GCB_RE,
    _BLM_RE,
    _CMS_RE,
    _PZ_RE,
    _MGLB_RE,
    _GZ_RE,
    _FENGHUA_CB_RE,
    _SAMSUNG_CI_RE,
    _TDK_MZ_RE,
    _MGGB_RE,
    _BK_RE,
)


def _best_match_in(s: str) -> Optional[str]:
    hits: list[str] = []
    for rx in _SERIES_RES:
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
