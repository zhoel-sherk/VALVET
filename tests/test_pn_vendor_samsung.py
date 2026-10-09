"""Samsung CL field tables, transcribed from the two catalogues in ``doc/info``.

* ``Samsung_MLCC_2512.pdf`` — *Part I. Commercial/Industrial*, December 2025
* ``MLCC_Automotive_2512.pdf`` — *Part II. Automotive*, December 2025

Both are needed because neither is a superset of the other. Every letter below
appears in at least one sheet, and where both print it they agree — so these
tables are a union, not a merge of conflicts.

The previous tables were a different thing: they mixed in letters that appear in
*neither* sheet (``G``=Y5U, ``R``=NP0, and the tolerance letters ``P``/``Q``/
``R``/``S``/``T``), which are mostly voltage codes that leaked into the wrong
map. So the failure was in both directions at once — the real voltage letters
were shuffled among the wrong values (``L``=16 V instead of 35 V, ``C``=630 V
instead of 100 V) *and* undocumented ones were accepted as if they were real.

The dangerous direction was the overstatement: ``C``=630 V reported a 100 V part
as 630 V, and ``K``=10 V turned a 3 kV part into a 10 V one.
"""

from __future__ import annotations

import pytest

from pn_original import samsung_capacitor as sc

# 6 RATED VOLTAGE CODE - Samsung_MLCC_2512.pdf p.7, Automotive p.5.
SAMSUNG_VOLTAGES = [
    ("S", "2.5V"),
    ("R", "4.0V"),
    ("Q", "6.3V"),
    ("P", "10V"),
    ("O", "16V"),
    ("A", "25V"),
    ("L", "35V"),
    ("B", "50V"),
    ("T", "75V"),
    ("C", "100V"),
    ("D", "200V"),
    ("E", "250V"),
    ("F", "350V"),
    ("G", "500V"),
    ("H", "630V"),
    ("I", "1kV"),
    ("X", "1250V"),
    ("V", "1500V"),
    ("J", "2kV"),
    ("K", "3kV"),
]

# 3 DIELECTRIC CODE - Samsung_MLCC_2512.pdf p.6, Automotive p.4.
SAMSUNG_DIELECTRICS = [
    ("C", "C0G"),
    ("G", "X8G"),
    ("A", "X5R"),
    ("X", "X6S"),
    ("W", "X6T"),
    ("B", "X7R"),
    ("K", "X7R(S)"),
    ("Y", "X7S"),
    ("Z", "X7T"),
    ("F", "Y5V"),
    ("D", "X8R"),
    ("E", "X8L"),
    ("M", "X8M"),
    ("J", "JIS-B"),
]

# 5 CAPACITANCE TOLERANCE CODE - Samsung_MLCC_2512.pdf p.7, Automotive p.4.
# Absolute class-1 grades render as a bare pF magnitude.
SAMSUNG_TOLERANCES = [
    ("N", "0.03pF"),
    ("A", "0.05pF"),
    ("B", "0.1pF"),
    ("C", "0.25pF"),
    ("H", "0.25pF"),
    ("L", "0.25pF"),
    ("D", "0.5pF"),
    ("V", "-5%"),
    ("G", "2%"),
    ("J", "5%"),
    ("K", "10%"),
    ("M", "20%"),
    ("U", "+5%"),
    ("Z", "+80%/-20%"),
]

# 2 SIZE CODE - Samsung_MLCC_2512.pdf p.6, Automotive p.4. Keyed to the repo's
# inch vocabulary. The last four are land-grid sizes with no entry there yet and
# register under the code the sheet prints.
SAMSUNG_SIZES = [
    ("R1", "0201"),
    ("02", "01005"),
    ("03", "0201"),
    ("05", "0402"),
    ("10", "0603"),
    ("21", "0805"),
    ("31", "1206"),
    ("32", "1210"),
    ("42", "1808"),
    ("43", "1812"),
    ("55", "2220"),
    ("L6", "0610"),
    ("01", "0816"),
    ("19", "1209"),
    ("L5", "0510"),
]


def _part(size: str, diel: str, cap: str, tol: str, volt: str) -> str:
    """Build a well-formed CL part: the tail fields are not decoded."""
    return f"CL{size}{diel}{cap}{tol}{volt}8NNNC"


@pytest.mark.parametrize("code,expected", SAMSUNG_VOLTAGES, ids=lambda p: p)
def test_samsung_rated_voltage_is_the_sheet_code(code: str, expected: str) -> None:
    """Every published voltage letter decodes to the value both sheets agree on.

    The regression this pins is a table, not a regex: the letters were all
    matched correctly and then looked up wrongly.
    """
    out = sc.parse(_part("05", "A", "105", "K", code), "CAP")
    assert out is not None, f"voltage letter {code!r} was refused"
    assert out == f"0402_1uF_{expected}_X5R_10%"


@pytest.mark.parametrize("code,expected", SAMSUNG_DIELECTRICS, ids=lambda p: p)
def test_samsung_dielectric_is_the_sheet_code(code: str, expected: str) -> None:
    out = sc.parse(_part("05", code, "105", "K", "A"), "CAP")
    assert out is not None, f"dielectric {code!r} was refused"
    assert out == f"0402_1uF_25V_{expected}_10%"


