"""Walsin WR thick-film chip resistors, read against the manufacturer's sheets.

The size code was the defect that mattered: it was assumed to increase with the
series number, which is false. ``ASC_WR_TR_V07`` p.3 and p.5 give
``WR10: 1210`` and ``WR12: 1206`` - the series numbers are not ordered by size -
and ``WR18-20-25X(W)_V14`` p.3 adds ``WR18: 1218``. With ``10`` aliased onto
``0805`` a 1210 part cleaned to the same string as an 0805 part, a footprint
error roughly 4x off that no downstream size check would catch.
"""

from __future__ import annotations

import pytest

from pn_original import walsin_wr_resistor


def _parse(pn: str) -> str | None:
    return walsin_wr_resistor.parse(pn, "RES")


@pytest.mark.parametrize(
    ("pn", "expected"),
    [
        # ASC_WR_TR_V07 p.5, catalogue-number table.
        ("WR04X1001FTL", "0402_1K_1%"),
        ("WR06X472JTL", "0603_4.7K_5%"),
        ("WR08X1001FTL", "0805_1K_1%"),
        ("WR10X1001FTL", "1210_1K_1%"),
        ("WR12X1001FTL", "1206_1K_1%"),
        # WR18-20-25X(W)_V14 p.5.
        ("WR18X472JTL", "1218_4.7K_5%"),
        ("WR20X472JTL", "2010_4.7K_5%"),
        ("WR25X1001FTL", "2512_1K_1%"),
    ],
)
def test_size_codes_come_from_each_sheet(pn: str, expected: str) -> None:
    assert _parse(pn) == expected


def test_wr10_and_wr08_are_not_the_same_body() -> None:
    """The bug in one assertion: ``10`` was an alias of ``08``."""
    assert _parse("WR10X1001FTL") != _parse("WR08X1001FTL")
    assert _parse("WR10X1001FTL") == "1210_1K_1%"
    assert _parse("WR08X1001FTL") == "0805_1K_1%"


def test_wr12_is_1206_not_1210() -> None:
    assert _parse("WR12X1001FTL") == "1206_1K_1%"


def test_wr02_is_0201_on_production_evidence() -> None:
    """Not in the two local WR sheets, but not a guess either.

    The CO1271 corpus carries two real rows: ``WR02X3301FTL`` described as
    ``RES_3K3 ±1%_1/20W_R0201_SMD``, and the jumper ``WR02X000 PAL`` described
    as ``RES 0 OHM 1/20W (0201) 1%``. A 0201-specific catalogue sheet simply is
    not in the local set; production data settles it. Refusing ``WR02`` here
    was wrong and cost one vendor-decoded corpus row.
    """
    assert _parse("WR02X3301FTL") == "0201_3.3K_1%"
    assert _parse("WR02X000PAL") == "0201_0R"


@pytest.mark.parametrize(
    ("pn", "expected"),
    [
        # "P : Jumper" - no percentage is stated, so none is emitted. The old
        # code hardcoded 5% and the datasheet sample still passed, because
        # test_parser_generated asserts `expected in out` and "0805_0R" is a
        # substring of "0805_0R_5%".
        ("WR08X000PTL", "0805_0R"),
        ("WR04X000PTL", "0402_0R"),
    ],
)
def test_jumper_carries_no_invented_tolerance(pn: str, expected: str) -> None:
    assert _parse(pn) == expected


@pytest.mark.parametrize(
    ("pn", "expected"),
    [
        ("WR06X4754FTL", "0603_4.75M_1%"),
        ("WR06X4R70FTL", "0603_4.7R_1%"),
        ("WR04X24R0FTL", "0402_24R_1%"),
        ("WR04X2742FTL", "0402_27.4K_1%"),
    ],
)
def test_resistance_tokens_reach_the_shared_decoder(pn: str, expected: str) -> None:
    assert _parse(pn) == expected


def test_wr_is_resistor_only() -> None:
    assert walsin_wr_resistor.parse("WR04X1001FTL", "CAP") is None
