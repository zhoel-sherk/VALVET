"""
TCC MLCC PN parser — ``TCC + size + dielectric + EIA value + tolerance + voltage + tail``.

.. warning::

   **UNVERIFIED — no manufacturer part-number catalogue has been obtained.**

   Everything below is derived from nine production rows of the CO1271 SKU3 BOM
   whose description column is the ground truth, not from a CCTC publication. The
   only CCTC file retrieved (2026-10-04) was a "Specification for Approval"
   template from Chaozhou Three-Circle (Group) Co., Ltd whose tables are images;
   it has no part-number section. A web search surfaced only the vendor product
   selector and a third-party article, neither of which is a catalogue.

   Treat the field layout below as a hypothesis that happens to fit nine observed
   parts. In particular the rated-voltage rule — a 3-digit block divided by ten —
   is unconfirmed: a real catalogue could turn out to use an EIA
   mantissa-exponent form, in which case codes not ending in 0 would be wrong,
   exactly as they were for Fenghua before that was checked. Do not widen this
   codec further without a catalogue; when one appears, verify the voltage
   convention first.

Part Number Format:
``TCC`` | size (4) | dielectric (3) | capacitance (3) | tolerance (1) | voltage (3 or dRd) | tail

Examples (all nine distinct MPNs are production rows of CO1271 SKU3; the BOM
description column is the ground truth these decode to):
- TCC0402X5R104K250AT  → 0402_100nF_X5R_10%_25V   (MLCC_0.1uF_X5R_25V_+/-10%_C0402…)
- TCC0402C0G820J500AT  → 0402_82pF_C0G_5%_50V     (MLCC_82pF_C0G_50V_+/-5%_C0402…)
- TCC0402X5R106M6R3ATR → 0402_10uF_X5R_20%_6.3V   (MLCC_10uF_X5R_6.3V_+/-20%_0402…)

Size codes: 0201, 0402, 0603, 0805, 1206, 1210 (4 digits after ``TCC``)

Dielectric: X5R, X7R, X6S, X7S, Y5V, Y5U plus the class-I spellings ``C0G`` and
``COG`` (TCC0402COG331J500AT spells it with a letter O) — both normalize to C0G,
as do NP0/NPO.

Tolerance: F=±1%, G=±2%, J=±5%, K=±10%, M=±20%

Voltage: 3-digit block ÷10 (160→16V, 250→25V, 500→50V) or the decimal form
``dRd`` (6R3→6.3V), decoded by ``china_mlcc_vol_token``.

Tail: packaging/reel letters (``AT``, ``ATR``) — ignored.

PARSER_PRIORITY 100 (the tier Yageo/Murata use): the pattern is anchored on the
literal ``TCC`` prefix, which no other converter module claims, so it can neither
be shadowed by a sibling capacitor parser nor shadow one.

Note:
``parse()`` does not swallow exceptions — "not my format" is an explicit
``return None``; a raise is a genuine bug and must reach the ``parse_pn``
arbiter, which logs it with a traceback and names the vendor.
"""

from __future__ import annotations

from parsers.regex_api import I, compile

from ._cap_decode import pf_eia_3_to_str
from ._mlcc_china_vol import china_mlcc_vol_token

VENDOR_NAME = "TCC"
COMPONENT_TYPES = ["CAP"]
PARSER_PRIORITY = 100

_TOL = {"F": "1%", "G": "2%", "J": "5%", "K": "10%", "M": "20%"}
_DIELECTRICS = ("C0G", "COG", "NP0", "NPO")
_RE = compile(
    r"^TCC(\d{4})(Y5V|Y5U|X7S|X6S|X7R|X5R|C0G|COG|NP0|NPO)"
    r"(\d{3})([FGJKM])((?:\d{3})|(?:\dR\d))([A-Z]*)$",
    I,
)


def parse(pn: str, component_type: str) -> str | None:
    if component_type != "CAP":
        return None
    pn2 = "".join(str(pn).strip().upper().split())
    m = _RE.match(pn2)
    if not m:
        return None
    size, film_raw, c3, tch, vtok, _tail = m.groups()
    cap = pf_eia_3_to_str(c3)
    if not cap:
        return None
    film = "C0G" if film_raw in _DIELECTRICS else film_raw
    tol = _TOL.get(str(tch).upper(), "")
    vol = china_mlcc_vol_token(vtok)
    parts = [size, cap, film]
    if tol:
        parts.append(tol)
    if vol:
        parts.append(vol)
    return "_".join(parts)
