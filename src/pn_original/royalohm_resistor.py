"""
Royal Ohm Resistor PN Parser

RoyalOhm and UniOhm are the two brands of **Uniroyal Electronics Global Co.,
Ltd.** (Kunshan, Jiangsu) - one datasheet covers both - so this codec and
``uniohm_resistor.py`` decode the same layout and must not disagree.

Royal Ohm Thick Film Chip Resistor Part Number Format (14 codes):
Size(4) + Power(2) + Tolerance(1) + Resistance(4) + Packaging(3)

Examples:
- 0805W8J0103T5E → RES_0805_10K_5%_1/8W   (the datasheet's own ordering example)
- 0402WGF1004TCE → RES_0402_1M_1%_1/16W
- 0603WAF3001T5E → RES_0603_3K_1%_1/10W
- 0402WGD1002TCE → RES_0402_10K_0.5%_1/16W
- 0402WGF100MTCE → RES_0402_0.01R_1%_1/16W

Size codes:
0201, 0402, 0603, 0805, 1206, 1210, 2010, 2512

Power (codes 5-6) and tolerance (code 7) are independent fields, so D=0.5% and
G=2% resolve; see ``_POWER_CODES``.

Tolerance:
D=±0.5%, F=±1%, G=±2%, J=±5%

Resistance coding (codes 8-11, three significant figures plus a power-of-ten code):
- digit exponent: 4-digit XXXY = XXX×10^Y Ω  (e.g. 1004 = 1M)
- letter exponent: XYZJ = XYZ×10^-1, XYZK = XYZ×10^-2, XYZL = XYZ×10^-3,
  XYZM = XYZ×10^-4, XYZN = XYZ×10^-5, XYZP = XYZ×10^-6
  (e.g. 330K = 3.3 Ω, 100M = 0.01 Ω)

Note:
``parse()`` does not swallow exceptions. "Not my format" is reported by an explicit
``return None``; a raise means a genuine parser bug and is meant to reach the
``pn_original.parse_pn`` arbiter, which logs it with a traceback and names the vendor.
"""

from parsers.regex_api import match

VENDOR_NAME = "Royal Ohm"
COMPONENT_TYPES = ["RES"]
PARSER_PRIORITY = 25

# Datasheet "Explanation of Part No. System", code 5-6 (power rating), which the
# manufacturer publishes as independent of the tolerance letter in code 7.
_POWER_CODES = (
    ("WH", "1/32W"),
    ("WM", "1/20W"),
    ("WG", "1/16W"),
    ("WA", "1/10W"),
    ("W8", "1/8W"),
    ("W4", "1/4W"),
    ("W2", "1/2W"),
)

# Datasheet 2.4.3: the 11th code is the power of ten. Digits 0-6 mean 10^0..10^6
# and the letters are negative exponents: J=10^-1 K=10^-2 L=10^-3 M=10^-4
# N=10^-5 P=10^-6. Omitting M/N/P made those parts decode 10^3..10^6 too high
# while also dropping the tolerance (GRM-style fallthrough to the 3-digit rule).
_EXPONENT_MAP = {
    "J": 0.1,
    "K": 0.01,
    "L": 0.001,
    "M": 0.0001,
    "N": 0.00001,
    "P": 0.000001,
}


def _format_ohm(value: float) -> str:
    if value < 0:
        return ""
    if value == 0:
        return "0R"
    if value >= 1_000_000:
        v = value / 1_000_000.0
        return f"{v:.3f}".rstrip("0").rstrip(".") + "M"
    if value >= 1_000:
        v = value / 1_000.0
        return f"{v:.3f}".rstrip("0").rstrip(".") + "K"
    if float(value).is_integer():
        return f"{int(value)}R"
    return f"{value:.3f}".rstrip("0").rstrip(".") + "R"


def parse_resistance(code: str) -> str:
    """Decode resistance value

    3-digit: XXY = XX × 10^Y ohms
    4-digit: XXXY = XXX × 10^Y ohms (E96)
    """
    code = code.upper().strip()

    if not code.isdigit():
        return code

    if len(code) == 4:
        mantissa = int(code[:3])
        exponent = int(code[3])
    elif len(code) == 3:
        mantissa = int(code[:2])
        exponent = int(code[2])
    else:
        return code

    value = float(mantissa * (10**exponent))
    # Guardrail: absurd giga-ohm expansions for tiny SMD PNs are likely decode mistakes.
    if value > 100_000_000:
        return ""
    return _format_ohm(value)


