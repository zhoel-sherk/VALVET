"""
Fenghua (风华) MLCC PN parser — ``CG``/``COG`` class-1 and ``B``/``X`` class-2 lines.

Ordering per the Fenghua MLCC data sheets (X7R and NPO/COG editions, retrieved
2026-10-04; local copies under the gitignored ``datasheet/pdf/``)::

    A size(4)  B dielectric  C capacitance  D tolerance
    E rated voltage  F termination  G packaging

    0402 | CG | 102   | J    | 500 | N | T

Fields, and what the previous version got wrong:

- **Dielectric** is a code, not a fixed guess: ``CG``/``COG`` are the class-1
  NPO line, ``B`` is X7R and ``X`` is X5R. The old pattern hard-wired ``B`` to
  X7R and had no ``X`` branch at all, so every X5R part returned ``None`` and
  lost size, capacitance, tolerance and voltage with it.
- **Capacitance** is three EIA digits, or an ``R``-decimal for the sub-10 pF
  values (``0R5`` = 0.5 pF, ``1R0`` = 1 pF), which a bare three-digit field
  cannot match. Note the ``R``-decimal applies to the **capacitance** in this
  datasheet; the rated-voltage field is always a three-digit EIA code.
- **Tolerance** per the NPO sheet: ``B`` +/-0.10 pF, ``C`` +/-0.25 pF,
  ``D`` +/-0.5 pF (absolute, class 1), ``F`` 1%, ``G`` 2%, ``J`` 5%, ``K`` 10%,
  ``M`` 20%, and ``S`` +50%/-20% (X7R sheet). The absolute codes and ``S`` were
  missing, and since the pattern *required* a tolerance letter, each of them made
  the whole part unparseable rather than merely dropping a field.
- **Rated voltage** is the EIA mantissa-exponent code, *not* the V/10 form the
  other China-vendor catalogues use: ``160``=16 V, ``250``=25 V, ``500``=50 V,
  ``630``=63 V, ``101``=100 V, ``201``=200 V, ``501``=500 V, ``102``=1 kV,
  ``202``=2 kV. The shared ``china_mlcc_vol_from_digits`` divides by ten, so it
  reported "101V" for a 100 V part and "202V" for a 2 kV part. This module uses
  :func:`eia_vol_code_to_v`, the same helper Walsin needs. The two conventions
  agree only on codes ending in 0, which is why the wrong one still looked
  plausible on the common 16/25/50/63 V parts.
- **Termination + packaging** are one letter each and are accepted as any pair,
  so a termination change does not lose an otherwise-decodable part.

Examples:
- 0402CG101J500NT → 0402_100pF_C0G_5%_50V
- 0402B223K250NT → 0402_22nF_X7R_10%_25V
- 0402X104M101NT → 0402_100nF_X5R_20%_100V
- 0805COG102J630SB → 0805_1nF_C0G_5%_63V
- 0402CG1R0B160SB → 0402_1pF_C0G_5%_16V
"""

from __future__ import annotations

from parsers.regex_api import I, compile

from ._cap_decode import eia_vol_code_to_v, pf_eia_3_to_str

VENDOR_NAME = "Fenghua"
COMPONENT_TYPES = ["CAP"]
PARSER_PRIORITY = 86

# Percentage codes plus the class-1 absolute-pF codes. ``L``/``N`` are not in
# this datasheet's table and are deliberately absent rather than assumed.
#
# The absolute codes render as a bare ``0.25pF`` magnitude, matching the cleaned
# string the pipeline produced before this parser gained them. Writing them as
# ``+/-0.25pF`` changes the token, and the class-1 downstream normaliser then
# fails to recognise the part at all - it drops both the capacitance and the
# tolerance and reorders the rest, so ``parse_pn`` and ``clean_one`` disagree.
_TOL = {
    "B": "0.1pF",
    "C": "0.25pF",
    "D": "0.5pF",
    "F": "1%",
    "G": "2%",
    "J": "5%",
    "K": "10%",
    "M": "20%",
    "S": "+50%/-20%",
}

# A size, B dielectric, C capacitance (EIA or R-decimal), D tolerance,
# E rated voltage, F termination + G packaging.
#
# The termination and packaging letters are enumerated from the datasheet rather
# than left as ``[A-Z]{1,2}``: Walsin reuses the same ``B``/``X``/``CG`` bodies
# with a ``CT`` tape suffix, and a permissive tail made this codec claim parts
# that belong to Walsin (which carries the higher priority and emits its own
# token order). Datasheet F/G: termination S=silver or N=Ni-barrier/tin,
# packaging T=tape&reel or B=bulk, so the pairs are ST, NT, SB, NB.
_RE = compile(
    r"^(\d{4})(COG|CG|B|X)(\d{3}|\dR\d)([BCDFGJKMS])(\d{3})(?:ST|NT|SB|NB)$",
    I,
)

# Dielectric code → normalised name.
_FILM = {"COG": "C0G", "CG": "C0G", "B": "X7R", "X": "X5R"}


def _parse_line(m) -> str | None:
    size, diel, cap_raw, tch, vraw = m.groups()
    raw = cap_raw.upper()
    if "R" in raw:
        # R-decimal: every digit is significant, unit is pF (0R5 -> 0.5 pF).
        whole, _, frac = raw.partition("R")
        value = float(f"{whole}.{frac or '0'}")
        cap = f"{int(value)}pF" if value.is_integer() else f"{value}pF"
    else:
        cap = pf_eia_3_to_str(raw)
    if not cap:
        return None
    tol = _TOL.get(tch.upper(), "")
    vol = eia_vol_code_to_v(vraw)
    parts = [size, cap, _FILM.get(diel.upper(), diel.upper())]
    if tol:
        parts.append(tol)
    if vol:
        parts.append(vol)
    return "_".join(p for p in parts)


def parse(pn: str, component_type: str) -> str | None:
    if component_type != "CAP":
        return None
    pn2 = "".join(str(pn).strip().upper().split())
    m = _RE.match(pn2)
    if not m:
        return None
    return _parse_line(m)
