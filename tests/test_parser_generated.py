"""Every datasheet/*.md sample row must parse (vendor or regex path)."""

from __future__ import annotations

from dataclasses import replace

import pytest
from tools.clean_corpus_lib import load_corpus_profile
from tools.gen_parser_fixtures import load_all_samples, noise_variants

import clean_component
import pn_original


def _vendor_cfg():
    cfg = load_corpus_profile()
    return replace(
        cfg,
        use_hanwha_mdb=False,
        hanwha_partnames=None,
        clean_pipeline_disabled=tuple(
            sorted(set(cfg.clean_pipeline_disabled) | {"hanwha"})
        ),
    )


def _regex_cfg():
    cfg = _vendor_cfg()
    return replace(
        cfg,
        clean_pipeline_disabled=tuple(
            sorted(set(cfg.clean_pipeline_disabled) | {"hanwha", "vendor"})
        ),
        infer_resistor_watt_from_package=False,
    )


SAMPLES = load_all_samples()
assert SAMPLES, "datasheet/*.md has no ## samples tables"


@pytest.mark.parametrize(
    "rec",
    SAMPLES,
    ids=[f"{r.get('file','')}:{r.get('mpn_or_bom','')[:40]}" for r in SAMPLES],
)
def test_datasheet_sample_row(rec: dict[str, str]) -> None:
    raw = rec["mpn_or_bom"]
    ctype = rec["ctype"].strip().upper()
    expected = rec["expected"].strip()
    path = rec.get("path", "vendor").strip().lower()
    if path == "vendor":
        pn_original.CONVERTERS.clear()
        pn_original.load_converters()
        cfg = _vendor_cfg()
        if " | " in raw or raw.upper().startswith(("RES", "CAP", "MLCC", "NETRES")):
            cleaned, typ, _c, _src = clean_component.clean_one(raw, cfg)
            assert expected in cleaned or cleaned == expected
        else:
            ct = "RES" if ctype.startswith("RES") else "CAP" if ctype.startswith("CAP") else ctype
            out = pn_original.parse_pn(raw, ct, cfg)
            assert out, f"vendor parse failed for {raw!r}"
            assert out == expected or expected in out
    else:
        cfg = _regex_cfg()
        for variant in noise_variants(raw):
            cleaned, typ, _c, src = clean_component.clean_one(variant, cfg)
            assert cleaned == expected, (variant, cleaned, expected)
            assert src == "regex"
