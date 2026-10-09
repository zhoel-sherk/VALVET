from __future__ import annotations

import json
from pathlib import Path

import pytest

import logger
from clean_alerts import _best_film_hint, analyze_token_alert
from clean_component import CleanConfig, clean_one, clean_preview
from services.clean_config import build_clean_config


def test_cap_missing_tokens_alert_text() -> None:
    a = analyze_token_alert("1206_22uF", "CAP")
    assert a.is_alert is True
    assert "voltage" in a.missing
    assert "film" in a.missing
    assert "tolerance" in a.missing


def test_res_missing_tokens_alert_text() -> None:
    a = analyze_token_alert("0402_10K", "RESISTOR")
    assert a.is_alert is True
    assert a.missing == ("tolerance",)


def test_cap_pf_tolerance_is_counted_as_tolerance() -> None:
    a = analyze_token_alert("0402_5pF_C0G_0.25pF_50V", "CAP")
    assert a.is_alert is False
    assert a.missing == ()


def test_clean_preview_emits_alert_column_without_master() -> None:
    rows = clean_preview(["MLCC_1206_22uF"], CleanConfig(regex_master_enabled=False))
    assert len(rows) == 1
    assert len(rows[0]) == 6
    assert rows[0][5].startswith("missing=")


def test_clean_preview_emits_alert_column_with_master(
    tmp_path: Path, monkeypatch
) -> None:
    log_path = tmp_path / "missing_tokens.jsonl"
    monkeypatch.setenv("BOOMER_MISSING_TOKENS_LOG", str(log_path))
    cfg = CleanConfig(regex_master_enabled=True, regex_master_preview_scores=True)
    rows = clean_preview(["MLCC_1206_22uF"], cfg)
    assert len(rows[0]) == 8
    assert rows[0][7].startswith("missing=")
    assert log_path.exists()
    line = log_path.read_text(encoding="utf-8").strip().splitlines()[0]
    payload = json.loads(line)
    assert payload["alert"].startswith("missing=")


def test_best_film_hint_logs_when_rapidfuzz_missing(mocker) -> None:
    warn_spy = mocker.spy(logger, "warning")
    mocker.patch.dict("sys.modules", {"rapidfuzz": None})
    assert _best_film_hint(["X7S"]) == ""
    assert warn_spy.called
    msg = str(warn_spy.call_args.args[0]).lower()
    assert "rapidfuzz" in msg


# ---------------------------------------------------------------------------
# Config-aware expectations.
#
# The alert used to assume a fixed output shape, which was wrong twice over: the
# ohm "R" suffix is a user toggle, and so is every role in the template. On the
# CO1271 SKU3 sheet that produced 104 false "missing=nominal" rows out of 108
# alerts. These tests go through build_clean_config, not CleanConfig, because
# the two defaults had drifted apart and the app path is what the user sees.
# ---------------------------------------------------------------------------

_RES = ("pack", "nom", "%")
_CAP = ("pack", "nom", "V", "film", "%")
_IND = ("pack", "nom", "%", "Imax", "DCR")


def _cfg(**kw) -> CleanConfig:
    return build_clean_config(
        res_template=kw.pop("res_template", _RES),
        cap_template=kw.pop("cap_template", _CAP),
        ind_template=_IND,
        output_separator="_",
        **kw,
    )


def _alert(raw: str, cfg: CleanConfig) -> str:
    cleaned, typ, _c, _s = clean_one(raw, cfg)
    return analyze_token_alert(
        cleaned,
        typ,
        separator=cfg.output_separator,
        resistor_ohm_r_suffix=cfg.resistor_include_ohm_r_suffix,
        resistor_roles=_roles(cfg.resistor_template, _RES),
        cap_roles=_roles(cfg.cap_template, _CAP),
    ).as_text()


def _roles(template, tokens):
    from clean_component import _alert_roles

    return _alert_roles(template, tokens)


def test_the_reported_row_no_longer_flags_a_missing_nominal() -> None:
    """The row from the Clean BOM tab: 0603WAF220KT5E, SKU3 row 137.

    It cleaned correctly to 0603_2.2_1% and was still reported as
    missing=nominal, because the nominal was rendered without the ohm "R"
    suffix and the alert only knew the suffix spelling.
    """
    assert _alert("0603WAF220KT5E", _cfg()) == ""


