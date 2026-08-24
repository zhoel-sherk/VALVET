from __future__ import annotations

import json
from pathlib import Path

from clean_alerts import analyze_token_alert
from clean_component import CleanConfig, clean_preview


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


def test_clean_preview_emits_alert_column_with_master(tmp_path: Path, monkeypatch) -> None:
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
