"""
Inductor BOM regex parser (`regex` pipeline step for IND).

Works on '+'-separated PnP-style lines (µH / nH, DCR, Imax, package codes).

Catalog labels for Debug settings:
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from clean_types import CleanConfig, default_clean_config

from parsers.bom_text_utils import normalize_for_regex_parsing
from parsers.constants import PACKAGE_PATTERN
from parsers.formatting import format_inductor_fields, inductor_pack_guess
from parsers.inferit_pars import parse_inferit_inductor
from parsers.regex_api import I, compile, match, split, sub
from parsers.registry import ParserModuleInfo, register_parser_module

PARSER_GUI_NAME = "Inductor — PnP token regex"
PARSER_CLI_NAME = "regex.inductor"

_PL_JOIN_HEAD = compile(
    r"^PL_(?P<nom>[\d.]+(?:uH|nH|mH|H))_"
    r"(?:±|\+/-|\+-)?(?P<tol>[\d.]+)%_"
    r"(?P<dcr>[\d.]+(?:mΩ|mohm|mOHM|Ω|OHM))_"
    r"(?P<imax>[\d.]+[Aa])",
    I,
)


def _inductor_spec_parts(spec: str) -> list[str]:
    s = str(spec).strip()
    if s.upper().startswith("PL_"):
        return [p for p in s.split("_") if p]
    return [p.strip() for p in split(r"[+]", s) if p.strip()]


def try_parse_pl_join_inductor_fields(
    spec: str, cfg: CleanConfig
) -> Optional[Tuple[Dict[str, str], str]]:
    s = str(spec).strip()
    m = _PL_JOIN_HEAD.match(s)
    if not m:
        return None
    raw = {
        "pack": inductor_pack_guess(s),
        "nom": m.group("nom"),
        "%": f"{m.group('tol')}%",
        "DCR": m.group("dcr").replace("MOHM", "mΩ").replace("mohm", "mΩ"),
        "Imax": m.group("imax").upper().replace(" ", ""),
    }
    out = format_inductor_fields(raw, cfg)
    return (raw, out) if out else None


def parse_inductor_token_fields(
    spec: str,
    config: Optional[CleanConfig] = None,
) -> Tuple[Dict[str, str], str]:
    """Token-regex path only (no INFERIT)."""
    cfg = default_clean_config(config)
    raw_in = str(spec).strip()
    if not cfg.parse_inductors:
        return {}, raw_in
    spec2 = normalize_for_regex_parsing(raw_in)
    spec2 = spec2.replace("\\", "/").strip()

    pl = try_parse_pl_join_inductor_fields(spec2, cfg)
    if pl is not None:
        return pl

    parts = _inductor_spec_parts(spec2)

    package = ""
    value = ""
    imax = ""
    tolerance = ""
    dcr = ""

    for part in parts:
        if not part:
            continue
        if match(rf"^({PACKAGE_PATTERN})$", part, I):
            package = part
        elif (
            "V" in part.upper()
            and any(c.isdigit() for c in part)
            and "A" not in part.upper()
        ):
            continue
        elif (
            "A" in part.upper()
            and any(c.isdigit() for c in part)
            and "Ω" not in part.upper()
        ):
            imax = part.upper().replace(" ", "")
        elif "mΩ" in part.upper() or "mohm" in part.upper():
            dcr = sub(r"\s+", "", part).upper().replace("MAX", "")
        elif "%" in part:
            tol = part.replace("%", "").replace("±", "")
            if tol and tol != "30":
                tolerance = f"{tol}%"
        elif match(r"^[\d\.]+(U|N|P)?H$", part, I):
            value = part.upper().replace(" ", "")

    if not value:
        for part in parts:
            m = match(r"^([\d\.]+)(UH|NH|MH|H)$", part, I)
            if m:
                num, unit = m.groups()
                value = f"{num}{unit.upper()}"
                break

    if not package:
        for part in parts:
            if match(rf"^({PACKAGE_PATTERN})$", part, I):
                package = part
                break

    fields = {"pack": package, "nom": value, "Imax": imax, "%": tolerance, "DCR": dcr}
    result = format_inductor_fields(fields, cfg)
    raw = {k: v for k, v in fields.items() if str(v).strip()}
    out = result if result else spec2
    return raw, out


def parse_inductor(
    spec: str,
    config: Optional[CleanConfig] = None,
    *,
    skip_inferit_presets: bool = False,
) -> str:
    """Parse inductor specifications like '2.2uH+±30%+…'."""
    cfg = default_clean_config(config)
    if not cfg.parse_inductors:
        return str(spec).strip()
    spec_ns = normalize_for_regex_parsing(str(spec).strip())
    if not skip_inferit_presets:
        inferit = parse_inferit_inductor(spec_ns, cfg)
        if inferit:
            return inferit
    _, out = parse_inductor_token_fields(spec_ns, cfg)
    return out


register_parser_module(
    ParserModuleInfo(
        module_stem="ind_pars",
        role="regex_ind",
        gui_name=PARSER_GUI_NAME,
        cli_name=PARSER_CLI_NAME,
        summary="Fallback inductor regex after INFERIT inductor presets.",
    )
)
