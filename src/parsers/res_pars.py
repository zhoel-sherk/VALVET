"""
Resistor BOM regex parser (`regex` pipeline step for RES).

Extends chip/value/watt/tolerance extraction from '+' or whitespace-separated tokens.

Catalog labels for Debug settings:
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from clean_types import CleanConfig, default_clean_config

from parsers.bom_text_utils import (
    normalize_for_regex_parsing,
    normalize_res_ohm_value,
    tokenize_bom_spec,
)
from parsers.constants import PACKAGE_PATTERN
from parsers.formatting import format_resistor_fields
from parsers.inferit_pars import parse_inferit_resistor
from parsers.regex_api import I, match, search
from parsers.registry import ParserModuleInfo, register_parser_module

PARSER_GUI_NAME = "Resistor — chip token regex"
PARSER_CLI_NAME = "regex.resistor"


def parse_resistor_token_fields(
    spec: str,
    config: Optional[CleanConfig] = None,
) -> Tuple[Dict[str, str], str]:
    """Token-regex path only (no INFERIT): raw slot dict and formatted string."""
    cfg = default_clean_config(config)
    raw_spec = str(spec).strip()
    if not cfg.parse_resistors:
        return {}, raw_spec
    spec2 = normalize_for_regex_parsing(raw_spec)
    spec2 = spec2.replace("\\", "/").replace("CHIP RES.(THICK FILM)", "").strip()

    package = ""
    netres = match(r"^NETRES[-\s]+SMD\s+(?P<pack>\d{4})-8P4R\b", spec2, I)
    if netres:
        package = netres.group("pack")

    parts = tokenize_bom_spec(spec2)

    value = ""
    watt = ""
    tolerance = ""

    for part in parts:
        if not part:
            continue
        if not package and match(rf"^({PACKAGE_PATTERN})$", part, I):
            package = part
            continue
        if not package and match(rf"^({PACKAGE_PATTERN})-(?:8P4R|\d+P\d+R|[A-Za-z0-9]+)$", part, I):
            package = match(rf"^({PACKAGE_PATTERN})", part, I).group(1)
            continue
        wm = search(r"(?<![0-9.])(\d+/\d+W|\d+(?:\.\d+)?W)(?![0-9A-Z])", part, I)
        if wm:
            watt = wm.group(1).upper()
        if "%" in part and "(" in part:
            tol_match = match(r"^[±]?(\d+)%\((\w)\)$", part)
            if tol_match:
                tol, letter = tol_match.groups()
                tolerance = f"{tol}%({letter})"
            continue
        if "%" in part:
            tol = part.replace("%", "").replace("±", "")
            if match(r"^[\d\.]+$", tol):
                if tol:
                    tolerance = f"{tol}%"
            continue
        if match(r"^[\d\.]+[RKM]?$", part, I):
            # Keep original case so lowercase m (milli) survives normalize.
            value = part.strip()
            continue

        if match(r"^[\d.]+[RKM]$", part, I):
            value = part.strip()
            continue

    if not value:
        for part in parts:
            # Case-sensitive milli: 1m / 2mOHM before IGNORECASE mega paths.
            m_milli = match(r"^([0-9.]+)m(?:ohm)?$", part)
            if m_milli:
                value = f"{m_milli.group(1)}m"
                break
            m_ohm = match(
                r"^([0-9.]+)(R|KR|MR|M|K|OHM|KOHM|MOHM)$", part, I
            )
            if m_ohm:
                num, unit = m_ohm.groups()
                # Preserve original unit case for m vs M when single-letter.
                unit_raw = part[len(num) :]
                unit = unit.upper()
                if unit == "R":
                    unit = ""
                elif unit == "KR":
                    unit = "K"
                elif unit in ["MR", "MOHM"]:
                    unit = "M"
                elif unit == "M" and unit_raw.startswith("m") and not unit_raw.upper().startswith("MOHM"):
                    # lowercase m alone → milliohm marker for normalize_res_ohm_value
                    value = f"{num}m"
                    break
                elif unit == "M":
                    unit = "M"
                value = f"{num}{unit}" if unit else num
                break

    if value:
        value = normalize_res_ohm_value(
            value, include_ohm_r_suffix=cfg.resistor_include_ohm_r_suffix
        )

    if not package:
        for part in parts:
            if match(rf"^({PACKAGE_PATTERN})$", part, I):
                package = part
                break
    if not watt:
        for part in parts:
            wm = search(r"(?<![0-9.])(\d+/\d+W|\d+(?:\.\d+)?W)(?![0-9A-Z])", part, I)
            if wm:
                watt = wm.group(1).upper()
                break
    if not package:
        for part in parts:
            m = search(r"\((\d{4})\)", part)
            if m and match(rf"^({PACKAGE_PATTERN})$", m.group(1), I):
                package = m.group(1)
                break

    if not tolerance:
        for part in parts:
            m = search(r"(\d+)%\s*$", part)
            if m:
                tolerance = f"{m.group(1)}%"
                break

    fields = {"pack": package, "nom": value, "watt": watt, "%": tolerance}
    result = format_resistor_fields(fields, cfg)
    raw = {k: v for k, v in fields.items() if str(v).strip()}
    out = result if result else raw_spec
    return raw, out


def parse_resistor(
    spec: str,
    config: Optional[CleanConfig] = None,
    *,
    skip_inferit_presets: bool = False,
) -> str:
    """Parse resistor specifications like '100R+1/16W+±5%+0402'."""
    cfg = default_clean_config(config)
    if not cfg.parse_resistors:
        return str(spec).strip()
    spec_ns = normalize_for_regex_parsing(str(spec).strip())
    if not skip_inferit_presets:
        inferit = parse_inferit_resistor(spec_ns, cfg)
        if inferit:
            return inferit
    _, out = parse_resistor_token_fields(spec_ns, cfg)
    return out


register_parser_module(
    ParserModuleInfo(
        module_stem="res_pars",
        role="regex_res",
        gui_name=PARSER_GUI_NAME,
        cli_name=PARSER_CLI_NAME,
        summary="Token resistor parser after optional INFERIT resistor presets.",
    )
)
