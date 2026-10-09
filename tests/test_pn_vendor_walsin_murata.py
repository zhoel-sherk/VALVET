"""Walsin ``NT`` packaging suffix and Murata ``R6Y`` series (PLAN 5.8).

Both families used to fall through the vendor phase and were returned unchanged
by the regex phase (a silent no-op). Expected values below follow the token
order each parser already emits (size_value[_dielectric][_voltage][_tolerance]).
"""

from __future__ import annotations

import pn_original
from pn_original import murata_capacitor, walsin_mlcc_capacitor, walsin_ww_resistor


def _parse(pn: str, ctype: str) -> str | None:
    pn_original.CONVERTERS.clear()
    pn_original.load_converters()
    return pn_original.parse_pn(pn, ctype, None)


# --- Walsin: packaging / termination suffixes ------------------------------


def test_walsin_nt_parts_are_not_walsin_parts() -> None:
    """``NT`` is not a Walsin ending, so Walsin must not claim the part.

    Walsin's catalog gives termination ``L``/``C`` with packaging ``T``/``Q``/
    ``G`` and an optional thickness symbol. ``…NT`` is Fenghua's ending, and the
    two vendors share the ``B``/``X``/``CG`` bodies, so such a part is Fenghua's
    to decode. The electrical values agree either way; what matters is that
    exactly one codec owns it.
    """
    assert walsin_mlcc_capacitor.parse("0201X104K500NT", "CAP") is None
    assert _parse("0201X104K500NT", "CAP") == "0201_100nF_X5R_10%_50V"


def test_walsin_nt_suffix_xkv_line() -> None:
    """X-line ``NT`` parts decode via Fenghua, which owns that ending."""
    assert _parse("0402X224K160NT", "CAP") == "0402_220nF_X5R_10%_16V"
    assert _parse("0603X226M100NT", "CAP") == "0603_22uF_X5R_20%_10V"


def test_fenghua_owns_the_drd_voltage_spelling_on_nt_parts() -> None:
    """The Walsin ``NT`` hand-off left the ``dRd`` voltage spelling unowned.

    Walsin's MLCC catalogue gives termination ``L``/``C``/``P`` (plus ``P`` for
    the Cu/polymer lines), so its codec correctly refuses ``NT``; the ``NT``
    ending belongs to Fenghua, whose sheet lists termination ``S``/``N``. But
    Fenghua accepted only the 3-digit EIA voltage form, so an ``X``-line part
    written with the decimal spelling had no owner at all:

        0201X104K6R3NT -> None   (CO1271 production row)

    The row fell through to the regex phase and lost size, capacitance,
    dielectric, tolerance and voltage. Both spellings are now accepted, the EIA
    form unchanged.
    """
    assert _parse("0201X104K6R3NT", "CAP") == "0201_100nF_X5R_10%_6.3V"
    assert _parse("0805X475M6R3NT", "CAP") == "0805_4.7uF_X5R_20%_6.3V"
    # The EIA form is unaffected.
    assert _parse("0805X475M6R3CT", "CAP") == "0805_4.7uF_X5R_6.3V_20%"


def test_walsin_cq_and_cg_reel_codes_decode() -> None:
    """The documented 10" and 13" reels must behave like the 7" reel."""
    assert _parse("0805X475M6R3CQ", "CAP") == _parse("0805X475M6R3CT", "CAP")
    assert _parse("0805X475M6R3CG", "CAP") == _parse("0805X475M6R3CT", "CAP")


def test_walsin_ct_forms_are_unchanged() -> None:
    """Regression: the already-working CT parts keep their exact output."""
    assert _parse("0402B101K500CT", "CAP") == "0402_100pF_X7R_50V_10%"
    assert _parse("0805X475M6R3CT", "CAP") == "0805_4.7uF_X5R_6.3V_20%"
    assert _parse("1206X106K250CT", "CAP") == "1206_10uF_X5R_25V_10%"
    assert _parse("0402B102K500CT", "CAP") == "0402_1nF_X7R_50V_10%"


def test_walsin_n_line_carries_the_np0_dielectric() -> None:
    """Catalog: dielectric ``N`` = NP0, so the cleaned string names C0G."""
    assert _parse("0402N100J500CT", "CAP") == "0402_10pF_C0G_50V_5%"


