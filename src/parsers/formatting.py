"""Format parsed resistor/capacitor/inductor fields using CleanConfig templates."""

from __future__ import annotations

from clean_types import CleanConfig

from parsers.constants import PACKAGE_PATTERN
from parsers.regex_api import I, compile, match, search

_CAP_ASCII_U_BEFORE_F = compile(r"(?<=[0-9.])([uU])(?=F\b)")

_RES_TEMPLATE_FIELDS = {"nom", "pack", "watt", "%"}
_CAP_TEMPLATE_FIELDS = {"nom", "pack", "film", "%", "V"}
_IND_TEMPLATE_FIELDS = {"pack", "nom", "%", "Imax", "DCR"}


def template_fields(
    template: tuple[str, ...] | list[str] | None,
    allowed: set[str],
    default: tuple[str, ...],
) -> tuple[str, ...]:
    if not template:
        return default
    out: list[str] = []
    seen: set[str] = set()
    for raw in template:
        key = str(raw).strip()
        if not key or key.lower() == "none":
            continue
        if key == "W" and "V" in allowed:
            key = "V"
        if key not in allowed or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return tuple(out) if out else default


def format_component_fields(
    fields: dict[str, str],
    template: tuple[str, ...] | list[str] | None,
    allowed: set[str],
    default: tuple[str, ...],
    sep: str,
) -> str:
    parts: list[str] = []
    for key in template_fields(template, allowed, default):
        val = fields.get(key, "")
        if val:
            parts.append(val)
    return sep.join(parts)


def polish_cap_ascii_uf_to_micro(text: str, cfg: CleanConfig) -> str:
    """Replace ASCII ``u`` in ``uF`` / ``UF`` with Unicode micro sign (µ)."""
    if not cfg.cap_uf_micro_sign:
        return text
    return _CAP_ASCII_U_BEFORE_F.sub("\u00b5", str(text))


def apply_prefix(text: str, prefix: str, cfg: CleanConfig) -> str:
    body = str(text).strip()
    pre = str(prefix or "").strip()
    if not body or not pre:
        return body
    joined = (
        f"{pre}{cfg.output_separator}{body}"
        if cfg.prefix_use_separator
        else f"{pre}{body}"
    )
    if body == pre or (
        cfg.prefix_use_separator
        and cfg.output_separator
        and body.startswith(f"{pre}{cfg.output_separator}")
    ):
        return body
    return joined


def format_resistor_fields(fields: dict[str, str], cfg: CleanConfig) -> str:
    from parsers.bom_text_utils import normalize_res_ohm_value

    f = dict(fields)
    if f.get("nom"):
        f["nom"] = normalize_res_ohm_value(
            f["nom"],
            include_ohm_r_suffix=cfg.resistor_include_ohm_r_suffix,
        )
    if not cfg.resistor_include_package:
        f.pop("pack", None)
    if not cfg.resistor_include_tolerance:
        f.pop("%", None)
    out = format_component_fields(
        f,
        cfg.resistor_template,
        _RES_TEMPLATE_FIELDS,
        ("pack", "nom", "%"),
        cfg.output_separator,
    )
    out = apply_prefix(out, cfg.resistor_prefix, cfg)
    return out


def format_cap_fields(fields: dict[str, str], cfg: CleanConfig) -> str:
    from parsers.bom_text_utils import cap_value_token_pf, normalize_value_unit

    f = dict(fields)
    if f.get("nom"):
        f["nom"] = normalize_value_unit(
            f["nom"], cap_uf_micro_sign=cfg.cap_uf_micro_sign
        )
    tol_s = str(f.get("%", "")).strip()
    if tol_s and cap_value_token_pf(tol_s) is not None and "%" not in tol_s:
        f["%"] = normalize_value_unit(tol_s, cap_uf_micro_sign=cfg.cap_uf_micro_sign)
    film_up = str(f.get("film", "")).strip().upper()
    if (
        film_up in ("NPO", "NP0", "COG", "C0G")
        and tol_s
        and cap_value_token_pf(tol_s) is not None
        and "%" not in tol_s
    ):
        f["film"] = "C0G"
    if not cfg.cap_include_package:
        f.pop("pack", None)
    if not cfg.cap_include_voltage:
        f.pop("V", None)
    if not cfg.cap_include_dielectric:
        f.pop("film", None)
    if not cfg.cap_include_tolerance:
        f.pop("%", None)
    out = format_component_fields(
        f,
        cfg.cap_template,
        _CAP_TEMPLATE_FIELDS,
        ("pack", "nom", "V", "film", "%"),
        cfg.output_separator,
    )
    out = apply_prefix(out, cfg.cap_prefix, cfg)
    return polish_cap_ascii_uf_to_micro(out, cfg)


