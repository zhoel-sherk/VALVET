"""Vendor ``parse()`` must let exceptions reach the ``parse_pn`` arbiter.

``yageo_capacitor``, ``samsung_capacitor``, ``royalohm_resistor`` and
``uniohm_resistor`` each used to wrap their whole ``parse()`` body in
``except Exception -> logger.warning -> return None``. That swallowed the very
signal ``pn_original.parse_pn`` needs: the arbiter cannot tell a crash from a
legitimate "not my format", so the substitution to the next vendor was silent.

Each test below pins two things per vendor:

1. the datasheet samples still parse to exactly the values they parsed to before,
2. an exception raised inside ``parse()`` is surfaced — either it propagates out of
   ``parse()`` itself, or ``parse_pn`` logs it with ``logger.exception`` naming the
   vendor, and the part is never *silently* handed to another vendor.

A raise is provoked by monkeypatching a helper the happy path actually calls, so
the test is deterministic and independent of any genuinely malformed PN.
"""

from __future__ import annotations

import pytest

import logger
import pn_original
from pn_original import (
    royalohm_resistor,
    samsung_capacitor,
    uniohm_resistor,
    yageo_capacitor,
)

# (pn, ctype, expected) — the samples recorded in datasheet/<vendor>.md plus the
# extra MPNs quoted in each module header. Values are byte-for-byte what these
# four parse()s produced before the blanket handlers were removed.
YAGEO_CAP_SAMPLES = [
    ("CC0402KRX7R9BB102", "CAP", "0402_1nF_50V_X7R_10%"),
    ("CC0402KRX7R7BB105", "CAP", "0402_1uF_16V_X7R_10%"),
    # Real production MPN (bom.xlsx SKU3), description says
    # MLCC_100pF_X7R_50V_+/-10%_C0402. BB=50V per the Yageo code table.
    ("CC0402KRX7R9BB101", "CAP", "0402_100pF_50V_X7R_10%"),
]

SAMSUNG_CAP_SAMPLES = [
    ("CL05A105MQ5NNNC", "CAP", "0402_1uF_6.3V_X5R_20%"),
    # Real production MPNs from bom.xlsx SKU3, expected values taken from the
    # human-readable description in that same sheet (column C), which states the
    # nominal, dielectric, voltage and tolerance.
    ("CL10A106MO8NQNC", "CAP", "0603_10uF_16V_X5R_20%"),
    ("CL05B104KA5NNNC", "CAP", "0402_100nF_25V_X7R_10%"),
]

ROYALOHM_RES_SAMPLES = [
    ("0402WGF100JTCE", "RES", "0402_10R_1%_1/16W"),
    ("0402WGF1004TCE", "RES", "0402_1M_1%_1/16W"),
    ("0603WAF3001T5E", "RES", "0603_3K_1%_1/10W"),
    ("0603WAF220KT5E", "RES", "0603_2.2R_1%_1/10W"),
]

UNIOHM_RES_SAMPLES = [
    ("0603WAF3001T5E", "RES", "0603_3K_1%_1/10W"),
    ("0402WGF4701TCE", "RES", "0402_4.7K_1%_1/16W"),
    ("0805W8F1001T5E", "RES", "0805_1K_1%_1/8W"),
    ("0402WGJ0223TCE", "RES", "0402_22K_5%_1/16W"),
    ("0402WGF3922TCE", "RES", "0402_39.2K_1%_1/16W"),
    ("0402WGJ0472TCE", "RES", "0402_4.7K_5%_1/16W"),
    ("0402WGF4991TCE", "RES", "0402_4.99K_1%_1/16W"),
    ("0402WGJ0000TCE", "RES", "0402_0R_5%_1/16W"),
    # Tol-first form that only Uniohm decodes (Royal Ohm returns None for it).
    ("0201F7502TCE", "RES", "0201_75K_1%_1/20W"),
]


@pytest.fixture(autouse=True)
def _fresh_registry():
    """Registry + failure-dedup cache reset per test (dedup is module state)."""
    pn_original.CONVERTERS.clear()
    pn_original.load_converters()
    pn_original._reset_vendor_failure_log()
    yield
    pn_original._reset_vendor_failure_log()