def test_walsin_every_catalog_dielectric_decodes() -> None:
    """All eight letters from the catalog's dielectric table must be reachable.

    Five of them (``G`` X8G, ``R`` X8R, ``A`` X7S, ``S`` X6S, ``F`` Y5V) were
    absent from the codec, so those parts returned ``None`` outright.
    """
    expected = {
        "N": "C0G",
        "G": "X8G",
        "R": "X8R",
        "B": "X7R",
        "A": "X7S",
        "S": "X6S",
        "X": "X5R",
        "F": "Y5V",
    }
    for letter, film in expected.items():
        got = _parse(f"0805{letter}104K500CT", "CAP")
        assert got is not None, f"{letter} ({film}) did not parse"
        assert f"_{film}_" in got, got


def test_walsin_absolute_and_asymmetric_tolerances() -> None:
    """Catalog section 5: A/B/C/D are absolute pF, Z is asymmetric.

    These were missing from the table, so a part could decode "successfully"
    while silently losing its tolerance.
    """
    assert _parse("0805B104A500CT", "CAP") == "0805_100nF_X7R_50V_0.05pF"
    assert _parse("0805B104B500CT", "CAP") == "0805_100nF_X7R_50V_0.1pF"
    assert _parse("0805B104C500CT", "CAP") == "0805_100nF_X7R_50V_0.25pF"
    assert _parse("0805B104D500CT", "CAP") == "0805_100nF_X7R_50V_0.5pF"
    assert _parse("0805B104Z500CT", "CAP") == "0805_100nF_X7R_50V_-20%/+80%"


def test_walsin_high_voltage_codes_are_eia_not_v_over_ten() -> None:
    """Catalog: 101=100V, 631=630V, 202=2kV — mantissa-exponent, not /10."""
    assert _parse("0805B104K101CT", "CAP") == "0805_100nF_X7R_100V_10%"
    assert _parse("0805B104K631CT", "CAP") == "0805_100nF_X7R_630V_10%"
    assert _parse("1206B471K202CT", "CAP") == "1206_470pF_X7R_2000V_10%"


def test_walsin_rejects_non_catalog_packaging_suffix() -> None:
    """Termination is ``L``/``C`` and packaging ``T``/``Q``/``G``; nothing else.

    A permissive ``[A-Z]{2}`` tail had started accepting ``…6R3PT``.
    """
    for tail in ("PT", "NT", "XX"):
        # Walsin must not claim it. ``NT`` still resolves through the arbiter,
        # because Fenghua owns that ending - see the sibling test.
        assert walsin_mlcc_capacitor.parse(f"0201X104K500{tail}", "CAP") is None, tail
    for tail in ("CT", "CQ", "CG", "LT", "LQ", "LG", "CTG"):
        got = _parse(f"0201X104K500{tail}", "CAP")
        assert got == "0201_100nF_X5R_50V_10%", tail


def test_walsin_real_catalog_part_numbers() -> None:
    """Part numbers printed in the catalog's own tables must all decode.

    Includes the ``0612`` low-inductance size and the ``Z`` asymmetric tolerance,
    both of which the previous pattern could not reach.
    """
    assert _parse("0805B104K500CT", "CAP") == "0805_100nF_X7R_50V_10%"
    assert _parse("0805B104K500CTG", "CAP") == "0805_100nF_X7R_50V_10%"
    assert _parse("1206F104Z500CT", "CAP") == "1206_100nF_Y5V_50V_-20%/+80%"
    assert _parse("1808N100J202CT", "CAP") == "1808_10pF_C0G_2000V_5%"
    assert _parse("0612B103K500CT", "CAP") == "0612_10nF_X7R_50V_10%"


def test_walsin_rejects_unknown_packaging_suffix() -> None:
    assert walsin_mlcc_capacitor.parse("0201X104K6R3PT", "CAP") is None
    assert walsin_mlcc_capacitor.parse("0402X104K6R3T", "CAP") is None
    assert walsin_mlcc_capacitor.parse("9999X104K6R3NT", "CAP") is None
    assert _parse("0201X104K6R3PT", "CAP") is None


# --- Murata: R6Y letter series ---------------------------------------------


def test_murata_r6y_series_is_parsed() -> None:
    """R6Y is a 35V X5R line: the letter after the series is not a voltage code."""
    got = _parse("GRM188R6YA106MA73D", "CAP")
    assert got == "0603_10uF_35V_X5R_20%"


