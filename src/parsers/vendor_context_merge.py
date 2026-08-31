"""
Fill gaps in vendor PN normalized strings using the same BOM prose as token-regex.

Vendor ``pn_original`` decoders return MPN-centric tokens (often no watt / no dielectric).
Regex parsers see the full comment and can fill missing slots.

For capacitors, ``V`` / ``film`` / ``%`` from the full BOM line are merged conservatively:
gap-fill when the vendor field is empty; when vendor and regex disagree, prefer regex
only if the BOM line looks like a **structured cap spec** (value/voltage slash like
``1UF/16V``, mirroring :func:`parsers.bom_text_utils.normalize_for_regex_parsing`) or
the regex parse already extracted a **nominal** from ``orig`` (token stream / MLCC line).
That avoids overwriting MPN-derived fields from stray ``…25V…`` text unrelated to the part.
"""

from __future__ import annotations

from clean_types import CleanConfig, default_clean_config
from parsers.bom_text_utils import (
    canonicalize_cap_dielectric,
    cap_value_token_pf,
    normalize_value_unit,
)
from parsers.cap_pars import parse_capacitor_token_fields
from parsers.formatting import (
    capacitor_fields_from_cleaned_segments,
    format_cap_fields,
    format_resistor_fields,
    resistor_fields_from_cleaned_segments,
    split_cleaned_segments,
)
from parsers.regex_api import I, match, search
from parsers.res_pars import parse_resistor_token_fields


def _orig_has_explicit_cap_value_voltage_slash(orig: str) -> bool:
    """Same idea as ``normalize_for_regex_parsing`` keeping full string for ``UF/V``."""
    return bool(
        search(
            r"[\d.]+\s*(?:PF|NF|UF|F)\s*/\s*[\d.]+\s*V",
            str(orig),
            I,
        )
    )


def _bom_cap_regex_anchors_cap_spec(orig: str, cx: dict[str, str]) -> bool:
    if _orig_has_explicit_cap_value_voltage_slash(orig):
        return True
    if search(r"^MLCC_[^_]+_[^_]+_\d", str(orig).strip(), I):
        return True
    return bool(str(cx.get("nom", "")).strip())


def _cap_v_equiv(a: str, b: str) -> bool:
    ma = match(r"^([\d.]+)\s*V$", a.strip(), I)
    mb = match(r"^([\d.]+)\s*V$", b.strip(), I)
    if ma and mb:
        return abs(float(ma.group(1)) - float(mb.group(1))) < 1e-9
    return a.strip().upper() == b.strip().upper()


def _cap_film_equiv(a: str, b: str) -> bool:
    return canonicalize_cap_dielectric(a) == canonicalize_cap_dielectric(b)


def _cap_pct_equiv(a: str, b: str) -> bool:
    sa = a.replace("±", "").strip().upper()
    sb = b.replace("±", "").strip().upper()
    ma = match(r"^([\d.]+)\s*%$", sa, I)
    mb = match(r"^([\d.]+)\s*%$", sb, I)
    if ma and mb:
        return abs(float(ma.group(1)) - float(mb.group(1))) < 1e-9
    pa = cap_value_token_pf(sa)
    pb = cap_value_token_pf(sb)
    if pa is not None and pb is not None:
        return abs(pa - pb) < 1e-9
    return sa == sb


def _cap_nom_equiv(a: str, b: str) -> bool:
    pa = cap_value_token_pf(a)
    pb = cap_value_token_pf(b)
    if pa is not None and pb is not None:
        return abs(pa - pb) < 1e-9
    return normalize_value_unit(a) == normalize_value_unit(b)


def _cap_slot_equiv(key: str, vendor_val: str, rx_val: str) -> bool:
    if key == "V":
        return _cap_v_equiv(vendor_val, rx_val)
    if key == "film":
        return _cap_film_equiv(vendor_val, rx_val)
    if key == "%":
        return _cap_pct_equiv(vendor_val, rx_val)
    return vendor_val.strip() == rx_val.strip()


def _normalize_cap_regex_slots(slots: dict[str, str]) -> dict[str, str]:
    """Legacy regex dicts may still use ``W`` for voltage; prefer ``V``."""
    d = dict(slots)
    wv = str(d.get("W", "")).strip()
    vv = str(d.get("V", "")).strip()
    if wv and not vv:
        d["V"] = d.pop("W", "")
    else:
        d.pop("W", None)
    return d


def enrich_vendor_cleaned_from_bom(
    orig: str,
    vendor_cleaned: str,
    classify_eff: str,
    config: CleanConfig,
) -> str:
    cfg = default_clean_config(config)
    if classify_eff == "RESISTOR" and cfg.parse_resistors:
        rx, _ = parse_resistor_token_fields(orig, cfg)
        segs = split_cleaned_segments(str(vendor_cleaned).strip(), cfg)
        fields = resistor_fields_from_cleaned_segments(segs)
        for k in ("watt", "%"):
            if not str(fields.get(k, "")).strip() and str(rx.get(k, "")).strip():
                fields[k] = rx[k]
        if not str(fields.get("watt", "")).strip():
            wm = search(
                r"(?<![0-9.])(\d+/\d+W|\d+(?:\.\d+)?W)(?![0-9A-Z])",
                str(orig),
                I,
            )
            if wm:
                fields["watt"] = wm.group(1).upper()
        return format_resistor_fields(fields, cfg) or vendor_cleaned
    if classify_eff == "CAP" and cfg.parse_capacitors:
        cx_raw, _ = parse_capacitor_token_fields(orig, cfg)
        cx = _normalize_cap_regex_slots(cx_raw)
        segs = split_cleaned_segments(str(vendor_cleaned).strip(), cfg)
        fields = capacitor_fields_from_cleaned_segments(segs)
        anchored = _bom_cap_regex_anchors_cap_spec(orig, cx)
        for k in ("nom", "V", "film", "%"):
            cv_rx = str(cx.get(k, "")).strip()
            if not cv_rx:
                continue
            cv_vend = str(fields.get(k, "")).strip()
            if not cv_vend:
                fields[k] = cx[k]
            elif anchored and k == "nom" and not _cap_nom_equiv(cv_vend, cv_rx):
                fields[k] = cx[k]
            elif (
                anchored
                and k == "%"
                and cv_rx
                and cap_value_token_pf(cv_rx) is not None
                and not str(cv_vend).strip()
            ):
                fields[k] = cx[k]
            elif (
                anchored
                and k == "%"
                and cv_rx
                and cap_value_token_pf(cv_rx) is not None
                and match(r"^[\d.]+\s*%$", cv_vend.replace("±", "").strip(), I)
            ):
                fields[k] = cx[k]
            elif anchored and k != "nom" and not _cap_slot_equiv(k, cv_vend, cv_rx):
                fields[k] = cx[k]
        return format_cap_fields(fields, cfg) or vendor_cleaned
    return vendor_cleaned
