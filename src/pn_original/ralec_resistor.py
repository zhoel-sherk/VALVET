"""
Ralec chip resistor PN parser.

Field order from the "Explanation Of Part Numbers" section the manufacturer's own
catalogue prints for every series (retrieved 2026-10-04; local copy under the
gitignored ``datasheet/pdf/``), e.g. catalogue page 51::

    RTT  02   100   J  TH
    1    2    3     4  5
    prefix size ohm tol packing

- **Prefix** - the series. The catalogue documents 23 chip-resistor series and
  they are kept in separate table entries because they do **not** share a size
  table, a tolerance list or a packing list.
- **Size** - two digits, Ralec's own code, which is *not* the inch code: ``02`` is
  0402 and ``06`` is **1206**. Each series also has its own subset, and the
  wide-terminal series use a different table again (``05``=0508, ``06``=0612,
  ``18``=1218, ``20``=1020, ``25``=1225).
- **Resistance** - three digits, or four in the low-resistance ranges, with ``R``
  standing in for the decimal point: ``100``=10 ohm, ``4R7``=4.7 ohm, ``000``=jumper,
  ``10R2``=10.2 ohm, ``1002``=10 kohm, ``0000``=jumper, and for the sub-ohm ranges
  ``R050``=0.05 ohm, ``R100``=0.1 ohm, ``R240``=0.24 ohm.
- **Tolerance** - ``B`` +/-0.1 %, ``C`` +/-0.25 % (thin film only), ``D`` +/-0.5 %,
  ``F`` +/-1 %, ``G`` +/-2 %, ``J`` +/-5 %.
- **Extra field** - only the thin-film series carry a TCR letter after the
  tolerance (``RTX021002BDTH``: ``B`` tolerance, ``D`` TCR), and only the
  FoS-test series carry that letter (``RST02100JATH``: ``J`` tolerance, ``A`` FoS).
  Series without such a field must not grow one.
- **Packing** - ``TH`` 2 mm carrier tape, ``TP`` 4 mm tape, ``TE`` 4 mm embossed.

Why each prefix gets its own pattern

The same six characters carry different sizes depending on the series, which is
exactly why this cannot be one generic pattern::

    RTW06100JTP  ->  0612_10R_5%     wide-terminal series, 06 = 0612
    RTT06100JTH  ->  1206_10R_5%     standard series,      06 = 1206

A shared size table would silently attach 1206 to a wide-terminal part. So each
prefix gets a pattern built from its own sizes, tolerances, packing codes and
extra-field letters. That also removes the ambiguity a single shared pattern
would have: with a free-form size group, ``RAG061000FTP`` splits as size ``061``
+ resistance ``000`` rather than size ``06`` + resistance ``1000``, and the first
split is a jumper in a size that does not exist.

The table below is generated from the catalogue text rather than transcribed.
Catalogue pages that contradict themselves are handled explicitly:

- ``FTT`` page 80 lists only ``TP`` and ``TE`` as packing, yet its own printed
  example is ``FTT02100JTH``. The example is part of the datasheet, so ``TH``
  is accepted; the table on that page is simply incomplete.
- ``RTX``'s tolerance list includes ``C`` +/-0.25 %, which shares a letter with
  its TCR codes; the two fields stay positionally separate.

Series deliberately not decoded

- ``RHW`` - the catalogue prints two conflicting tables under one prefix: page 62
  gives ``06``=1206 (high-power low-resistance) and page 64 gives ``06``=0612
  (wide terminal). A part number does not say which product it belongs to, so the
  size cannot be resolved and the part falls through rather than being guessed.
- ``RAA`` / ``RTA`` / ``RSA`` / ``FTA`` / ``RTN`` - resistor arrays, which insert a
  circuit count and a terminal-type field (``RAA02-4D100JTH``). A different
  structure; not implemented here.

Also not implemented: the metal-alloy low-ohm and shunt families (``LR``,
``LRE``, ``LRH``, ``LRS`` and their ``-A`` automotive variants). They are a
different structure again - ``LR2512-21R001F4`` is prefix, inch size, terminal
count, power, milli-ohm code, tolerance and packing - and they use *true inch*
size codes where ``LR``'s 06 means 0603, the opposite of the chip series above.
Mixing the two tables would attach the wrong size, so they are left for a
separate pass.

Examples:
- RTT02100JTH -> 0402_10R_5%
- RTT02R100FTH -> 0402_0.1R_1%
- RTT18100JTP -> 1812_10R_5%
- RTW06100JTP -> 0612_10R_5%
- RTX021002BDTH -> 0402_10K_0.1%
"""

