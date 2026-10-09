"""TDK automotive MLCC codec — CGA series.

From ``doc/info/TDK_mlcc_automotive_general_en.pdf`` (Multilayer Ceramic Chip
Capacitors, automotive grade general, **up to 75 V**, June 2019).

The layout is fixed-width and every part number in the catalogue is exactly 20
characters, which is what makes the field spans unambiguous::

    C G A 1 A 2 C 0 G  1  H  0  1  0  C  0  3  0  B  A
    |   |   |   |   |  |-----|  |------|  |  |-----|  |--|
    |   |   |   |   |  |     |  |      |  |  |     |  |  +-- packaging
    |   |   |   |   |  |     |  |      |  |  |     |  +----- dimension (mm x10)
    |   |   |   |   |  |     |  |      |  |  +----- tolerance
    |   |   |   |   |  |     |  |      |  +-------- capacitance (pF)
    |   |   |   |   |  |     |  +------- rated voltage
    |   |   |   |   |  |     +---------- dielectric
    |   |   |   |   |  +---------------- (not decoded)
    |   |   |   |   +------------------- thickness
    |   |   |   +----------------------- size
    |   |   +--------------------------- series
    +---+

The size table is printed on p.1 as *Dimensions code: JIS[EIA]*::

    CGA1 0603 [0201 inch]      CGA5 3216 [1206 inch]
    CGA2 1005 [0402 inch]      CGA6 3225 [1210 inch]
    CGA3 1608 [0603 inch]      CGA8 4532 [1812 inch]
    CGA4 2012 [0805 inch]      CGA9 5750 [2220 inch]

The repo's size vocabulary is the EIA/inch name, so that is the one used here.
There is no ``CGA7``.

The dielectric is spelled out in full (``C0G``, ``X5R``, ``X7R``, ``X7S``,
``X7T``) rather than abbreviated, so it is read as written and normalised the
same way the other codecs here do. Rated voltage is a decade digit plus a
decade character: ``0G``=4 V, ``0J``=6.3 V, ``1A``=10 V, ``1C``=16 V, ``1E``=25 V,
``1H``=50 V, ``1V``=35 V, ``1N``=75 V — the eight this catalogue actually uses,
which is every code it prints because the document is scoped to 75 V and under.
A 100 V+ TDK part is not claimed here; that would need the full-range sheet.

Capacitance is EIA 3-digit with the same ``dRd`` decimal the other codecs accept
(``1R5`` = 1.5 pF). Tolerances: ``C`` ±0.25 pF, ``D`` ±0.5 pF (absolute, class 1,
rendered as a bare magnitude), ``J`` ±5 %, ``K`` ±10 %, ``M`` ±20 %.

Note:
``parse()`` does not swallow exceptions. "Not my format" is reported by an
explicit ``return None``; a raise means a genuine parser bug and is meant to
reach the ``pn_original.parse_pn`` arbiter, which logs it with a traceback and
names the vendor.
"""

from parsers.regex_api import match, sub

from ._cap_decode import pf_eia_3_to_str

VENDOR_NAME = "TDK"
COMPONENT_TYPES = ["CAP"]
PARSER_PRIORITY = 90

# Size - p.1 "Dimensions code: JIS[EIA]". No CGA7 is printed.
_SIZE = {
    "CGA1": "0201",
    "CGA2": "0402",
    "CGA3": "0603",
    "CGA4": "0805",
    "CGA5": "1206",
    "CGA6": "1210",
    "CGA8": "1812",
    "CGA9": "2220",
}

# Dielectric - spelled in full in the part number.
_DIEL = {
    "C0G": "C0G",
    "X5R": "X5R",
    "X7R": "X7R",
    "X7S": "X7S",
    "X7T": "X7T",
}

# Rated voltage - decade digit + decade character. The eight codes printed in
# this (sub-75 V) catalogue; higher ratings are a different document.
_VOLT = {
    "0G": "4V",
    "0J": "6.3V",
    "1A": "10V",
    "1C": "16V",
    "1E": "25V",
    "1H": "50V",
    "1V": "35V",
    "1N": "75V",
}

_TOL_ABS = {
    "C": "0.25pF",
    "D": "0.5pF",
}
_TOL_PCT = {
    "J": "5%",
    "K": "10%",
    "M": "20%",
}


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
    """Parse a TDK ``CGA`` automotive MLCC part number.

    ``CGA`` + size(1) + thickness(1) + undecoded(1) + dielectric(3) +
    voltage(2) + capacitance(3) + tolerance(1) + dimension(3) + packaging(2).

    Every catalogue part number is 20 characters, so the spans are fixed. The
    fields that are not cleaned (thickness, the digit after it, dimension and
    packaging) are not constrained, but every field that *is* cleaned must be a
    code this catalogue publishes, or the part is refused rather than
    half-reported.
    """
    if component_type != "CAP":
        return None

    pn = sub(r"\s*<[gG]>\s*$", "", str(pn).strip())
    pn = sub(r"\s+", "", pn).strip().upper()

    if len(pn) != 20 or not pn.startswith("CGA"):
        return None

    size = _SIZE.get(pn[0:4], "")
    if not size:
        return None
    diel = _DIEL.get(pn[6:9], "")
    if not diel:
        return None
    volt = _VOLT.get(pn[9:11], "")
    if not volt:
        return None
    cap = _capacitance(pn[11:14])
    if not cap:
        return None
    tol = _tolerance(pn[14])
    if not tol:
        return None

    # pn[4] thickness, pn[5] undecoded, pn[15:18] dimension, pn[18:20] packaging.
    return f"{size}_{cap}_{volt}_{diel}_{tol}"


def format_example(pn: str) -> str:
    """Format example of conversion"""
    result = parse(pn, "CAP")
    return f"{pn} → CAP_{result}" if result else f"{pn} → (not recognized)"
