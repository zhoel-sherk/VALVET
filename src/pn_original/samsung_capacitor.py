"""
Samsung Capacitor PN Parser

Samsung MLCC Part Number Format:
CL + Size(2) + Temp(1) + Capacitance EIA(3) + Tolerance(1) + Rated voltage(1) + Thickness(1) + control + packaging

Examples:
- CL05A105MQ5NNNC → CAP_0402_1uF_6.3V_X5R_20%
- CL21B225KOFNNNE → CAP_0805_2.2uF_16V_X7R_10%
- CL31A106KAHNNNE → CAP_1206_10uF_25V_X5R_10%

Size codes:
02=0201, 04/05=0402, 06=0603, 08/21=0805, 10=0603, 12=1206, 18=1210, 31=1206, …

Temp codes:
A=X5R, B=X7R, C=X6S, D=X8R, E=COG(C0G), F=Y5V, G=Y5U, L=X7R(Automotive), R=NP0

Tolerance (index 8, directly after the 3-digit EIA code):
F=±1%, G=±2%, J=±5%, K=±10%, M=±20%; C0G pF grades (B/C/D) are not decoded yet.

Rated voltage (index 9, right after the tolerance letter), verified against the
CO1271 order BOM descriptions:
A=25V, B=50V, O=16V, P=10V, Q=6.3V; R=4V, L=16V, J=6.3V, H=50V, E=100V are kept
from the previous table (unverified).

Thickness (index 10) is a millimetre digit, *not* a tolerance: 5=0.5mm,
7=0.7mm, 8=0.8mm, Y=1.25mm (0805). Reading it as the tolerance was the bug:
``CL10A106MO8NQNC`` (thickness 8) came out as ±10% although the M at index 8 is
±20%, and ``CL21A226MAYNNNE`` (thickness Y) lost the tolerance entirely.

Note:
``parse()`` does not swallow exceptions. "Not my format" is reported by an explicit
``return None``; a raise means a genuine parser bug and is meant to reach the
``pn_original.parse_pn`` arbiter, which logs it with a traceback and names the vendor.
"""

from parsers.regex_api import I, search, sub

from ._cap_decode import pf_eia_3_to_str

VENDOR_NAME = "Samsung"
COMPONENT_TYPES = ["CAP"]
PARSER_PRIORITY = 95


def parse(pn: str, component_type: str) -> str | None:
    """
    Parse Samsung capacitor PN

    Format: CL + Size(2) + Temp(1) + Value(3) + Tolerance(1) + Voltage(1) + Thickness(1) + Series(2) + Packaging(2)
    Example: CL05A105MQ5NNNC
      CL = Multi-layer Ceramic Capacitor
      05 = Size code: 05 -> 0402
      A = Temp code: A -> X5R
      105 = Capacitance: 105 = 1uF (10^5 pF)
      M = Tolerance: M -> ±20%
      Q = Rated voltage: Q -> 6.3V
      5 = Thickness: 5 -> 0.5mm
      NN = Control code
      NC = Packaging

    Value codes (3 digits in pF): 104 = 100nF, 105 = 1uF, 225 = 2.2uF, 106 = 10uF
    """
    if component_type != "CAP":
        return None

    pn = sub(r"\s*<[gG]>\s*$", "", str(pn).strip())
    pn = sub(r"\s+", "", pn).strip().upper()

    if not pn.startswith("CL"):
        return None

    size_map = {
        "02": "0201",
        "04": "0402",
        "03": "0201",
        "05": "0402",
        "06": "0603",
        "08": "0805",
        "10": "0603",
        "12": "1206",
        "18": "1210",
        "21": "0805",
        "31": "1206",
        "32": "1210",
    }

    temp_map = {
        "A": "X5R",
        "B": "X7R",
        "C": "X6S",
        "D": "X8R",
        "E": "COG",
        "F": "Y5V",
        "G": "Y5U",
        "L": "X7R",
        "R": "NP0",
    }

    # Rated voltage letter, index 9 (the character after the tolerance letter).
    # A/B/O/P/Q are the values the CO1271 BOM descriptions were checked against;
    # the remaining entries are kept from the previous table and are unverified.
    voltage_map = {
        "R": "4V",
        "Q": "6.3V",
        "P": "10V",
        "L": "16V",
        "J": "6.3V",
        "H": "50V",
        "E": "100V",
        "A": "25V",
        "B": "50V",
        "C": "630V",
        "M": "6.3V",
        "K": "10V",
        "N": "4V",
        "O": "16V",
    }

    # Capacitance tolerance letter, index 8 — right after the EIA value code.
    # Digits never occur here: position 10 carries the thickness in mm (5, 7, 8)
    # and used to be misread as a tolerance (5 -> 20%, 8 -> 10%).
    tol_map = {
        "F": "1%",
        "G": "2%",
        "J": "5%",
        "K": "10%",
        "M": "20%",
        "P": "5%",
        "Q": "10%",
        "R": "20%",
        "S": "5%",
        "T": "10%",
    }

    if len(pn) < 10:
        return None

    # Size: positions 2-3 (CL05 -> 05 = 0402)
    size_code = pn[2:4]
    size = size_map.get(size_code, "")

    # Temp: position 4
    temp = temp_map.get(pn[4], "")

    # Value: positions 5-7 (EIA 3 digits, pF base)
    value_code = pn[5:8]
    value_str = ""
    if value_code.isdigit() and len(value_code) == 3:
        value_str = pf_eia_3_to_str(value_code) or ""

    # Voltage: position 9, the letter right after the tolerance letter.
    voltage_char = pn[9] if len(pn) > 9 else ""
    voltage = voltage_map.get(voltage_char, "")

    # Thickness/plating: position 10 (mm digit, not used)

    # Tolerance: position 8, the letter right after the 3-digit EIA code.
    tol_char = pn[8] if len(pn) > 8 else ""
    tol = tol_map.get(tol_char, "")
    if not tol:
        # Alternate layouts / packaging: last tolerance letter before NNN… suffix
        mm = search(r"([FGJKM])(?:NN|NC|NE|NR|NQ)", pn, I)
        if mm:
            tol = tol_map.get(mm.group(1).upper(), "")

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


def format_example(pn: str) -> str:
    """Format example of conversion"""
    result = parse(pn, "CAP")
    return f"{pn} → CAP_{result}" if result else f"{pn} → (not recognized)"
