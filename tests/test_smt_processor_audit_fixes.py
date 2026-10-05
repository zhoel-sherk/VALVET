"""Regression tests for the 0.5.1.1 audit items fixed in ``smt_processor``.

Plan: rows 3.3, 3.4 (silent reader fallbacks) and 4.1, 4.2, 4.6, 4.13
("children's" mistakes) of ``PLAN_RELEASE_0.5.1.1.md``. Every case below is a
defect that was reproduced first; the comment on each test names what used to
happen instead.
"""

from __future__ import annotations

import os
import sys
import time

import pandas as pd
import pytest

tests_path = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(tests_path), "src"))

import smt_processor as sp  # noqa: E402

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _capture_warnings(monkeypatch) -> list[str]:
    """Collect ``logger.warning`` text; the module formats lazily, so do it here."""
    messages: list[str] = []

    def _record(msg, *args):
        messages.append(str(msg) % args if args else str(msg))

    monkeypatch.setattr(sp.logger, "warning", _record)
    return messages


def _processor(bom_rows, pnp_rows) -> sp.SMTDataProcessor:
    """Processor over two plain frames with every optional PnP column mapped."""
    proc = sp.SMTDataProcessor(sp.ProcessorConfig())
    proc._bom_df = pd.DataFrame(bom_rows)
    proc._pnp_df = pd.DataFrame(pnp_rows)
    proc._bom_config = sp.ColumnConfig(designator="Designator", comment="Comment")
    proc._pnp_config = sp.ColumnConfig(
        designator="Designator",
        coord_x="X",
        coord_y="Y",
        rotation="Rotation",
        layer="Layer",
        footprint="Footprint",
        comment="Comment",
    )
    return proc


def _pnp_row(ref, value, x, y, layer="Top"):
    return {
        "Designator": ref,
        "Comment": value,
        "X": x,
        "Y": y,
        "Rotation": "0",
        "Layer": layer,
        "Footprint": "0402",
    }


# ==============================================================================
# 4.1  _check_overlapping reported every pair twice and cost O(n^3)
# ==============================================================================

# Three 0402s on the top side, all within 3 mm of each other -> 3 unique pairs.
_PARTS = {
    "R1": ("v", "0402", 0.0, 0.0, "T"),
    "R2": ("v", "0402", 0.5, 0.0, "T"),
    "R3": ("v", "0402", 0.2, 0.1, "T"),
}


def test_check_overlapping_reports_three_records_for_three_pairs():
    """The repro from the plan returned 6 records; each unordered pair is one."""
    got = sp._check_overlapping(dict(_PARTS), 3.0, True)
    assert len(got) == 3
    assert {frozenset((a, b)) for a, b, _ in got} == {
        frozenset(("R1", "R2")),
        frozenset(("R1", "R3")),
        frozenset(("R2", "R3")),
    }


def test_check_overlapping_keeps_the_record_shape():
    """A caller unpacks ``(part1, part2, distance)``; that must not change."""
    for record in sp._check_overlapping(dict(_PARTS), 3.0, True):
        assert isinstance(record, tuple)
        assert len(record) == 3
        first, second, dist = record
        assert isinstance(first, str) and isinstance(second, str)
        assert isinstance(dist, float)
        assert 0 < dist < 3.0


def test_check_overlapping_orders_by_pnp_insertion_order():
    """Ordering contract: outer part is the earlier placement, in visit order."""
    got = sp._check_overlapping(dict(_PARTS), 3.0, True)
    assert [(a, b) for a, b, _ in got] == [("R1", "R2"), ("R1", "R3"), ("R2", "R3")]


def test_check_overlapping_dedups_in_a_reversed_dict_too():
    """The pair is unordered, so a reversed dict must give reversed records."""
    reversed_parts = {key: _PARTS[key] for key in ("R3", "R2", "R1")}
    got = sp._check_overlapping(reversed_parts, 3.0, True)
    assert len(got) == 3
    assert [(a, b) for a, b, _ in got] == [("R3", "R2"), ("R3", "R1"), ("R2", "R1")]


