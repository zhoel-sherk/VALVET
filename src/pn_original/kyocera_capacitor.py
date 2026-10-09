"""Kyocera AVX automotive MLCC codec — KAM series.

From ``doc/info/Kyocera_KAM_Series.pdf`` (Automotive MLCC, KAM Series General
Specifications), "HOW TO ORDER" on p.1::

    KAM 31 G R7 1H 475 K U
    Series Size Thickness Dielectric Voltage Capacitance Capacitance Packaging
                    Tolerance

All seven fields are read. The catalogue prints the size both ways, which is
what makes this unambiguous:

======  ================  ==========
code    inch             metric (mm)
======  ================  ==========
03      0201              0603
05      0402              1005
15      0603              1608
21      0805              2012
31      1206              3216
32      1210              3225
42      1808              4520
43      1812              4532
55      2220              5750
======  ================  ==========

The repo's size vocabulary is the inch name, so the inch column is the one used
here. Note ``15``=0603 and not ``06``: Kyocera writes 0603 as ``15``, which is
the 1608 JIS code, so a codec that assumes EIA digits here would misread it.

Dielectric codes are two characters (``CG``=C0G, ``R7``=X7R, ``S7``=X7S,
``T7``=X7T, ``R8``=X8R, ``L8``=X8L, ``G8``=X8G) and voltage codes are two
characters where the first is a decade digit (``1H``=50 V) — see the tables
below, which hold exactly what the sheet prints. Two things in that block read
like more than they are: ``0G`` is the 4 V *voltage* code sitting directly to the
right of ``CG``, not an eighth dielectric, and no X5R code is printed at all.
``NP0`` appears as a KAM product line without an order code, so it is not
claimed.

Capacitance is 2 significant digits plus zeros in pF, with the same ``dRd``
decimal the other codecs here accept (``1R5`` = 1.5 pF).

Tolerances: ``B`` ±0.1 pF, ``C`` ±0.25 pF, ``D`` ±0.5 pF (all C0G only, below
10 pF), ``F`` ±1 %, ``G`` ±2 %, ``J`` ±5 %, ``K`` ±10 %, ``M`` ±20 %. The
absolute grades render as a bare pF magnitude, matching every other codec here.

Note:
``parse()`` does not swallow exceptions. "Not my format" is reported by an
explicit ``return None``; a raise means a genuine parser bug and is meant to
reach the ``pn_original.parse_pn`` arbiter, which logs it with a traceback and
names the vendor.
"""

from parsers.regex_api import match, sub

from ._cap_decode import pf_eia_3_to_str

VENDOR_NAME = "Kyocera"
COMPONENT_TYPES = ["CAP"]
PARSER_PRIORITY = 90

# 2 SIZE CODE - inch name. ``15`` is 0603 (Kyocera writes the 1608 JIS code).
_SIZE = {
    "03": "0201",
    "05": "0402",
    "15": "0603",
    "21": "0805",
    "31": "1206",
    "32": "1210",
    "42": "1808",
    "43": "1812",
    "55": "2220",
}

# 3 DIELECTRIC CODE - the seven codes the HOW TO ORDER column prints. ``CG`` is
# the sheet's symbol for C0G and normalises like every other codec here does.
# ``0G`` is *not* one of these: it is the 4 V entry of the voltage column, which
# the table prints immediately to the right of ``CG`` and reads like a
# continuation of the dielectric list. No X5R code is printed either, and R5 is
# therefore not accepted. ``NP0`` is listed as a KAM product line but the sheet
# never prints an order code for it.
_DIEL = {
    "CG": "C0G",
    "R7": "X7R",
    "S7": "X7S",
    "T7": "X7T",
    "R8": "X8R",
    "L8": "X8L",
    "G8": "X8G",
}

# 6 RATED VOLTAGE CODE - decade digit + decade character.
_VOLT = {
    "0G": "4V",
    "0J": "6.3V",
    "1A": "10V",
    "1C": "16V",
    "1E": "25V",
    "1H": "50V",
    "2A": "100V",
    "2D": "200V",
    "2E": "250V",
    "2H": "500V",
    "2J": "630V",
    "3A": "1000V",
    "3N": "1500V",
    "3D": "2000V",
    "3E": "2500V",
    "3U": "3000V",
}

# 5 CAPACITANCE TOLERANCE CODE.
_TOL_ABS = {
    "B": "0.1pF",
    "C": "0.25pF",
    "D": "0.5pF",
}
_TOL_PCT = {
    "F": "1%",
    "G": "2%",
    "J": "5%",
    "K": "10%",
    "M": "20%",
}

# 1 SERIES CODE. KAM is the automotive series; KAF is FLEXITERM and is a
# different catalogue, so it is not claimed here.
_SERIES = "KAM"


def _capacitance(code: str) -> str:
    """EIA 3-digit or ``dRd`` pF code -> cleaned string."""
    raw = str(code or "").strip().upper()
    mr = match(r"^(\d)R(\d)$", raw)
    if mr:
        pf = float(f"{mr.group(1)}.{mr.group(2)}")
        return f"{int(pf)}pF" if pf.is_integer() else f"{pf}pF"
    return pf_eia_3_to_str(raw) or ""


def _tolerance(letter: str) -> str:
    key = str(letter or "").strip().upper()
    return _TOL_ABS.get(key, _TOL_PCT.get(key, ""))


def parse(pn: str, component_type: str) -> str | None:
    """Parse a Kyocera AVX ``KAM`` automotive MLCC part number.

    ``KAM`` + size(2) + thickness(1) + dielectric(2) + voltage(2) +
    capacitance(3) + tolerance(1) + packaging(1).

    Fields 3 (thickness) and 8 (packaging) are not part of the cleaned value and
    so are not constrained — but every field that *is* cleaned must be a code
    the sheet publishes, or the part is refused rather than half-reported.
    """
    if component_type != "CAP":
        return None

    pn = sub(r"\s*<[gG]>\s*$", "", str(pn).strip())
    pn = sub(r"\s+", "", pn).strip().upper()

    if len(pn) != 15 or not pn.startswith(_SERIES):
        return None

    size = _SIZE.get(pn[3:5], "")
    if not size:
        return None
    diel = _DIEL.get(pn[6:8], "")
    if not diel:
        return None
    volt = _VOLT.get(pn[8:10], "")
    if not volt:
        return None
    cap = _capacitance(pn[10:13])
    if not cap:
        return None
    tol = _tolerance(pn[13])
    if not tol:
        return None

    # pn[5] is the thickness code and pn[14] the packaging code.
    return f"{size}_{cap}_{volt}_{diel}_{tol}"


def format_example(pn: str) -> str:
    """Format example of conversion"""
    result = parse(pn, "CAP")
    return f"{pn} → CAP_{result}" if result else f"{pn} → (not recognized)"
