"""Phase 3 / 2.8 / 4.x silent-fallback fixes (release 0.5.1.1).

Each test pins the *deliberate* behaviour chosen for one audit finding:
3.1 vendor arbiter, 3.2 debug→error, 3.5 NF/UF consistency, 3.6 dropped mapping,
3.7 sqlite cache, 3.8 registry discovery, 3.9 merged_count, 2.8 log flooding,
4.4 tie-break, 4.9 first ``%``.
"""

from __future__ import annotations

import sqlite3
from dataclasses import replace

import pandas as pd
import pytest

import clean_component
import logger
import machine_library.hanwha_sqlite_cache as hanwha_cache
import pcb_preview.outline_resolve as outline_resolve
from clean_types import CleanConfig
from hanwha_mdb_edit.core import part_enriched
from parsers import registry
from parsers.cap_pars import (
    parse_capacitor_token_fields,
    try_parse_mlcc_bom_line_slots,
)
from parsers.si_units import (
    convert_nf_token_to_uf,
    try_convert_nf_token_to_uf,
)

# ``ui.bom_tab`` / ``ui.pnp_tab`` and ``app.window`` import each other, so the app
# package has to be initialised before the mixins resolve.
import app.window  # noqa: F401  isort:skip
from ui.bom_tab import BomTabMixin  # noqa: E402  isort:skip
from ui.pnp_tab import PnpTabMixin  # noqa: E402  isort:skip


# ---------------------------------------------------------------------------
# 3.1 — vendor arbiter: "returned None" vs "raised"
# ---------------------------------------------------------------------------


class _FakeModule:
    """Stand-in vendor module with a scriptable ``parse``."""

    PARSER_PRIORITY = 0

    def __init__(self, parse):
        self.parse = parse


def _arbiter(converters):
    return {"V": {"module": converters, "types": ["CAP"]}}


def _raising(_pn, _ct):
    raise RuntimeError("regex boom")


def _none(_pn, _ct):
    return None


def _hit(_pn, _ct):
    return "0402_100nF_50V_X7R_10%"


def _logged_text(spy) -> str:
    """Every logged message with its arguments rendered into the format string."""
    import logging

    return " ".join(
        logging.LogRecord("x", 0, "", 0, call.args[0], call.args[1:], None).getMessage()
        for call in spy.call_args_list
        if call.args
    )


@pytest.fixture
def clean_arbiter(monkeypatch):
    """Isolated CONVERTERS + failure-dedup state for parse_pn."""
    import pn_original

    monkeypatch.setattr(pn_original, "CONVERTERS", {})
    pn_original._reset_vendor_failure_log()
    yield pn_original
    pn_original._reset_vendor_failure_log()


def test_raising_vendor_is_logged_with_traceback(clean_arbiter, mocker):
    """A vendor that raises must be logged at exception level, not a debug line."""
    exc_spy = mocker.spy(logger, "exception")
    clean_arbiter.CONVERTERS = _arbiter(_FakeModule(_raising))

    assert clean_arbiter.parse_pn("CC0405KRX7R9BB104", "CAP", CleanConfig()) is None

    assert exc_spy.called
    args = exc_spy.call_args.args
    assert "V" in str(args)
    assert "CC0405KRX7R9BB104" in str(args)


def test_raising_vendor_does_not_win_and_falls_through(clean_arbiter, mocker):
    """Explicit arbiter contract: raise -> log, skip, continue to the next vendor.

    The raising vendor's own answer is never produced (it has none), and the loop
    proceeds to the next vendor by priority. The substitute is returned, but the
    raise is on the record at exception level, so the value is never silent.
    """
    exc_spy = mocker.spy(logger, "exception")
    boom = _FakeModule(_raising)
    boom.PARSER_PRIORITY = 100
    ok = _FakeModule(_hit)
    ok.PARSER_PRIORITY = 10
    clean_arbiter.CONVERTERS = {
        "BOOM": {"module": boom, "types": ["CAP"]},
        "OK": {"module": ok, "types": ["CAP"]},
    }

    got = clean_arbiter.parse_pn("CC0405KRX7R9BB104", "CAP", CleanConfig())

    assert got == "0402_100nF_50V_X7R_10%"  # substitute used…
    assert exc_spy.called  # …but the raise that caused it is on the record
    assert "BOOM" in str(exc_spy.call_args.args)


def test_raising_vendor_alone_returns_none_not_another_vendors_value(
    clean_arbiter, mocker
):
    """A lone raising vendor yields no part, rather than a silently substituted one."""
    exc_spy = mocker.spy(logger, "exception")
    clean_arbiter.CONVERTERS = _arbiter(_FakeModule(_raising))

    assert clean_arbiter.parse_pn("CC0405KRX7R9BB104", "CAP", CleanConfig()) is None
    assert exc_spy.called


