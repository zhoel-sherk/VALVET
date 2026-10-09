"""Samsung Capacitor PN Parser

Samsung MLCC part-number format, from the two catalogues in ``doc/info``:

* ``Samsung_MLCC_2512.pdf`` — *Part I. Commercial/Industrial*, December 2025.
* ``MLCC_Automotive_2512.pdf`` — *Part II. Automotive*, December 2025.

Both print the same layout (``Samsung_MLCC_2512.pdf`` p.6)::

    CL 10 A 106 M Q 8 N N N C
    1 2 3 4 5 6 7 8 9 10 11

    1 CL      series               7 thickness
    2 10      size                 8 design
    3 A       dielectric           9 product / size control
    4 106     capacitance          10 control
    5 M       capacitance tol.     11 packaging
    6 Q       rated voltage

So the tolerance letter is at index 8 and the rated-voltage letter at index 9.
Fields 7-11 are not part of the cleaned value, and index 10 in particular is a
thickness in mm — never a tolerance, which is what the old index-8/index-9 swap
got wrong.

Field positions are fixed by the format, but the *code tables* differ between
the two catalogues, so each is transcribed from both and unioned below. The
union is unambiguous: where both print a letter they agree on its value, and
each contributes codes the other omits.

* Commercial/Industrial p.7 prints 17 voltages and adds ``F``=350 V and ``K``=3 kV.
* Automotive p.5 prints 18 and adds ``T``=75 V, ``X``=1250 V and ``V``=1500 V.

The dielectric table splits the same way: Commercial/Industrial p.6 adds
``W``=X6T, ``K``=X7R(S), ``F``=Y5V and ``J``=JIS-B, Automotive p.4 adds
``D``=X8R. The tolerance table is a superset relationship — Automotive p.4
prints only ``B``/``C``/``D``/``J``/``K``/``M`` and refers ``A``/``F``/``G`` to a
footnote, all of which Commercial/Industrial p.7 already lists.

The size table is Commercial/Industrial p.6 (Automotive p.4 lists a 9-code
subset). Samsung's own size names are not the repo's: ``R1`` is 008004 and
``02`` is 01005, neither of which is the body anyone else calls by those digits,
so the map below is keyed to the name the repo already uses elsewhere.

Examples:
- CL05A105MQ5NNNC → 0402_1uF_6.3V_X5R_20%
- CL21B225KOFNNNE → 0805_2.2uF_16V_X7R_10%
- CL31A106KAHNNNE → 1206_10uF_25V_X5R_10%

Note:
``parse()`` does not swallow exceptions. "Not my format" is reported by an explicit
``return None``; a raise means a genuine parser bug and is meant to reach the
``pn_original.parse_pn`` arbiter, which logs it with a traceback and names the vendor.
"""

from parsers.regex_api import match, sub

from ._cap_decode import pf_eia_3_to_str

VENDOR_NAME = "Samsung"
COMPONENT_TYPES = ["CAP"]
PARSER_PRIORITY = 95

# 2 SIZE CODE - Samsung_MLCC_2512.pdf p.6, Automotive p.4. Keyed to the repo's
# vocabulary, which is the inch name. The four land-grid sizes have no entry
# there yet, so they register under the code the sheet prints; tracked in
# doc/TODO.md.
_SIZE = {
    "R1": "0201",  # 008004/0201
    "02": "01005",  # 01005/0402
    "03": "0201",  # 0201/0603
    "05": "0402",  # 0402/1005
    "10": "0603",  # 0603/1608
    "21": "0805",  # 0805/2012
    "31": "1206",  # 1206/3216
    "32": "1210",  # 1210/3225
    "42": "1808",  # 1808/4520
    "43": "1812",  # 1812/4532
    "55": "2220",  # 2220/5750
    "L6": "0610",  # 0304/0610
    "01": "0816",  # 0306/0816
    "19": "1209",  # 0503/1209
    "L5": "0510",  # 0204/0510
}

# 3 DIELECTRIC CODE - Samsung_MLCC_2512.pdf p.6 + Automotive p.4, unioned.
# ``C`` is the sheet's symbol for C0G and is normalised like every other codec
# here does, so a Samsung C0G part cleans the same as a Murata one.
_DIEL = {
    "C": "C0G",
    "G": "X8G",
    "A": "X5R",
    "X": "X6S",
    "W": "X6T",
    "B": "X7R",
    "K": "X7R(S)",
    "Y": "X7S",
    "Z": "X7T",
    "F": "Y5V",
    "D": "X8R",
    "E": "X8L",
    "M": "X8M",
    "J": "JIS-B",
}

