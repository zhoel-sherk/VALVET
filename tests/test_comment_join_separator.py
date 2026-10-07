"""Join and split must agree on the separator (A1).

A joined BOM cell is written with whatever separator the Clean options say
(``clean/double_comment_sep``), but the row was then split back apart with a
hardcoded ``" | "`` at five call sites. With a non-default separator nothing was
split, so the MPN tail was never recovered: the regex phase parsed the joined
text itself and read values out of the *description*, e.g. joined with a space
the answer was ``0402_100K_1%`` where the part number says ``0402_1M_1%``.
A wrong nominal, not merely a missing one.

Measured on the CO1271 order (bom.xlsx, SKU3, 266 rows):

    descr + mpn, sep=" | "  -> vendor 180
    descr + mpn, sep=" "    -> vendor   0
    descr + mpn, sep="~"    -> vendor 180 after the fix, 0 before
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

tests_path = os.path.dirname(os.path.realpath(__file__))
sys_path_repo = os.path.join(os.path.dirname(tests_path), "src")
import sys

if sys_path_repo not in sys.path:
    sys.path.insert(0, sys_path_repo)

import clean_component  # noqa: E402
from parsers.bom_text_utils import (  # noqa: E402
    DEFAULT_DOUBLE_COMMENT_JOIN,
    joined_clean_comment_bom_prose,
    merge_clean_comment_cell_parts,
    split_joined_clean_comment,
)
from services.clean_config import build_clean_config  # noqa: E402

DESCR = "RES_100K_+/-1%_1/16W_R0402_SMD"
MPN = "0402WGF1004TCE"


def _cfg(sep: str):
    return build_clean_config(
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
        double_comment_separator=sep,
    )


# --------------------------------------------------------------------------
# split must tolerate an unset separator
# --------------------------------------------------------------------------


def test_empty_separator_resolves_to_default_instead_of_raising():
    """ ""str.split('')"" raises ValueError; an unset separator must not crash."""
    joined = merge_clean_comment_cell_parts([DESCR, MPN], "")
    assert split_joined_clean_comment(joined, "") == (DESCR, "", MPN)
    # and the prose helper agrees, so join/split stay symmetric
    assert joined_clean_comment_bom_prose(joined, "") == DESCR


def test_empty_separator_equals_default_join():
    assert DEFAULT_DOUBLE_COMMENT_JOIN == " | "
    joined = f"{DESCR}{DEFAULT_DOUBLE_COMMENT_JOIN}{MPN}"
    assert split_joined_clean_comment(joined, "") == split_joined_clean_comment(
        joined, DEFAULT_DOUBLE_COMMENT_JOIN
    )


# --------------------------------------------------------------------------
# round trip: what was joined can be split back
# --------------------------------------------------------------------------


@pytest.mark.parametrize("sep", [" | ", "\t", "~~", "@@"])
def test_join_split_round_trip_for_a_plain_separator(sep):
    parts = [DESCR, MPN]
    joined = merge_clean_comment_cell_parts(parts, sep)
    assert joined == f"{DESCR}{sep}{MPN}"
    bom, _label, tail = split_joined_clean_comment(joined, sep)
    assert bom == DESCR
    assert tail == MPN


def test_split_without_the_separator_used_to_join_returns_one_blob():
    """The old behaviour: mismatch leaves the whole cell glued."""
    joined = merge_clean_comment_cell_parts([DESCR, MPN], "~~")
    bom, _label, tail = split_joined_clean_comment(joined, " | ")
    assert bom == joined  # nothing was split
    assert tail == ""


# --------------------------------------------------------------------------
# the defect itself: the vendor step has to see the MPN tail
# --------------------------------------------------------------------------


def test_vendor_parses_when_the_join_separator_matches_the_config():
    joined = f"{DESCR} {MPN}"
    cleaned, ctype, _part_code, source = clean_component.clean_one(joined, _cfg(" "))
    assert source == "vendor"
    assert cleaned == "0402_1M_1%"
    assert ctype == "RESISTOR"


def test_mismatched_separator_scrapes_the_description_instead_of_the_mpn():
    """The defect, shown as a wrong nominal rather than a missing one.

    Joined with a space but split with the default: nothing is split, so the
    regex phase parses the joined text itself and reads the resistance out of
    the description (100K) instead of the part number (1M). A wrong value, not
    merely an unparsed one.
    """
    joined = f"{DESCR} {MPN}"
    cleaned, _ctype, _part_code, source = clean_component.clean_one(joined, _cfg(" | "))
    assert source != "vendor"
    assert cleaned == "0402_100K_1%"
    assert cleaned != "0402_1M_1%"


def test_separator_on_config_defaults_to_the_join_default():
    from clean_types import CleanConfig

    cfg = CleanConfig()
    assert cfg.double_comment_separator == DEFAULT_DOUBLE_COMMENT_JOIN
    joined = merge_clean_comment_cell_parts([DESCR, MPN], cfg.double_comment_separator)
    assert split_joined_clean_comment(joined, cfg.double_comment_separator) == (
        DESCR,
        "",
        MPN,
    )


# --------------------------------------------------------------------------
# baseline on the real order: any sane separator must give the same answer
# --------------------------------------------------------------------------

_BOM = Path(r"C:\Users\SMD\Documents\Production\TechOne 27 (CO1271)\PNP\bom.xlsx")


@pytest.mark.skipif(not _BOM.exists(), reason="CO1271 BOM not present")
def test_join_separator_does_not_change_the_vendor_count():
    """M4 from the plan: vendor must be 180 for every usable separator.

    ``"2"`` is deliberately excluded: it occurs inside the data itself
    (``25V``), so joining with it destroys information and cannot be recovered
    by any split - see the note under A1 in the plan.
    """
    import openpyxl
    import pandas as pd

    from services.clean_import import import_bom_comments_for_clean

    wb = openpyxl.load_workbook(_BOM, data_only=True)
    ws = wb["SKU3"]
    rows = [r for r in ws.iter_rows(values_only=True) if len(r) > 3 and r[3]]
    df = pd.DataFrame(
        [list(r[:4]) for r in rows], columns=["qty", "ref", "descr", "mpn"]
    )
    idx = list(range(len(df)))

    results = {}
    for sep in (" | ", "", " ", "~"):
        comments = import_bom_comments_for_clean(
            df, ["descr", "mpn"], idx, double_comment_separator=sep
        )
        preview = clean_component.clean_preview(comments, _cfg(sep))
        results[sep] = sum(1 for r in preview if r[4] == "vendor")

    assert results[" | "] == 180, results
    assert results[""] == results[" | "], results
    assert results[" "] == results[" | "], results
    assert results["~"] == results[" | "], results