def test_vendor_returning_none_falls_through_quietly(clean_arbiter, mocker):
    """Returning None is a legitimate 'not my format' — no exception, no warning."""
    exc_spy = mocker.spy(logger, "exception")
    warn_spy = mocker.spy(logger, "warning")
    clean_arbiter.CONVERTERS = _arbiter(_FakeModule(_none))

    assert clean_arbiter.parse_pn("CC0405KRX7R9BB104", "CAP", CleanConfig()) is None
    assert not exc_spy.called
    assert not warn_spy.called


def test_vendor_failure_log_is_deduplicated(clean_arbiter, mocker):
    """2.8: one traceback per (pn, vendor, type), not one per BOM row."""
    exc_spy = mocker.spy(logger, "exception")
    clean_arbiter.CONVERTERS = _arbiter(_FakeModule(_raising))
    cfg = CleanConfig()

    for _ in range(25):
        clean_arbiter.parse_pn("CC0405KRX7R9BB104", "CAP", cfg)

    assert exc_spy.call_count == 1


# ---------------------------------------------------------------------------
# 3.2 — real failures logged at error with exc_info
# ---------------------------------------------------------------------------


def test_parse_pn_wrapper_failure_is_error_with_exc_info(mocker):
    err_spy = mocker.spy(logger, "error")
    mocker.patch("pn_original.parse_pn", side_effect=RuntimeError("import broke"))
    cfg = replace(CleanConfig(), use_pn_codecs=True, use_vendor_pn=True)

    out = clean_component._try_parse_vendor_pn("RC0603FR-0710KL", "RESISTOR", cfg)

    assert out is None
    assert err_spy.called
    kwargs = err_spy.call_args.kwargs
    assert kwargs.get("exc_info") is True
    assert "parse_pn failed" in str(err_spy.call_args.args[0])


def test_component_library_lookup_failure_is_error_with_exc_info(mocker):
    err_spy = mocker.spy(logger, "error")
    mocker.patch(
        "component_library.lookup_component",
        side_effect=OSError("library file gone"),
    )
    cfg = replace(CleanConfig(), use_component_library=True)

    out = clean_component._clean_one_try_library("0402 10K 1%", cfg)

    assert out is None
    assert err_spy.called
    assert err_spy.call_args.kwargs.get("exc_info") is True


# ---------------------------------------------------------------------------
# 3.5 — NF and UF must not share one output column
# ---------------------------------------------------------------------------


def test_strict_nf_conversion_never_returns_nf():
    assert try_convert_nf_token_to_uf("0.5NF") == "0.0005UF"
    assert try_convert_nf_token_to_uf("0.1NF") == "0.0001UF"
    assert try_convert_nf_token_to_uf("1000NF") == "1UF"
    # Not an NF token at all -> no conversion available.
    assert try_convert_nf_token_to_uf("10uF") is None
    assert try_convert_nf_token_to_uf("") is None


def test_strict_nf_conversion_returns_none_on_float_failure(mocker):
    mocker.patch("parsers.si_units._as_float", side_effect=RuntimeError("bad number"))
    assert try_convert_nf_token_to_uf("22NF") is None


def test_sub_1nf_values_no_longer_keep_nf_suffix():
    """3.2.5 / 3.5: the old `elif n >= 1` fallback left 0.5NF as NF."""
    cfg = replace(CleanConfig(), cap_convert_nf_to_uf=True)
    for spec, expected in (
        ("MLCC 0.5NF 50V 0402 X7R 10%", "0.0005uF"),
        ("MLCC 0.1NF 50V 0402 X7R 10%", "0.0001uF"),
        ("MLCC 1000NF 50V 0402 X7R 10%", "1uF"),
    ):
        _fields, cleaned = parse_capacitor_token_fields(spec, cfg)
        assert "NF" not in cleaned.upper(), spec
        assert expected in cleaned, (spec, cleaned)


def test_failed_nf_conversion_drops_nominal_instead_of_mixing_units(mocker):
    """A failed conversion must not leave an NF token next to UF values."""
    err_spy = mocker.spy(logger, "error")
    mocker.patch("parsers.si_units._as_float", side_effect=RuntimeError("bad number"))
    cfg = replace(CleanConfig(), cap_convert_nf_to_uf=True)

    _fields, cleaned = parse_capacitor_token_fields("MLCC 22NF 50V 0402 X7R 10%", cfg)

    assert "NF" not in cleaned.upper()
    assert "22" not in cleaned
    assert err_spy.called


