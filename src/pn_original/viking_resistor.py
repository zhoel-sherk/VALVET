"""
Viking Tech thin-film chip resistor PN parser (ARG series).

Ordering per the Viking "Thin Film Chip Resistor (ARG Series)" sheet, REV.A6
dated 2022-01-22 (retrieved 2026-10-04; local copy under the gitignored
``datasheet/pdf/``), "Part Numbering"::

    series  size  tolerance  resistance  TCR  packaging
    ARG     03    C          1002        D    T

Fields, from the datasheet's own Part Numbering table:

- **Series** ``ARG``, literal.
- **Size** ``02``=0402, ``03``=0603, ``05``=0805, ``06``=1206. These are the
  inch-equivalent code pair the table prints (``ARG03 0603``), so the size code
  is two digits and must be mapped, not read as a four-digit EIA code.
- **Tolerance** ``B`` +/-0.1%, ``C`` +/-0.25%, ``D`` +/-0.5%, ``F`` +/-1%.
- **Resistance** four digits, three significant figures plus a power of ten,
  with the marking table giving ``0010``=1 ohm, ``4R70``=4.7 ohm, ``1001``=1 k,
  ``1004``=1 M. Sub-ohm values therefore also use the ``R``-decimal spelling.
- **TCR** ``C`` = +/-25 ppm/degC, ``D`` = +/-50 ppm/degC.
- **Packaging** ``T`` tape & reel, ``B`` bulk.

The codec is only wired in for ``RES``; there is no wattage in the ARG code, so
the cleaned string carries size, resistance and tolerance.

Examples:
- ARG03C1002DT → 0603_10K_0.25%
- ARG02F1001BT → 0402_1K_1%
- ARG06D4R70CT → 1206_4.7R_0.5%
"""

from __future__ import annotations

from parsers.regex_api import I, compile

VENDOR_NAME = "Viking Tech"
COMPONENT_TYPES = ["RES"]
PARSER_PRIORITY = 84

# Datasheet "Size Code": ARG02=0402, ARG03=0603, ARG05=0805, ARG06=1206.
_SIZE = {"02": "0402", "03": "0603", "05": "0805", "06": "1206"}
_TOL = {"B": "0.1%", "C": "0.25%", "D": "0.5%", "F": "1%"}
_TCR = {"C": "25ppm", "D": "50ppm"}

# ARG + 2-digit size + 1-letter tolerance + 4-digit resistance + 1-letter TCR
# + 1-letter packaging.
_RE = compile(r"^ARG(\d{2})([BCDF])(\d{4}|\dR\d\d)([CD])([TB])$", I)


def _format_ohm(value: float) -> str:
    if value < 0:
        return ""
    if value == 0:
        return "0R"
    if value >= 1_000_000:
        return f"{value / 1_000_000.0:.3f}".rstrip("0").rstrip(".") + "M"
    if value >= 1_000:
        return f"{value / 1_000.0:.3f}".rstrip("0").rstrip(".") + "K"
    if float(value).is_integer():
        return f"{int(value)}R"
    return f"{value:.3f}".rstrip("0").rstrip(".") + "R"


def _decode_resistance(code: str) -> str:
    raw = str(code or "").strip().upper()
    if "R" in raw:
        # R-decimal spelling used below 1 ohm: 4R70 -> 4.7 ohm.
        whole, _, frac = raw.partition("R")
        if not whole.isdigit() or not frac.isdigit():
            return ""
        return _format_ohm(float(f"{whole}.{frac}"))
    if not raw.isdigit():
        return ""
    if len(raw) != 4:
        return ""
    mantissa = int(raw[:3])
    exponent = int(raw[3])
    value = float(mantissa * (10**exponent))
    if value > 100_000_000:
        return ""
    return _format_ohm(value)


def parse(pn: str, component_type: str) -> str | None:
    if component_type != "RES":
        return None
    pn2 = "".join(str(pn).strip().upper().split())
    m = _RE.match(pn2)
    if not m:
        return None
    size_code, tol_ch, res_raw, tcr_ch, _pack = m.groups()
    size = _SIZE.get(size_code)
    if not size:
        return None
    resistance = _decode_resistance(res_raw)
    if not resistance:
        return None
    parts = [size, resistance, _TOL.get(tol_ch, "")]
    # TCR is a real published field; keep it only when it adds information
    # beyond the cleaned string the UI shows.
    tcr = _TCR.get(tcr_ch, "")
    if tcr:
        parts.append(tcr)
    return "_".join(p for p in parts if p)