def test_check_overlapping_still_respects_layer_and_threshold():
    """Dedup must not swallow the existing layer filter or the distance window."""
    mixed = {
        "R1": ("v", "0402", 0.0, 0.0, "T"),
        "R2": ("v", "0402", 0.1, 0.0, "B"),
        "R3": ("v", "0402", 50.0, 0.0, "T"),
    }
    assert sp._check_overlapping(mixed, 3.0, True) == []


def test_check_overlapping_converts_mils_only_for_the_comparison():
    """overlap_xy_are_mm=False scales by 0.0254; stored data stays untouched."""
    as_mm = sp._check_overlapping(dict(_PARTS), 3.0, True)
    # 100 mil apart = 2.54 mm apart: still inside a 3 mm window.
    as_mils = sp._check_overlapping(dict(_PARTS), 3.0, False)
    assert len(as_mm) == len(as_mils) == 3
    assert all(mm[2] > mil[2] for mm, mil in zip(as_mm, as_mils, strict=True))
    assert _PARTS["R2"][2] == 0.5  # inputs are not mutated


def test_check_overlapping_is_quadratic_not_cubic():
    """400 placements in one cluster: 79 800 unique pairs.

    The old inner-loop ``in`` scan over a per-key list made this the O(n^3) case
    the plan warns about; the budget is loose enough not to flake but far below
    what the old shape costs.
    """
    n = 400
    spacing = 0.005  # widest gap 1.995 mm, inside the 3 mm window
    dense = {f"R{i}": ("v", "0402", i * spacing, 0.0, "T") for i in range(n)}
    started = time.perf_counter()
    got = sp._check_overlapping(dense, 3.0, True)
    elapsed = time.perf_counter() - started
    assert len(got) == n * (n - 1) // 2
    assert elapsed < 10.0, f"overlap check took {elapsed:.1f}s for {n} placements"


# ==============================================================================
# 3.3  the reader lost rows silently and had a dead latin-1 fallback
# ==============================================================================

# Two rows carry more fields than the header: those are the ones pandas drops.
_CSV_WITH_BAD_ROWS = (
    "Designator,Comment,X,Y,Layer\n"
    "R1,10K,1.0,2.0,Top\n"
    "R2,10K,3.0,4.0,Top,EXTRA\n"
    "R3,10K,5.0,6.0,Top\n"
    "R4,10K,7.0,8.0,Top,MORE,AND_MORE\n"
    "R5,10K,9.0,10.0,Top\n"
)


def test_malformed_csv_rows_are_counted_and_warned_about(tmp_path, monkeypatch):
    """on_bad_lines="skip" used to drop these two rows with no counter and no log."""
    warnings = _capture_warnings(monkeypatch)
    path = tmp_path / "pnp.csv"
    path.write_text(_CSV_WITH_BAD_ROWS, encoding="utf-8")

    df = sp.read_file(str(path), separator=",")

    assert list(df["Designator"]) == ["R1", "R3", "R5"]
    reported = [m for m in warnings if "malformed rows skipped" in m]
    assert reported, f"skip was silent: {warnings}"
    assert reported[0].startswith("2 malformed rows skipped in pnp.csv")


def test_malformed_rows_are_dropped_not_kept_as_junk(tmp_path, monkeypatch):
    """The count must describe a real loss, so the rows really are gone."""
    _capture_warnings(monkeypatch)
    path = tmp_path / "pnp.csv"
    path.write_text(_CSV_WITH_BAD_ROWS, encoding="utf-8")
    df = sp.read_file(str(path), separator=",")
    assert len(df) == 3
    assert not df.astype(str).apply(lambda c: c.str.contains("EXTRA")).any().any()


