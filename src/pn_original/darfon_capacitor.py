"""
Darfon (达方) MLCC PN parser — metric ``C1005…`` NP0/C0G series.

Examples:
- C1005NP0508CGTS → 0402_0.5pF_C0G_50V
"""

from __future__ import annotations

from parsers.regex_api import I, compile, match

from ._mlcc_china_vol import china_mlcc_vol_from_digits, metric_size_to_imperial

VENDOR_NAME = "Darfon"
COMPONENT_TYPES = ["CAP"]
PARSER_PRIORITY = 84

_RE = compile(r"^C(\d{4})NP(\d{3})(\d)(CG)TS$", I)


def _np0_cap_from_code(code: str) -> str | None:
    """``050`` on 0.5 pF NP0 lines → ``0.5pF`` (not EIA-3)."""
    c = str(code).strip()
    if not c.isdigit() or len(c) != 3:
        return None
    if c.startswith("0") and c != "000":
        n = int(c)
        if n < 100:
            t = f"{n / 100:.2f}".rstrip("0").rstrip(".")
            return f"{t}pF"
    return None


def parse(pn: str, component_type: str) -> str | None:
    if component_type != "CAP":
        return None
    pn2 = "".join(str(pn).strip().upper().split())
    m = _RE.match(pn2)
    if not m:
        return None
    metric, cap3, vdig, _cg = m.groups()
    size = metric_size_to_imperial(metric)
    if not size:
        mr = match(r"^04(\d{2})$", metric, I)
        if mr:
            size = f"04{mr.group(1)}"
        else:
            return None
    cap = _np0_cap_from_code(cap3)
    if not cap:
        return None
    vol = china_mlcc_vol_from_digits(f"{vdig}00") or china_mlcc_vol_from_digits("500")
    if vdig == "8":
        vol = "50V"
    parts = [size, cap, "C0G"]
    if vol:
        parts.append(vol)
    return "_".join(parts)