def test_murata_r6x_numeric_series_reads_the_published_pair() -> None:
    """R60/R61 keep the series digit, and digit+letter IS the voltage code.

    Datasheet C02E21 "Rated Voltage": 0J = 6.3V, 1A = 10V, 1C = 16V, 1E = 25V.
    The revision that dropped the series digit reported 100V for a 6.3V part and
    16V for a 25V part, because the bare letter was looked up in a legacy table.
    """
    assert _parse("GRM155R60J105KE19D", "CAP") == "0402_1uF_6.3V_X5R_10%"
    assert _parse("GRM155R61A104KA01D", "CAP") == "0402_100nF_10V_X5R_10%"
    assert _parse("GRM155R61C105KA12D", "CAP") == "0402_1uF_16V_X5R_10%"
    assert _parse("GRM155R61E104K", "CAP") == "0402_100nF_25V_X5R_10%"
    assert _parse("GRM188R61J106MA73D", "CAP") == "0603_10uF_63V_X5R_20%"
    assert _parse("GRM188R62D106MA73D", "CAP") == "0603_10uF_200V_X5R_20%"


def test_murata_r71_and_c1h_forms_match_published_codes() -> None:
    """R7 is the temperature code, so the pair after it is the voltage field.

    Datasheet C02E21: R7 = X7R and 1C = 16 V. The earlier ``R(71|72)`` pattern
    consumed the leading digit as part of the series and then read a bare letter,
    which made GRM155R71C104KA88D report 6.3 V and GRM155R71E104KA01D report
    16 V. GRM155R71J104KA01D reported 100 V for a 63 V part.
    """
    assert _parse("GRM155R71C104KA88D", "CAP") == "0402_100nF_16V_X7R_10%"
    assert _parse("GRM188R71H102KA01D", "CAP") == "0603_1nF_50V_X7R_10%"
    assert _parse("GRM155R70J104KA01D", "CAP") == "0402_100nF_6.3V_X7R_10%"
    assert _parse("GRM155R71E104KA01D", "CAP") == "0402_100nF_25V_X7R_10%"
    assert _parse("GRM155R71J104KA01D", "CAP") == "0402_100nF_63V_X7R_10%"
    assert _parse("GRM155R71K104KA01D", "CAP") == "0402_100nF_80V_X7R_10%"
    assert _parse("GRM188R73D104KA01D", "CAP") == "0603_100nF_2kV_X7R_10%"
    # NP0/C0G line, where 1H really is 50V.
    assert _parse("GRM1555C1H100JA01D", "CAP") == "0402_10pF_50V_C0G_5%"


def test_murata_unknown_letter_series_is_not_mislabelled() -> None:
    """An unverified R6-letter series must stay unparsed, never guessed."""
    assert murata_capacitor.parse("GRM188R6ZA106MA73D", "CAP") is None
    assert _parse("GRM188R6ZA106MA73D", "CAP") is None


# --- Murata: official rated-voltage codes (datasheet C02E21) ----------------


def test_murata_voltage_table_matches_published_c02e21() -> None:
    """The two-character rated-voltage codes, verbatim from the datasheet.

    C02E21 "Chip Multilayer Ceramic Capacitors for General", section 6
    "Rated Voltage". YA = DC35V is the entry that confirms the R6Y line.
    """
    table = murata_capacitor._VOLT_2CH
    expected = {
        "0D": "2V",
        "0E": "2.5V",
        "0G": "4V",
        "0J": "6.3V",
        "1A": "10V",
        "1C": "16V",
        "1E": "25V",
        "1H": "50V",
        "1J": "63V",
        "1K": "80V",
        "2A": "100V",
        "2D": "200V",
        "2E": "250V",
        "2W": "450V",
        "2H": "500V",
        "2J": "630V",
        "3A": "1kV",
        "3B": "1.25kV",
        "3D": "2kV",
        "3F": "3.15kV",
        "BB": "350V",
        "E2": "AC250V",
        "GB": "AC250V",
        "GD": "AC250V",
        "GF": "AC250V",
        "YA": "35V",
    }
    assert table == expected
    # The whole point of the table: a one-character map cannot express YA.
    assert "Y" not in table
    # 23 codes in the "Rated Voltage" table plus GB/GD/GF individual-spec codes.
    assert len(table) == 26


