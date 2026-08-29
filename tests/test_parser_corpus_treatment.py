"""Regression tests for clean corpus parser treatments (P0, P1, P2 fixes)."""

from __future__ import annotations

import pytest
from tools.clean_corpus_lib import load_corpus_profile

import clean_component


@pytest.fixture
def corpus_cfg():
    return load_corpus_profile()


def test_p0_yageo_resistor_124rl(corpus_cfg):
    """RC0402FR-07124RL must decode as 124 ohms (not E24 120k)."""
    orig = "RES_124R_+/-1%_1/16W_R0402_SMD_RC0402FR-07124RL | 国巨(YAGEO) | RC0402FR-07124RL"
    cleaned, typ, code, src = clean_component.clean_one(orig, corpus_cfg)
    assert typ == "RESISTOR"
    assert code == "RES"
    assert "124R" in cleaned
    assert "120K" not in cleaned
    assert cleaned == "0402_124R_1/16W_1%"


def test_p0_pl_inductors(corpus_cfg):
    """PL_* power-inductor rows must be classified as INDUCTOR and extract all slots."""
    cases = [
        (
            "PL_1uH_+/-20%_7mΩ_13A_SCCT0630-1R0M_0630_SMD | 国巨(YAGEO) | SCCT0630-1R0M",
            "0630_1uH_20%_13A_7mΩ",
        ),
        (
            "PL_1uH_+-20%_9mΩ_12A_SCCT0630-1R0M_SMD | 国巨(YAGEO) | SCCT0630-1R0M",
            "0630_1uH_20%_12A_9mΩ",
        ),
        (
            "PL_1uH_+/-20%_6.5mΩ_12A_STPI1003-1R0M-A_SMD | 顺络 | STPI1003-1R0M-A",
            "1003_1uH_20%_12A_6.5mΩ",
        ),
        (
            "PL_0.68uH_+/-20%_4.5mΩ_17A_SCCT0630-R68M_0630_SMD | 国巨(YAGEO) | SCCT0630-R68M",
            "0630_0.68uH_20%_17A_4.5mΩ",
        ),
        (
            "PL_2.2uH_+/-20%_15mΩ_8.5A_STPI0630-2R2M_0630_SMD | 顺络 | STPI0630-2R2M",
            "0630_2.2uH_20%_8.5A_15mΩ",
        ),
        (
            "PL_2.2uH_+/-20%_12mΩ_10A_STPI1003-2R2M-A_SMD | 顺络 | STPI1003-2R2M-A",
            "1003_2.2uH_20%_10A_12mΩ",
        ),
    ]
    for orig, expected in cases:
        cleaned, typ, code, src = clean_component.clean_one(orig, corpus_cfg)
        assert typ == "INDUCTOR", f"Wrong type for {orig}: {typ}"
        assert code == "IND"
        assert cleaned == expected, f"Expected {expected!r}, got {cleaned!r}"


def test_p1_netres_package_retention(corpus_cfg):
    """NETRES rows must retain 0402 package."""
    cases = [
        ("NETRES-SMD 0402-8P4R 33 OHM +/-5% LEAD-FREE - Y01", "0402_33R_5%"),
        ("NETRES-SMD 0402-8P4R 10K OHM +/-5% LEAD-FREE - Y01", "0402_10K_5%"),
        ("NETRES-SMD 0402-8P4R 100 OHM +/-5% LEAD-FREE - Y01", "0402_100R_5%"),
        ("NETRES-SMD 0402-8P4R 4.7K OHM +/-5% LEAD-FREE - Y01", "0402_4.7K_5%"),
    ]
    for orig, expected in cases:
        cleaned, typ, code, src = clean_component.clean_one(orig, corpus_cfg)
        assert typ == "RESISTOR"
        assert cleaned == expected


def test_p1_hv_cap_and_package_retention(corpus_cfg):
    """HV capacitors (3KV) and MLCC bare packages must be parsed without truncation."""
    cases = [
        (
            "CAP-SMD 1812 2200PF/3KV +/-10% X7R LEAD-FREE - 402(HCM1812X7R222K302PT)",
            "1812_2200pF_X7R_10%_3KV",
        ),
        (
            "MLCC 22uF/6.3V 0603 X5R 20% / TAIYO/JDK107BBJ226MA-T",
            "0603_22uF_X5R_20%_6.3V",
        ),
        (
            "MLCC 100UF/6.3V 1206 X5R 20% / MURATA/GRM31CR60J107ME39L",
            "1206_100uF_X5R_20%_6.3V",
        ),
    ]
    for orig, expected in cases:
        cleaned, typ, code, src = clean_component.clean_one(orig, corpus_cfg)
        assert typ == "CAP"
        assert cleaned == expected


def test_p1_sunlord_sdnt_thermistor(corpus_cfg):
    """Sunlord SDNT series thermistors must be routed to thermistor parser."""
    orig = "CHIP NTC Thermistor_47K_+/-1%_4050_1%_25/50_R0402 | 顺络 | SDNT1005X473F4050FTF"
    cleaned, typ, code, src = clean_component.clean_one(orig, corpus_cfg)
    assert typ == "OTHER"
    assert src == "thermistor"
    assert cleaned == "SDNT1005X473F4050FTF"


def test_p1_join_watt_preservation(corpus_cfg):
    """Watt from join-mode comments must be preserved in vendor output."""
    cases = [
        (
            "RES_68R_+/-1%_1/16W_R0402_SMD | 华科 | WR04X68R0FTL",
            "0402_68R_1/16W_1%",
        ),
        (
            "RES_0R_1/16W_R0402_SMD | 华科 | WR04X0000FTL",
            "0402_0R_1/16W_1%",
        ),
    ]
    for orig, expected in cases:
        cleaned, typ, code, src = clean_component.clean_one(orig, corpus_cfg)
        assert typ == "RESISTOR"
        assert src == "vendor"
        assert cleaned == expected


def test_p2_poscap_tantalum_capacitors(corpus_cfg):
    """POSCAP tantalum capacitors must be classified as CAP with case codes."""
    cases = [
        (
            "POSCAP 330UF/2.5V (3528/B) 20% | PANASONIC/ETPE330MA9GB(9mohm)",
            "3528/B_330uF_20%_2.5V",
        ),
        (
            "POSCAP 330UF/6.3V (7343/D) 20% | SANYO/6TPE330MAP(85℃)",
            "7343/D_330uF_20%_6.3V",
        ),
        (
            "POSCAP 100UF/6.3V (3528/B) 20% | SANYO/6TPE100MAZB(35mohm)",
            "3528/B_100uF_20%_6.3V",
        ),
        (
            "POSCAP 220UF/6.3V (7343/D) 20% | PANASONIC/6TPE220MAP",
            "7343/D_220uF_20%_6.3V",
        ),
        (
            "POSCAP 47UF/6.3V (3528/B) 20% | PANASONIC/6TPE47MAP",
            "3528/B_47uF_20%_6.3V",
        ),
        (
            "POSCAP 150uF/6.3V 20% 3528/B | SANYO/6TPE150MAZB",
            "3528/B_150uF_20%_6.3V",
        ),
        (
            "POSCAP 47UF/10V (7343/D) 20% | PANASONIC/10TPE47MAP",
            "7343/D_47uF_20%_10V",
        ),
        (
            "POSCAP 47uF/25V (7343/D) 20% | PANASONIC/25TQC47MV",
            "7343/D_47uF_20%_25V",
        ),
    ]
    for orig, expected in cases:
        cleaned, typ, code, src = clean_component.clean_one(orig, corpus_cfg)
        assert typ == "CAP"
        assert cleaned == expected
