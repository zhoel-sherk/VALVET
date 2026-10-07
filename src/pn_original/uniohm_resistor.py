"""
Uniohm Resistor PN Parser

Uniohm and RoyalOhm are the two brands of **Uniroyal Electronics Global Co.,
Ltd.** (Kunshan, Jiangsu) - one datasheet covers both - so this codec and
``royalohm_resistor.py`` decode the same layout and must not disagree.

Uniohm Thick Film Chip Resistor Part Number Format (14 codes):
Size(4) + Power(2) + Tolerance(1) + Resistance(4) + Packaging(3)

Power and tolerance are independent fields, so D=0.5% and G=2% are reachable;
the 11th code of the resistance field is the power of ten, with the letters
meaning negative exponents (see ``_EXPONENT_MAP``).

Examples:
- 0805W8J0103T5E → RES_0805_10K_5%_1/8W   (the datasheet's own ordering example)
- 0603WAF3001T5E → RES_0603_3K_1%_1/10W
- 0402WGF4701TCE → RES_0402_4.7K_1%_1/16W
- 0402WGD1002TCE → RES_0402_10K_0.5%_1/16W
- 0402WGF100MTCE → RES_0402_0.01R_1%_1/16W

Size codes:
0201, 0402, 0603, 0805, 1206, 1210, 2010, 2512

Note:
``parse()`` does not swallow exceptions. "Not my format" is reported by an explicit
``return None``; a raise means a genuine parser bug and is meant to reach the
``pn_original.parse_pn`` arbiter, which logs it with a traceback and names the vendor.
"""

from parsers.regex_api import match

VENDOR_NAME = "Uniohm"
COMPONENT_TYPES = ["RES"]
PARSER_PRIORITY = 25

# UniOhm and RoyalOhm are the two brands of Uniroyal Electronics Global Co., Ltd.
# (Kunshan, Jiangsu); both use the same 14-code ordering procedure, so both
# codecs mirror one datasheet. See the module docstring.
#
# Datasheet "Explanation of Part No. System", code 5-6 (power rating), published
# as independent of the tolerance letter in code 7.
_POWER_CODES = (
    ("WH", "1/32W"),
    ("WM", "1/20W"),
    ("WG", "1/16W"),
    ("WA", "1/10W"),
    ("W8", "1/8W"),
    ("W4", "1/4W"),
    ("W2", "1/2W"),
)

# Datasheet 2.4.3: 11th code is the power of ten; letters are negative
# exponents J=10^-1 K=10^-2 L=10^-3 M=10^-4 N=10^-5 P=10^-6.
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
    if value > 100_000_000:
        return ""
    return _format_ohm(value)


def parse(pn: str, component_type: str) -> str | None:
    """Parse Uniohm resistor PN"""
    if component_type not in COMPONENT_TYPES:
        return None

    pn = pn.strip().upper().replace(" ", "")

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
    tol_map = {"D": "0.5%", "F": "1%", "G": "2%", "J": "5%", "K": "10%"}
    # Power (codes 5-6) and tolerance (code 7) are independent fields in the
    # datasheet, so read them as such; this is what makes D=0.5% and G=2%
    # reachable instead of only the F/J pairs baked into wattage_rules.
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
        # Truncated / spaced MPN: «0201 F7502TCE» → size + tol-first resistance.
        # Insert size-default wattage when remaining starts with a tol letter.
        _size_default_watt = {
            "0201": ("1/20W", ""),
            "0402": ("1/16W", ""),
            "0603": ("1/10W", ""),
            "0805": ("1/8W", ""),
            "1206": ("1/4W", ""),
            "1210": ("1/2W", ""),
            "2010": ("3/4W", ""),
            "2512": ("1W", ""),
        }
        if (
            remaining
            and remaining[0] in ("F", "J", "K", "G")
            and size in _size_default_watt
        ):
            wattage, default_tolerance = _size_default_watt[size]
            remaining2 = remaining
        else:
            return None
    else:
        remaining2 = remaining[res_start:]

    # Check if 3-digit format (resistance + tol at position 3)
    tolerance = ""
    res_code = ""
    resistance = ""

    # Tol-first form after wattage omit: F7502TCE
    if (
        not resistance
        and len(remaining2) >= 5
        and remaining2[0] in tol_map
        and remaining2[1:5].isdigit()
    ):
        tolerance = tol_map[remaining2[0]]
        res_code = remaining2[1:5]
        resistance = parse_resistance(res_code)

    if len(remaining2) >= 4 and not resistance:
        # Royal Ohm / Uniohm use J/K/L as decimal multipliers for the 3-digit
        # value field (datasheet: "J" ~ 0.1, "K" ~ 0.01, "L" ~ 0.001).
        # Confirmed against LCSC / datasheet:
        #   0402WGF100JTCE  -> 10R   ±1%   (100 × 0.1)
        #   0402WGF200JTCE  -> 20R   ±1%   (200 × 0.1)
        #   0402WGF549JTCE  -> 54.9R ±1%   (549 × 0.1)
        #   0402WGF511KTCE  -> 5.11R ±1%   (511 × 0.01)
        #   0603WAF220KT5E  -> 2.2R  ±1%   (220 × 0.01)
        multiplier_map = _EXPONENT_MAP
        if remaining2[3] in multiplier_map:
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
            tolerance = default_tolerance or "1%"
        elif len(remaining2) >= 3:
            res_code = remaining2[:3]
            tolerance = default_tolerance or tolerance

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
