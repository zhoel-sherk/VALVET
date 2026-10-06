"""Tests for pcb_preview.footprint_db (SQLite cache + aliases, no Qt)."""

from __future__ import annotations

import json
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pcb_preview.footprint_db import (
    FootprintStore,
    default_data_dir,
    normalize_footprint_key,
)
from pcb_preview.footprint_heuristic import _CHIP_MM
from pcb_preview.types import BBoxMM, FootprintOutlineMM, PadRectMM, StrokeLineMM


def _outline_payload(source: str = "kicad_mod") -> str:
    return json.dumps(
        {
            "lines": [{"x1": -1.0, "y1": -0.5, "x2": 1.0, "y2": -0.5}],
            "circles": [],
            "pads": [
                {
                    "cx": -0.8,
                    "cy": 0.0,
                    "width_mm": 0.4,
                    "height_mm": 0.5,
                    "rotation_deg": 0.0,
                    "number": "1",
                }
            ],
            "bbox": {"min_x": -1.0, "min_y": -0.5, "max_x": 1.0, "max_y": 0.5},
            "source": source,
        }
    )


def _insert(store: FootprintStore, key: str, norm_key: str, payload: str) -> None:
    store._conn.execute(
        "INSERT INTO footprints (key, norm_key, outline_json) VALUES (?, ?, ?)",
        (key, norm_key, payload),
    )
    store._conn.commit()


@pytest.fixture
def store(tmp_path):
    s = FootprintStore(tmp_path / "fpdata")
    yield s
    s.close()


# --------------------------------------------------------------------------
# normalize_footprint_key
# --------------------------------------------------------------------------


def test_normalize_collapses_case_backslashes_and_whitespace() -> None:
    assert normalize_footprint_key("R0402") == "r0402"
    assert normalize_footprint_key("lib\\footprints\\R_0402.kicad_mod") == (
        "lib/footprints/r_0402.kicad_mod"
    )
    assert normalize_footprint_key("R  0402") == "r 0402"
    assert normalize_footprint_key("R\t0402") == "r 0402"
    assert normalize_footprint_key("R\n\n 0402") == "r 0402"
    assert normalize_footprint_key("  R0402  ") == "r0402"


def test_normalize_tolerates_empty_and_none() -> None:
    assert normalize_footprint_key("") == ""
    assert normalize_footprint_key(None) == ""  # type: ignore[arg-type]
    assert normalize_footprint_key("   ") == ""


def test_normalize_is_idempotent() -> None:
    for raw in ("  Lib\\FOOT   Prints\\R_0402 ", "LED-1210", "", "\\"):
        once = normalize_footprint_key(raw)
        assert normalize_footprint_key(once) == once


def test_distinct_keys_normalize_to_the_same_string() -> None:
    assert normalize_footprint_key("R 0402") == normalize_footprint_key("R  0402")
    assert normalize_footprint_key("R\\0402") == "r/0402"


# --------------------------------------------------------------------------
# default_data_dir
# --------------------------------------------------------------------------


def test_default_data_dir_creates_footprints_dir(tmp_path) -> None:
    base = tmp_path / "root"
    out = default_data_dir(base)
    assert out == base
    assert (out / "footprints").is_dir()
    assert default_data_dir(base) == base  # idempotent


