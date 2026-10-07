"""
Capacitance decode helpers (pn_original)

Shared MLCC utilities used by vendor capacitor parsers:

Part Number Format (conceptual — not a single PN):
EIA 3-digit capacitance in pF: XY Z → value = XY × 10^Z pF → normalized string (pF/nF/uF)

Examples:
- pf_eia_3_to_str("104") → "100nF"
- pf_eia_3_to_str("105") → "1uF"

Walsin voltage numeric helper:
- walsin_vol_code_to_v: 3-digit codes use EIA-style mantissa-exponent (500→50V, 202→2000V)

See vendor modules for full PN structures.
"""


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


def walsin_vol_code_to_v(v: str) -> str:
    """
    Walsin MLCC rated-voltage code.

    Three-digit codes use the EIA-style mantissa-exponent form:
    ``XYZ`` → ``XY × 10^Z`` V (e.g. 500 → 50V, 202 → 2000V, 302 → 3000V).
    Two-digit and one-digit codes are treated as direct voltage values.
    """
    if not v.isdigit() or not v:
        return ""
    n = int(v)
    if len(v) == 3:
        mantissa = int(v[:2])
        exponent = int(v[2])
        return f"{mantissa * (10**exponent)}V"
    if 1 <= n <= 9999:
        return f"{n}V"
    return f"{n}V"
