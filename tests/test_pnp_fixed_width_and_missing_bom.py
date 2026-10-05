"""Regression tests for fixed-width PnP parsing and the missing-from-BOM report.

Both defects were found on the CO1271 job (DXB101_MB_V11_20260527A), where the
placement file is fixed-width and the ``Layer`` column is empty on every Top-side
row. The two regressions must not come back:

1. ``read_text_whitespace_sp`` used ``str.split()``, so the blank Layer column
   collapsed on Top rows and every later column shifted one place left there.
2. ``merge_bom_pnp`` treated "not in the BOM" as DNP and dropped such placements
   with no message at all.
"""

from __future__ import annotations

import os
import sys

import pandas as pd
import pytest

tests_path = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(tests_path), "src"))

import smt_processor as sp  # noqa: E402

# One Top row (blank Layer), one Bot row (Layer 'm'), laid out fixed-width with
# the same column starts as a real PnP file: 0, 21, 35, 48, 53, 55.
_TOP = "C6421                5615.87       2344.63      270    C0402               "
_BOT = "MK7303               6856.87        201.63        0  m FIDUCIAL_40_PACKAGE "


def _fixed_width_file(tmp_path, top_rows: int = 30, bot_rows: int = 4, name="pnp.txt"):
    """A fixed-width placement file whose Layer column is blank on Top rows."""
    lines = [_TOP for _ in range(top_rows)]
    lines += [_BOT.replace("MK7303", f"MK73{i:02d}") for i in range(bot_rows)]
    path = tmp_path / name
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


# --------------------------------------------------------------------------
# Fixed-width detection
# --------------------------------------------------------------------------


def test_detect_fixed_width_columns_on_synthetic_file(tmp_path):
    starts = sp.detect_fixed_width_columns(
        sp._read_text_lines(_fixed_width_file(tmp_path))
    )
    assert starts == (0, 21, 35, 48, 53, 55)


def test_read_pnp_whitespace_keeps_blank_layer_column(tmp_path):
    """The whole point: Layer stays empty for Top and 'm' for Bot."""
    df = sp.read_pnp_whitespace(_fixed_width_file(tmp_path))
    assert list(df.columns) == ["0", "1", "2", "3", "4", "5"]
    assert set(df["4"].unique()) == {"", "m"}
    # Footprint must be read from column 5 on BOTH sides, never from column 4.
    top = df[df["4"] == ""]
    bot = df[df["4"] == "m"]
    assert len(top) == 30
    assert len(bot) == 4
    assert set(top["5"].unique()) == {"C0402"}
    assert set(bot["5"].unique()) == {"FIDUCIAL_40_PACKAGE"}


def test_fixed_width_never_loses_or_invents_a_token(tmp_path):
    """Positional slicing must reproduce exactly what str.split() found."""
    path = _fixed_width_file(tmp_path)
    lines = sp._read_text_lines(path)
    starts = sp.detect_fixed_width_columns(lines)
    assert starts is not None
    for line in lines:
        if not line.strip():
            continue
        cells = [c for c in sp._slice_fixed_width_row(line, starts) if c]
        assert cells == line.split()


def test_fixed_width_row_count_matches_whitespace(tmp_path):
    path = _fixed_width_file(tmp_path)
    fw = sp.read_pnp_whitespace(path)
    ws = sp.read_text_whitespace_sp(path)
    assert len(fw) == len(ws)


def test_units_banner_row_is_not_a_data_row(tmp_path):
    """'UUNITS = MILS' lands in one slice and must still be rejected."""
    lines = [_TOP for _ in range(30)] + [_BOT for _ in range(4)]
    path = tmp_path / "banner.txt"
    path.write_text("UUNITS = MILS\n" + "\n".join(lines) + "\n", encoding="utf-8")
    assert len(sp.read_pnp_whitespace(str(path))) == 34


# --------------------------------------------------------------------------
# Detection must stay out of the way of ordinary whitespace files
# --------------------------------------------------------------------------


def test_uniform_whitespace_file_is_left_alone(tmp_path):
    """Same token count on every row means nothing can shift: do not switch."""
    path = tmp_path / "sp.txt"
    rows = [f"R{i} 10.00 20.00 90 C0603" for i in range(30)]
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    assert sp.detect_fixed_width_columns(sp._read_text_lines(str(path))) is None


def test_ragged_whitespace_file_is_not_claimed(tmp_path):
    path = tmp_path / "ragged.txt"
    rows = [" ".join(f"c{i}_{j}" for j in range(i % 4 + 4)) for i in range(40)]
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    assert sp.detect_fixed_width_columns(sp._read_text_lines(str(path))) is None


def test_too_few_rows_is_not_claimed(tmp_path):
    path = tmp_path / "few.txt"
    path.write_text(f"{_TOP}\n{_BOT}\n", encoding="utf-8")
    assert sp.detect_fixed_width_columns(sp._read_text_lines(str(path))) is None


# --------------------------------------------------------------------------
# Missing-from-BOM must not masquerade as DNP
# --------------------------------------------------------------------------