def test_default_data_dir_uses_app_paths_when_no_base(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app_paths.pcb_preview_data_root", lambda: tmp_path / "state")
    out = default_data_dir()
    assert out == tmp_path / "state"
    assert (out / "footprints").is_dir()


# --------------------------------------------------------------------------
# FootprintStore: schema + lifecycle
# --------------------------------------------------------------------------


def test_constructor_creates_table_and_index(tmp_path) -> None:
    s = FootprintStore(tmp_path / "d")
    try:
        assert (tmp_path / "d" / "footprints.sqlite3").is_file()
        tables = {
            r[0]
            for r in s._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "footprints" in tables
        indexes = {
            r[0]
            for r in s._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
        assert "idx_norm" in indexes
        cols = [r[1] for r in s._conn.execute("PRAGMA table_info(footprints)")]
        assert cols == [
            "key",
            "norm_key",
            "source_path",
            "sha256",
            "outline_json",
            "min_x",
            "min_y",
            "max_x",
            "max_y",
        ]
    finally:
        s.close()


def test_constructor_is_idempotent_on_the_same_dir(tmp_path) -> None:
    first = FootprintStore(tmp_path / "d")
    _insert(first, "K1", "k1", _outline_payload())
    first.close()

    second = FootprintStore(tmp_path / "d")
    try:
        n = second._conn.execute("SELECT COUNT(*) FROM footprints").fetchone()[0]
        assert n == 1
    finally:
        second.close()


def test_close_closes_the_connection(tmp_path) -> None:
    s = FootprintStore(tmp_path / "d")
    s.close()
    with pytest.raises(sqlite3.ProgrammingError):
        s._conn.execute("SELECT 1 FROM footprints")


def test_default_outline_when_name_is_empty(store: FootprintStore) -> None:
    assert store.lookup_outline("") == FootprintOutlineMM(source="none")
    assert store.lookup_outline("   ").source == "none"
    assert store.lookup_outline(None).source == "none"  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# lookup: DB tiers
# --------------------------------------------------------------------------


def test_exact_key_resolves(store: FootprintStore) -> None:
    _insert(store, "lib:LED_1210", "lib:led_1210", _outline_payload("hanwha_upd"))
    out = store.lookup_outline("lib:LED_1210")
    assert out.source == "hanwha_upd"
    assert out.bbox == BBoxMM(-1.0, -0.5, 1.0, 0.5)
    assert len(out.lines) == 1
    assert isinstance(out.lines[0], StrokeLineMM)
    assert out.pads == (PadRectMM(-0.8, 0.0, 0.4, 0.5, 0.0, "1"),)
    assert out.circles == ()


def test_normalized_key_resolves_a_row_stored_only_by_norm_key(
    store: FootprintStore,
) -> None:
    _insert(store, "x", "lib/led_1210", _outline_payload("kicad_mod"))
    assert store.lookup_outline("LIB/LED_1210").source == "kicad_mod"
    assert store.lookup_outline("lib\\led_1210").source == "kicad_mod"


def test_missing_source_key_defaults_to_none(store: FootprintStore) -> None:
    payload = json.dumps(
        {
            "lines": [],
            "pads": [],
            "bbox": {"min_x": 0.0, "min_y": 0.0, "max_x": 1.0, "max_y": 1.0},
        }
    )
    _insert(store, "k", "k", payload)
    out = store.lookup_outline("k")
    assert out.source == "none"
    assert out.bbox == BBoxMM(0.0, 0.0, 1.0, 1.0)


def test_unknown_source_string_flows_through_unvalidated(store: FootprintStore) -> None:
    # Defect probe: _outline_from_dict does source=d.get("source", "none")
    # behind a `# type: ignore`, so the Literal is never enforced at runtime.
    _insert(store, "k", "k", _outline_payload("totally_bogus_source"))
    out = store.lookup_outline("k")
    assert out.source == "totally_bogus_source"  # not coerced to "none"
    assert out.source not in (
        "heuristic",
        "kicad_mod",
        "hanwha_upd",
        "yamaha_tou",
        "yamaha_heuristic",
        "vspd_heuristic",
        "none",
    )


# --------------------------------------------------------------------------
# aliases
# --------------------------------------------------------------------------


def test_alias_separator_forms(tmp_path) -> None:
    s = FootprintStore(tmp_path / "d")
    try:
        (tmp_path / "d" / "aliases.txt").write_text(
            "# a comment\n"
            "\n"
            "  \n"
            "ARROW_ALIAS => arrow_target\n"
            "TAB_ALIAS\tTAB TARGET  \n"
            "SPACE_ALIAS   space target\n",
            encoding="utf-8",
        )
        aliases = s._aliases()
        assert aliases["arrow_alias"] == "arrow_target"
        assert aliases["tab_alias"] == "TAB TARGET"
        assert aliases["space_alias"] == "space target"
        assert "" not in aliases
        assert not any(k.startswith("#") for k in aliases)
        assert len(aliases) == 3
    finally:
        s.close()


def test_alias_absent_file_yields_empty_map(store: FootprintStore) -> None:
    assert store._aliases() == {}


def test_alias_resolves_a_name_with_no_direct_row(store: FootprintStore) -> None:
    _insert(store, "db:REAL_0402", "db:real_0402", _outline_payload("kicad_mod"))
    (store._root / "aliases.txt").write_text(
        "SHOP ALIAS => db:REAL_0402\n", encoding="utf-8"
    )
    assert store.lookup_outline("SHOP ALIAS").source == "kicad_mod"
    assert store.lookup_outline("  shop   alias  ").source == "kicad_mod"


def test_alias_target_is_what_gets_looked_up(store: FootprintStore) -> None:
    _insert(store, "AIM", "aim", _outline_payload("kicad_mod"))
    _insert(store, "B", "b", _outline_payload("vspd_heuristic"))
    (store._root / "aliases.txt").write_text("ALIAS => AIM\n", encoding="utf-8")
    assert store.lookup_outline("ALIAS").source == "kicad_mod"


def test_alias_chain_respects_direct_hit_first(store: FootprintStore) -> None:
    _insert(store, "SHOP", "shop", _outline_payload("hanwha_upd"))
    _insert(store, "REAL", "real", _outline_payload("kicad_mod"))
    (store._root / "aliases.txt").write_text("SHOP => REAL\n", encoding="utf-8")
    assert store.lookup_outline("SHOP").source == "hanwha_upd"


def test_alias_cache_is_invalidated_when_mtime_changes(store: FootprintStore) -> None:
    path = store._root / "aliases.txt"
    path.write_text("ONE => target_one\n", encoding="utf-8")
    assert store._aliases() == {"one": "target_one"}

    path.write_text("TWO => target_two\n", encoding="utf-8")
    stat = path.stat()
    os.utime(path, (stat.st_atime, stat.st_mtime + 10))
    assert store._aliases() == {"two": "target_two"}
    assert store._aliases_mtime == path.stat().st_mtime


def test_alias_cache_is_reused_when_mtime_unchanged(store: FootprintStore) -> None:
    path = store._root / "aliases.txt"
    path.write_text("ONE => target_one\n", encoding="utf-8")
    first = store._aliases()
    assert store._aliases() is first


# --------------------------------------------------------------------------
# lookup: heuristic fallback tiers
# --------------------------------------------------------------------------


def test_unknown_name_with_chip_code_falls_through_to_heuristic(
    store: FootprintStore,
) -> None:
    out = store.lookup_outline("SHOP-ONLY-0805")
    assert out.source == "heuristic"
    length, width = _CHIP_MM["0805"]
    assert out.bbox == BBoxMM(-length / 2, -width / 2, length / 2, width / 2)


def test_unknown_name_without_chip_code_is_none(store: FootprintStore) -> None:
    out = store.lookup_outline("SOIC-8_WIDE")
    assert out.source == "none"
    assert out.lines == () and out.pads == () and out.circles == ()


def test_db_hit_beats_heuristic(store: FootprintStore) -> None:
    _insert(store, "R_0402", "r_0402", _outline_payload("hanwha_upd"))
    assert store.lookup_outline("R_0402").source == "hanwha_upd"
