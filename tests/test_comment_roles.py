"""Joined comments: the roles come from the content, not the position (A2).

A row joined as `description | MPN` used to be split back as prose=parts[0],
mpn=parts[-1]. With the columns written the other way round both roles inverted:
the classifier saw the MPN as if it were prose, so its anchored rules missed, and
measured on the CO1271 order the reversed join gave

    vendor 0, other 196, OTHER 199, RESISTOR 9

instead of the natural order's `vendor 180, other 74, RESISTOR 125`.

Rows with no decoder for their type were also hurt in either order: the regex
phase parsed the description and returned a fragment of it (`H3.2`,
`AL6063-T5_PAD`) where the part number is what should survive.
"""

from __future__ import annotations

import os
import sys

tests_path = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(tests_path), "src"))

import clean_component  # noqa: E402
from parsers.bom_text_utils import (  # noqa: E402
    joined_clean_comment_bom_prose,
    joined_clean_comment_mpn,
    looks_like_part_number,
    split_joined_clean_comment,
)
from services.clean_config import build_clean_config  # noqa: E402

DESCR = "RES_100K_+/-1%_1/16W_R0402_SMD"
MPN = "0402WGF1004TCE"
SEP = " | "


def _cfg(**over):
    kw = dict(
        res_template=("pack", "nom", "%", "none"),
        cap_template=("pack", "nom", "V", "film", "%"),
        ind_template=("pack", "nom", "%", "Imax", "DCR"),
        use_pn_codecs=True,
        use_vendor_pn=True,
        use_component_library=True,
        use_hanwha_mdb=True,
        hanwha_partial_match=True,
        clean_pipeline_order=("vendor", "inferit", "library", "hanwha", "regex"),
        clean_pipeline_disabled=(),
        output_separator="_",
    )
    kw.update(over)
    return build_clean_config(**kw)


# --------------------------------------------------------------------------
# the predicate
# --------------------------------------------------------------------------


def test_part_numbers_are_recognised():
    for mpn in (
        "0402WGF1004TCE",
        "CL05A105KA5NQNC",
        "GRM188R6YA106MA73D",
        "DXB101_MB_V11_20260527A",
        "FH82HM770_SRM8M",
        "JRH-LL0-0016",
        "RT8237EZQW(2)",
        "801000641",  # bare numeric, five digits or more
    ):
        assert looks_like_part_number(mpn), mpn


def test_descriptions_are_not_recognised():
    for descr in (
        DESCR,
        "MLCC_1uF_X5R_25V_\u00b110%_C0402_0.5\u00b10.1MM_SMD",
        "Thermal Module_PCH_Sink_Plate AL6063-T5_PAD",
        "APD_KG_CPU_13500HX_Intel_Raptor Lake HX_Chipset_PCH_HM770_28x25mm_SMD",
        "SCAP_560uF_Polymer aluminum solid electrolytic capacitor_2.5V_+/-20%",
        "PCB_DXB101_MB_V11_20260527A-GBR_6Layer_Matte Black_ENIG_single_170x170x1.6mm",
        "H3.2",
        "",
        None,
        " ",
        "12",  # too short to be a bare numeric part number
    ):
        assert not looks_like_part_number(descr), repr(descr)


def test_too_long_is_not_a_part_number():
    assert not looks_like_part_number("A" * 65)


# --------------------------------------------------------------------------
# role detection
# --------------------------------------------------------------------------


def test_prose_first_is_split_the_old_way():
    assert split_joined_clean_comment(f"{DESCR}{SEP}{MPN}") == (DESCR, "", MPN)


def test_mpn_first_is_split_by_content_not_position():
    assert split_joined_clean_comment(f"{MPN}{SEP}{DESCR}") == (DESCR, "", MPN)


def test_mpn_first_with_a_vendor_label_keeps_the_label():
    joined = f"{MPN}{SEP}Royal Ohm{SEP}{DESCR}"
    assert split_joined_clean_comment(joined) == (DESCR, "Royal Ohm", MPN)