def test_nf_column_stays_consistent_across_mixed_source_units():
    """Every row in a converted column carries the same unit, whatever the source."""
    cfg = replace(CleanConfig(), cap_convert_nf_to_uf=True)
    cleaned_rows = [
        parse_capacitor_token_fields(f"MLCC {v} 50V 0402 X7R 10%", cfg)[1]
        for v in ("1000NF", "22NF", "0.5NF", "0.1NF")
    ]
    units = {u for row in cleaned_rows for u in ("NF",) if u in row.upper()}
    assert units == set()
    assert all("uF" in row for row in cleaned_rows)


def test_convert_nf_token_to_uf_keeps_its_documented_original_token():
    """The legacy helper keeps its 'unparsed -> original' contract for callers."""
    assert convert_nf_token_to_uf("not_a_value") == "not_a_value"
    assert convert_nf_token_to_uf("1000NF") == "1UF"


# ---------------------------------------------------------------------------
# 4.9 — first ``%`` wins, not the last
# ---------------------------------------------------------------------------


def test_first_percentage_is_used_as_tolerance():
    cfg = CleanConfig()
    slots = try_parse_mlcc_bom_line_slots("1UF/16V(0402)X7R 10% 0402/50%", cfg)
    assert slots is not None
    _raw, result = slots
    assert "%" in result
    assert "10%" in result
    assert "50%" not in result


# ---------------------------------------------------------------------------
# 3.6 — dropped column mapping is surfaced
# ---------------------------------------------------------------------------


class _StubWindow:
    """Minimal host for the mixin warning helper."""

    def __init__(self):
        self.messages: list[tuple[str, str]] = []

    def _log(self, message: str, level: str = "info") -> None:
        self.messages.append((message, level))


@pytest.mark.parametrize(
    ("mixin", "kind", "attr"),
    [(BomTabMixin, "BOM", "bom_col_combos"), (PnpTabMixin, "PnP", "pnp_col_combos")],
)
def test_discarded_column_mapping_warns_in_console(
    mixin, kind, attr, monkeypatch, mocker
):
    warn_spy = mocker.spy(logger, "warning")
    host = _StubWindow()
    monkeypatch.setattr(type(host), attr, [object(), object(), object()], raising=False)
    monkeypatch.setattr(type(host), "_log", host._log, raising=False)

    mixin._warn_dropped_mapping_profile(host, kind, 5, 3)

    assert warn_spy.called
    level = host.messages[-1][1]
    assert level == "warning"
    assert kind in host.messages[-1][0]
    assert "discarded" in host.messages[-1][0].lower()


# ---------------------------------------------------------------------------
# 3.7 — sqlite cache must not return an empty frame on failure
# ---------------------------------------------------------------------------


def test_sqlite_table_returns_none_and_logs_table_name(mocker):
    """A broken DB read must not read as 'table legitimately empty'."""
    err_spy = mocker.spy(logger, "error")
    conn = sqlite3.connect(":memory:")
    mocker.patch.object(
        pd,
        "read_sql_query",
        side_effect=pd.errors.DatabaseError("database is locked"),
    )

    got = hanwha_cache._sqlite_table(conn, "VISION_CHIP_WHOLE_Det", "AP1")

    assert got is None
    assert err_spy.called
    assert "VISION_CHIP_WHOLE_Det" in str(err_spy.call_args.args)


def test_sqlite_table_missing_table_is_not_a_failure(mocker):
    """A cache dumped without this table is a legitimate empty result, not an error."""
    err_spy = mocker.spy(logger, "error")
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE OTHER (a INTEGER)")

    got = hanwha_cache._sqlite_table(conn, "VISION_CHIP_WHOLE_Det", "AP1")

    assert got is not None and got.empty
    assert not err_spy.called


