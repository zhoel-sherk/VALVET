"""
Eyang (宇阳) MLCC PN parser.

Part number: ``C`` + size + temperature characteristic + 3-digit capacitance
+ tolerance + rated voltage + termination + packaging, i.e. sections 1-8 of the
datasheet's "Part Number System".

Source: Eyang "Multilayer Ceramic Chip Capacitors for General Purpose"
(retrieved 2026-10-04, local copy under the gitignored ``datasheet/pdf/``).

Datasheet scope, which is what the tables below mirror:
- 1.1 temperature characteristics: class 1 ``C0G``; class 2 ``X7R X7T X7S X6S
  X6T X5R``. ``X7T``/``X7S``/``X6T`` were missing here, so those parts returned
  ``None`` and lost size, capacitance, dielectric and voltage.
- 1.2 size codes ``A8A4``(008004) ``0105`` ``0201`` ``0402`` ``0603`` ``0805``
  ``1206`` ``1210``.
- 1.4 rated voltage DC 2.5 V to 63 V; section 6 codes ``100``=10V ``160``=16V
  ``250``=25V ``350``=35V ``500``=50V ``630``=63V ``4R0``=4.0V ``2R5``=2.5V
  ``6R3``=6.3V - a plain V/10 scaling for the digit forms, not an EIA exponent.
- section 5 tolerance: ``F``+/-1% ``G``+/-2% ``J``+/-5% ``K``+/-10% ``L``+/-15%
  ``M``+/-20% ``N``+/-30%, plus the absolute-pF codes ``A``/``B``/``C``/``D``/
  ``P`` and the asymmetric ``S``/``X``/``Y``/``Z``. ``L`` and ``N`` were missing,
  and because the pattern requires a tolerance letter they made the whole part
  unparseable rather than merely dropping a field.

Examples:
- C0402C0G180J500NTB → 0402_18pF_C0G_5%_50V
- C0402X7R221K500NTB → 0402_220pF_X7R_10%_50V
- C0201X5R334M6R3NTJ → 0201_0.33uF_X5R_20%_6.3V
- C0402X7T120L250NTB → 0402_12pF_X7T_15%_25V
"""

from __future__ import annotations

from parsers.regex_api import I, compile

from ._cap_decode import pf_eia_3_to_str
from ._mlcc_china_vol import china_mlcc_vol_token

VENDOR_NAME = "Eyang"
COMPONENT_TYPES = ["CAP"]
PARSER_PRIORITY = 88

# Datasheet 1.1: class 1 C0G; class 2 X7R X7T X7S X6S X6T X5R.
# COG/NP0/NPO are accepted as the usual alternate spellings of C0G, X8R is kept
# because it appears in sibling China-vendor catalogues.
_DIELECTRICS = "C0G|COG|X7R|X8R|X7T|X7S|X6S|X6T|X5R|NP0|NPO"
# Datasheet section 5. The absolute-pF and asymmetric codes are deliberately not
# here: they cannot be rendered as a percentage, and guessing one would be worse
# than omitting the field.
_TOL = {"F": "1%", "G": "2%", "J": "5%", "K": "10%", "L": "15%", "M": "20%", "N": "30%"}
_RE = compile(
    r"^C(\d{4})(" + _DIELECTRICS + r")"
    r"(\d{3})([FGJKLMN])"
    r"((?:\d{3})|(?:\dR\d))([A-Z]*)$",
    I,
)


def parse(pn: str, component_type: str) -> str | None:
    if component_type != "CAP":
        return None
    pn2 = "".join(str(pn).strip().upper().split())
    if not pn2.startswith("C") or len(pn2) < 14:
        return None
    m = _RE.match(pn2)
    if not m:
        return None
    size, film_raw, c3, tch, vtok, _tail = m.groups()
    cap = pf_eia_3_to_str(c3)
    if not cap:
        return None
    film = (
        "C0G" if film_raw.upper() in ("C0G", "COG", "NP0", "NPO") else film_raw.upper()
    )
    tol = _TOL.get(tch.upper(), "")
    vol = china_mlcc_vol_token(vtok)
    parts = [size, cap, film]
    if tol:
        parts.append(tol)
    if vol:
        parts.append(vol)
    return "_".join(parts)