def test_prose_first_with_a_vendor_label_is_unchanged():
    joined = f"{DESCR}{SEP}Royal Ohm{SEP}{MPN}"
    assert split_joined_clean_comment(joined) == (DESCR, "Royal Ohm", MPN)


def test_ambiguous_segments_fall_back_to_position():
    """Neither half is part-number shaped: keep the documented order."""
    a = "H3.2"
    b = "AL6063-T5_PAD"
    assert split_joined_clean_comment(f"{a}{SEP}{b}") == (a, "", b)


def test_both_halves_part_number_shaped_falls_back_to_position():
    """Only an unambiguous single MPN is allowed to move the roles."""
    first, second = "0402WGF1004TCE", "0603WAF220JT5E"
    assert looks_like_part_number(first) and looks_like_part_number(second)
    assert split_joined_clean_comment(f"{first}{SEP}{second}") == (first, "", second)


def test_helpers_agree_on_both_orders():
    natural = f"{DESCR}{SEP}{MPN}"
    reversed_ = f"{MPN}{SEP}{DESCR}"
    for joined in (natural, reversed_):
        assert joined_clean_comment_bom_prose(joined) == DESCR
        assert joined_clean_comment_mpn(joined) == MPN


# --------------------------------------------------------------------------
# the effect on cleaning
# --------------------------------------------------------------------------


def test_order_does_not_change_the_answer_for_a_resistor():
    natural = f"{DESCR}{SEP}{MPN}"
    reversed_ = f"{MPN}{SEP}{DESCR}"
    a = clean_component.clean_one(natural, _cfg())
    b = clean_component.clean_one(reversed_, _cfg())
    assert a == b
    assert a[3] == "vendor"
    assert a[0] == "0402_1M_1%"


def test_an_undecodable_type_keeps_the_mpn_not_a_description_fragment():
    """Joined or not, an identity that nothing can decode must survive intact."""
    mpn = "MDXB101003"
    descr = "CKD_PCBA(MB)_DXB101_MainBoard_KG i5 13500HX_For APD AIO_DDR4"

    solo = clean_component.clean_one(mpn, _cfg())
    joined = clean_component.clean_one(f"{descr}{SEP}{mpn}", _cfg())
    assert solo[0] == mpn
    assert joined[0] == mpn, "the description leaked into Cleaned"
    assert "CKD_PCBA" not in joined[0]

    reversed_ = clean_component.clean_one(f"{mpn}{SEP}{descr}", _cfg())
    assert reversed_[0] == mpn, "reversed join leaked the description"


def test_description_still_supplies_values_when_the_type_can_decode_them():
    """The description is not thrown away - it is what fills in the missing fields."""
    mpn = "MCSM52Z2R2M"
    # Real description cell from the CO1271 order.
    descr = "PL_2.2uH_20_50.1mΩ_4.2A_12.5A_5x5mm_2.0mm_SMD"
    joined = clean_component.clean_one(f"{descr}{SEP}{mpn}", _cfg())
    assert joined[3] == "regex"
    assert "2.2UH" in joined[0].upper(), joined[0]


def test_the_answer_is_the_same_whichever_column_is_written_first():
    rows = [
        (DESCR, MPN),
        (
            "SCAP_560uF_Polymer_2.5V_+/-20%_3.9A_DIP_2R5AREA561M0606P28",
            "2R5AREA561M0606P28",
        ),
        ("MLCC_1uF_X5R_25V_\u00b110%_C0402_0.5\u00b10.1MM_SMD", "CL05A105KA5NQNC"),
    ]
    for descr, mpn in rows:
        a = clean_component.clean_one(f"{descr}{SEP}{mpn}", _cfg())
        b = clean_component.clean_one(f"{mpn}{SEP}{descr}", _cfg())
        assert a == b, (descr, mpn, a, b)