def _processor(bom_refs, pnp_refs, pnp_layer=None):
    proc = sp.SMTDataProcessor(sp.ProcessorConfig())
    proc._bom_df = pd.DataFrame(
        {"Designator": bom_refs, "Comment": [f"V{i}" for i in range(len(bom_refs))]}
    )
    n = len(pnp_refs)
    proc._pnp_df = pd.DataFrame(
        {
            "Designator": pnp_refs,
            "X": ["1000.00"] * n,
            "Y": ["2000.00"] * n,
            "Rotation": ["0"] * n,
            "Layer": pnp_layer if pnp_layer is not None else ["Top"] * n,
            "Footprint": ["0402"] * n,
        }
    )
    proc._bom_config = sp.ColumnConfig(designator="Designator", comment="Comment")
    proc._pnp_config = sp.ColumnConfig(
        designator="Designator",
        coord_x="X",
        coord_y="Y",
        rotation="Rotation",
        layer="Layer",
        footprint="Footprint",
        comment="?",
    )
    return proc


def test_placements_missing_from_bom_are_reported_not_silently_dropped():
    proc = _processor(["C1", "R10"], ["C1", "R10", "C2601", "C2602", "TP1"])
    merged = proc.merge_bom_pnp(include_dnp=False)

    refs = list(merged["Ref"])
    assert "C1" in refs and "R10" in refs
    # Behaviour is unchanged, but the caller is now able to tell the user.
    assert proc.last_merge_not_in_bom_refs == ["C2601", "C2602", "TP1"]
    assert proc.last_merge_dnp_refs == []


def test_dnp_and_missing_from_bom_are_counted_apart():
    """A DNP part is an intentional exclusion; a missing row is a data gap."""
    proc = sp.SMTDataProcessor(sp.ProcessorConfig())
    proc._bom_df = pd.DataFrame(
        {"Designator": ["C1", "C2", "R5"], "Comment": ["V1", "DNP", "V5"]}
    )
    proc._pnp_df = pd.DataFrame(
        {
            "Designator": ["C1", "C2", "R5", "C9999"],
            "X": ["1.00"] * 4,
            "Y": ["1.00"] * 4,
            "Rotation": ["0"] * 4,
            "Layer": ["Top"] * 4,
            "Footprint": ["0402"] * 4,
        }
    )
    proc._bom_config = sp.ColumnConfig(designator="Designator", comment="Comment")
    proc._pnp_config = sp.ColumnConfig(
        designator="Designator",
        coord_x="X",
        coord_y="Y",
        rotation="Rotation",
        layer="Layer",
        footprint="Footprint",
        comment="?",
    )
    merged = proc.merge_bom_pnp(include_dnp=False)

    assert proc.last_merge_dnp_refs == ["C2"]
    assert proc.last_merge_not_in_bom_refs == ["C9999"]
    assert list(merged["Ref"]) == ["C1", "R5"]


def test_include_dnp_keeps_missing_rows_and_still_reports_them():
    proc = _processor(["C1"], ["C1", "C2601"])
    merged = proc.merge_bom_pnp(include_dnp=True)
    assert "C2601" in list(merged["Ref"])
    # Reported regardless of the flag, so the data gap is never hidden.
    assert proc.last_merge_not_in_bom_refs == ["C2601"]


def test_report_is_reset_between_runs():
    proc = _processor(["C1"], ["C1", "C2601"])
    proc.merge_bom_pnp(include_dnp=False)
    assert proc.last_merge_not_in_bom_refs
    proc._pnp_df = pd.DataFrame(
        {
            "Designator": ["C1"],
            "X": ["1.00"],
            "Y": ["1.00"],
            "Rotation": ["0"],
            "Layer": ["Top"],
            "Footprint": ["0402"],
        }
    )
    proc.merge_bom_pnp(include_dnp=False)
    assert proc.last_merge_not_in_bom_refs == []
    assert proc.last_merge_dnp_refs == []


def test_end_to_end_fixed_width_merge_keeps_both_sides(tmp_path):
    """Fixed-width read plus merge: Bot rows survive with the right Layer."""
    path = _fixed_width_file(tmp_path)
    proc = sp.SMTDataProcessor(sp.ProcessorConfig())
    proc._pnp_df = sp.read_pnp_whitespace(path)
    proc._pnp_config = sp.ColumnConfig(
        designator="0",
        coord_x="1",
        coord_y="2",
        rotation="3",
        layer="4",
        footprint="5",
        comment="?",
    )
    proc._bom_df = pd.DataFrame({"Designator": ["MK7303"], "Comment": ["FIDUCIAL"]})
    proc._bom_config = sp.ColumnConfig(designator="Designator", comment="Comment")

    merged = proc.merge_bom_pnp(include_dnp=False)
    assert list(merged["Ref"]) == ["MK7303"]
    assert merged.iloc[0]["Layer"] == "m"
    assert merged.iloc[0]["Footprint"] == "FIDUCIAL_40_PACKAGE"
    assert proc.last_merge_not_in_bom_refs


@pytest.mark.parametrize("n_rows", [0, 1])
def test_no_merge_rows_is_not_a_crash(n_rows):
    proc = _processor([], [])
    out = proc.merge_bom_pnp(include_dnp=False)
    assert out.empty
    assert proc.last_merge_not_in_bom_refs == []
