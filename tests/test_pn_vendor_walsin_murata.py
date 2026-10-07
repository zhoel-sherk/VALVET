"""Walsin ``NT`` packaging suffix and Murata ``R6Y`` series (PLAN 5.8).

Both families used to fall through the vendor phase and were returned unchanged
by the regex phase (a silent no-op). Expected values below follow the token
order each parser already emits (size_value[_dielectric][_voltage][_tolerance]).
"""

from __future__ import annotations

import pn_original
from pn_original import murata_capacitor, walsin_mlcc_capacitor


def _parse(pn: str, ctype: str) -> str | None:
    pn_original.CONVERTERS.clear()
    pn_original.load_converters()
    return pn_original.parse_pn(pn, ctype, None)


# --- Walsin: NT (7" plastic tape) packaging suffix -------------------------


def test_walsin_nt_suffix_x6r3_line() -> None:
    got = _parse("0201X104K6R3NT", "CAP")
    assert got == "0201_100nF_X5R_6.3V_10%"


def test_walsin_nt_suffix_xkv_line() -> None:
    assert _parse("0402X224K160NT", "CAP") == "0402_220nF_X5R_16V_10%"
    assert _parse("0603X226M100NT", "CAP") == "0603_22uF_X5R_10V_20%"


def test_walsin_nt_and_ct_suffix_give_the_same_value() -> None:
    """NT only changes the reel code; every decoded field must be identical."""
    assert _parse("0805X475M6R3NT", "CAP") == _parse("0805X475M6R3CT", "CAP")


def test_walsin_ct_forms_are_unchanged() -> None:
    """Regression: the already-working CT parts keep their exact output."""
    assert _parse("0402N100J500CT", "CAP") == "0402_10pF_50V_5%"
    assert _parse("0402B101K500CT", "CAP") == "0402_100pF_X7R_50V_10%"
    assert _parse("0805X475M6R3CT", "CAP") == "0805_4.7uF_X5R_6.3V_20%"
    assert _parse("1206X106K250CT", "CAP") == "1206_10uF_X5R_25V_10%"


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
