"""HTML report from cross-check DataFrame (smt_processor output)."""

from __future__ import annotations

import html as html_mod
import time
from pathlib import Path

import pandas as pd

SEVERITY_COLORS: dict[str, str] = {
    "critical": "#c62828",
    "warning": "#f57c00",
    "info": "#1976d2",
}

_ISSUE_LABELS: dict[str, str] = {
    "missing_in_pnp": "Missing in PnP",
    "missing_in_bom": "Missing in BOM",
    "mismatch": "Value mismatch",
    "duplicate_coord": "Duplicate coordinates",
    "overlapping": "Overlapping placement",
}

_SEVERITY_LABELS: dict[str, str] = {
    "critical": "Critical",
    "warning": "Warning",
    "info": "Info",
}

_COLUMN_HEADERS: dict[str, str] = {
    "Designator": "Designator",
    "IssueType": "Issue",
    "BOM_Value": "BOM value",
    "PnP_Value": "PnP value",
    "Footprint": "Footprint",
    "Coord_X": "X",
    "Coord_Y": "Y",
    "Severity": "Severity",
}

# Columns where per-character highlighting helps compare BOM vs PnP (letters vs digits).
_HIGHLIGHT_COLUMNS: frozenset[str] = frozenset(
    {
        "Designator",
        "BOM_Value",
        "PnP_Value",
        "Footprint",
        "Coord_X",
        "Coord_Y",
    }
)

_REPORT_CSS = """
.valvet-report{color-scheme:light;color:#1a1a1a;font-family:system-ui,Segoe UI,sans-serif;line-height:1.4}
.valvet-report h2{margin:0 0 .5rem;font-size:1.25rem;font-weight:650}
.valvet-report .meta{margin:0 0 .75rem;color:#424242;font-size:.9rem}
.valvet-report .meta b{color:#1a1a1a;font-weight:600}
.valvet-report .summary{display:flex;flex-wrap:wrap;gap:.4rem;margin:0 0 .75rem}
.valvet-report .chip{display:inline-block;padding:.2rem .55rem;border-radius:999px;font-size:.8rem;font-weight:650;border:1px solid transparent}
.valvet-report .chip-total{background:#eceff1;color:#263238;border-color:#cfd8dc}
.valvet-report .chip-critical{background:#c62828;color:#fff}
.valvet-report .chip-warning{background:#f57c00;color:#fff}
.valvet-report .chip-info{background:#1976d2;color:#fff}
.valvet-report .legend{margin:0 0 .75rem;font-size:.8rem;color:#546e7a}
.valvet-report .legend .ch-num,.valvet-report .legend .ch-letter,.valvet-report .legend .ch-punct{font-weight:700}
.valvet-report .empty{margin:.5rem 0;padding:.75rem 1rem;background:#f5f5f5;border:1px solid #e0e0e0;border-radius:6px;color:#616161}
.ch-num{color:#1565c0;font-weight:600;font-variant-numeric:tabular-nums}
.ch-letter{color:#2e7d32}
.ch-punct{color:#6a1b9a}
mark.diff{background:#ffe082;color:#1a1a1a;padding:0 .12em;border-radius:2px}
.badge{display:inline-block;padding:.12rem .45rem;border-radius:4px;font-size:.75rem;font-weight:700;letter-spacing:.02em;text-transform:uppercase}
.badge-critical{background:#c62828;color:#fff}
.badge-warning{background:#f57c00;color:#fff}
.badge-info{background:#1976d2;color:#fff}
.badge-unknown{background:#78909c;color:#fff}
table.report{border-collapse:collapse;width:100%;max-width:100%;margin-top:.25rem;background:#fff;font-size:.9rem}
table.report td,table.report th{border:1px solid #cfd8dc;padding:7px 10px;text-align:left;vertical-align:top}
table.report th{background:#eceff1;color:#263238;font-weight:650;position:sticky;top:0;z-index:2}
table.report td.cell-code{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:.86rem;line-height:1.45;white-space:pre-wrap;word-break:break-word}
table.report td.cell-empty{color:#90a4ae}
table.report tr.sev-critical td{background:#fdecea}
table.report tr.sev-warning td{background:#fff8e1}
table.report tr.sev-info td{background:#e3f2fd}
table.report tr.sev-critical td:first-child{border-left:4px solid #c62828}
table.report tr.sev-warning td:first-child{border-left:4px solid #f57c00}
table.report tr.sev-info td:first-child{border-left:4px solid #1976d2}
table.report td.cell-mismatch{box-shadow:inset 0 0 0 1px rgba(198,40,40,.35)}
""".replace("\n", "")


