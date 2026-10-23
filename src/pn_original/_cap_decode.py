"""
Capacitance decode helpers (pn_original)

Shared MLCC utilities used by vendor capacitor parsers:

Part Number Format (conceptual — not a single PN):
EIA 3-digit capacitance in pF: XY Z → value = XY × 10^Z pF → normalized string (pF/nF/uF)

Examples:
- pf_eia_3_to_str("104") → "100nF"
- pf_eia_3_to_str("105") → "1uF"

Walsin voltage numeric helper:
- eia_vol_code_to_v: 3-digit codes use EIA-style mantissa-exponent (500→50V, 202→2000V)

See vendor modules for full PN structures.
"""

import re


def cap_code_to_str(code: str) -> str | None:
    r"""Decode a capacitance code: EIA-3 digits, or ``R`` as the decimal point.

    Murata C02E21 p.3 (and the Walsin/Fenghua sheets) define the unit as pF:
    the first two digits are significant and the third is the number of zeros.
    A decimal point is written with ``R``, and *every* digit is significant:
    ``R50`` = 0.50 pF, ``1R0`` = 1.0 pF, ``5R0`` = 5.0 pF. The leading-``R``
    form (``R50``) only appears in the Murata numbering, which is why the older
    ``^(\d)R(\d)$`` helpers could not read it.
    """
    raw = str(code or "").strip().upper()
    if not raw:
        return None
    decimal = re.fullmatch(r"(\d*)R(\d+)", raw)
    if decimal:
        whole, frac = decimal.groups()
        value = f"{whole or '0'}.{frac}"
        return f"{float(value):g}pF"
    return pf_eia_3_to_str(raw)


def pf_eia_3_to_str(abc: str) -> str | None:
    """
    3 characters XY Z: value = XY * 10^Z pF.
    e.g. 105 → 1µF, 104 → 100nF, 100 → 10pF.
    """
    if len(abc) != 3 or not abc.isdigit():
        return None
    xy, z = int(abc[0:2]), int(abc[2])
    pf = xy * (10**z)
    if pf < 0:
        return None
    if pf >= 1_000_000_000:  # 1 F+
        u = pf / 1_000_000_000.0
        t = f"{u:.3f}".rstrip("0").rstrip(".")
        return f"{t}F"
    if pf >= 1_000_000:  # µF
        u = pf / 1_000_000.0
        t = f"{u:.3f}".rstrip("0").rstrip(".")
        return f"{t}uF"
    if pf >= 1000:  # nF
        u = pf / 1000.0
        t = f"{u:.3f}".rstrip("0").rstrip(".")
        return f"{t}nF"
    if pf < 0.1:
        return f"{pf}pF"
    return f"{int(pf)}pF" if float(pf) == int(pf) else f"{pf}pF"


def eia_vol_code_to_v(v: str) -> str:
    """
    EIA-style rated-voltage code, shared by the vendors that publish it.

    Three-digit codes are mantissa-exponent: ``XYZ`` -> ``XY x 10^Z`` V
    (500 -> 50 V, 101 -> 100 V, 202 -> 2000 V, 302 -> 3000 V). This is what
    the Walsin "How to order" tables and the Fenghua MLCC "Rated Voltage"
    column both specify. Two- and one-digit codes are direct values.

    Note this is **not** the same convention as the V/10 form used by Eyang,
    TCC, Darfon and Viiyong - for those see ``china_mlcc_vol_from_digits``. The
    two agree only on codes ending in 0, which is why the wrong one still
    produced plausible results on the common 16/25/50/63 V parts.
    """
    if not v or not v.isdigit():
        return ""
    n = int(v)
    if len(v) == 3:
        mantissa = int(v[:2])
        exponent = int(v[2])
        return f"{mantissa * (10**exponent)}V"
    if 1 <= n <= 9999:
        return f"{n}V"
    return f"{n}V"


#: Backwards-compatible alias; the helper is not Walsin-specific.
walsin_vol_code_to_v = eia_vol_code_to_v