@pytest.mark.parametrize("code,expected", SAMSUNG_TOLERANCES, ids=lambda p: p)
def test_samsung_tolerance_is_the_sheet_code(code: str, expected: str) -> None:
    out = sc.parse(_part("05", "A", "105", code, "A"), "CAP")
    assert out is not None, f"tolerance {code!r} was refused"
    assert out == f"0402_1uF_25V_X5R_{expected}"


@pytest.mark.parametrize("code,expected", SAMSUNG_SIZES, ids=lambda p: p)
def test_samsung_size_is_the_sheet_code(code: str, expected: str) -> None:
    out = sc.parse(_part(code, "A", "105", "K", "A"), "CAP")
    assert out is not None, f"size {code!r} was refused"
    assert out == f"{expected}_1uF_25V_X5R_10%"


@pytest.mark.parametrize(
    ("cap", "expected"),
    [("101", "1%"), ("100", "1%"), ("1R0", "1pF"), ("0R5", "1pF")],
    ids=lambda p: p,
)
def test_samsung_f_tolerance_follows_the_footnote(cap: str, expected: str) -> None:
    """``F`` is +-1 pF below 10 pF and +-1 % at or above (sheet footnote).

    The threshold is on the *value*, so ``100`` (10 pF) is already the
    percentage form and ``1R0`` (1 pF) is not.
    """
    out = sc.parse(_part("05", "C", cap, "F", "A"), "CAP")
    assert out is not None
    assert out.endswith(f"_{expected}")


@pytest.mark.parametrize(
    ("cap", "expected"),
    [("1R5", "1.5pF"), ("0R5", "0.5pF"), ("2R2", "2.2pF")],
    ids=lambda p: p,
)
def test_samsung_r_decimal_capacitance_decodes(cap: str, expected: str) -> None:
    """``For values <10 pF, letter R denotes the decimal point`` (p.6).

    ``pf_eia_3_to_str`` only knows the 3-digit form, so a decimal code used to
    return ``None`` and cost the part its capacitance.
    """
    out = sc.parse(_part("05", "C", cap, "J", "A"), "CAP")
    assert out is not None
    assert out == f"0402_{expected}_25V_C0G_5%"


def test_samsung_c0g_normalises_like_every_other_codec() -> None:
    """``C`` is the sheet's C0G symbol; it must clean as ``C0G``.

    It used to emit the raw spelling ``COG``, which no other codec here does
    and which no cross-vendor match could see.
    """
    assert sc.parse(_part("10", "C", "101", "J", "B"), "CAP") == (
        "0603_100pF_50V_C0G_5%"
    )


@pytest.mark.parametrize(
    "pn",
    [
        "CL10A105MZ8NNNC",  # undocumented voltage letter Z
        "CL10Q105MK8NNNC",  # undocumented dielectric letter Q at index 4
        "CL99A105MK8NNNC",  # undocumented size 99
        "CL10A105K8NNNC",  # no voltage letter: layout collapsed
    ],
    ids=lambda p: p,
)
def test_samsung_refuses_a_part_it_cannot_read_completely(pn: str) -> None:
    """An unknown code means the layout was misread, so return nothing.

    Emitting the surviving fields would report the part as confidently wrong
    rather than as unread, which is how the old table turned a 100 V part into
    a 630 V one without complaint.
    """
    assert sc.parse(pn, "CAP") is None


def test_samsung_thickness_is_not_a_tolerance() -> None:
    """Index 10 is a thickness in mm, never a tolerance.

    ``CL21A226MAYNNNE`` has thickness ``Y`` at index 10; reading the tolerance
    from there lost it entirely.
    """
    assert sc.parse("CL21A226MAYNNNE", "CAP") == "0805_22uF_25V_X5R_20%"


def test_samsung_non_cap_is_not_claimed() -> None:
    assert sc.parse("CL05A105KA5NQNC", "RES") is None


@pytest.mark.parametrize(
    "pn",
    [
        "XX10A106MQ8NNNC",  # right shape, wrong series
        "XK10A106MQ8NNNC",
        "C110A106MQ8NNNC",  # plausible-looking series prefix
        "CLA0A106MQ8NNNC",
    ],
    ids=lambda p: p,
)
def test_samsung_requires_the_cl_series_prefix(pn: str) -> None:
    """The series prefix must be ``CL`` and nothing else.

    Every other field here is valid, so a part that dropped the ``startswith``
    check would decode cleanly as ``0603_10uF_6.3V_X5R_20%`` and no other test
    would notice. A CL-shaped string from another vendor is exactly the case
    the arbiter needs the prefix to reject.
    """
    assert sc.parse(pn, "CAP") is None


def test_samsung_part_numbers_are_case_insensitive() -> None:
    """Case is normalised, not validated - the prefix check runs on the upper form.

    Pinning this next to the prefix test above, because the obvious way to
    "fix" a case-insensitive part is to drop the ``.upper()`` and then start
    rejecting lowercase MPNs that production BOMs do contain.
    """
    assert sc.parse("cl10a106mq8nnnc", "CAP") == sc.parse("CL10A106MQ8NNNC", "CAP")
    assert sc.parse("Cl10A106Mq8NnNc", "CAP") == "0603_10uF_6.3V_X5R_20%"
