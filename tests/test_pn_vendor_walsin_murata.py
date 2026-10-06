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


def test_murata_r6x_numeric_series_is_unchanged() -> None:
    """Regression: R60/R61 keep using the separate voltage letter."""
    assert _parse("GRM155R60J105KE19D", "CAP") == "0402_1uF_100V_X5R_10%"
    assert _parse("GRM155R61A104KA01D", "CAP") == "0402_100nF_10V_X5R_10%"
    assert _parse("GRM155R61C105KA12D", "CAP") == "0402_1uF_6.3V_X5R_10%"
    assert _parse("GRM155R61E104K", "CAP") == "0402_100nF_16V_X5R_10%"


def test_murata_r71_and_c1h_forms_are_unchanged() -> None:
    """Regression: the R71 and NP0/C1H branches keep their exact output."""
    assert _parse("GRM155R71C104KA88D", "CAP") == "0402_100nF_6.3V_X7R_10%"
    assert _parse("GRM188R71H102KA01D", "CAP") == "0603_1nF_50V_X7R_10%"
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
    assert len(table) == 24


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
