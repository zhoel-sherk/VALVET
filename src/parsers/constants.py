"""
Shared constants for BOM text parsing (packages, units, MLCC dielectrics).

Safe to import from anywhere in `parsers/` or `clean_component`.
"""

from __future__ import annotations

from typing import Set

from parsers.regex_api import I, compile

# Extended package list for all component types
PACKAGES = [
    "01005",
    "0201",
    "0402",
    "0603",
    "0805",
    "1206",
    "1210",
    "1812",
    "2010",
    "2512",
    "2220",
    "2225",
    "3015",
    "3020",
    "3030",
    "0630",
    "0730",
    "1030",
    "1239",
    "1340",
    "1350",
    "1913",
    "2135",
    "2312",
    "2550",
    "2759",
    "3921",
    "5650",
    "5850",
    "5950",
    "7060",
    "7640",
    "1540",
    "4516",
    "3812",
    "3813",
    "5012",
    "5013",
    "5015",
    "5020",
    "5025",
    "5030",
    "5035",
    "5040",
    "5050",
    "5060",
    "5125",
    "5130",
    "5140",
    "5155",
    "5820",
    "5840",
    "5850",
    "6108",
    "6115",
    "6120",
    "6135",
    "6150",
    "6155",
    "6165",
    "6265",
    "6330",
    "7012",
    "7035",
    "7040",
    "7055",
    "7345",
    "7355",
    "8050",
    "8060",
    "8250",
    "8450",
    "8850",
]
PACKAGE_PATTERN = "|".join(PACKAGES)

CAP_UNITS = {
    "F": "",
    "UF": "u",
    "NF": "n",
    "PF": "p",
    "F0": "",
    "UF0": "u",
    "NF0": "n",
    "PF0": "p",
}

RES_UNITS = {
    "R": "",
    "KR": "K",
    "MR": "M",
    "MRM": "m",
    "OHM": "",
    "KOHM": "K",
    "MOHM": "M",
    "M": "M",
    "K": "K",
}

INDUCTOR_UNITS = {
    "UH": "uH",
    "NH": "nH",
    "MH": "mH",
    "H": "H",
}

# Standard SMD case sizes — gate weak RES/CAP heuristics (avoid eating IC prose).
# Also accept footprint prefixes R0402 / C0603 common in underscore BOM lines.
STRICT_CHIP_CASE_RE = compile(
    r"(?<![0-9A-Z])[RC]?(01005|0201|0402|0603|0805|1206|1210|1812|2010|2512)\b",
    I,
)


def has_strict_chip_case_size(t: str) -> bool:
    return bool(STRICT_CHIP_CASE_RE.search(t))


MLCC_DIELECTRIC: Set[str] = {
    "NPO",
    "C0G",
    "COG",
    "X7R",
    "X5R",
    "X6S",
    "X8R",
    "Y5V",
    "Z5U",
}
