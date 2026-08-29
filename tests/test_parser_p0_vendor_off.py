"""Vendor-off regex: join rows 1199–1214 style (no Hanwha)."""

from __future__ import annotations

from dataclasses import replace

import pytest
from tools.clean_corpus_lib import load_corpus_profile

import clean_component
from parsers.chip_tokens import expand_compact_rkm, match_package_token
from parsers.si_units import (
    convert_nf_token_to_uf,
    quantity_farads,
    quantity_ohms,
    quantity_volts,
    unit_registry,
)


@pytest.fixture
def vendor_off_cfg():
    base = load_corpus_profile()
    disabled = tuple(
        sorted(set(base.clean_pipeline_disabled) | {"hanwha", "vendor"})
    )
    return replace(
        base,
        use_hanwha_mdb=False,
        hanwha_partnames=None,
        infer_resistor_watt_from_package=False,
        clean_pipeline_disabled=disabled,
    )


VENDOR_OFF_JOIN_ROWS = [
    (
        "RES_22K_+/-5%_1/16W_R0402_SMD | 厚声(UniOhm) | 0402WGJ0223TCE",
        "0402_22K_1/16W_5%",
    ),
    (
        "RES_39K2_+/-1%_1/16W_R0402_SMD | 厚声(UniOhm) | 0402WGF3922TCE",
        "0402_39.2K_1/16W_1%",
    ),
    (
        "RES_75R_+/-5%_1/16W_R0402_SMD | 厚声(UniOhm) | 0402WGJ0750TCE",
        "0402_75R_1/16W_5%",
    ),
    (
        "RES_6K2_+/-1%_1/16W_R0402_SMD | 华科(Walsin) | WR04X6201FTL",
        "0402_6.2K_1/16W_1%",
    ),
    (
        "RES_20K_+/-1%_1/16W_R0402_SMD | 厚声(UniOhm) | 0402WGF2002TCE",
        "0402_20K_1/16W_1%",
    ),
    (
        "RES_2K49_+/-1%_1/16W_R0402_SMD | 华科(Walsin) | WR04X2491FTL",
        "0402_2.49K_1/16W_1%",
    ),
    (
        "RES_4K7_+/-5%_1/16W_R0402_SMD | 厚声(UniOhm) | 0402WGJ0472TCE",
        "0402_4.7K_1/16W_5%",
    ),
    (
        "RES_100K_+/-5%_1/16W_R0402_SMD | 厚声(UniOhm) | 0402WGJ0104TCE",
        "0402_100K_1/16W_5%",
    ),
    (
        "RES_1M_+/-5%_1/16W_R0402_SMD | 厚声(UniOhm) | 0402WGJ0105TCE",
        "0402_1M_1/16W_5%",
    ),
    (
        "RES_0R_+/-5%_1/16W_R0402_SMD | 厚声(UniOhm) | 0402WGJ0000TCE",
        "0402_0R_1/16W_5%",
    ),
    (
        "RES_33R_+/-5%_1/16W_R0402_SMD | 厚声(UniOhm) | 0402WGJ0330TCE",
        "0402_33R_1/16W_5%",
    ),
    (
        "RES_0R_+/-5%_1/10W_R0603_SMD | 厚声(UniOhm) | 0603WAJ0000T5E",
        "0603_0R_1/10W_5%",
    ),
    (
        "RES_2K2_+/-5%_1/16W_R0402_SMD | 厚声(UniOhm) | 0402WGJ0222TCE",
        "0402_2.2K_1/16W_5%",
    ),
    (
        "RES_10K_+/-1%_1/16W_R0402_SMD | 厚声(UniOhm) | 0402WGF1002TCE",
        "0402_10K_1/16W_1%",
    ),
    (
        "RES_1K_+/-1%_1/16W_R0402_SMD | 厚声(UniOhm) | 0402WGF1001TCE",
        "0402_1K_1/16W_1%",
    ),
    (
        "RES_4K99_+/-1%_1/16W_R0402_SMD | 厚声(UniOhm) | 0402WGF4991TCE",
        "0402_4.99K_1/16W_1%",
    ),
]


@pytest.mark.parametrize("orig,expected", VENDOR_OFF_JOIN_ROWS)
def test_vendor_off_join_res_r0402(vendor_off_cfg, orig, expected):
    cleaned, typ, _code, src = clean_component.clean_one(orig, vendor_off_cfg)
    assert typ == "RESISTOR"
    assert src == "regex"
    assert cleaned == expected


def test_watt_from_package_checkbox_off_by_default(vendor_off_cfg):
    orig = "RES 0402 10K OHM +/-1%"
    cleaned, typ, _c, src = clean_component.clean_one(orig, vendor_off_cfg)
    assert typ == "RESISTOR"
    assert "W" not in cleaned
    assert cleaned == "0402_10K_1%"


def test_watt_from_package_checkbox_on(vendor_off_cfg):
    cfg = replace(vendor_off_cfg, infer_resistor_watt_from_package=True)
    orig = "RES 0402 10K OHM +/-1%"
    cleaned, typ, _c, src = clean_component.clean_one(orig, cfg)
    assert cleaned == "0402_10K_1/16W_1%"


def test_expand_compact_rkm_samples():
    assert expand_compact_rkm("39K2") == "39.2K"
    assert expand_compact_rkm("2K2") == "2.2K"
    assert expand_compact_rkm("2K49") == "2.49K"
    assert expand_compact_rkm("4K7") == "4.7K"
    assert expand_compact_rkm("4K99") == "4.99K"
    assert expand_compact_rkm("49R9") == "49.9R"
    assert expand_compact_rkm("10K") is None
    assert match_package_token("R0402") == "0402"
    assert match_package_token("C0603") == "0603"


def test_pint_nf_and_voltage():
    assert convert_nf_token_to_uf("1000NF") == "1UF"
    q = quantity_farads("22nF")
    assert q is not None
    assert abs(q.to("nanofarad").magnitude - 22) < 1e-9
    v = quantity_volts("3KV")
    assert v is not None
    assert abs(v.to("volt").magnitude - 3000) < 1e-6


def test_pint_registry_lazy_load():
    assert unit_registry() is unit_registry()


def test_pint_capacitor_invalid_returns_none():
    assert quantity_farads("22") is None
    assert quantity_farads("22X") is None
    assert quantity_farads("") is None


def test_convert_nf_to_uf_matrix():
    assert convert_nf_token_to_uf("22NF") == "0.022UF"
    assert convert_nf_token_to_uf("1NF") == "0.001UF"
    assert convert_nf_token_to_uf("100NF") == "0.1UF"
    assert convert_nf_token_to_uf("not_a_value") == "not_a_value"


def test_pint_ohm_prefixes():
    q = quantity_ohms("10R")
    assert q is not None
    assert abs(q.to("ohm").magnitude - 10) < 1e-9
    qk = quantity_ohms("4.7K")
    assert qk is not None
    assert abs(qk.to("ohm").magnitude - 4700) < 1e-6
    qm = quantity_ohms("1M")
    assert qm is not None
    assert abs(qm.to("ohm").magnitude - 1_000_000) < 1e-3
    assert quantity_ohms("") is None