@pytest.mark.parametrize(
    "raw",
    [
        "0603WAF220KT5E",
        "RC0603FR-0710RL",
        "WR06X2200FTL",
        "0402WAF1002KTL",
        "RES_499R_+/-1%_1/16W_R0402_SMD",
        "RMC0402FR071K",
    ],
    ids=lambda p: p,
)
def test_no_spurious_alert_with_the_ohm_r_suffix_off(raw: str) -> None:
    """The 104-row class: a plain-ohm value with the suffix toggle switched off.

    "0603_10_1%" is deliberate at this shop - no R means ohms, and a capacitor
    always shows uF/pF - so the alert has to read it, not flag it.
    """
    cfg = _cfg(res_ohm_r_suffix=False)
    assert _alert(raw, cfg) == ""


@pytest.mark.parametrize(
    "raw",
    ["0603WAF220KT5E", "RC0603FR-0710RL", "WR06X2200FTL", "0402WAF1002KTL"],
    ids=lambda p: p,
)
def test_no_spurious_alert_with_the_ohm_r_suffix_on(raw: str) -> None:
    assert _alert(raw, _cfg(res_ohm_r_suffix=True)) == ""


@pytest.mark.parametrize("raw", ["0402WAF1002KTL", "0603WAF1001KTL", "0402WAF1R01TL"])
def test_kilo_and_mega_pass_in_both_modes(raw: str) -> None:
    """``K``/``M`` are emitted unchanged by the toggle, so they always passed."""
    assert _alert(raw, _cfg(res_ohm_r_suffix=True)) == ""
    assert _alert(raw, _cfg(res_ohm_r_suffix=False)) == ""


def test_the_package_token_cannot_satisfy_the_nominal_check() -> None:
    """``0603`` is a bare number too, so it must never count as the value.

    Without this exclusion a value that was genuinely dropped would look
    complete purely because the package was present.
    """
    a = analyze_token_alert(
        "0603_1%",
        "RESISTOR",
        resistor_ohm_r_suffix=False,
    )
    assert "nominal" in a.missing


def test_a_bare_value_is_still_recognised_without_the_suffix() -> None:
    assert (
        analyze_token_alert(
            "0603_2.2_1%", "RESISTOR", resistor_ohm_r_suffix=False
        ).missing
        == ()
    )
    # ...but not when the suffix is on and the value has no suffix: that is a
    # malformed magnitude, and the K/M forms must not be affected.
    assert analyze_token_alert(
        "0603_2.2_1%", "RESISTOR", resistor_ohm_r_suffix=True
    ).missing == ("nominal",)
    assert (
        analyze_token_alert(
            "0603_10K_1%", "RESISTOR", resistor_ohm_r_suffix=True
        ).missing
        == ()
    )


def test_roles_dropped_from_the_template_are_not_reported_missing() -> None:
    """A role the user removed from the template was never asked for."""
    cfg = _cfg(res_template=("pack", "nom"))
    assert _alert("0603WAF220KT5E", cfg) == ""
    cap = _cfg(cap_template=("pack", "nom", "film", "%"))
    assert _alert("CL10A106MQ8NNNC", cap) == ""


def test_a_genuinely_missing_field_is_still_reported() -> None:
    """RB520S-40 is the one real miss in SKU3 - a Schottky MPN typed as RESISTOR.

    It must keep alerting, otherwise the fix has simply turned the column off.
    """
    assert "missing" in _alert("RB520S-40", _cfg())
    assert analyze_token_alert(
        "0402_10K", "RESISTOR", resistor_ohm_r_suffix=False
    ).missing == ("tolerance",)


def test_the_app_default_keeps_the_ohm_r_suffix() -> None:
    """The UI toggle already defaulted to on; the builder now agrees with it.

    build_clean_config used to default this to False while CleanConfig and the
    checkbox defaulted to True, so a programmatic caller got a different shape
    from the one the settings screen shows.
    """
    assert _cfg().resistor_include_ohm_r_suffix is True
