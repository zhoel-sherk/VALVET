"""Normalize and tokenize BOM comment strings before regex parsers."""

from __future__ import annotations

import math

from parsers.regex_api import I, fullmatch, match, search, split, sub

# Separator when the UI field is left empty (legacy default).
DEFAULT_DOUBLE_COMMENT_JOIN = " | "

# Thickness / height stack before tokenize splits on «+» (e.g. 0.8+0.15/-0.10mm).
_STACK_PLACEHOLDER = "__BOOMER_STACK_{}__"


def merge_clean_comment_cell_parts(parts: list[object], sep_raw: str) -> str:
    """
    Join non-empty BOM cells for Clean BOM «Double Comment import».

    ``sep_raw`` is taken as-is (so a single space is preserved). Only a completely
    empty string falls back to ``DEFAULT_DOUBLE_COMMENT_JOIN`` — unlike
    ``str.strip()`` on the separator, which used to erase intentional spaces.
    """
    sep = DEFAULT_DOUBLE_COMMENT_JOIN if sep_raw == "" else sep_raw
    bits: list[str] = []
    for p in parts:
        if p is None:
            continue
        if isinstance(p, float) and (math.isnan(p) or math.isinf(p)):
            continue
        t = str(p).strip()
        if t and t.lower() != "nan":
            bits.append(t)
    return sep.join(bits)


def normalize_value_unit(
    text: str,
    *,
    cap_uf_micro_sign: bool = False,
) -> str:
    s = sub(r"\s+", "", str(text)).strip()
    m = match(r"^([0-9.]+)(PF|NF|UF|F|UH|NH|MH|H)$", s, I)
    if not m:
        return s.upper()
    num, unit = m.groups()
    uf_display = "\u00b5F" if cap_uf_micro_sign else "uF"
    unit_map = {
        "PF": "pF",
        "NF": "nF",
        "UF": uf_display,
        "F": "F",
        "UH": "uH",
        "NH": "nH",
        "MH": "mH",
        "H": "H",
    }
    out_unit = unit_map[unit.upper()]
    try:
        n = float(num)
    except ValueError:
        return f"{num}{out_unit}"
    if out_unit == "pF" and n == int(n):
        return f"{int(n)}pF"
    if out_unit == "pF":
        t = f"{n:.3f}".rstrip("0").rstrip(".")
        return f"{t}pF"
    return f"{num}{out_unit}"


_C0G_DIELECTRIC_ALIASES = frozenset({"NPO", "NP0", "COG", "C0G"})


def canonicalize_cap_dielectric(diel: str) -> str:
    """Map NP0-class MLCC labels to ``C0G`` for cleaned output."""
    up = str(diel or "").strip().upper()
    if up in _C0G_DIELECTRIC_ALIASES:
        return "C0G"
    return str(diel or "").strip()


def cap_value_token_pf(seg: str) -> float | None:
    """Picofarads for a capacitance token, or ``None`` if not a value token."""
    s = sub(r"\s+", "", str(seg)).strip()
    if not s:
        return None
    if not fullmatch(r"^[0-9]+(?:\.[0-9]+)?(?:PF|NF|UF|F|pF|nF|uF)$", s, I):
        return None
    return capacitor_nominal_pf(s)


def is_cap_abs_pf_tolerance_token(seg: str) -> bool:
    """Bare ``0.25pF`` / ``0.25PF`` style absolute tolerance (not nominal)."""
    s = sub(r"\s+", "", str(seg)).strip()
    m = fullmatch(r"^0\.[0-9]+(?:PF|pF)$", s, I)
    return bool(m)