def test_a_clean_csv_warns_about_no_malformed_rows(tmp_path, monkeypatch):
    """The counter must not fire when nothing was dropped."""
    warnings = _capture_warnings(monkeypatch)
    path = tmp_path / "pnp.csv"
    path.write_text(
        "Designator,Comment,X,Y,Layer\nR1,10K,1.0,2.0,Top\nR2,10K,3.0,4.0,Top\n",
        encoding="utf-8",
    )
    sp.read_file(str(path), separator=",")
    assert not [m for m in warnings if "malformed rows skipped" in m]


# ---- encoding strategy: ordered trial decoding, latin-1 last and announced ---


def test_cp932_file_is_decoded_as_cp932_not_mojibake(tmp_path):
    """Chosen strategy: strict trial decoding over a fixed candidate list.

    The removed fallback was ``except UnicodeDecodeError: latin-1``. latin-1 maps
    all 256 byte values, so it could not fail and a Shift-JIS file "succeeded" as
    mojibake whose designators then went into the merge export. Here the file is
    named CP932 and round-trips.
    """
    text = "Designator,Comment,X,Y\nR1,抵抗 10K,1.0,2.0\nR2,コンデンサ,3.0,4.0\n"
    path = tmp_path / "sjis.csv"
    path.write_bytes(text.encode("cp932"))
    raw = path.read_bytes()

    assert sp.detect_text_encoding(raw) == "cp932"
    assert raw.decode("latin-1") != text  # what the old branch produced

    assert sp._read_text_lines(str(path))[1].split(",")[1] == "抵抗 10K"

    df = sp.read_file(str(path), separator=",")
    assert list(df["Designator"]) == ["R1", "R2"]
    assert list(df["Comment"]) == ["抵抗 10K", "コンデンサ"]


def test_cp932_read_does_not_claim_to_be_mojibake(tmp_path, monkeypatch):
    """A losslessly decoded file must not be announced as a latin-1 guess."""
    warnings = _capture_warnings(monkeypatch)
    path = tmp_path / "sjis.csv"
    path.write_bytes("Designator,Comment\nR1,抵抗\n".encode("cp932"))
    sp.read_file(str(path), separator=",")
    assert not [m for m in warnings if "latin-1" in m]


def test_undecodable_bytes_fall_through_to_latin1_and_say_so(tmp_path, monkeypatch):
    """0x98 is the one byte value no earlier candidate accepts.

    Reaching latin-1 is now a named, warned event rather than the silent default.
    """
    assert sp.detect_text_encoding(b"\x98") == "latin-1"

    warnings = _capture_warnings(monkeypatch)
    path = tmp_path / "broken.csv"
    path.write_bytes(b"Designator,Comment\nR1,\x98\n")

    lines = sp._read_text_lines(str(path))
    assert len(lines) == 2
    assert [m for m in warnings if "latin-1" in m and "broken.csv" in m]


def test_undecodable_file_raises_a_clear_error_instead_of_guessing(
    tmp_path, monkeypatch
):
    """With no candidate fitting, the read fails and says how to fix the file."""
    monkeypatch.setattr(sp, "_TEXT_ENCODINGS", ("utf-8", "utf-8-sig"))
    path = tmp_path / "sjis.csv"
    path.write_bytes("Designator,Comment\nR1,抵抗\n".encode("cp932"))

    with pytest.raises(sp.SMTProcessorError) as exc:
        sp._read_text_lines(str(path))
    assert "UTF-8" in str(exc.value)
    assert path.name in str(exc.value)

    with pytest.raises(sp.SMTProcessorError):
        sp.read_file(str(path), separator=",")


def test_plain_utf8_and_utf8_bom_still_win_over_the_legacy_candidates(tmp_path):
    """utf-8 is first, so the ordinary path is untouched by the candidate list."""
    for name, payload in (
        ("plain.csv", "Designator,Comment\nR1,10K\n".encode("utf-8")),
        ("bom.csv", "Designator,Comment\nR1,10K\n".encode("utf-8-sig")),
    ):
        path = tmp_path / name
        path.write_bytes(payload)
        assert sp.detect_text_encoding(payload).startswith("utf-8")
        df = sp.read_file(str(path), separator=",")
        assert list(df["Designator"]) == ["R1"]
        assert [str(c) for c in df.columns] == ["Designator", "Comment"]


