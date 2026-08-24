"""Tests for regex_master parser arbiter (clean_arbiter + clean_one flags)."""

from __future__ import annotations

import os
import sys

tests_path = os.path.dirname(os.path.realpath(__file__))
_boomer_root = os.path.dirname(tests_path)
sys.path.insert(0, os.path.join(_boomer_root, "src"))

import clean_arbiter  # noqa: E402
from clean_types import CleanConfig, DEFAULT_CLEAN_PIPELINE  # noqa: E402
import clean_component  # noqa: E402


def test_pick_best_prefers_vendor_over_weak_regex_res():
    cand_v = clean_arbiter.ParserCandidate(
        name="vendor_pn",
        tier="vendor",
        cleaned="0402_10K_1%",
        type_tag="RESISTOR",
        part_code="RES",
        source_note="pn",
        slots={"p0": "0402", "p1": "10K", "p2": "1%"},
    )
    cand_r = clean_arbiter.ParserCandidate(
        name="regex_res",
        tier="regex_rcl",
        cleaned="1%",
        type_tag="RESISTOR",
        part_code="RES",
        source_note="regex",
        slots={"%": "1%"},
    )
    picked = clean_arbiter.pick_best([cand_r, cand_v])
    assert picked is not None
    assert picked[0].tier == "vendor"


def test_pick_best_other_beats_resistor_only_tolerance():
    cand_r = clean_arbiter.ParserCandidate(
        name="regex_res",
        tier="regex_rcl",
        cleaned="1%",
        type_tag="RESISTOR",
        part_code="RES",
        source_note="regex",
        slots={"%": "1%"},
    )
    cand_o = clean_arbiter.ParserCandidate(
        name="regex_other",
        tier="regex_other",
        cleaned="CJ3401A",
        type_tag="OTHER",
        part_code="OTHER",
        source_note="other",
        slots={"mpn": "CJ3401A"},
    )
    picked = clean_arbiter.pick_best([cand_r, cand_o])
    assert picked is not None
    assert picked[0].tier == "regex_other"


def test_regex_master_clean_one_inference_path():
    cfg = CleanConfig(
        clean_pipeline_order=DEFAULT_CLEAN_PIPELINE,
        clean_pipeline_disabled=(),
        regex_master_enabled=True,
        regex_master_preview_scores=False,
        use_pn_codecs=False,
    )
    s = "RES 0402 12.5K OHM +/- 1%"
    quad = clean_component.clean_one(s, cfg)
    assert quad[0]
    assert "0402" in quad[0]


def test_parse_resistor_token_fields_slots():
    cfg = CleanConfig()
    sl, out = clean_component.parse_resistor_token_fields("100R+1/16W+0402+1%", cfg)
    assert sl
    assert out