from __future__ import annotations

from parsers.regex_api import I, compile

from ._resistor_decode import decode_ohms_suffix

VENDOR_NAME = "Ralec"
COMPONENT_TYPES = ["RES"]
PARSER_PRIORITY = 80

_SERIES = {
    "AHH": {
        # catalog p.27
        "sizes": {"03": "0603", "05": "0805", "06": "1206"},
        "tolerances": {"F": "1%", "J": "5%"},
        "packing": {"TP"},
        "extra": "",
        "extra_letters": "",
    },
    "AHW": {
        # catalog p.28
        "sizes": {"25": "1225"},
        "tolerances": {"F": "1%", "J": "5%"},
        "packing": {"TE"},
        "extra": "",
        "extra_letters": "",
    },
    "ARST": {
        # catalog p.34
        "sizes": {
            "01": "0201",
            "02": "0402",
            "03": "0603",
            "05": "0805",
            "06": "1206",
            "12": "1210",
            "20": "2010",
            "25": "2512",
        },
        "tolerances": {"D": "0.5%", "F": "1%", "J": "5%"},
        "packing": {"TE", "TH", "TP"},
        "extra": "",
        "extra_letters": "",
    },
    "ARTX": {
        # catalog p.17
        "sizes": {"02": "0402", "03": "0603", "05": "0805", "06": "1206"},
        "tolerances": {"B": "0.1%", "C": "0.25%", "D": "0.5%"},
        "packing": {"TH", "TP"},
        "extra": "TCR",
        "extra_letters": "BCD",
    },
    "FTG": {
        # catalog p.86+88
        "sizes": {"06": "1206", "12": "1210", "20": "2010", "25": "2512"},
        "tolerances": {"D": "0.5%", "F": "1%", "J": "5%"},
        "packing": {"TE", "TP"},
        "extra": "",
        "extra_letters": "",
    },
    "FTH": {
        # catalog p.89
        "sizes": {
            "01": "0201",
            "02": "0402",
            "03": "0603",
            "05": "0805",
            "06": "1206",
            "12": "1210",
            "20": "2010",
            "25": "2512",
        },
        "tolerances": {"F": "1%", "J": "5%"},
        "packing": {"TE", "TH", "TP"},
        "extra": "",
        "extra_letters": "",
    },
    "FTT": {
        # catalog p.80+82
        "sizes": {
            "01": "0201",
            "02": "0402",
            "03": "0603",
            "05": "0805",
            "06": "1206",
            "12": "1210",
            "20": "2010",
            "25": "2512",
        },
        "tolerances": {"B": "0.1%", "D": "0.5%", "F": "1%", "J": "5%"},
        "packing": {"TE", "TH", "TP"},
        "extra": "",
        "extra_letters": "",
    },
    "RAG": {
        # catalog p.29+31
        "sizes": {
            "02": "0402",
            "03": "0603",
            "05": "0805",
            "06": "1206",
            "12": "1210",
            "20": "2010",
            "25": "2512",
        },
        "tolerances": {"D": "0.5%", "F": "1%", "J": "5%"},
        "packing": {"TE", "TH", "TP"},
        "extra": "",
        "extra_letters": "",
    },
    "RAH": {
        # catalog p.25+26
        "sizes": {
            "02": "0402",
            "03": "0603",
            "05": "0805",
            "06": "1206",
            "12": "1210",
            "20": "2010",
            "25": "2512",
        },
        "tolerances": {"B": "0.1%", "D": "0.5%", "F": "1%", "J": "5%"},
        "packing": {"TE", "TH", "TP"},
        "extra": "",
        "extra_letters": "",
    },
    "RAR": {
        # catalog p.23+24
        "sizes": {
            "03": "0603",
            "05": "0805",
            "06": "1206",
            "12": "1210",
            "20": "2010",
            "25": "2512",
        },
        "tolerances": {"D": "0.5%", "F": "1%"},
        "packing": {"TE", "TH", "TP"},
        "extra": "",
        "extra_letters": "",
    },
    "RAT": {
        # catalog p.18+20
        "sizes": {
            "01": "0201",
            "02": "0402",
            "03": "0603",
            "05": "0805",
            "06": "1206",
            "12": "1210",
            "20": "2010",
            "25": "2512",
        },
        "tolerances": {"B": "0.1%", "D": "0.5%", "F": "1%", "G": "2%", "J": "5%"},
        "packing": {"TE", "TH", "TP"},
        "extra": "",
        "extra_letters": "",
    },
    "RAV": {
        # catalog p.33
        "sizes": {
            "03": "0603",
            "05": "0805",
            "06": "1206",
            "12": "1210",
            "20": "2010",
            "25": "2512",
        },
        "tolerances": {"D": "0.5%", "F": "1%", "J": "5%"},
        "packing": {"TE", "TH", "TP"},
        "extra": "",
        "extra_letters": "",
    },
    "RAW": {
        # catalog p.21+22
        "sizes": {"05": "0508", "06": "0612", "18": "1218", "20": "1020", "25": "1225"},
        "tolerances": {"D": "0.5%", "F": "1%", "J": "5%"},
        "packing": {"TE", "TP"},
        "extra": "",
        "extra_letters": "",
    },
    "RSR": {
        # catalog p.78
        "sizes": {
            "01": "0201",
            "02": "0402",
            "03": "0603",
            "05": "0805",
            "06": "1206",
            "12": "1210",
            "20": "2010",
            "25": "2512",
        },
        "tolerances": {"D": "0.5%", "F": "1%"},
        "packing": {"TE", "TH", "TP"},
        "extra": "",
        "extra_letters": "",
    },
    "RST": {
        # catalog p.72
        "sizes": {
            "01": "0201",
            "02": "0402",
            "03": "0603",
            "05": "0805",
            "06": "1206",
            "12": "1210",
            "20": "2010",
            "25": "2512",
        },
        "tolerances": {"B": "0.1%", "D": "0.5%", "F": "1%", "J": "5%"},
        "packing": {"TE", "TH", "TP"},
        "extra": "FOS",
        "extra_letters": "AB",
    },
    "RSV": {
        # catalog p.79
        "sizes": {
            "03": "0603",
            "05": "0805",
            "06": "1206",
            "12": "1210",
            "20": "2010",
            "25": "2512",
        },
        "tolerances": {"D": "0.5%", "F": "1%", "J": "5%"},
        "packing": {"TE", "TP"},
        "extra": "",
        "extra_letters": "",
    },
    "RTG": {
        # catalog p.67+69+70
        "sizes": {
            "02": "0402",
            "03": "0603",
            "05": "0805",
            "06": "1206",
            "20": "2010",
            "25": "2512",
        },
        "tolerances": {"D": "0.5%", "F": "1%", "J": "5%"},
        "packing": {"TE", "TH", "TP"},
        "extra": "",
        "extra_letters": "",
    },
    "RTH": {
        # catalog p.60
        "sizes": {
            "01": "0201",
            "02": "0402",
            "03": "0603",
            "05": "0805",
            "06": "1206",
            "12": "1210",
            "20": "2010",
            "25": "2512",
        },
        "tolerances": {"B": "0.1%", "D": "0.5%", "F": "1%", "J": "5%"},
        "packing": {"TE", "TH", "TP"},
        "extra": "",
        "extra_letters": "",
    },
    "RTR": {
        # catalog p.57+59
        "sizes": {
            "01": "0201",
            "02": "0402",
            "03": "0603",
            "05": "0805",
            "06": "1206",
            "12": "1210",
            "20": "2010",
            "25": "2512",
        },
        "tolerances": {"B": "0.1%", "D": "0.5%", "F": "1%"},
        "packing": {"TE", "TH", "TP"},
        "extra": "",
        "extra_letters": "",
    },
    "RTT": {
        # catalog p.51+53
        "sizes": {
            "01": "0201",
            "02": "0402",
            "03": "0603",
            "05": "0805",
            "06": "1206",
            "12": "1210",
            "18": "1812",
            "20": "2010",
            "25": "2512",
        },
        "tolerances": {"B": "0.1%", "D": "0.5%", "F": "1%", "G": "2%", "J": "5%"},
        "packing": {"TE", "TH", "TP"},
        "extra": "",
        "extra_letters": "",
    },
    "RTV": {
        # catalog p.65
        "sizes": {
            "03": "0603",
            "05": "0805",
            "06": "1206",
            "12": "1210",
            "20": "2010",
            "25": "2512",
        },
        "tolerances": {"D": "0.5%", "F": "1%", "J": "5%"},
        "packing": {"TE", "TP"},
        "extra": "",
        "extra_letters": "",
    },
    "RTW": {
        # catalog p.55+56
        "sizes": {"05": "0508", "06": "0612", "18": "1218", "20": "1020", "25": "1225"},
        "tolerances": {"D": "0.5%", "F": "1%", "J": "5%"},
        "packing": {"TE", "TP"},
        "extra": "",
        "extra_letters": "",
    },
    "RTX": {
        # catalog p.49
        "sizes": {
            "01": "0201",
            "02": "0402",
            "03": "0603",
            "05": "0805",
            "06": "1206",
            "12": "1210",
            "20": "2010",
            "25": "2512",
        },
        "tolerances": {"B": "0.1%", "C": "0.25%", "D": "0.5%", "F": "1%"},
        "packing": {"TE", "TH", "TP"},
        "extra": "TCR",
        "extra_letters": "BCDE",
    },
}

