"""
Walsin WW low-ohm / current-sense chip resistor PN parser.

Field order per the "CATALOGUE NUMBERS" section printed on the manufacturer
approval sheets (retrieved 2026-10-04; local copies under the gitignored
``datasheet/pdf/``), e.g. ``WW25N_V16``::

    WW25  N   R005  J  T  L
    size  type  ohm  tol pack term

- **Size code** - the sheets state it explicitly: ``WW10`` = 1210, ``WW20`` = 2010,
  ``WW25`` = 2512.
- **Type code** - ``N`` 2 W sensing, ``X`` thick film, ``R`` metal low-ohm power,
  ``A``/``B``/``W``/``P``/``D`` other documented families.
- **Resistance code** - "R is first digit followed by 3 significant digits":
  ``R010`` = 0.010 Ω, ``R005`` = 0.005 Ω, ``R100`` = 0.1 Ω, ``R976`` = 0.976 Ω.
- **Tolerance** - ``J`` ±5 %, ``F`` ±1 %.
- **Packaging / termination** - ``T`` 7" reeled taping, ``L`` Sn-base lead-free.
  Neither carries electrical meaning, but they are validated.

``12`` is deliberately **absent** from the size table. Two sheets disagree about
it: ``WW12R.PDF`` prints ``WW12: 0603`` while ``WW12R_V.PDF`` prints
``WW12: 1206``. Rather than pick one, a ``WW12…`` part returns ``None`` and falls
through, because guessing would silently attach the wrong imperial size to a
current-sense resistor.

Likewise the ``WW…C`` family (0201…1206, no separate type letter) is not decoded:
its sheets print no type code, so there is nothing to key on.

Type letters are limited to those a datasheet was obtained for. An unrecognised
letter returns ``None`` instead of being decoded on a guess.

Sizes: 06=0603, 08=0805, 10=1210, 20=2010, 25=2512.  (12 unresolved; see above.)
Resistance: ``Rxxx`` → xxx / 1000 Ω.

Examples:
- WW25NR005JT → 2512_0.005R_5%
- WW10XR100JT → 1210_0.1R_5%
- WW20PR100JT → 2010_0.1R_5%
- WW25BR005FT → 2512_0.005R_1%
"""

from __future__ import annotations

from parsers.regex_api import I, compile, match, sub

VENDOR_NAME = "Walsin_WW"
COMPONENT_TYPES = ["RES"]
PARSER_PRIORITY = 75

# Series number -> imperial size, from each sheet's own "Size code" line.
# ``12`` is intentionally missing: WW12R.PDF says 0603, WW12R_V.PDF says 1206.
_SIZE = {
    "06": "0603",
    "08": "0805",
    "10": "1210",
    "20": "2010",
    "25": "2512",
}
# Type codes a datasheet was obtained for.
_TYPE = ("N", "X", "R", "A", "B", "P", "D", "W")
_TOL = {"F": "1%", "J": "5%"}

# The tail after the tolerance is packing + termination and carries no
# electrical meaning. It is bounded but not spelled letter-by-letter: the
# catalogue prints ``WW25NR005JT`` (one packing letter) while the same numbers
# extract from the sheet body as ``WW25NR005JTLS``, and one carries a digit
# (``…PR100JTLJS``). Every electrical field is fixed-shape before it, and ``WW``
# is a distinctive prefix, so a bounded tail cannot attach the wrong size or
# value to a foreign part.
_RE = compile(
    r"^WW(06|08|10|20|25)(?:" + "[" + "".join(_TYPE) + r"])?"
    r"(R[0-9]{3})([FJ])[A-Z0-9]{1,4}$",
    I,
)


def _low_ohm(token: str) -> str | None:
    """``R005`` → ``0.005R``; the three digits after ``R`` are milli-ohms."""
    m = match(r"^R([0-9]{3})$", token.strip().upper())
    if not m:
        return None
    milli = int(m.group(1))
    if milli == 0:
        return "0R"
    return f"{milli / 1000.0:.3f}".rstrip("0").rstrip(".") + "R"


def parse(pn: str, component_type: str) -> str | None:
    if component_type != "RES":
        return None
    pn0 = sub(r"\s+", "", str(pn).strip()).upper()
    m = _RE.match(pn0)
    if not m:
        return None
    size_code, raw, tol_code = m.groups()
    size = _SIZE.get(size_code)
    ohm = _low_ohm(raw)
    tol = _TOL.get(tol_code.upper(), "")
    if not size or not ohm:
        return None
    return "_".join(p for p in (size, ohm, tol) if p)