def capacitor_nominal_pf(value_token: str) -> float:
    """Convert a capacitor value token (e.g. ``22PF``, ``1NF``, ``0.1UF``) to picofarads."""
    s = sub(r"\s+", "", str(value_token)).strip().upper()
    m = fullmatch(r"^([0-9]+(?:\.[0-9]+)?)(PF|NF|UF|F)$", s)
    if not m:
        return 0.0
    num_s, unit = m.groups()
    n = float(num_s)
    u = unit.upper()
    if u == "PF":
        return n
    if u == "NF":
        return n * 1000.0
    if u == "UF":
        return n * 1_000_000.0
    if u == "F":
        return n * 1e12
    return 0.0


def snap_cap_tolerance_pf_to_std_pct(tol_pf: float, nom_pf: float) -> str:
    """
    Map absolute pF tolerance vs nominal to the nearest standard MLCC % bucket (5 / 10 / 20).

    Thresholds on ``tol_pf / nom_pf * 100``: ≤ 7.5 → 5%, ≤ 15 → 10%, else 20%.
    """
    if nom_pf <= 0 or tol_pf < 0:
        return ""
    ratio_pct = tol_pf / nom_pf * 100.0
    if ratio_pct <= 7.5:
        return "5%"
    if ratio_pct <= 15.0:
        return "10%"
    return "20%"


def normalize_res_ohm_value(
    text: str,
    *,
    include_ohm_r_suffix: bool = True,
) -> str:
    """
    Normalize resistor magnitude token. When ``include_ohm_r_suffix`` is True (default),
    append «R» for plain ohm values. When False, plain numeric+R becomes numeric only
    (100R→100); K/M and fractional «4R7»-style tokens are left unchanged.

    Lowercase ``m`` (before uppercasing) means milliohm: ``1m`` / ``1mOHM`` → ``0.001R``.
    Uppercase ``M`` remains megaohm.
    """
    compact = sub(r"\s+", "", str(text)).strip()
    if not compact:
        return ""
    # Case-sensitive milli before .upper() (1m OHM ≠ 1M OHM).
    m_milli = match(r"^([0-9]+(?:\.[0-9]+)?)m(?:[Rr]|[Oo][Hh][Mm])?$", compact)
    if m_milli:
        try:
            ohms = float(m_milli.group(1)) / 1000.0
        except ValueError:
            ohms = 0.0
        body = f"{ohms:.6f}".rstrip("0").rstrip(".")
        if not body or body == ".":
            body = "0"
        return f"{body}R" if include_ohm_r_suffix else body
    s = compact.upper()
    if s.endswith(("K", "M")):
        return s
    m_plain_r = fullmatch(r"([0-9]+(?:\.[0-9]+)?)R", s)
    if m_plain_r:
        body = m_plain_r.group(1)
        return f"{body}R" if include_ohm_r_suffix else body
    if s.endswith("R"):
        return s
    if include_ohm_r_suffix:
        return f"{s}R"
    return s


def preprocess_cap_tokens_for_slash_voltage(spec: str) -> str:
    """
    Device/CPL strings often use ``…0.22UF/6.3V/0.22UF/6.3V`` (slash, no spaces).

    Insert ``+`` between capacitance and voltage so :func:`tokenize_bom_spec` can
    split them like PnP ``+``-separated fields. Also splits ``…V/0.22UF…`` repeats.
    """
    s = str(spec)
    prev = None
    while prev != s:
        prev = s
        s = sub(
            r"([\d.]+(?:UF|NF|PF|F))\s*/\s*([\d.]+\s*(?:kV|KV|V))\b",
            r"\1+\2",
            s,
            flags=I,
        )
    prev = None
    while prev != s:
        prev = s
        s = sub(
            r"(?<=[\d.]V)\s*/\s*(?=[\d.]+\s*(?:UF|NF|PF|F)\b)",
            "+",
            s,
            flags=I,
        )
    return s