def parse(pn: str, component_type: str) -> str | None:
    """Parse Royal Ohm resistor PN"""
    if component_type not in COMPONENT_TYPES:
        return None

    pn = pn.strip().upper()

    if not match(r"^\d{4}", pn):
        return None

    size = pn[:4]
    remaining = pn[4:]

    wattage_rules = (
        ("WGFTC", "1/16W", ""),
        ("WGF", "1/16W", ""),
        ("WGJ", "1/16W", "5%"),
        ("WAF", "1/10W", ""),
        ("WAJ", "1/10W", "5%"),
        ("WMF", "1/20W", ""),
        ("WMJ", "1/20W", "5%"),
        ("W8F", "1/8W", ""),
        ("W8J", "1/8W", "5%"),
        ("W4F", "1/4W", ""),
        ("W4J", "1/4W", "5%"),
        ("W2F", "1/2W", ""),
        ("W2J", "1/2W", "5%"),
        ("WG", "1/16W", ""),
        ("WA", "1/10W", ""),
        ("W8", "1/8W", ""),
        ("W4", "1/4W", ""),
    )

    wattage = ""
    default_tolerance = ""
    res_start = 0
    # The datasheet makes power (codes 5-6) and tolerance (code 7) independent
    # fields, so the pair is read as "power code" + "tolerance letter" instead of
    # as fused tokens. That is what makes D=+/-0.5% and G=+/-2% reachable.
    tol_map = {"D": "0.5%", "F": "1%", "G": "2%", "J": "5%"}
    power_code = None
    for code, label in _POWER_CODES:
        if remaining.startswith(code):
            power_code = (code, label)
            break

    if power_code is not None:
        wattage = power_code[1]
        res_start = len(power_code[0])
        tol_char = remaining[res_start : res_start + 1]
        if tol_char in tol_map:
            default_tolerance = tol_map[tol_char]
            res_start += 1
    else:
        for code, label, tol in wattage_rules:
            if remaining.startswith(code):
                wattage = label
                default_tolerance = tol
                res_start = len(code)
                break

    if res_start == 0:
        return None

    remaining2 = remaining[res_start:]

    # Royal Ohm format: after wattage code
    # 3-digit resistance: XXX + tol at position 3 (e.g., 100J = 10R)
    # 4-digit resistance: XXXX (E96 series, default ±1%) + optional TCR + pack

    tolerance = ""
    res_code = ""

    # Check if 3-digit + decimal-multiplier format.
    # Royal Ohm uses J/K/L as decimal multipliers for the 3-digit value field
    # (datasheet: "J" ~ 0.1, "K" ~ 0.01, "L" ~ 0.001).  The series tolerance
    # (F/J/...) is already encoded in the wattage prefix above.
    # Confirmed against LCSC / datasheet:
    #   0402WGF100JTCE  -> 10R   ±1%   (100 × 0.1)
    #   0402WGF200JTCE  -> 20R   ±1%   (200 × 0.1)
    #   0402WGF549JTCE  -> 54.9R ±1%   (549 × 0.1)
    #   0402WGF511KTCE  -> 5.11R ±1%   (511 × 0.01)
    #   0603WAF220KT5E  -> 2.2R  ±1%   (220 × 0.01)
    multiplier_map = _EXPONENT_MAP
    if len(remaining2) >= 4 and remaining2[3] in multiplier_map:
        tolerance = default_tolerance or "1%"
        res_code = remaining2[:3]
        if res_code.isdigit():
            resistance = _format_ohm(
                float(int(res_code)) * multiplier_map[remaining2[3]]
            )
        else:
            resistance = ""
    else:
        resistance = ""

    # If not 3-digit, check if 4-digit (E96 series, default ±1%)
    if not res_code:
        if len(remaining2) >= 4 and remaining2[:4].isdigit():
            res_code = remaining2[:4]
            tolerance = default_tolerance or "1%"  # Default for 4-digit E96
        elif len(remaining2) >= 3:
            res_code = remaining2[:3]
            tolerance = default_tolerance or tolerance

    # If not 3-digit, check 4-digit format (resistance at positions 0-3, tol at position 4)
    if not res_code and len(remaining2) >= 5:
        if remaining2[4] in tol_map:
            tol_char = remaining2[4]
            tolerance = tol_map.get(tol_char, "")
            res_code = remaining2[:4]

    # Fallback: assume 4-digit if all digits
    if not res_code:
        if len(remaining2) >= 4 and remaining2[:4].isdigit():
            res_code = remaining2[:4]
        elif len(remaining2) >= 3:
            res_code = remaining2[:3]

    if not resistance:
        resistance = parse_resistance(res_code) if res_code.isdigit() else ""
    if not resistance:
        return None

    parts = []
    if size:
        parts.append(size)
    if resistance:
        parts.append(resistance)
    if tolerance:
        parts.append(tolerance)
    if wattage:
        parts.append(wattage)

    return "_".join(parts) if parts else None


def format_example(pn: str) -> str:
    result = parse(pn, "RES")
    return f"{pn} → {result}" if result else f"{pn} → (not recognized)"