# ==============================================================================
# 3.4  the CSV fallback of _read_excel was unvalidated
# ==============================================================================


def test_csv_fallback_rejects_a_one_column_frame(tmp_path, monkeypatch):
    """A binary workbook re-read as text yields one junk column.

    That frame used to be returned as if it were data, logged at ``info`` level.
    """
    warnings = _capture_warnings(monkeypatch)
    path = tmp_path / "fake.xlsx"
    path.write_text("PK zip-ish junk header\nR1\nR2\nR3\n", encoding="utf-8")

    with pytest.raises(sp.SMTProcessorError) as exc:
        sp.read_file(str(path))
    message = str(exc.value)
    assert "single column" in message
    assert "3 row(s)" in message
    assert [m for m in warnings if "loaded as CSV" in m]


def test_csv_fallback_rejects_an_empty_frame(tmp_path, monkeypatch):
    """No usable rows is SMTEmptyDataError, so existing callers keep catching it."""
    _capture_warnings(monkeypatch)
    path = tmp_path / "fake.xlsx"
    path.write_text("PK zip-ish junk header\n", encoding="utf-8")

    with pytest.raises(sp.SMTEmptyDataError):
        sp.read_file(str(path))


def test_a_real_csv_named_xlsx_still_falls_back_and_warns(tmp_path, monkeypatch):
    """Shape validation must not break the documented CSV fallback."""
    warnings = _capture_warnings(monkeypatch)
    path = tmp_path / "text_export.xlsx"
    path.write_text(
        "Designator,Footprint,Comment\nR1,0402,10K\nR2,0603,22nF\n", encoding="utf-8"
    )

    df = sp.read_file(str(path))
    assert list(df["Designator"]) == ["R1", "R2"]
    assert [m for m in warnings if "loaded as CSV" in m]


# ==============================================================================
# 4.2  truthiness where "is not None" was meant
# ==============================================================================


def test_zero_coordinates_are_not_serialised_as_empty():
    """``r.coord_x if r.coord_x else ""`` blanked a part at the board origin."""
    df = sp.SMTDataProcessor(sp.ProcessorConfig())._results_to_dataframe(
        [
            sp.CrossCheckResult(
                designator="C1", issue_type="mismatch", coord_x=0.0, coord_y=0.0
            ),
            sp.CrossCheckResult(
                designator="C2", issue_type="mismatch", coord_x=100.0, coord_y=50.0
            ),
            sp.CrossCheckResult(designator="C3", issue_type="missing_in_bom"),
        ]
    )
    assert df.iloc[0]["Coord_X"] == 0.0
    assert df.iloc[0]["Coord_Y"] == 0.0
    assert df.iloc[1]["Coord_X"] == 100.0
    assert df.iloc[1]["Coord_Y"] == 50.0
    # A genuinely absent coordinate still shows as empty, not as the string "None".
    assert df.iloc[2]["Coord_X"] == ""


def test_cross_check_keeps_a_zero_coordinate_end_to_end():
    proc = _processor(
        [{"Designator": "C1", "Comment": "100nF"}],
        [_pnp_row("C1", "10uF", "0.00", "0.00")],
    )
    df = proc.cross_check()
    mismatch = df[df["IssueType"] == "mismatch"]
    assert len(mismatch) == 1
    assert mismatch.iloc[0]["Coord_X"] == 0.0
    assert mismatch.iloc[0]["Coord_Y"] == 0.0


# ==============================================================================
# 4.6  Y=0 materialisation and the (0, 0) duplicate exclusion
# ==============================================================================


def test_parse_placement_xy_needs_both_axes():
    assert sp._parse_placement_xy(("v", "0402", 5.0)) is None  # no Y slot at all
    assert sp._parse_placement_xy(("v", "0402", 5.0, None, "T")) is None
    assert sp._parse_placement_xy(("v", "0402", 5.0, float("nan"), "T")) is None
    assert sp._parse_placement_xy(("v", "0402", None, 5.0, "T")) is None
    assert sp._parse_placement_xy(("v", "0402", "bad", 5.0, "T")) is None
    assert sp._parse_placement_xy(("v", "0402")) is None