def _escape_cell_plain(cell: str) -> str:
    return html_mod.escape(cell)


def _cell_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    if isinstance(value, str) and value.lower() == "nan":
        return ""
    return str(value)


def _severity_key(value: object) -> str:
    return _cell_text(value).strip().lower()


def _issue_label(raw: str) -> str:
    key = raw.strip().lower()
    if key in _ISSUE_LABELS:
        return _ISSUE_LABELS[key]
    if not raw:
        return ""
    return raw.replace("_", " ").strip()


def _column_header(name: str) -> str:
    return _COLUMN_HEADERS.get(name, name)


def escape_cell_with_char_highlight(cell: str) -> str:
    """
    Escape HTML and wrap runs of digits / letters / punctuation in spans for readability.

    Whitespace stays unwrapped so layout stays natural; coord and part strings use monospace via td.cell-code.
    """
    if not cell:
        return ""

    def kind(ch: str) -> str:
        if ch.isdigit():
            return "num"
        if ch.isalpha():
            return "letter"
        if ch.isspace():
            return "ws"
        return "punct"

    parts: list[str] = []
    i = 0
    n = len(cell)
    while i < n:
        k = kind(cell[i])
        j = i + 1
        while j < n and kind(cell[j]) == k:
            j += 1
        chunk = cell[i:j]
        esc = html_mod.escape(chunk)
        if k == "ws":
            parts.append(esc)
        elif k == "num":
            parts.append(f'<span class="ch-num">{esc}</span>')
        elif k == "letter":
            parts.append(f'<span class="ch-letter">{esc}</span>')
        else:
            parts.append(f'<span class="ch-punct">{esc}</span>')
        i = j
    return "".join(parts)


def escape_cell_with_value_diff(cell: str, other: str) -> str:
    """Char highlighting plus a yellow mark on the substring that differs from *other*."""
    if not cell:
        return ""
    if not other or cell == other:
        return escape_cell_with_char_highlight(cell)
    n = min(len(cell), len(other))
    prefix = 0
    while prefix < n and cell[prefix] == other[prefix]:
        prefix += 1
    suffix = 0
    max_suf = n - prefix
    while suffix < max_suf and cell[-(suffix + 1)] == other[-(suffix + 1)]:
        suffix += 1
    mid_end = len(cell) - suffix
    if prefix >= mid_end:
        return escape_cell_with_char_highlight(cell)
    head = escape_cell_with_char_highlight(cell[:prefix])
    mid = escape_cell_with_char_highlight(cell[prefix:mid_end])
    tail = escape_cell_with_char_highlight(cell[mid_end:])
    return f'{head}<mark class="diff">{mid}</mark>{tail}'


def _severity_counts(df: pd.DataFrame) -> dict[str, int]:
    counts = {"critical": 0, "warning": 0, "info": 0}
    if df is None or df.empty or "Severity" not in df.columns:
        return counts
    for raw in df["Severity"]:
        key = _severity_key(raw)
        if key in counts:
            counts[key] += 1
    return counts


def _summary_html(df: pd.DataFrame) -> str:
    n = 0 if df is None or df.empty else len(df)
    counts = _severity_counts(df)
    chips = [
        f'<span class="chip chip-total">{n} issue{"s" if n != 1 else ""}</span>',
        f'<span class="chip chip-critical">{counts["critical"]} critical</span>',
        f'<span class="chip chip-warning">{counts["warning"]} warning</span>',
        f'<span class="chip chip-info">{counts["info"]} info</span>',
    ]
    return '<div class="summary">' + "".join(chips) + "</div>"


def _legend_html() -> str:
    return (
        '<p class="legend">'
        '<span class="ch-num">Digits</span>, '
        '<span class="ch-letter">letters</span>, '
        '<span class="ch-punct">punctuation</span> are coloured in code cells. '
        '<mark class="diff">Yellow</mark> marks BOM vs PnP differences.'
        "</p>"
    )