# Series deliberately not decoded, with the reason.
_REFUSED = {
    # Page 62 prints 06=1206 (high-power low-R), page 64 prints 06=0612 (wide
    # terminal) under one prefix, and the part number cannot say which.
    "RHW": "conflicting size tables in the catalogue",
    # Arrays insert a circuit count and a terminal-type field: RAA02-4D100JTH.
    "RAA": "array structure, not implemented",
    "RSA": "array structure, not implemented",
    "RTA": "array structure, not implemented",
    "FTA": "array structure, not implemented",
    "RTN": "array structure, not implemented",
}

# Resistance field. Ordered so the longest forms win: "10R2" and "R100" must not
# be read as a bare "100" / "10", and the plain 3-4 digit form comes last.
_RES = r"(\d{1,2}R\d{1,2}|R\d{2,3}|\d{3,4})"


def _pattern(prefix: str, spec: dict) -> object:
    """Build one series' pattern from the codes its own catalogue page prints."""
    sizes = "|".join(sorted(spec["sizes"], key=len, reverse=True))
    tols = "|".join(sorted(spec["tolerances"]))
    packs = "|".join(sorted(spec["packing"]))
    extra = "([%s])" % spec["extra_letters"] if spec["extra_letters"] else ""
    return compile(
        r"^%s(%s)%s([%s])%s(%s)$" % (prefix, sizes, _RES, tols, extra, packs), I
    )


