"""Vendor PN parsers: Eyang, Fenghua, Viiyong, Darfon + join-row clean_one."""

from __future__ import annotations

import pytest
from tools.clean_corpus_lib import load_corpus_profile

import clean_component
import pn_original


@pytest.fixture(scope="module")
def cfg():
    pn_original.CONVERTERS.clear()
    pn_original.load_converters()
    return load_corpus_profile()


@pytest.mark.parametrize(
    "mpn,needles",
    [
        ("C0402C0G180J500NTB", ("0402", "18pF", "C0G", "5%", "50V")),
        ("C0402X7R221K500NTB", ("0402", "220pF", "X7R", "10%", "50V")),
        ("C0201X5R334M6R3NTJ", ("0201", "330nF", "X5R", "20%", "6.3V")),
        ("0402CG101J500NT", ("0402", "100pF", "C0G", "5%", "50V")),
        ("0402B223K250NT", ("0402", "22nF", "X7R", "10%", "25V")),
        ("V105K0201X5R160NXT", ("0201", "1uF", "X5R", "10%", "16V")),
        ("C1005NP0508CGTS", ("0402", "0.5pF", "C0G", "50V")),
    ],
)
def test_china_vendor_pn_parse(cfg, mpn: str, needles: tuple[str, ...]) -> None:
    from pn_original import parse_pn

    out = parse_pn(mpn, "CAP", cfg)
    assert out
    for n in needles:
        assert n in out, (mpn, out)


def test_mlcc_join_row_samsung_vendor_merge(cfg) -> None:
    s = "MLCC_2.2uF_X5R_6.3V_+/-20%_0402_0.5MM+-0.05MM_SMD | 三星(Samsung) | CL05A225MQ5NSNC"
    got = clean_component.clean_one(s, cfg)[0]
    assert got == "0402_2.2uF_X5R_20%_6.3V"


def test_mlcc_join_row_walsin_height_stack_not_broken(cfg) -> None:
    s = "MLCC_2.2uF_X7R_16V_±10%_0603_0.8+0.15/-0.10mm_SMD | 华科(Walsin) | 0603B225K160CT"
    got = clean_component.clean_one(s, cfg)[0]
    assert "0603" in got and "2.2uF" in got
    assert got.startswith("-0.1") is False


def test_darfon_join_row_classifies_cap(cfg) -> None:
    s = "MLCC_0.5pF_NP0_50V_+/-0.25pF_C0402_H0P5_SMD | 达方(Darfon) | C1005NP0508CGTS"
    cleaned, typ, _pc, src = clean_component.clean_one(s, cfg)
    assert typ == "CAP"
    assert "0.5pF" in cleaned
    assert cleaned != "DARFON"