def _severity_badge(sev: str) -> str:
    label = _SEVERITY_LABELS.get(sev, sev.title() if sev else "")
    cls = sev if sev in SEVERITY_COLORS else "unknown"
    if not label:
        return ""
    return f'<span class="badge badge-{html_mod.escape(cls)}">{html_mod.escape(label)}</span>'


def result_dataframe_to_html(
    df: pd.DataFrame,
    bom_path: str = "",
    pnp_path: str = "",
) -> str:
    """Build a self-contained HTML fragment (no html/body) for clipboard and viewers."""
    bom_name = Path(bom_path).name if bom_path else "(no BOM file)"
    pnp_name = Path(pnp_path).name if pnp_path else "(no PnP file)"
    out: list[str] = [
        '<div class="valvet-report">',
        "<h2>Cross-check report</h2>",
        "<p class=\"meta\">",
        f"BOM: <b>{html_mod.escape(bom_name)}</b><br/>",
        f"PnP: <b>{html_mod.escape(pnp_name)}</b><br/>",
        f"Generated: <b>{time.strftime('%Y-%m-%d %H:%M:%S')}</b>",
        "</p>",
        _summary_html(df),
        f"<style>{_REPORT_CSS}</style>",
    ]
    if df is None or df.empty:
        out.append('<p class="empty">No issues in this view.</p>')
        out.append("</div>")
        return "\n".join(out)

    out.append(_legend_html())
    cols = [str(c) for c in df.columns]
    out.append('<table class="report"><thead><tr>')
    for c in cols:
        out.append(f"<th>{html_mod.escape(_column_header(c))}</th>")
    out.append("</tr></thead><tbody>")

    has_sev = "Severity" in df.columns
    has_bom = "BOM_Value" in df.columns
    has_pnp = "PnP_Value" in df.columns

    for _, row in df.iterrows():
        sev = _severity_key(row["Severity"]) if has_sev else ""
        row_cls = f' class="sev-{html_mod.escape(sev)}"' if sev in SEVERITY_COLORS else ""
        out.append(f"<tr{row_cls}>")
        bom_txt = _cell_text(row["BOM_Value"]) if has_bom else ""
        pnp_txt = _cell_text(row["PnP_Value"]) if has_pnp else ""
        values_differ = bool(bom_txt and pnp_txt and bom_txt != pnp_txt)
        for c in df.columns:
            col_name = str(c)
            cell = _cell_text(row[c])
            if col_name == "Severity":
                out.append(f"<td>{_severity_badge(sev)}</td>")
                continue
            if col_name == "IssueType":
                out.append(f"<td>{_escape_cell_plain(_issue_label(cell))}</td>")
                continue
            if col_name in _HIGHLIGHT_COLUMNS:
                classes = ["cell-code"]
                if not cell:
                    classes.append("cell-empty")
                    inner = "—"
                elif col_name == "BOM_Value" and values_differ:
                    classes.append("cell-mismatch")
                    inner = escape_cell_with_value_diff(cell, pnp_txt)
                elif col_name == "PnP_Value" and values_differ:
                    classes.append("cell-mismatch")
                    inner = escape_cell_with_value_diff(cell, bom_txt)
                else:
                    inner = escape_cell_with_char_highlight(cell)
                out.append(f'<td class="{" ".join(classes)}">{inner}</td>')
            else:
                out.append(f"<td>{_escape_cell_plain(cell)}</td>")
        out.append("</tr>")
    out.append("</tbody></table>")
    out.append("</div>")
    return "\n".join(out)


def html_document_from_fragment(
    fragment: str,
    *,
    title: str = "Cross-check report",
) -> str:
    """Wrap the clipboard-oriented fragment in a minimal HTML5 document for saving to disk."""
    safe_title = html_mod.escape(title)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8"/>\n'
        '<meta name="color-scheme" content="light"/>\n'
        f"<title>{safe_title}</title>\n"
        "<style>"
        "html{color-scheme:light}"
        "body{margin:1.25rem;background:#fafafa;color:#1a1a1a}"
        "</style>\n"
        "</head>\n"
        "<body>\n"
        f"{fragment}\n"
        "</body>\n"
        "</html>\n"
    )


def result_dataframe_plain_text(df: pd.DataFrame) -> str:
    """Plain text fallback for clipboard."""
    if df is None or df.empty:
        return ""
    return df.to_string(index=False)