def _parse_pn(pn: str, ctype: str):
    return pn_original.parse_pn(pn, ctype, None)


def _boom(monkeypatch, module, attr: str) -> None:
    """Make ``module.attr`` raise, as a genuine parser bug would."""

    def _raise(*_args, **_kwargs):
        raise RuntimeError("regex boom")

    monkeypatch.setattr(module, attr, _raise)


# --- Valid parts are unaffected ---------------------------------------------


@pytest.mark.parametrize(
    "pn,ctype,expected",
    YAGEO_CAP_SAMPLES,
    ids=[pn for pn, _, _ in YAGEO_CAP_SAMPLES],
)
def test_yageo_cap_valid_samples_unchanged(pn, ctype, expected) -> None:
    assert yageo_capacitor.parse(pn, ctype) == expected
    assert _parse_pn(pn, ctype) == expected


@pytest.mark.parametrize(
    "pn,ctype,expected",
    SAMSUNG_CAP_SAMPLES,
    ids=[pn for pn, _, _ in SAMSUNG_CAP_SAMPLES],
)
def test_samsung_cap_valid_samples_unchanged(pn, ctype, expected) -> None:
    assert samsung_capacitor.parse(pn, ctype) == expected
    assert _parse_pn(pn, ctype) == expected


@pytest.mark.parametrize(
    "pn,ctype,expected",
    ROYALOHM_RES_SAMPLES,
    ids=[pn for pn, _, _ in ROYALOHM_RES_SAMPLES],
)
def test_royalohm_res_valid_samples_unchanged(pn, ctype, expected) -> None:
    assert royalohm_resistor.parse(pn, ctype) == expected
    assert _parse_pn(pn, ctype) == expected


@pytest.mark.parametrize(
    "pn,ctype,expected",
    UNIOHM_RES_SAMPLES,
    ids=[pn for pn, _, _ in UNIOHM_RES_SAMPLES],
)
def test_uniohm_res_valid_samples_unchanged(pn, ctype, expected) -> None:
    assert uniohm_resistor.parse(pn, ctype) == expected
    assert _parse_pn(pn, ctype) == expected


@pytest.mark.parametrize(
    "module,ctype",
    [
        (yageo_capacitor, "CAP"),
        (samsung_capacitor, "CAP"),
        (royalohm_resistor, "RES"),
        (uniohm_resistor, "RES"),
    ],
    ids=["yageo", "samsung", "royalohm", "uniohm"],
)
def test_foreign_component_type_still_returns_none(module, ctype) -> None:
    """ "Not my component type" is an explicit ``None``, never an exception."""
    other = "RES" if ctype == "CAP" else "CAP"
    assert module.parse("0402WGF1004TCE", other) is None


# --- A raise inside parse() propagates out of parse() -----------------------


def test_yageo_cap_parse_propagates_internal_error(monkeypatch) -> None:
    _boom(monkeypatch, yageo_capacitor, "search")
    with pytest.raises(RuntimeError, match="regex boom"):
        yageo_capacitor.parse("CC0402KRX7R9BB102", "CAP")


def test_samsung_cap_parse_propagates_internal_error(monkeypatch) -> None:
    _boom(monkeypatch, samsung_capacitor, "pf_eia_3_to_str")
    with pytest.raises(RuntimeError, match="regex boom"):
        samsung_capacitor.parse("CL05A105MQ5NNNC", "CAP")


def test_royalohm_res_parse_propagates_internal_error(monkeypatch) -> None:
    # 4-digit E96 form is the one that reaches parse_resistance(); the 3-digit
    # "100J" layout decodes inline via _format_ohm and never calls it.
    _boom(monkeypatch, royalohm_resistor, "parse_resistance")
    with pytest.raises(RuntimeError, match="regex boom"):
        royalohm_resistor.parse("0402WGF1004TCE", "RES")


def test_uniohm_res_parse_propagates_internal_error(monkeypatch) -> None:
    # 0201F7502TCE is Uniohm-only, so no sibling vendor can mask the raise.
    _boom(monkeypatch, uniohm_resistor, "parse_resistance")
    with pytest.raises(RuntimeError, match="regex boom"):
        uniohm_resistor.parse("0201F7502TCE", "RES")


