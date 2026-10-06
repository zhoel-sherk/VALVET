"""Invariant tests for pn_original parse() error logging.

These previously asserted that ``yageo_capacitor.parse()`` swallowed its own
internal errors and returned ``None`` with a bare ``logger.warning``. That
blanket handler defeated the ``parse_pn`` arbiter's ability to tell a crash from
a legitimate "not my format", so it was removed from all four vendor modules
(yageo/samsung capacitors, royalohm/uniohm resistors) and this test now pins the
new contract instead: the raise propagates, and ``parse_pn`` reports it.
"""

from __future__ import annotations

import pytest

import logger
import pn_original
from pn_original import yageo_capacitor


def test_yageo_cap_parse_no_longer_swallows_internal_errors(mocker) -> None:
    """``parse()`` must propagate, so ``parse_pn`` can report the crash."""
    mocker.patch.object(
        yageo_capacitor, "search", side_effect=RuntimeError("regex boom")
    )
    with pytest.raises(RuntimeError, match="regex boom"):
        yageo_capacitor.parse("CC0402KRX7R9BB102", "CAP")


def test_parse_pn_reports_a_raising_vendor_with_logger_exception(mocker) -> None:
    """The substituted result is never silent: the raise is logged, vendor named."""
    pn_original.CONVERTERS.clear()
    pn_original.load_converters()
    pn_original._reset_vendor_failure_log()
    exception_spy = mocker.spy(logger, "exception")
    mocker.patch.object(
        yageo_capacitor, "search", side_effect=RuntimeError("regex boom")
    )

    # No other CAP vendor claims a CC/CH MPN, so the failure surfaces as None.
    assert pn_original.parse_pn("CC0402KRX7R9BB102", "CAP", None) is None

    assert exception_spy.called
    assert "Yageo_CAP" in str(exception_spy.call_args.args[1])
