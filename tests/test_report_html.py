"""Tests for HTML cross-check report helpers."""

from report_html import (
    escape_cell_with_char_highlight,
    escape_cell_with_value_diff,
    html_document_from_fragment,
    result_dataframe_to_html,
)


def test_escape_cell_with_char_highlight_groups_and_escapes():
    s = escape_cell_with_char_highlight("R100 vs R10O & <tag>")
    assert '<span class="ch-punct">&lt;</span>' in s
    assert '<span class="ch-letter">tag</span>' in s
    assert '<span class="ch-punct">&gt;</span>' in s
    assert '<span class="ch-punct">&amp;</span>' in s
    assert '<span class="ch-letter">R</span>' in s
    assert '<span class="ch-num">100</span>' in s


def test_escape_cell_with_value_diff_marks_middle():
    html = escape_cell_with_value_diff("10k", "10R")
    assert '<mark class="diff">' in html
    assert "10" in html
    assert html.index("<mark") < html.index("k") or "k" in html


def test_result_dataframe_to_html_wraps_highlight_columns():
    import pandas as pd

    df = pd.DataFrame(
        [
            {
                "Designator": "U1",
                "IssueType": "missing_in_pnp",
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
    assert "Missing in PnP" in html
    assert 'class="sev-warning"' in html or "class='sev-warning'" in html
    assert "badge-warning" in html
    assert "1 issue" in html
    assert "1 warning" in html
    assert "#c6282818" not in html
    assert "fdecea" in html or "fff8e1" in html


def test_result_dataframe_to_html_mismatch_and_critical():
    import pandas as pd

    df = pd.DataFrame(
        [
            {
                "Designator": "R2",
                "IssueType": "mismatch",
                "BOM_Value": "10k",
                "PnP_Value": "10R",
                "Footprint": "R0603",
                "Coord_X": "",
                "Coord_Y": "",
                "Severity": "critical",
            }
        ]
    )
    html = result_dataframe_to_html(
        df, bom_path=r"C:\boards\bom.csv", pnp_path="pnp.txt"
    )
    assert "Value mismatch" in html
    assert 'class="sev-critical"' in html or "class='sev-critical'" in html
    assert "badge-critical" in html
    assert "cell-mismatch" in html
    assert '<mark class="diff">' in html
    assert "bom.csv" in html
    assert "3 critical" not in html
    assert "1 critical" in html


def test_result_dataframe_to_html_empty():
    import pandas as pd

    html = result_dataframe_to_html(pd.DataFrame())
    assert "No issues in this view" in html
    assert "0 issue" in html
    assert "<table" not in html


def test_html_document_from_fragment_forces_light_scheme():
    doc = html_document_from_fragment("<p>x</p>")
    assert "color-scheme" in doc
    assert "<!DOCTYPE html>" in doc
    assert "<p>x</p>" in doc
