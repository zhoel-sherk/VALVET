"""Invariant tests for parsers.cap_pars NF→UF fallback logging."""

from __future__ import annotations

from dataclasses import replace

import logger
from clean_types import CleanConfig
from parsers.cap_pars import parse_capacitor_token_fields


def test_cap_nf_to_uf_manual_fallback_logs_warning(mocker) -> None:
    warn_spy = mocker.spy(logger, "warning")
    mocker.patch(
        "parsers.si_units.convert_nf_token_to_uf",
        side_effect=RuntimeError("si_units down"),
    )
    cfg = replace(CleanConfig(), cap_convert_nf_to_uf=True)
    _fields, cleaned = parse_capacitor_token_fields("MLCC 1000NF 50V 0402 X7R 10%", cfg)
    assert "1UF" in cleaned.upper()
    assert warn_spy.called
    msg = str(warn_spy.call_args.args[0]).lower()
    assert "si_units" in msg or "fallback" in msg