def inductor_pack_guess(s: str) -> str:
    """Infer SMD size code from MPN in parentheses or explicit package token."""
    m = search(r"\(([A-Z0-9][A-Z0-9+\-]{3,})\)", s, I)
    if m:
        tok = m.group(1)
        em = search(r"(?<=[A-Za-z])(\d{4})(?=[A-Za-z\-]|$)", tok)
        if em:
            return em.group(1)
    mpn_m = search(r"(?<![A-Za-z0-9])(?:SCCT|SCCB|STPI|SWAI|MCW|CCCA)(\d{4})[-\w]*", s, I)
    if mpn_m:
        return mpn_m.group(1)
    mm = search(rf"(?<![A-Za-z0-9])({PACKAGE_PATTERN})(?![A-Za-z0-9])", s, I)
    return mm.group(1) if mm else ""


def format_inductor_fields(fields: dict[str, str], cfg: CleanConfig) -> str:
    f = {k: v for k, v in fields.items() if v}
    out = format_component_fields(
        f,
        cfg.inductor_template,
        _IND_TEMPLATE_FIELDS,
        ("pack", "nom", "%", "Imax", "DCR"),
        cfg.output_separator,
    )
    return apply_prefix(out, cfg.inductor_prefix, cfg)


def resistor_fields_from_cleaned_segments(segs: list[str]) -> dict[str, str]:
    """Map underscore / separator segments from a cleaned resistor string to slots."""
    fields = {"nom": "", "pack": "", "watt": "", "%": ""}
    for seg in segs:
        up = seg.upper()
        if match(rf"^({PACKAGE_PATTERN})$", seg, I):
            fields["pack"] = seg
        elif match(r"^\d+/\d+W$|^\d+(?:\.\d+)?W$", up):
            fields["watt"] = up
        elif "%" in seg:
            fields["%"] = seg
        elif match(r"^[0-9.]+(?:R[0-9.]*)?[KM]?$|^[0-9.]+[KM]$", up):
            fields["nom"] = seg
    return fields


def capacitor_fields_from_cleaned_segments(segs: list[str]) -> dict[str, str]:
    """Map underscore / separator segments from a cleaned capacitor string to slots."""
    from parsers.bom_text_utils import (
        cap_value_token_pf,
        is_cap_abs_pf_tolerance_token,
    )
    from parsers.constants import MLCC_DIELECTRIC

    fields = {"nom": "", "pack": "", "film": "", "%": "", "V": ""}
    cap_tokens: list[str] = []
    for seg in segs:
        up = seg.upper()
        if match(rf"^({PACKAGE_PATTERN})$", seg, I):
            fields["pack"] = seg
        elif match(r"^[0-9.]+V$", up):
            fields["V"] = up
        elif up in MLCC_DIELECTRIC or up in ("NP0", "C0G", "COG", "NPO"):
            fields["film"] = "C0G" if up == "COG" else seg
        elif "%" in seg:
            fields["%"] = seg
        elif match(r"^[0-9.]+(?:UF|NF|PF|pF|nF|uF|F)$", seg, I):
            cap_tokens.append(seg)

    if cap_tokens:
        if len(cap_tokens) == 1:
            tok = cap_tokens[0]
            if is_cap_abs_pf_tolerance_token(tok) and not fields["nom"]:
                fields["%"] = tok
            else:
                fields["nom"] = tok
        else:
            ranked = sorted(
                cap_tokens,
                key=lambda t: cap_value_token_pf(t) or 0.0,
                reverse=True,
            )
            fields["nom"] = ranked[0]
            for extra in ranked[1:]:
                if is_cap_abs_pf_tolerance_token(extra) or (
                    (cap_value_token_pf(extra) or 0.0)
                    < (cap_value_token_pf(ranked[0]) or 0.0) * 0.5
                ):
                    fields["%"] = extra
                elif not fields["nom"]:
                    fields["nom"] = extra
    return fields


def split_cleaned_segments(cleaned: str, cfg: CleanConfig) -> list[str]:
    text = str(cleaned).strip()
    if not text:
        return []
    if "_" in text:
        return [x for x in text.split("_") if x]
    sep = cfg.output_separator
    if sep and sep != "_" and sep in text:
        return [x for x in text.split(sep) if x]
    return [text]


def reformat_cleaned_pn(cleaned: str, classify_type: str, cfg: CleanConfig) -> str:
    """
    Vendor parsers return normalized strings; re-map segments to user template.
    """
    segs = split_cleaned_segments(cleaned, cfg)
    if not segs:
        return cleaned
    if classify_type == "RESISTOR":
        fields = resistor_fields_from_cleaned_segments(segs)
        out = format_resistor_fields(fields, cfg)
        return out or cleaned
    if classify_type == "CAP":
        fields = capacitor_fields_from_cleaned_segments(segs)
        out = format_cap_fields(fields, cfg)
        return out or cleaned
    return cleaned