def split_joined_clean_comment(
    spec: str,
    sep: str = DEFAULT_DOUBLE_COMMENT_JOIN,
) -> tuple[str, str, str]:
    """
    Split «prose | vendor label | MPN» join rows (Double Comment import).

    Returns ``(bom_prose, vendor_label, mpn_tail)``; empty strings when absent.
    """
    parts = [p.strip() for p in str(spec).split(sep) if str(p).strip()]
    if len(parts) >= 3:
        return parts[0], parts[1], parts[-1]
    if len(parts) == 2:
        return parts[0], "", parts[1]
    if len(parts) == 1:
        return parts[0], "", ""
    return str(spec).strip(), "", ""


def joined_clean_comment_mpn(spec: str, sep: str = DEFAULT_DOUBLE_COMMENT_JOIN) -> str:
    """Bare MPN from the last join segment, or the whole string."""
    _bom, _label, mpn = split_joined_clean_comment(spec, sep)
    return mpn or str(spec).strip()


def joined_clean_comment_bom_prose(
    spec: str, sep: str = DEFAULT_DOUBLE_COMMENT_JOIN
) -> str:
    """BOM description (first join segment) for regex / vendor merge."""
    bom, _label, _mpn = split_joined_clean_comment(spec, sep)
    return bom or str(spec).strip()


def _protect_dimension_stackups(s: str) -> tuple[str, list[str]]:
    """Mask ``0.8+0.15/-0.10mm`` so ``+`` is not a field separator."""
    stacks: list[str] = []

    def _repl(m) -> str:
        stacks.append(m.group(0))
        return _STACK_PLACEHOLDER.format(len(stacks) - 1)

    out = sub(
        r"\d+(?:\.\d+)?\+\d+(?:\.\d+)?/-\d+(?:\.\d+)?(?:mm|MM)\b",
        _repl,
        s,
        flags=I,
    )
    return out, stacks


def _restore_dimension_stackups(parts: list[str], stacks: list[str]) -> list[str]:
    if not stacks:
        return parts
    out: list[str] = []
    for p in parts:
        t = str(p)
        for i, raw in enumerate(stacks):
            t = t.replace(_STACK_PLACEHOLDER.format(i), raw)
        out.append(t)
    return out


def tokenize_bom_spec(spec: str) -> list[str]:
    """
    PnP/CSV often uses '+' between fields; BOM exports may use spaces instead.
    If there is no '+', split on whitespace so parse_* loops see separate tokens.
    """
    s = spec.strip()
    if not s:
        return []
    # «+/-5%» contains '+'; do not treat it as a PnP '+' field separator.
    s = sub(r"\+/-", "±", s)
    s, stacks = _protect_dimension_stackups(s)
    if match(r"^(RES|MLCC|CAP|PL)_", s, I):
        parts = [p.strip() for p in s.split("_") if p.strip()]
        return _restore_dimension_stackups(parts, stacks)
    if "+" in s:
        parts = [p.strip() for p in s.split("+") if p.strip()]
        return _restore_dimension_stackups(parts, stacks)
    if search(r"\s", s):
        parts = [p.strip() for p in split(r"\s+", s) if p.strip()]
        return _restore_dimension_stackups(parts, stacks)
    return _restore_dimension_stackups([s], stacks)


def normalize_for_regex_parsing(spec: str) -> str:
    """
    Reduce 'MFR/MPN' to bare MPN for token-based regex (mirrors vendor normalization).
    Keeps the full string when the slash is value/voltage (e.g. 15PF/50V).
    """
    s = sub(r"\+/-", "±", str(spec).strip())
    s = sub(r"<[gG]>\s*$", "", s).strip()
    if "/" not in s:
        return s
    if search(r"[\d.]+\s*(?:PF|NF|UF|F)\s*/\s*[\d.]+\s*(?:kV|KV|V)(?![A-Za-z0-9])", s, I):
        return s
    if search(r"(?<![0-9.])\d+/\d+W(?![0-9A-Z])", s, I):
        return s
    if search(r"^(?:CAP[\s_-]*SMD|MLCC|NETRES|RES(?:ISTOR)?|PL_)(?:[^A-Za-z0-9]|$)", s, I):
        return s
    return s.split("/")[-1].strip()
