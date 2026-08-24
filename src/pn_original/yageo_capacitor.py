"""
Yageo Capacitor PN Parser

Yageo MLCC Part Number Format:
CC|CH + Size(4) + Tolerance letter + series/temp block + voltage digit before BB + BB + EIA value digits + tail
NP0 lines: …NPO{digit}BN{EIA3}… (no BB block)

Examples:
- CC0402KRX7R9BB102 → CAP_0402_1nF_50V_X7R_10%
- CC0603ZRY5V7BB105 → CAP_0603_1uF_16V_Y5V_20%
- CC0402JRNPO9BN150 → CAP_0402_15pF_50V_NP0_5%

Size codes:
0201, 0402, 0603, 0805, 1206, 1210 (digits after CC|CH)

Temp / dielectric codes:
X7R, X5R, X7U, Y5V, Y5U, COG, NPO→NP0, X6S

Voltage codes:
Digit (or letter) immediately before ``BB`` in …X7R9BB… pattern; table voltage_before_bb + voltage_letter in code

Tolerance:
F=±1%, G=±2%, J=±5%, K=±10%, M=±20% (position after size + fallback scan)
"""

from parsers.regex_api import I, match, search, sub

from ._cap_decode import pf_eia_3_to_str

VENDOR_NAME = "Yageo_CAP"
COMPONENT_TYPES = ["CAP"]
PARSER_PRIORITY = 100


def parse(pn: str, component_type: str) -> str | None:
    """Parse Yageo capacitor PN"""
    if component_type != "CAP":
        return None

    pn = sub(r"\s*<[gG]>\s*$", "", str(pn).strip())
    pn = sub(r"\s+", "", pn).strip().upper()

    if not pn.startswith("CC") and not pn.startswith("CH"):
        return None

    size_map = {
        "0201": "0201",
        "0402": "0402",
        "0603": "0603",
        "0805": "0805",
        "1206": "1206",
        "1210": "1210",
    }

    temp_map = {
        "X7R": "X7R",
        "X5R": "X5R",
        "X7U": "X7U",
        "Y5V": "Y5V",
        "Y5U": "Y5U",
        "COG": "COG",
        "NPO": "NP0",
    }

    # Yageo CC/CH: letter codes (and digits before BB) for rated voltage
    voltage_letter = {
        "R": "4V",
        "Q": "6.3V",
        "P": "10V",
        "L": "16V",
        "J": "25V",
        "H": "50V",
        "E": "100V",
        "G": "250V",
        "A": "250V",
    }
    # Char immediately before "BB" (e.g. ...X7R9BB102, ...X5R5BB226)
    voltage_before_bb = {
        "0": "2.5V",
        "1": "4V",
        "2": "5V",
        "3": "6.3V",
        "4": "4V",
        "5": "6.3V",
        "6": "10V",
        "7": "16V",
        "8": "25V",
        "9": "50V",
    }

    tol_map = {"F": "1%", "G": "2%", "J": "5%", "K": "10%", "M": "20%"}

    try:
        size = size_map.get(pn[2:6], "")
        if not size:
            return None

        temp_match = search(r"(X[57][RU]|Y[5U]|COG|NPO|X5R|X6S)", pn)
        temp = temp_map.get(temp_match.group(1), "") if temp_match else ""
        if not temp and "X5R" in pn:
            temp = "X5R"

        value_str = ""
        voltage = ""

        npo_bn = search(r"NPO(\d)BN(\d{3})", pn, I) or search(
            r"NP0(\d)BN(\d{3})", pn, I
        )
        npo_br0 = search(r"NPO(\d)BN(5R\d)", pn, I) or search(
            r"NP0(\d)BN(5R\d)", pn, I
        )
        if npo_br0:
            vdig, rval = npo_br0.groups()
            voltage = voltage_before_bb.get(vdig, "") or voltage_letter.get(vdig, "")
            mr0 = match(r"^5R([0-9])$", rval, I)
            if mr0:
                value_str = f"5.{mr0.group(1)}pF"
            temp = temp or "C0G"
        elif npo_bn:
            vdig, eia3 = npo_bn.groups()
            voltage = voltage_before_bb.get(vdig, "") or voltage_letter.get(vdig, "")
            value_str = pf_eia_3_to_str(eia3) or ""
            temp = temp or "C0G"
        else:
            bbm = search(r"([0-9A-Z])BB([0-9]{2,4})", pn, I)
            if bbm:
                vcode = bbm.group(1).upper()
                voltage = voltage_before_bb.get(vcode, "") or voltage_letter.get(
                    vcode, ""
                )

            value_match = search(r"BB(\d+)", pn)
            if value_match:
                raw = value_match.group(1)
                if len(raw) == 3 and raw.isdigit():
                    value_str = pf_eia_3_to_str(raw) or ""
                else:
                    value = int(raw)
                    if value >= 1000:
                        value_str = f"{value // 1000}uF"
                    else:
                        value_str = f"{value}pF"

        # Tolerance: first spec letter after size (CC + 4-char package) → index 6
        tol = tol_map.get(pn[6], "") if len(pn) > 6 else ""
        if not tol:
            tlm = search(r"([FGJKM])(?:[0-9A-Z]*)$", pn, I)
            tol = tol_map.get(tlm.group(1), "") if tlm else ""

        parts = []
        if size:
            parts.append(size)
        if value_str:
            parts.append(value_str)
        if voltage:
            parts.append(voltage)
        if temp:
            parts.append(temp)
        if tol:
            parts.append(tol)

        return "_".join(parts) if parts else None

    except Exception:
        return None


def format_example(pn: str) -> str:
    """Format example of conversion"""
    result = parse(pn, "CAP")
    return f"{pn} → CAP_{result}" if result else f"{pn} → (not recognized)"
