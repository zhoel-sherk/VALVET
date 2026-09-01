"""Invariant tests for pn_original parse() error logging."""

from __future__ import annotations

import logger
from pn_original import yageo_capacitor


def test_yageo_cap_parse_logs_on_internal_error(mocker) -> None:
    warn_spy = mocker.spy(logger, "warning")
    mocker.patch.object(
        yageo_capacitor, "search", side_effect=RuntimeError("regex boom")
    )
    assert yageo_capacitor.parse("CC0402KRX7R9BB102", "CAP") is None
    assert warn_spy.called
    msg = str(warn_spy.call_args.args[0]).lower()
    assert "yageo" in msg or "parse failed" in msg
