"""The shared resistance decoder every vendor resistor codec routes through.

``src/pn_original/_resistor_decode.decode_ohms_suffix`` is used by ``yageo``,
``tai_rm``, ``walsin_wr`` and ``ralec``, so a defect here shows up in four
independent codecs at once. Two of them (``royalohm``, ``viking``) carry their
own private ``_format_ohm`` and both divide by 1e6 unconditionally - which is
what pinned the intended output when this helper disagreed with them.
"""

from __future__ import annotations

import pytest

from pn_original._resistor_decode import decode_ohms_suffix


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        # E24/E96 mantissa-exponent, plain ohm.
        ("100", "10R"),
        ("470", "47R"),
        ("101", "100R"),
        ("499", None),  # 49 x 10^9: see test_absurd_expansions_are_refused
        ("4R7", "4.7R"),
        ("49R9", "49.9R"),
        # Kilo: whole values and fractions must both normalise.
        ("1000", "100R"),  # 100 x 10^0 - four digits, exponent 0, not a kilo
        ("1002", "10K"),
        ("4751", "4.75K"),
        ("4753", "475K"),
        # Mega: this is the regression. The M branch used to fire only on exact
        # multiples of 1e6, so everything else fell through to a raw "4750000R"
        # while the K branch above handled fractions correctly.
        ("1004", "1M"),
        ("2004", "2M"),
        ("4754", "4.75M"),
        ("1014", "1.01M"),
        ("1055", "10.5M"),
        ("1054", "1.05M"),
        ("4994", "4.99M"),
    ],
)
def test_eia_codes_normalise(code: str, expected: str) -> None:
    assert decode_ohms_suffix(code) == expected


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        # "R" stands for the decimal point. A trailing zero in the fraction is
        # not significant: 4R7 and 4R70 are the same part and must produce the
        # same string or equality-based dedup sees two different components.
        ("4R7", "4.7R"),
        ("4R70", "4.7R"),
        ("10R0", "10R"),
        ("10R2", "10.2R"),
        ("1R50", "1.5R"),
        ("2R20", "2.2R"),
        ("10R05", "10.05R"),
        ("1R00", "1R"),
    ],
)
def test_r_decimal_normalises(code: str, expected: str) -> None:
    assert decode_ohms_suffix(code) == expected


@pytest.mark.parametrize("code", ["0", "00", "000", "0000"])
def test_jumper_codes(code: str) -> None:
    assert decode_ohms_suffix(code) == "0R"


@pytest.mark.parametrize("code", ["499", "4998", "4999", "9709", "9959"])
def test_absurd_expansions_are_refused(code: str) -> None:
    """A chip resistor is not 499 GΩ, so a high exponent means a mis-split.

    ``royalohm`` and ``viking`` both refuse these; this helper did not, so the
    same part number decoded differently depending on which codec ran first.
    """
    assert decode_ohms_suffix(code) is None


@pytest.mark.parametrize("code", ["", "   ", "R", "4R", "abc", "12", "12345"])
def test_undecodable_tokens_return_none(code: str) -> None:
    assert decode_ohms_suffix(code) is None


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("9995", "99.9M"),  # largest expansion the ceiling admits
        ("1006", "100M"),  # the ceiling itself, so the bound is inclusive
        ("1007", None),  # first value past it
        ("1008", None),
    ],
)
def test_the_resistance_ceiling_is_inclusive_and_exactly_where_documented(
    code: str, expected: str | None
) -> None:
    """Pin ``_MAX_OHMS`` on both sides and at the edge.

    The other tests here bracket the ceiling from a long way out - ``4994`` is
    4.99 M and ``499`` is 49 G - which would still pass if the bound were moved
    anywhere between those two. Only these values distinguish ``>`` from ``>=``
    at 100 M, or a ceiling moved up to 1 G.
    """
    assert decode_ohms_suffix(code) == expected


def test_the_ceiling_matches_what_the_older_codecs_refuse() -> None:
    """The bound is a shared contract, not a private preference.

    ``royalohm`` and ``viking`` predate this helper and already refused absurd
    expansions; before the ceiling existed the same part number decoded
    differently depending on which codec ran first.
    """
    from pn_original._resistor_decode import _MAX_OHMS

    assert decode_ohms_suffix("9995") == "99.9M"
    assert decode_ohms_suffix("1006") == "100M"
    assert _MAX_OHMS == 100_000_000
    for absurd in ("499", "4998", "4999", "9709", "9959", "1007"):
        assert decode_ohms_suffix(absurd) is None