def test_parse_placement_xy_keeps_a_real_zero():
    """A genuine Y of 0 is a placement, not a missing value."""
    assert sp._parse_placement_xy(("v", "0402", 5.0, 0.0, "T")) == (5.0, 0.0)
    assert sp._parse_placement_xy(("v", "0402", 0, 0, "T")) == (0.0, 0.0)


def test_two_parts_at_the_origin_are_reported_as_duplicates():
    """``coord != (0.0, 0.0)`` excluded the origin from duplicate detection."""
    proc = _processor(
        [{"Designator": "C1,C2", "Comment": "100nF"}],
        [
            _pnp_row("C1", "100nF", "0.00", "0.00"),
            _pnp_row("C2", "100nF", "0.00", "0.00"),
        ],
    )
    dups = proc.cross_check()
    dups = dups[dups["IssueType"] == "duplicate_coord"]
    assert len(dups) == 1
    assert "C1" in dups.iloc[0]["Designator"] and "C2" in dups.iloc[0]["Designator"]
    assert dups.iloc[0]["Severity"] == "critical"


def test_a_part_without_y_does_not_collide_with_a_part_on_the_y0_line():
    """The materialisation bug would have parked it at Y=0 and cried duplicate."""
    proc = _processor(
        [
            {"Designator": "C1", "Comment": "100nF"},
            {"Designator": "C2", "Comment": "100nF"},
        ],
        [
            _pnp_row("C1", "100nF", "5.00", "0.00"),
            _pnp_row("C2", "100nF", "5.00", None),
        ],
    )
    dups = proc.cross_check()
    assert (dups["IssueType"] == "duplicate_coord").sum() == 0


def test_duplicate_coordinates_still_need_the_same_layer():
    proc = _processor(
        [{"Designator": "C1,C2", "Comment": "100nF"}],
        [
            _pnp_row("C1", "100nF", "7.00", "8.00", layer="Top"),
            _pnp_row("C2", "100nF", "7.00", "8.00", layer="Bot"),
        ],
    )
    dups = proc.cross_check()
    assert (dups["IssueType"] == "duplicate_coord").sum() == 0


# ==============================================================================
# 4.13  unterminated quote dropped the tail of the row
# ==============================================================================


def test_unterminated_quote_no_longer_swallows_the_rest_of_the_row():
    """The buffered run used to fall out of the loop, shifting every later column."""
    assert sp._read_sp_quoted_row(["R3", '"oops', "0402", "C0603"]) == [
        "R3",
        "oops 0402 C0603",
    ]


def test_terminated_quote_still_merges_into_one_cell():
    assert sp._read_sp_quoted_row(["R2", '"10', 'K"', "0402"]) == ["R2", "10 K", "0402"]


def test_plain_rows_are_untouched():
    assert sp._read_sp_quoted_row(["R1", "10K", "0402"]) == ["R1", "10K", "0402"]


def test_read_text_whitespace_sp_keeps_every_token_of_a_broken_row(tmp_path):
    lines = [
        "R1 10K 0402 C0603",
        'R2 "10 K" 0402 C0603',
        'R3 "truncated 0402 C0603',
        "R4 22nF 0603 C0603",
    ]
    path = tmp_path / "sp.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    df = sp.read_text_whitespace_sp(str(path))
    assert list(df.columns) == ["0", "1", "2", "3"]
    assert len(df) == 4
    # Row 3 lost its tail entirely before the fix, which shifted every later
    # column one place left; no token may go missing now.
    assert df.iloc[2].tolist() == ["R3", "truncated 0402 C0603", "", ""]
    assert df.iloc[3].tolist() == ["R4", "22nF", "0603", "C0603"]
    assert df.iloc[1].tolist() == ["R2", "10 K", "0402", "C0603"]
