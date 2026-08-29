"""
Royal Ohm Resistor PN Parser

Royal Ohm Thick Film Chip Resistor Part Number Format:
Size(4) + Wattage block + Tolerance + Resistance(3|4 digits) + TCR + packaging suffix

Examples:
- 0402WGF100JTCE → RES_0402_10R_5%_1/16W
- 0402WGF1004TCE → RES_0402_1M_1%_1/16W
- 0603WAF3001T5E → RES_0603_3K_1%_1/10W

Size codes:
0201, 0402, 0603, 0805, 1206, 1210, 2010, 2512

Wattage codes (examples):
WGF=1/16W (0402), WAF=1/10W (0603), W8F=1/8W (0805), W4F=1/4W (1206)

Tolerance:
F=±1%, J=±5%

Resistance coding:
3-digit E24 XXY = XX×10^Y Ω; 4-digit E96 XXXY = XXX×10^Y Ω
"""

from parsers.regex_api import match

import logger

VENDOR_NAME = "Royal Ohm"
COMPONENT_TYPES = ["RES"]
PARSER_PRIORITY = 25


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

    try:
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
        for code, label, tol in wattage_rules:
            if remaining.startswith(code):
                wattage = label
                default_tolerance = tol
                res_start = len(code)
                break

        if res_start == 0:
            return None

        remaining2 = remaining[res_start:]

        tol_map = {"F": "1%", "J": "5%", "K": "10%"}

        # Royal Ohm format: after wattage code
        # 3-digit resistance: XXX + tol at position 3 (e.g., 100J = 10R)
        # 4-digit resistance: XXXX (E96 series, default ±1%) + optional TCR + pack

        tolerance = ""
        res_code = ""

        # Check if 3-digit format (resistance + tol at position 3)
        if len(remaining2) >= 4:
            if remaining2[3] in tol_map:
                tol_char = remaining2[3]
                tolerance = tol_map.get(tol_char, "")
                res_code = remaining2[:3]
                if res_code.isdigit():
                    resistance = _format_ohm(float(int(res_code)) / 10.0)
                else:
                    resistance = ""
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

    except Exception as exc:
        logger.warning("Royal Ohm parse failed for %r: %s", pn, exc)
        return None


def format_example(pn: str) -> str:
    result = parse(pn, "RES")
    return f"{pn} → {result}" if result else f"{pn} → (not recognized)"