# --- Through parse_pn: the raise is surfaced, never silent ------------------


def test_parse_pn_logs_yageo_cap_failure_and_returns_none(monkeypatch) -> None:
    """No other CAP vendor claims a CC/CH MPN, so a raising Yageo yields ``None``.

    The important part is that the drop is *reported*: ``logger.exception`` fires
    and names the vendor. Before the fix the vendor returned ``None`` itself, the
    arbiter saw an ordinary non-match and logged nothing at all.
    """
    _boom(monkeypatch, yageo_capacitor, "search")
    logged: list = []
    monkeypatch.setattr(logger, "exception", lambda *a, **k: logged.append(a))

    assert _parse_pn("CC0402KRX7R9BB102", "CAP") is None

    assert len(logged) == 1
    assert "Yageo_CAP" in logged[0]
    assert "CC0402KRX7R9BB102" in logged[0]


def test_parse_pn_logs_samsung_cap_failure_and_returns_none(monkeypatch) -> None:
    _boom(monkeypatch, samsung_capacitor, "pf_eia_3_to_str")
    logged: list = []
    monkeypatch.setattr(logger, "exception", lambda *a, **k: logged.append(a))

    assert _parse_pn("CL05A105MQ5NNNC", "CAP") is None

    assert len(logged) == 1
    assert "Samsung" in logged[0]
    assert "CL05A105MQ5NNNC" in logged[0]


def test_parse_pn_reports_royalohm_failure_even_when_uniohm_covers_it(
    monkeypatch,
) -> None:
    """Royal Ohm and Uniohm share the WG/W8/W4 layout, so one rescues the other.

    The fallback result is the historical behaviour and is kept — but it must be
    accompanied by a traceback naming Royal Ohm, so the substitution is visible.
    """
    _boom(monkeypatch, royalohm_resistor, "parse_resistance")
    logged: list = []
    monkeypatch.setattr(logger, "exception", lambda *a, **k: logged.append(a))

    # Uniohm parses the very same MPN to the very same value.
    assert _parse_pn("0402WGF1004TCE", "RES") == "0402_1M_1%_1/16W"

    assert len(logged) == 1
    assert "Royal Ohm" in logged[0]
    assert "0402WGF1004TCE" in logged[0]


def test_parse_pn_logs_uniohm_failure_and_returns_none(monkeypatch) -> None:
    """``0201F7502TCE`` is Uniohm-only, so its raise cannot be masked."""
    _boom(monkeypatch, uniohm_resistor, "parse_resistance")
    logged: list = []
    monkeypatch.setattr(logger, "exception", lambda *a, **k: logged.append(a))

    assert _parse_pn("0201F7502TCE", "RES") is None

    assert len(logged) == 1
    assert "Uniohm" in logged[0]
    assert "0201F7502TCE" in logged[0]


@pytest.mark.parametrize(
    "module,attr,pn,ctype",
    [
        (yageo_capacitor, "search", "CC0402KRX7R9BB102", "CAP"),
        (samsung_capacitor, "pf_eia_3_to_str", "CL05A105MQ5NNNC", "CAP"),
        (royalohm_resistor, "parse_resistance", "0402WGF1004TCE", "RES"),
        (uniohm_resistor, "parse_resistance", "0201F7502TCE", "RES"),
    ],
    ids=["yageo", "samsung", "royalohm", "uniohm"],
)
def test_raising_vendor_does_not_emit_a_bare_warning(
    monkeypatch, module, attr, pn, ctype
) -> None:
    """The removed handler's ``logger.warning`` is gone; the arbiter logs instead."""
    _boom(monkeypatch, module, attr)
    warnings: list = []
    exceptions: list = []
    monkeypatch.setattr(logger, "warning", lambda *a, **k: warnings.append(a))
    monkeypatch.setattr(logger, "exception", lambda *a, **k: exceptions.append(a))

    _parse_pn(pn, ctype)

    assert warnings == []
    assert len(exceptions) == 1
    assert module.VENDOR_NAME in exceptions[0]