# 6 RATED VOLTAGE CODE - Samsung_MLCC_2512.pdf p.7 + Automotive p.5, unioned.
# 3kV/2kV/1kV are spelled the way the sheet spells them.
_VOLT = {
    "S": "2.5V",
    "R": "4.0V",
    "Q": "6.3V",
    "P": "10V",
    "O": "16V",
    "A": "25V",
    "L": "35V",
    "B": "50V",
    "T": "75V",
    "C": "100V",
    "D": "200V",
    "E": "250V",
    "F": "350V",
    "G": "500V",
    "H": "630V",
    "I": "1kV",
    "V": "1500V",
    "J": "2kV",
    "X": "1250V",
    "K": "3kV",
}

# 5 CAPACITANCE TOLERANCE CODE - Samsung_MLCC_2512.pdf p.7, Automotive p.4.
# The absolute grades are class 1 (pF, not a percentage) and render as a bare
# magnitude, matching walsin/viiyong/eyang for the same two tolerance classes.
# ``F`` is not here: the sheet's footnote makes it mean +-1 pF below 10 pF and
# +-1 % at or above, so it depends on the value and is resolved in _tolerance().
_TOL_ABS = {
    "N": "0.03pF",
    "A": "0.05pF",
    "B": "0.1pF",
    "C": "0.25pF",
    "H": "0.25pF",
    "L": "0.25pF",
    "D": "0.5pF",
}
_TOL_PCT = {
    "G": "2%",
    "J": "5%",
    "K": "10%",
    "M": "20%",
}
_TOL_ASYM = {
    "V": "-5%",
    "U": "+5%",
    "Z": "+80%/-20%",
}


def _capacitance(code: str) -> tuple[float | None, str]:
    """EIA 3-digit or ``dRd`` pF code -> (value in pF, cleaned string).

    ``1R5`` is 1.5 pF (Samsung_MLCC_2512.pdf p.6, "For values <10 pF, letter R
    denotes the decimal point"). ``pf_eia_3_to_str`` only knows the 3-digit
    form, so the decimal one used to drop the capacitance from the whole part.
    """
    raw = str(code or "").strip().upper()
    mr = match(r"^(\d)R(\d)$", raw)
    if mr:
        pf = float(f"{mr.group(1)}.{mr.group(2)}")
        return pf, f"{int(pf)}pF" if pf.is_integer() else f"{pf}pF"
    text = pf_eia_3_to_str(raw)
    if not text:
        return None, ""
    return float(raw[:2]) * (10 ** int(raw[2])), text


def _tolerance(letter: str, pf: float | None) -> str:
    """Capacitance tolerance at index 8, resolving the ``F`` footnote."""
    key = str(letter or "").strip().upper()
    if key in _TOL_ABS:
        return _TOL_ABS[key]
    if key in _TOL_PCT:
        return _TOL_PCT[key]
    if key in _TOL_ASYM:
        return _TOL_ASYM[key]
    if key == "F":
        # * For values <10pF, F=+-1pF / values >=10pF, F=+-1%.
        if pf is not None and pf < 10:
            return "1pF"
        return "1%"
    return ""


def parse(pn: str, component_type: str) -> str | None:
    """Parse a Samsung CL capacitor part number.

    ``CL`` + size(2) + dielectric(1) + capacitance(3) + tolerance(1) + voltage(1)
    + thickness(1) + design/product/control/packaging(4).

    Every field the cleaned string carries must be a code one of the two sheets
    publishes: a letter outside those tables means the layout was misread, and
    returning the surviving half would report a part as confidently wrong rather
    than as unread. Fields 7-11 are not decoded, so they are not constrained.
    """
    if component_type != "CAP":
        return None

    pn = sub(r"\s*<[gG]>\s*$", "", str(pn).strip())
    pn = sub(r"\s+", "", pn).strip().upper()

    if len(pn) < 10 or not pn.startswith("CL"):
        return None

    size = _SIZE.get(pn[2:4], "")
    if not size:
        return None
    diel = _DIEL.get(pn[4], "")
    if not diel:
        return None
    pf, cap = _capacitance(pn[5:8])
    if not cap:
        return None
    tol = _tolerance(pn[8], pf)
    if not tol:
        return None
    volt = _VOLT.get(pn[9], "")
    if not volt:
        return None

    # Thickness at index 10 is a millimetre code, not a tolerance; design,
    # product, control and packaging follow it and are not cleaned.
    return f"{size}_{cap}_{volt}_{diel}_{tol}"


def format_example(pn: str) -> str:
    """Format example of conversion"""
    result = parse(pn, "CAP")
    return f"{pn} → CAP_{result}" if result else f"{pn} → (not recognized)"