# One pattern per series, so a part number is only accepted when every field
# belongs to the series it names.
_PATTERNS = {prefix: _pattern(prefix, spec) for prefix, spec in _SERIES.items()}

# Greedy to four letters is safe: every size code starts with a digit, so the
# prefix can never swallow the first digit of the size.
_RE_PREFIX = compile(r"^([A-Z]{2,4})", I)


def _format_ohm(value: float) -> str:
    if value <= 0:
        return "0R"
    if value >= 1_000_000:
        return f"{value / 1_000_000.0:.3f}".rstrip("0").rstrip(".") + "M"
    if value >= 1000:
        return f"{value / 1000.0:.3f}".rstrip("0").rstrip(".") + "K"
    if float(value).is_integer():
        return f"{int(value)}R"
    return f"{value:.3f}".rstrip("0").rstrip(".") + "R"


def _decode_resistance(code: str) -> str | None:
    """``R100`` -> ``0.1R``; ``1002`` -> ``10K``; ``000`` -> ``0R``."""
    raw = str(code or "").strip().upper()
    if raw.startswith("R") and raw[1:].isdigit():
        # Sub-ohm spelling: R stands for the decimal point, so R100 = 0.100 ohm
        # and R050 = 0.050 ohm. The catalogue also prints the shorter
        # R10 = 0.1 ohm on the RTT low-resistance page.
        digits = raw[1:]
        if not 2 <= len(digits) <= 3:
            return None
        return _format_ohm(int(digits) / (10 ** len(digits)))
    return decode_ohms_suffix(raw)


def parse(pn: str, component_type: str) -> str | None:
    if component_type != "RES":
        return None
    pn2 = "".join(str(pn).strip().upper().split())
    pm = _RE_PREFIX.match(pn2)
    if not pm:
        return None
    prefix = pm.group(1)
    if prefix in _REFUSED:
        return None
    pattern = _PATTERNS.get(prefix)
    if pattern is None:
        return None
    m = pattern.match(pn2)
    if not m:
        return None
    size_code, res_code, tol_ch = m.group(1), m.group(2), m.group(3)
    spec = _SERIES[prefix]
    size = spec["sizes"].get(size_code)
    if not size:
        return None
    resistance = _decode_resistance(res_code)
    if not resistance:
        return None
    tolerance = spec["tolerances"].get(tol_ch)
    if not tolerance:
        return None
    return "_".join(p for p in (size, resistance, tolerance) if p)
