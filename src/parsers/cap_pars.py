"""
Capacitor BOM regex parser (`regex` pipeline step for CAP).

Handles:
  • INFERIT CAP lines (delegated when ``skip_inferit_presets`` is False)
  • Single-line BOM prose with ``nom/V`` slash (e.g. ``1UF/16V(0402)X5R …``), not only
    lines that spell «MLCC»
  • Token streams (+ or whitespace separated): value, V (volt), package, film, tolerance

To extend: add branches in `parse_capacitor` or extract helpers below; register extra
`ParserModuleInfo` rows if you split into multiple files.

Catalog labels for Debug settings:
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from clean_types import CleanConfig, default_clean_config

from parsers.bom_text_utils import (
    capacitor_nominal_pf,
    normalize_for_regex_parsing,
    normalize_value_unit,
    preprocess_cap_tokens_for_slash_voltage,
    snap_cap_tolerance_pf_to_std_pct,
    tokenize_bom_spec,
)
from parsers.chip_tokens import canonical_voltage_token, find_package_in_text, match_package_token
from parsers.constants import MLCC_DIELECTRIC
from parsers.formatting import format_cap_fields
from parsers.inferit_pars import parse_inferit_capacitor, try_parse_mlcc_underscore_cap_fields
from parsers.regex_api import I, escape, findall, match, search
from parsers.registry import ParserModuleInfo, register_parser_module

PARSER_GUI_NAME = "Capacitor — UF/V slash line + token regex"
PARSER_CLI_NAME = "regex.capacitor"


def try_parse_mlcc_bom_line_slots(
    spec: str, cfg: CleanConfig
) -> Optional[Tuple[Dict[str, str], str]]:
    """BOM line with ``<value><PF|NF|UF|F>/<n>V`` (optional ``(0402)`` dielectric) → slots."""
    s = spec.strip()
    vm = search(r"([\d.]+)\s*(PF|NF|UF|F)\s*/\s*([\d.]+)\s*(kV|KV|V)\b", s, I)
    if not vm:
        return None
    value = normalize_value_unit(
        f"{vm.group(1)}{vm.group(2)}", cap_uf_micro_sign=cfg.cap_uf_micro_sign
    )
    vraw = vm.group(4).upper()
    voltage = canonical_voltage_token(vm.group(3), vraw)
    package = ""
    pm = search(r"\((\d{4}(?:/[A-Z])?)\)", s)
    if pm:
        package = pm.group(1)
    if not package:
        package = find_package_in_text(s)
    if not package:
        pm2 = search(r"\b(\d{4}/[A-Z])\b", s, I)
        if pm2:
            package = pm2.group(1)
    dielectric = ""
    diel_alts = sorted(MLCC_DIELECTRIC | {"COG"}, key=len, reverse=True)
    m_stuck = search(
        r"\(\d{4}\)\s*(" + "|".join(escape(x) for x in diel_alts) + r")\b",
        s,
        I,
    )
    if m_stuck:
        cand = m_stuck.group(1).upper()
        dielectric = "C0G" if cand == "COG" else cand
    if not dielectric:
        m_word = search(
            r"\b(" + "|".join(sorted(MLCC_DIELECTRIC, key=len, reverse=True)) + r")\b",
            s,
            I,
        )
        if m_word:
            d = m_word.group(1).upper()
            dielectric = "C0G" if d == "COG" else d
    tolerance = ""
    tpl = search(
        r"(?:\+/-|±)\s*([0-9]+(?:\.[0-9]+)?)\s*(?:PF|pF)\b",
        s,
        I,
    )
    if tpl:
        tol_pf = float(tpl.group(1))
        nom_pf = capacitor_nominal_pf(f"{vm.group(1)}{vm.group(2).upper()}")
        tolerance = snap_cap_tolerance_pf_to_std_pct(tol_pf, nom_pf)
    if not tolerance:
        tpf = search(r"(0\.\d+)\s*PF\b", s, I)
        if tpf:
            tolerance = normalize_value_unit(
                f"{tpf.group(1)}PF", cap_uf_micro_sign=cfg.cap_uf_micro_sign
            )
        else:
            pcts = findall(r"(\d+\.?\d*)\s*%", s)
            if pcts:
                tolerance = f"{pcts[-1]}%"

    fields = {
        "pack": package,
        "nom": value,
        "V": voltage,
        "film": dielectric,
        "%": tolerance,
    }
    result = format_cap_fields(fields, cfg)
    if not result:
        return None
    raw = {k: v for k, v in fields.items() if str(v).strip()}
    return raw, result


def try_parse_mlcc_bom_line(spec: str, cfg: CleanConfig) -> Optional[str]:
    t = try_parse_mlcc_bom_line_slots(spec, cfg)
    return t[1] if t else None


def parse_capacitor_token_fields(
    spec: str,
    config: Optional[CleanConfig] = None,
) -> Tuple[Dict[str, str], str]:
    """Token + MLCC prose path only (no INFERIT). Raw non-empty slots and formatted string."""
    cfg = default_clean_config(config)
    raw_in = str(spec).strip()
    if not cfg.parse_capacitors:
        return {}, raw_in
    spec2 = normalize_for_regex_parsing(raw_in)
    spec2 = spec2.replace("\\", "/").replace("CHIP MLCC CAP.", "").strip()
    under = try_parse_mlcc_underscore_cap_fields(spec2, cfg)
    if under is not None:
        return under
    # Slash ``UF/V`` line (incl. «MLCC …») must run before preprocess, which turns it into
    # ``UF+V`` and would break ``try_parse_mlcc_bom_line_slots``.
    slash_line = try_parse_mlcc_bom_line_slots(spec2, cfg)
    if slash_line is not None:
        return slash_line
    spec2 = preprocess_cap_tokens_for_slash_voltage(spec2)
    parts = tokenize_bom_spec(spec2)

    package = ""
    value = ""
    voltage = ""
    dielectric = ""
    tolerance = ""

    for part in parts:
        if not part:
            continue
        pack_tok = match_package_token(part)
        if pack_tok:
            package = pack_tok
            continue
        if match(r"^[\d\.]+V$", part, I):
            voltage = part.upper()
            continue
        if part.upper() in [
            "X5R",
            "X7R",
            "X6S",
            "X8R",
            "C0G",
            "NP0",
            "COG",
            "Y5V",
            "Z5U",
        ]:
            dielectric = part.upper()
            continue
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
        if match(r"^[\d\.]+(UF|NF|PF|F)$", part, I):
            value = part.upper()
            continue

    if not value:
        for part in parts:
            m_val = match(r"^([\d\.]+)(UF|NF|PF|F)$", part, I)
            if m_val:
                num, unit = m_val.groups()
                value = f"{num}{unit.upper()}"
                break

    if not package:
        for part in parts:
            pack_tok = match_package_token(part)
            if pack_tok:
                package = pack_tok
                break
        if not package:
            pm = search(r"\((\d{4}(?:/[A-Z])?)\)", spec2)
            if pm:
                package = pm.group(1)
            else:
                pm2 = search(r"\b(\d{4}/[A-Z])\b", spec2, I)
                if pm2:
                    package = pm2.group(1)

    if (
        cfg.cap_convert_nf_to_uf
        and value
        and value.upper().endswith("NF")
        and "UF" not in value.upper()
    ):
        try:
            from parsers.si_units import convert_nf_token_to_uf

            value = convert_nf_token_to_uf(value)
        except Exception:
            m = match(r"^([\d.]+)NF$", value, I)
            if m:
                n = float(m.group(1))
                if n >= 1000 and n % 1000 == 0:
                    value = f"{int(n // 1000)}UF"
                elif n >= 1:
                    value = f"{n / 1000.0}UF".replace(".0UF", "UF")

    if value:
        for part in parts:
            tm = match(r"^(?:±|\+/-)\s*([\d.]+)\s*(?:PF|pF)$", part, I)
            if not tm:
                continue
            tol_pf = float(tm.group(1))
            nom_pf = capacitor_nominal_pf(value)
            sp = snap_cap_tolerance_pf_to_std_pct(tol_pf, nom_pf)
            if sp:
                tolerance = sp

    fields = {
        "pack": package,
        "nom": value,
        "V": voltage,
        "film": dielectric,
        "%": tolerance,
    }
    result = format_cap_fields(fields, cfg)
    raw = {k: v for k, v in fields.items() if str(v).strip()}
    out = result if result else spec2
    return raw, out


def parse_capacitor(
    spec: str,
    config: Optional[CleanConfig] = None,
    *,
    skip_inferit_presets: bool = False,
) -> str:
    """Parse capacitor specifications like '22PF+50V+±5%(J)+0402' or MLCC prose lines."""
    cfg = default_clean_config(config)
    if not cfg.parse_capacitors:
        return str(spec).strip()
    spec_ns = normalize_for_regex_parsing(str(spec).strip())
    if not skip_inferit_presets:
        inferit = parse_inferit_capacitor(spec_ns, cfg)
        if inferit:
            return inferit
    _, out = parse_capacitor_token_fields(spec_ns, cfg)
    return out


register_parser_module(
    ParserModuleInfo(
        module_stem="cap_pars",
        role="regex_cap",
        gui_name=PARSER_GUI_NAME,
        cli_name=PARSER_CLI_NAME,
        summary="Token-based chip cap parsing + UF/V slash one-liner (MLCC-style BOM rows).",
    )
)
