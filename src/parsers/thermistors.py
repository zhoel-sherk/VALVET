"""
Chip NTC thermistor MPN extraction (series-specific pass-through).

Pass-through: returns the MPN as it appears in the BOM (no reformatting).
Strict series-specific regexes only — no generic «NTC» substring heuristics.
"""

from __future__ import annotations

from typing import Optional

from parsers.regex_api import I, compile, finditer
from parsers.registry import ParserModuleInfo, register_parser_module

PARSER_GUI_NAME = "Thermistor — chip NTC MPN pass-through"
PARSER_CLI_NAME = "regex.thermistor"

_END = r"(?=(?:$|[^A-Z0-9]))"

# Murata NCP (incl. 02 / 01005): NCP15WF104F03RC, NCP02WF104F05RL
_NCP_RE = compile(
    r"\b(NCP(?:02|03|05|15|18|21)[A-Z][A-Z0-9]{5,})\b",
    I,
)
# Murata NCU automotive: NCU18XH103F6SRB
_NCU_RE = compile(
    r"\b(NCU(?:03|15|18)[A-Z][A-Z0-9]{5,})\b",
    I,
)
# Murata NCG conductive glue: NCG18XH103F0SRB
_NCG_RE = compile(
    r"\b(NCG(?:15|18)[A-Z][A-Z0-9]{5,})\b",
    I,
)
# TDK chip NTC: NTCG103JF103FT1
_NTCG_RE = compile(
    r"\b(NTCG(?:04|06|10|16|18|20|21)[A-Z0-9]{6,})\b",
    I,
)
# Panasonic ERTJ: ERTJ0EP473F, ERTJZEG103JA (Z = 0201)
_ERTJ_RE = compile(
    r"\b(ERTJ[0-9Z][A-Z0-9]{5,})\b",
    I,
)
# Panasonic automotive hyphen: ERT-J0EP473FM
_ERTJ_HYPH_RE = compile(
    rf"(ERT-J[0-9Z][A-Z0-9]{{5,}}){_END}",
    I,
)
# Sunlord SDNT: SDNT1005X473F4050FTF
_SDNT_RE = compile(
    r"\b(SDNT\d{4}[A-Z][A-Z0-9]{5,})\b",
    I,
)
# Fenghua CMF: R25 then B, suffix ANT — CMFD103J3900HANT
_CMF_FH_RE = compile(
    rf"(CMF[ABCDX]\d{{3}}[FGHJKX]\d{{4}}[FGHJK]ANT){_END}",
    I,
)
# Cantherm CMF: B then R25, suffix NT — CMFA3435103JNT
_CMF_CT_RE = compile(
    rf"(CMF[ABXC]\d{{4}}\d{{3}}[FGHJK]NT){_END}",
    I,
)
# Thinking TSM: TSM1A103F34D1RZ
_TSM_RE = compile(
    rf"(TSM[A012][AB]\d{{3}}[A-Z0-9]{{3,}}){_END}",
    I,
)
# Vishay NTCS: NTCS0603E3103FLT, NTCS0603E3103JMT
_NTCS_RE = compile(
    rf"(NTCS(?:0402|0603|0805|1206)E[34]\d{{3}}[FGHJ][LMX]T){_END}",
    I,
)
# TDK/EPCOS SMD B573xx / B572xx: B57321V2103J060
_B57_RE = compile(
    rf"(B57\d{{3}}V[25]\d{{3,4}}[FGHJ]0(?:60|62|70|72)){_END}",
    I,
)
# Kyocera AVX NB/NC chip: NB12K00103JBB
_NB_RE = compile(
    rf"(N[BC](?:12|20|21)[A-Z]0\d{{3,4}}[FGHJKLMX][A-Z]{{2}}){_END}",
    I,
)
# Abracon: ABNTC-0603-103J-3950F-T
_ABNTC_RE = compile(
    rf"(ABNTC-(?:0402|0603|0805)-\d{{3}}[FGHJK]-\d{{4}}[FH]-T){_END}",
    I,
)
# Bourns BTN SMD (not disc ICL): BTN04G103F3HFT00
_BTN_RE = compile(
    rf"(BTN0[24]G\d{{3}}[FGHJ]\d[A-Z]FT[A-Z0-9]{{2,}}){_END}",
    I,
)

_SERIES_RES = (
    _NCP_RE,
    _NCU_RE,
    _NCG_RE,
    _NTCG_RE,
    _ERTJ_RE,
    _ERTJ_HYPH_RE,
    _SDNT_RE,
    _CMF_FH_RE,
    _CMF_CT_RE,
    _TSM_RE,
    _NTCS_RE,
    _B57_RE,
    _NB_RE,
    _ABNTC_RE,
    _BTN_RE,
)


def _best_match_in(s: str) -> Optional[str]:
    hits: list[str] = []
    for rx in _SERIES_RES:
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
        summary=(
            "Chip NTC pass-through: Murata NCP/NCU/NCG, TDK NTCG/B57, "
            "Panasonic ERTJ, Sunlord SDNT, Vishay NTCS, Thinking TSM, CMF, …"
        ),
    )
)
