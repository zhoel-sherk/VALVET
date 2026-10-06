"""Tests for Tier A footprint heuristics (no Qt)."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pcb_preview.footprint_heuristic import (
    _CHIP_MM,
    _find_imperial_code,
    heuristic_footprint_outline,
)
from pcb_preview.types import BBoxMM
from pcb_preview.upd_footprint_builder import chip_heuristic_pads

# --------------------------------------------------------------------------
# _find_imperial_code
# --------------------------------------------------------------------------


def test_every_table_code_is_found_in_a_bare_name() -> None:
    for code in _CHIP_MM:
        assert _find_imperial_code(code) == code


def test_table_codes_are_unique_five_vs_four_chars() -> None:
    # The length sort only means something because exactly one code is longer.
    assert [c for c in _CHIP_MM if len(c) == 5] == ["01005"]
    assert all(len(c) == 4 for c in _CHIP_MM if c != "01005")


@pytest.mark.parametrize(
    "name, expected",
    [
        ("R0402", "0402"),
        ("C_0603", "0603"),
        ("LED-1210", "1210"),
        ("CAP 0805", "0805"),
        ("SMD2010", "2010"),
        ("Resistor_SMD:R_0402_1005Metric", "0402"),
        ("D_0603_1608Metric", "0603"),
        ("diode_sod_123", None),
        ("SOT-23", None),
        ("TO-252", None),
    ],
)
def test_codes_are_found_inside_longer_names(name: str, expected: str | None) -> None:
    assert _find_imperial_code(name) == expected


def test_case_and_separators_are_ignored() -> None:
    assert _find_imperial_code("r0402") == _find_imperial_code("R_0402")
    assert _find_imperial_code("r0402") == _find_imperial_code("R-0402")
    assert _find_imperial_code("r0402") == _find_imperial_code("R 0402")
    assert _find_imperial_code("led 1210") == "1210"
    assert _find_imperial_code("cap-0603") == "0603"
    assert _find_imperial_code("cap_0603") == "0603"


def test_five_char_code_is_found_and_position_decides_between_two_codes() -> None:
    # 01005 is the only 5-char code. A name can hold both sizes, and then the
    # one that starts first wins - which matches KiCad naming, where the imperial
    # code comes first and the metric equivalent second (C_0402_1005Metric).
    assert len("01005") > len("0402")
    assert _find_imperial_code("01005") == "01005"
    assert _find_imperial_code("C_01005_0402Metric") == "01005"
    assert _find_imperial_code("0402_01005") == "0402"
    # Real KiCad-style names resolve on the imperial size, as before.
    assert _find_imperial_code("C_0402_1005MetricPad1.0x1.0mm") == "0402"
    assert _find_imperial_code("R_1210_3225Metric") == "1210"


def test_unknown_names_return_none() -> None:
    assert _find_imperial_code("") is None
    assert _find_imperial_code("R_") is None
    assert _find_imperial_code("CAP_SMD") is None


def test_numeric_fallback_only_fires_for_known_codes() -> None:
    # 4-5 digit run matched by \b(\d{4,5})\b, but only accepted if in table.
    assert _find_imperial_code("PART 9999") is None
    assert _find_imperial_code("R9999") is None
    assert _find_imperial_code("9999") is None
    assert _find_imperial_code("12345") is None
    assert _find_imperial_code("PART 0402") == "0402"
    assert _find_imperial_code("PART 2512") == "2512"


def test_none_name_is_tolerated_by_the_helper() -> None:
    # heuristic_footprint_outline() did (name or "") before calling the helper,
    # and now the helper guards too, so both entry points accept None.
    assert _find_imperial_code(None) is None  # type: ignore[arg-type]
    assert _find_imperial_code("") is None
    assert heuristic_footprint_outline(None) is None  # type: ignore[arg-type]


def test_two_codes_in_one_name_pick_the_earliest_in_the_string() -> None:
    # The code that starts earliest wins, regardless of table order.
    assert _find_imperial_code("x-2010-1210") == "2010"
    assert _find_imperial_code("x-1210-2010") == "1210"
    assert _find_imperial_code("CAP_0805_1206") == "0805"
    assert _find_imperial_code("CAP_1206_0805") == "1206"


def test_adjacent_codes_do_not_splice_into_a_third_code() -> None:
    # "1210" + "2010" used to contain the substring "0201" straddling the
    # boundary, and 0201 was scanned first, so the footprint was drawn as a
    # 0203-sized 0.6x0.3mm body.
    assert _find_imperial_code("C_1210_2010") == "1210"
    assert _find_imperial_code("C_2010_1210") == "2010"
    assert _find_imperial_code("LED-1210-2010") == "1210"


# --------------------------------------------------------------------------
# heuristic_footprint_outline
# --------------------------------------------------------------------------


def test_outline_is_none_without_a_code() -> None:
    assert heuristic_footprint_outline("SOIC-8") is None
    assert heuristic_footprint_outline("") is None
    assert heuristic_footprint_outline(None) is None  # type: ignore[arg-type]


@pytest.mark.parametrize("code", sorted(_CHIP_MM))
def test_bbox_is_centred_on_origin(code: str) -> None:
    out = heuristic_footprint_outline(code)
    assert out is not None
    length, width = _CHIP_MM[code]
    assert out.source == "heuristic"
    assert out.bbox == BBoxMM(-length / 2, -width / 2, length / 2, width / 2)
    assert out.bbox.width == pytest.approx(length)
    assert out.bbox.height == pytest.approx(width)


def test_body_is_four_lines_forming_a_closed_rectangle() -> None:
    out = heuristic_footprint_outline("R_1206")
    assert out is not None
    assert len(out.lines) == 4
    assert out.circles == ()

    half_l, half_w = 3.2 / 2, 1.6 / 2
    corners = {
        (round(x1, 6), round(y1, 6), round(x2, 6), round(y2, 6))
        for x1, y1, x2, y2, _w in (
            (ln.x1, ln.y1, ln.x2, ln.y2, ln.width_mm) for ln in out.lines
        )
    }
    assert corners == {
        (-half_l, -half_w, half_l, -half_w),
        (half_l, -half_w, half_l, half_w),
        (half_l, half_w, -half_l, half_w),
        (-half_l, half_w, -half_l, -half_w),
    }
    for ln in out.lines:
        assert ln.width_mm == pytest.approx(0.1)
        horizontal = abs(ln.y1 - ln.y2) < 1e-9
        vertical = abs(ln.x1 - ln.x2) < 1e-9
        assert horizontal != vertical  # axis aligned, not diagonal

    # closed loop: every endpoint appears exactly twice
    ends: list[tuple[float, float]] = []
    for ln in out.lines:
        ends.append((ln.x1, ln.y1))
        ends.append((ln.x2, ln.y2))
    assert len(ends) == 8
    for point in set(ends):
        assert ends.count(point) == 2


def test_pads_match_chip_heuristic_pads_for_the_same_size() -> None:
    for code, (length, width) in _CHIP_MM.items():
        out = heuristic_footprint_outline(code)
        assert out is not None
        assert out.pads == chip_heuristic_pads(length, width)
        assert len(out.pads) == 2
        assert [p.number for p in out.pads] == ["1", "2"]
        assert out.pads[0].cx == -out.pads[1].cx
        assert out.pads[0].rotation_deg == 0.0


def test_geometry_is_symmetric_about_the_origin() -> None:
    out = heuristic_footprint_outline("CAP_2010")
    assert out is not None
    assert out.bbox.min_x == -out.bbox.max_x
    assert out.bbox.min_y == -out.bbox.max_y
    assert out.pads[0].cx == -out.pads[1].cx
    assert out.pads[0].cy == out.pads[1].cy

    def undirected(segments):
        out_set = set()
        for x1, y1, x2, y2 in segments:
            a = (round(x1, 6), round(y1, 6))
            b = (round(x2, 6), round(y2, 6))
            out_set.add(tuple(sorted([a, b])))
        return out_set

    segments = [(l.x1, l.y1, l.x2, l.y2) for l in out.lines]
    mirrored = [(-x1, y1, -x2, y2) for x1, y1, x2, y2 in segments]
    assert undirected(mirrored) == undirected(segments)


def test_outline_scales_with_code() -> None:
    small = heuristic_footprint_outline("R_0402")
    large = heuristic_footprint_outline("R_2512")
    assert small is not None and large is not None
    assert large.bbox.width > small.bbox.width
    assert large.bbox.height > small.bbox.height
    assert large.pads[0].width_mm > small.pads[0].width_mm
