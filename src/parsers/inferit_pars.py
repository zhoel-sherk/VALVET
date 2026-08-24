"""
INFERIT-style BOM text presets (free-form English/Chinese BOM lines → normalized tokens).

These run in the `inferit` pipeline step before vendor MPN decoders and regex.

Adding a preset:
  1. Add a function `try_inferit_<family>(spec: str, cfg: CleanConfig) -> str | None`.
  2. Call it from `parse_inferit_*` below if it applies.
  3. Extend this module's docstring / summary for operators.

GUI / CLI labels below appear in Clean BOM → Debug settings (loaded modules list).
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from clean_types import CleanConfig, default_clean_config

from parsers.bom_text_utils import (
    capacitor_nominal_pf,
    normalize_res_ohm_value,
    normalize_value_unit,
    snap_cap_tolerance_pf_to_std_pct,
)
from parsers.chip_tokens import canonical_voltage_token, match_package_token, watt_for_package
from parsers.constants import PACKAGE_PATTERN
from parsers.formatting import (
    format_cap_fields,
    format_inductor_fields,
    format_resistor_fields,
    inductor_pack_guess,
)
from parsers.regex_api import I, S, match, search, sub
from parsers.registry import ParserModuleInfo, register_parser_module

# Catalog labels (shown in Debug settings dialog)
INFERIT_RESISTOR_GUI_NAME = "INFERIT — resistor line (RES … Ω ±%)"
INFERIT_RESISTOR_CLI_NAME = "inferit.resistor"

INFERIT_CAPACITOR_GUI_NAME = "INFERIT — capacitor line (CAP … / V ±%)"
INFERIT_CAPACITOR_CLI_NAME = "inferit.capacitor"

INFERIT_INDUCTOR_GUI_NAME = "INFERIT — inductor / ferrite bead lines"
INFERIT_INDUCTOR_CLI_NAME = "inferit.inductor"


def parse_inferit_resistor_fields(
    spec: str, cfg: Optional[CleanConfig] = None
) -> Optional[Tuple[Dict[str, str], str]]:
    """Return raw resistor slot dict and formatted string, or None if no INFERIT match."""
    c = default_clean_config(cfg)
    s = str(spec)
    if "FERRITE-BEAD" in s.upper() or "FERRITE BEAD" in s.upper():
        return None
    # NETRES-SMD 0402-8P4R 33 OHM +/-5% LEAD-FREE
    m = search(
        rf"^NETRES[-\s]+SMD\s+(?P<pack>[RC]?({PACKAGE_PATTERN}))-8P4R\s+"
        r"(?P<value>[0-9]+(?:\.[0-9]+)?(?:[KMR]\b|\s*(?:OHM|Ω)\b))"
        r".*?(?:\+/-|±)\s*(?P<tol>[0-9]+(?:\.[0-9]+)?)\s*%",
        s,
        I,
    )
    if not m:
        # Prefer pack-first form; also accept value-first «RES 1m OHM 2W (2512) 1%».
        m = search(
            rf"\bRES(?:ISTOR)?\s+(?P<pack>[RC]?({PACKAGE_PATTERN}))\s+"
            r"(?P<value>[0-9]+(?:\.[0-9]+)?(?:[KMR]\b|\s*(?:OHM|Ω)\b))"
            r".*?(?:\+/-|±)\s*(?P<tol>[0-9]+(?:\.[0-9]+)?)\s*%",
            s,
            I,
        )
    if not m:
        m = search(
            rf"\bRES(?:ISTOR)?\s+"
            rf"(?P<value>[0-9]+(?:\.[0-9]+)?(?:[KMR]\b|\s*(?:OHM|Ω)\b))"
            rf".*?(?:\(|\b)(?P<pack>[RC]?({PACKAGE_PATTERN}))(?:\)|\b)"
            rf".*?(?:\+/-|±)?\s*(?P<tol>[0-9]+(?:\.[0-9]+)?)\s*%",
            s,
            I,
        )
    if not m:
        return None
    pack = match_package_token(m.group("pack")) or m.group("pack")
    watt = ""
    wm = search(r"\b(\d+/\d+W|\d+(?:\.\d+)?W)\b", s, I)
    if wm:
        watt = wm.group(1).upper()
    if not watt and c.infer_resistor_watt_from_package:
        watt = watt_for_package(pack)
    # Preserve original case of value token for milli vs mega (1m vs 1M).
    val_span = m.span("value")
    val_raw = s[val_span[0] : val_span[1]]
    val_raw = sub(
        r"\s*(?:OHM|Ω)\s*$",
        "",
        val_raw.strip(),
        flags=I,
    ).strip()
    val_raw = sub(r"\s+", "", val_raw)
    raw: Dict[str, str] = {
        "pack": pack,
        "nom": normalize_res_ohm_value(
            val_raw,
            include_ohm_r_suffix=c.resistor_include_ohm_r_suffix,
        ),
        "watt": watt,
        "%": f"{m.group('tol')}%",
    }
    out = format_resistor_fields(raw, c)
    return (raw, out) if out else None


def parse_inferit_resistor(
    spec: str, cfg: Optional[CleanConfig] = None
) -> Optional[str]:
    d = parse_inferit_resistor_fields(spec, cfg)
    return d[1] if d else None


def try_parse_mlcc_underscore_cap_fields(
    spec: str, cfg: CleanConfig
) -> Optional[Tuple[Dict[str, str], str]]:
    """
    Curated BOM rows: ``MLCC_18pF_C0G_50V_±5%_C0402_0.5MM+-0.05MM_SMD``.
    """
    s = str(spec).strip()
    m = search(
        r"^MLCC_(?P<nom>[^_]+)_(?P<film>[^_]+)_(?P<voltage>\d+(?:\.\d+)?V)_"
        r"(?:±|\+/-)?(?P<tol>[^_]+)"
        r"(?:_(?:C)?(?P<pack>\d{4}))?",
        s,
        I,
    )
    if not m:
        return None
    pack_raw = str(m.group("pack") or "").strip()
    pack = pack_raw
    if not pack:
        pm = search(r"\bC?(\d{4})\b", s, I)
        pack = pm.group(1) if pm else ""
    film = (m.group("film") or "").upper()
    if film == "COG":
        film = "C0G"
    tol_s = str(m.group("tol") or "").strip()
    if tol_s and not tol_s.endswith("%") and "PF" in tol_s.upper():
        tol_s = normalize_value_unit(tol_s, cap_uf_micro_sign=cfg.cap_uf_micro_sign)
    raw = {
        "pack": pack,
        "nom": normalize_value_unit(
            m.group("nom"), cap_uf_micro_sign=cfg.cap_uf_micro_sign
        ),
        "V": str(m.group("voltage")).upper(),
        "film": film,
        "%": tol_s,
    }
    out = format_cap_fields(raw, cfg)
    return (raw, out) if out else None


def parse_inferit_capacitor_fields(
    spec: str, cfg: Optional[CleanConfig] = None
) -> Optional[Tuple[Dict[str, str], str]]:
    c = default_clean_config(cfg)
    s = str(spec)
    under = try_parse_mlcc_underscore_cap_fields(s, c)
    if under is not None:
        return under
    m = search(
        rf"\bCAP(?:[\s_-]*SMD)?\s+(?P<pack>[RC]?({PACKAGE_PATTERN}))\s+"
        r"(?P<value>[0-9]+(?:\.[0-9]+)?\s*(?:PF|NF|UF|F))\s*/\s*"
        r"(?P<voltage>[0-9]+(?:\.[0-9]+)?(?:kV|KV|V))"
        r".*?(?:\+/-|±)\s*(?P<tol>[0-9]+(?:\.[0-9]+)?)\s*(?P<tol_unit>%|PF|pF)"
        r"(?:\s+(?P<film>NPO|NP0|C0G|COG|X7R|X5R|X6S|X8R|Y5V|Z5U))?",
        s,
        I,
    )
    if not m:
        return None
    film = (m.group("film") or "").upper()
    if film == "COG":
        film = "C0G"
    tol_unit = (m.group("tol_unit") or "%").upper()
    tol_val = float(m.group("tol"))
    if tol_unit == "%":
        pct_s = f"{m.group('tol')}%"
    else:
        nom_pf = capacitor_nominal_pf(m.group("value"))
        pct_s = snap_cap_tolerance_pf_to_std_pct(tol_val, nom_pf)
        if not pct_s:
            pct_s = f"{m.group('tol')}PF"
    vol_m = match(r"^([\d.]+)(kV|KV|V)$", m.group("voltage"), I)
    volt = (
        canonical_voltage_token(vol_m.group(1), vol_m.group(2))
        if vol_m
        else m.group("voltage").upper()
    )
    raw = {
        "pack": match_package_token(m.group("pack")) or m.group("pack"),
        "nom": normalize_value_unit(
            m.group("value"),
            cap_uf_micro_sign=c.cap_uf_micro_sign,
        ),
        "V": volt,
        "film": film,
        "%": pct_s,
    }
    out = format_cap_fields(raw, c)
    return (raw, out) if out else None


def parse_inferit_capacitor(
    spec: str, cfg: Optional[CleanConfig] = None
) -> Optional[str]:
    d = parse_inferit_capacitor_fields(spec, cfg)
    return d[1] if d else None


def parse_inferit_inductor_fields(
    spec: str, cfg: Optional[CleanConfig] = None
) -> Optional[Tuple[Dict[str, str], str]]:
    c = default_clean_config(cfg)
    s = str(spec)
    up = s.upper()
    if "FERRITE" in up or "BEAD" in up:
        # Ferrite beads are cleaned via ferrite_beads MPN pass-through, not IND slots.
        return None
    smd = search(
        r"SMD-INDUCTOR\s+"
        r"[\d.]+\*[\d.]+\*[\d.]+\s*mm\s+"
        r"(?P<nomv>[0-9.]+\s*[uµ]?H)\b"
        r".*?(?P<tol>(?:±|\+/-)\s*[0-9.]+\s*%)"
        r".*?(?P<dcr>[0-9.]+\s*mΩ(?:Max)?)"
        r".*?(?P<imax>[0-9.]+\s*A)\b",
        s,
        I | S,
    )
    if smd:
        tol_raw = sub(r"\s+", "", smd.group("tol"))
        tol_pct = tol_raw.replace("±", "").replace("+/-", "") if tol_raw else ""
        dcr_raw = smd.group("dcr")
        dcr = sub(r"\s+", "", dcr_raw).replace("Max", "") if dcr_raw else ""
        pack = inductor_pack_guess(s)
        raw = {
            "pack": pack,
            "nom": normalize_value_unit(
                smd.group("nomv"),
                cap_uf_micro_sign=c.cap_uf_micro_sign,
            ),
            "%": tol_pct if tol_pct.endswith("%") else f"{tol_pct}%",
            "Imax": sub(r"\s+", "", smd.group("imax")).upper(),
            "DCR": dcr,
        }
        out = format_inductor_fields(raw, c)
        return (raw, out) if out else None
    if "INDUCT" not in up:
        return None
    vm = search(r"(?P<value>[0-9]+(?:\.[0-9]+)?\s*(?:UH|NH|MH|H))", s, I)
    if not vm:
        return None
    tm = search(r"(?:±|\+/-)\s*(?P<tol>[0-9]+(?:\.[0-9]+)?)\s*%", s, I)
    cm = search(r"(?P<cur>[0-9]+(?:\.[0-9]+)?\s*A)\b", s, I)
    dm = search(r"(?P<dcr>[0-9.]+\s*mΩ(?:Max)?)", s, I)

    dcr_s = ""
    if dm:
        dcr_s = sub(r"\s+", "", dm.group("dcr")).replace("Max", "")
    raw = {
        "pack": inductor_pack_guess(s),
        "nom": normalize_value_unit(
            vm.group("value"),
            cap_uf_micro_sign=c.cap_uf_micro_sign,
        ),
        "Imax": sub(r"\s+", "", cm.group("cur")).upper() if cm else "",
        "%": f"{tm.group('tol')}%" if tm else "",
        "DCR": dcr_s,
    }
    out = format_inductor_fields(raw, c)
    return (raw, out) if out else None


def parse_inferit_inductor(
    spec: str, cfg: Optional[CleanConfig] = None
) -> Optional[str]:
    d = parse_inferit_inductor_fields(spec, cfg)
    return d[1] if d else None


register_parser_module(
    ParserModuleInfo(
        module_stem="inferit_pars",
        role="inferit",
        gui_name=INFERIT_RESISTOR_GUI_NAME,
        cli_name=INFERIT_RESISTOR_CLI_NAME,
        summary="CHIP BOM lines: RES/RESISTOR + package + value Ω + tolerance.",
    )
)
register_parser_module(
    ParserModuleInfo(
        module_stem="inferit_pars",
        role="inferit",
        gui_name=INFERIT_CAPACITOR_GUI_NAME,
        cli_name=INFERIT_CAPACITOR_CLI_NAME,
        summary="CHIP BOM lines: CAP + package + value / voltage + tolerance + optional film.",
    )
)
register_parser_module(
    ParserModuleInfo(
        module_stem="inferit_pars",
        role="inferit",
        gui_name=INFERIT_INDUCTOR_GUI_NAME,
        cli_name=INFERIT_INDUCTOR_CLI_NAME,
        summary="Ferrite bead, SMD inductor prose, generic INDUCT… µH/nH lines.",
    )
)
