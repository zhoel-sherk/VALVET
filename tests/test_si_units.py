"""Invariant tests for parsers.si_units fallback logging."""

from __future__ import annotations

import logger
from parsers.si_units import convert_nf_token_to_uf


def test_convert_nf_token_to_uf_logs_on_float_failure(mocker) -> None:
    warn_spy = mocker.spy(logger, "warning")
    mocker.patch(
        "parsers.si_units._as_float",
        side_effect=RuntimeError("conversion failed"),
    )
    assert convert_nf_token_to_uf("22NF") == "22NF"
    assert warn_spy.called
    msg = str(warn_spy.call_args.args[0]).lower()
    assert "convert_nf_token_to_uf" in msg or "failed" in msg