def test_murata_r6y_voltage_comes_from_the_published_code() -> None:
    """R6Y + A is the YA code, so 35V is read from the datasheet table."""
    assert _parse("GRM188R6YA106MA73D", "CAP") == "0603_10uF_35V_X5R_20%"
    assert _parse("GRM188R6YA475KE15J", "CAP") == "0603_4.7uF_35V_X5R_10%"


def test_murata_numeric_series_prefers_published_pair_then_falls_back() -> None:
    """R61A resolves through the published 1A; R60H has no published pair."""
    # 1A is a published code and equals what the legacy per-series map gave.
    assert _parse("GRM188R61A106MA73D", "CAP") == "0603_10uF_10V_X5R_20%"
    # 0A is not published, so the legacy fallback still decides (10V).
    assert _parse("GRM188R60A106MA73D", "CAP") == "0603_10uF_10V_X5R_20%"
    # 0H is not published either; legacy letter map gives 50V.
    assert _parse("GRM188R60H106MA73D", "CAP") == "0603_10uF_50V_X5R_20%"


# --- Walsin WW: series letter, series-number sizes, WW12 refusal ------------


def test_ww_series_letter_part_numbers_decode() -> None:
    """The type code between size and value is a real field.

    Every WW sheet prints a ``CATALOGUE NUMBERS`` breakdown of
    ``WW25 | N | R005 | J | T | L``. The old pattern had no group for that
    letter, so of the 13 real part numbers in the sheets only 2 parsed.
    """
    assert walsin_ww_resistor.parse("WW25NR005JT", "RES") == "2512_0.005R_5%"
    assert walsin_ww_resistor.parse("WW25AR005JT", "RES") == "2512_0.005R_5%"
    assert walsin_ww_resistor.parse("WW25BR005FT", "RES") == "2512_0.005R_1%"
    assert walsin_ww_resistor.parse("WW20NR005JT", "RES") == "2010_0.005R_5%"
    assert walsin_ww_resistor.parse("WW20PR100JT", "RES") == "2010_0.1R_5%"
    assert walsin_ww_resistor.parse("WW10XR100JT", "RES") == "1210_0.1R_5%"
    assert walsin_ww_resistor.parse("WW10PR500JT", "RES") == "1210_0.5R_5%"
    # Legacy no-letter form still decodes.
    assert walsin_ww_resistor.parse("WW06RR005JT", "RES") == "0603_0.005R_5%"


def test_ww_series_number_is_not_the_size() -> None:
    """Sheets state the sizes: WW10=1210, WW20=2010, WW25=2512.

    The mapping is not monotonic - 12 would be 1206 while 10 is 1210 - so it
    has to be read from the datasheets rather than derived from the digits.
    """
    assert walsin_ww_resistor.parse("WW10XR100JT", "RES").startswith("1210_")
    assert walsin_ww_resistor.parse("WW20NR005JT", "RES").startswith("2010_")
    assert walsin_ww_resistor.parse("WW25NR005JT", "RES").startswith("2512_")


def test_ww12_is_refused_because_the_datasheets_disagree() -> None:
    """WW12R.PDF says 0603, WW12R_V.PDF says 1206.

    Rather than pick one, a WW12 part returns None so the part falls through.
    Guessing would silently attach the wrong imperial size to a current-sense
    resistor, which is the one field the size actually determines.
    """
    for pn in (
        "WW12RR005JT",
        "WW12XR020FT",
        "WW12WR020FT",
        "WW12DR020FT",
        "WW12RR005JTLS",
    ):
        assert walsin_ww_resistor.parse(pn, "RES") is None, pn


def test_ww_unknown_type_letter_is_refused() -> None:
    """Only type codes with a datasheet are decoded; the rest fall through."""
    assert walsin_ww_resistor.parse("WW25ZR005JT", "RES") is None


def test_ww_milli_ohm_code_matches_the_datasheet_examples() -> None:
    """ "R is first digit followed by 3 significant digits": R010=0.01, R976=0.976."""
    assert walsin_ww_resistor.parse("WW25NR010JT", "RES") == "2512_0.01R_5%"
    assert walsin_ww_resistor.parse("WW25NR976JT", "RES") == "2512_0.976R_5%"
    assert walsin_ww_resistor.parse("WW25NR000JT", "RES") == "2512_0R_5%"
