"""Tests for HTML cross-check report helpers."""

from report_html import escape_cell_with_char_highlight, result_dataframe_to_html


def test_escape_cell_with_char_highlight_groups_and_escapes():
    s = escape_cell_with_char_highlight("R100 vs R10O & <tag>")
    assert '<span class="ch-punct">&lt;</span>' in s
    assert '<span class="ch-letter">tag</span>' in s
    assert '<span class="ch-punct">&gt;</span>' in s
    assert '<span class="ch-punct">&amp;</span>' in s
    assert '<span class="ch-letter">R</span>' in s
    assert '<span class="ch-num">100</span>' in s


def test_result_dataframe_to_html_wraps_highlight_columns():
    import pandas as pd

    df = pd.DataFrame(
        [
            {
                "Designator": "U1",
                "IssueType": "x",
                "BOM_Value": "ABC123",
                "PnP_Value": "",
                "Footprint": "",
                "Coord_X": "1.5",
                "Coord_Y": "",
                "Severity": "warning",
            }
        ]
    )
    html = result_dataframe_to_html(df)
    assert 'class="report"' in html
    assert 'class="cell-code"' in html
    assert '<span class="ch-letter">ABC</span>' in html
    assert '<span class="ch-num">123</span>' in html
    assert "<td>x</td>" in html or ">x<" in html  # IssueType plain