def test_profile_snapshot_refuses_degenerate_outline_on_read_failure(tmp_path, mocker):
    """Unreadable tables must not yield a valid-looking zero-size outline."""
    err_spy = mocker.spy(logger, "error")
    hanwha_cache.sqlite_path(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    hanwha_cache.sqlite_path(tmp_path).write_bytes(b"not a database")

    snap = hanwha_cache.load_profile_snapshot_from_sqlite(tmp_path, "AP2318GEN")

    assert snap.vision_type == 0
    assert err_spy.called
    logged = _logged_text(err_spy)
    assert "refusing to build outline" in logged


def test_wide_merge_failure_is_logged_and_not_counted(mocker, tmp_path):
    """3.9: a failed merge must be logged and must not increment ``merged_count``.

    ``merged_count`` gates the ``_MAX_WIDE_TABLES`` budget, so counting a table that
    was never merged made the wide frame come back short with no explanation. The
    summary line reports both numbers, which is what the test pins.
    """
    warn_spy = mocker.spy(logger, "warning")
    base_df = pd.DataFrame({"PARTNAME": ["A"], "PROFILENAME": ["A"]})
    mocker.patch.object(
        part_enriched, "load_enriched_parts_dataframe", return_value=base_df
    )
    mocker.patch.object(
        part_enriched.mdbtools,
        "list_mdb_tables",
        return_value=["PART_Det", "EXTRA_Det"],
    )
    mocker.patch.object(
        part_enriched,
        "load_table_dataframe",
        return_value=pd.DataFrame({"PARTNAME": ["A"], "VAL": [1]}),
    )
    mocker.patch.object(pd.DataFrame, "merge", side_effect=ValueError("merge exploded"))

    base = part_enriched.load_wide_editor_dataframe(tmp_path)

    # Nothing was merged, so no EXTRA_Det columns appeared ...
    assert list(base.columns) == ["PARTNAME", "PROFILENAME"]
    logged = _logged_text(warn_spy)
    assert "merge failed" in logged
    # ... and the summary reports 0 merged, not 1.
    assert "EXTRA_Det (merge)" in logged
    assert "0 merged" in logged


def test_wide_read_failure_is_logged_and_not_counted(mocker, tmp_path):
    """Same rule for a table that could not be read at all."""
    warn_spy = mocker.spy(logger, "warning")
    mocker.patch.object(
        part_enriched,
        "load_enriched_parts_dataframe",
        return_value=pd.DataFrame({"PARTNAME": ["A"], "PROFILENAME": ["A"]}),
    )
    mocker.patch.object(
        part_enriched.mdbtools,
        "list_mdb_tables",
        return_value=["PART_Det", "EXTRA_Det"],
    )
    mocker.patch.object(
        part_enriched,
        "load_table_dataframe",
        side_effect=OSError("mdb locked"),
    )

    base = part_enriched.load_wide_editor_dataframe(tmp_path)

    assert list(base.columns) == ["PARTNAME", "PROFILENAME"]
    logged = _logged_text(warn_spy)
    assert "read failed" in logged
    assert "EXTRA_Det (read)" in logged
    assert "0 merged" in logged


# ---------------------------------------------------------------------------
# 3.8 — registry discovery may be retried
# ---------------------------------------------------------------------------


def test_ensure_discovered_retries_after_failure(monkeypatch):
    monkeypatch.delattr(registry.ensure_discovered, "_done", raising=False)
    attempts = {"n": 0}

    def _flaky():
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("builtin parser import failed")

    monkeypatch.setattr(registry, "_import_builtin_modules", _flaky)
    monkeypatch.setattr(registry, "_load_user_scripts", lambda _d: None)

    with pytest.raises(RuntimeError):
        registry.ensure_discovered()
    assert getattr(registry.ensure_discovered, "_done", False) is False

    registry.ensure_discovered()
    assert registry.ensure_discovered._done is True
    assert attempts["n"] == 2
    monkeypatch.delattr(registry.ensure_discovered, "_done", raising=False)


# ---------------------------------------------------------------------------
# 2.8 — outline_resolve aggregates instead of logging per package
# ---------------------------------------------------------------------------


def test_outline_fallback_logs_one_line_per_outcome(mocker, tmp_path):
    info_spy = mocker.spy(logger, "info")
    mocker.patch(
        "pcb_preview.outline_resolve._hanwha_outline_for_name",
        return_value=(None, ["P1"]),
    )
    mocker.patch.object(
        outline_resolve,
        "footprint_name_keys",
        side_effect=lambda k: [k],
    )
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "vision.sqlite").write_bytes(b"x")

    outline = outline_resolve.FootprintOutlineMM(source="vspd", bbox=None)
    result = {f"P{i}": outline for i in range(30)}

    stats = outline_resolve._apply_hanwha_mdb_fallback(
        result, cache_dir=str(cache), group_to_profile={}
    )

    assert stats["misses"] == 30
    assert info_spy.call_count == 1
    fmt, count, listed = info_spy.call_args.args[:3]
    assert "%d package(s)" in fmt
    assert count == 30
    assert "(+20 more)" in listed
    assert listed.count("[was vspd, tried P1]") == 10  # capped, not per-item


# ---------------------------------------------------------------------------
# 4.4 — tie-break compares four keys
# ---------------------------------------------------------------------------


def test_same_normalized_spelling_is_still_ambiguous():
    hit = clean_component.match_hanwha_mdb_partname("xxPARTAxx", {"PART-A", "PART_A"})
    assert hit is not None
    assert hit[1] == "AMBIGUOUS hanwha_mdb"


def test_different_parts_of_equal_length_are_not_ambiguous():
    """Two distinct parts that merely share a length are resolved, not flagged."""
    hit = clean_component.match_hanwha_mdb_partname(
        "xx IC_ABCxx and IC_XYZxx", {"IC_ABC", "IC_XYZ"}
    )
    assert hit is not None
    assert hit[1] != "AMBIGUOUS hanwha_mdb"
    assert hit[0] in {"IC_ABC", "IC_XYZ"}
