"""Invariant tests for parsers.cap_pars NF→UF column consistency.

Replaces the old ``test_cap_nf_to_uf_manual_fallback_logs_warning``, which pinned the
inline `n >= 1` manual fallback. That fallback only handled values ≥ 1 nF, so
``0.5NF``/``0.1NF`` kept their NF suffix and landed in the same column as ``1UF`` —
a 1000x read error for anything downstream (release 0.5.1.1 item 3.5).
"""

from __future__ import annotations

from dataclasses import replace

import logger
from clean_types import CleanConfig
from parsers.cap_pars import parse_capacitor_token_fields


def test_cap_nf_to_uf_conversion_failure_is_logged_as_error(mocker) -> None:
    """A failed conversion is a real error, not a silent warning-and-continue."""
    err_spy = mocker.spy(logger, "error")
    mocker.patch(
        "parsers.si_units._as_float",
        side_effect=RuntimeError("conversion failed"),
    )
    cfg = replace(CleanConfig(), cap_convert_nf_to_uf=True)

    _fields, cleaned = parse_capacitor_token_fields("MLCC 1000NF 50V 0402 X7R 10%", cfg)

    # The NF token is dropped rather than left in a microfarad column.
    assert "NF" not in cleaned.upper()
    assert err_spy.called
    msg = str(err_spy.call_args.args[0]).lower()
    assert "nf→uf" in msg or "nf" in msg
    assert "dropped" in msg


def test_cap_nf_to_uf_converts_sub_1nf_values() -> None:
    """Values below 1 nF convert too — the old `n >= 1` branch skipped them."""
    cfg = replace(CleanConfig(), cap_convert_nf_to_uf=True)
    for spec, expected in (
        ("MLCC 0.5NF 50V 0402 X7R 10%", "0.0005uF"),
        ("MLCC 0.1NF 50V 0402 X7R 10%", "0.0001uF"),
    ):
        _fields, cleaned = parse_capacitor_token_fields(spec, cfg)
        assert "NF" not in cleaned.upper(), spec
        assert expected in cleaned, (spec, cleaned)
