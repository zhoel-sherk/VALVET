"""
HTML report from cross-check DataFrame (smt_processor output).

(c) 2023-2026 Mariusz Midor
"""

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

_REPORT_TABLE_CSS = (
    ".ch-num{color:#0d47a1;font-weight:600;font-variant-numeric:tabular-nums}"
    ".ch-letter{color:#1b5e20}"
    ".ch-punct{color:#6a1b9a}"
    "table.report{border-collapse:collapse;width:100%;max-width:100%;margin-top:.75rem}"
    "table.report td,table.report th{border:1px solid #bdbdbd;padding:6px 10px;text-align:left;vertical-align:top}"
    "table.report th{background:#eceff1;font-weight:600;position:sticky;top:0;z-index:2;"
    "box-shadow:0 2px 2px -1px rgba(0,0,0,.12)}"
    "table.report td.cell-code{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;"
    "font-size:.9rem;line-height:1.45;white-space:pre-wrap;word-break:break-word}"
)


def _escape_cell_plain(cell: str) -> str:
    return html_mod.escape(cell)


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


def result_dataframe_to_html(
    df: pd.DataFrame,
    bom_path: str = "",
    pnp_path: str = "",
) -> str:
    """Build a self-contained HTML fragment (no html/body) for clipboard and viewers."""
    bom_name = Path(bom_path).name if bom_path else "(no BOM file)"
    pnp_name = Path(pnp_path).name if pnp_path else "(no PnP file)"
    out: list[str] = [
        "<h2>Cross-check report</h2>",
        "<p>",
        f"BOM: <b>{html_mod.escape(bom_name)}</b><br/>",
        f"PnP: <b>{html_mod.escape(pnp_name)}</b><br/>",
        f"Generated: <b>{time.strftime('%Y-%m-%d %H:%M:%S')}</b>",
        "</p>",
        f"<style>{_REPORT_TABLE_CSS}</style>",
    ]
    if df is None or df.empty:
        out.append("<p><i>Empty result</i></p>")
        return "\n".join(out)

    cols = [str(c) for c in df.columns]
    out.append('<table class="report"><thead><tr>')
    for c in cols:
        out.append(f"<th>{html_mod.escape(c)}</th>")
    out.append("</tr></thead><tbody>")

    sev_key = "Severity" if "Severity" in df.columns else None
    for _, row in df.iterrows():
        sev = str(row[sev_key]).lower() if sev_key is not None else ""
        color = SEVERITY_COLORS.get(sev, "")
        row_style = f' style="background-color:{color}18"' if color else ""
        out.append(f"<tr{row_style}>")
        for c in df.columns:
            v = row[c]
            if isinstance(v, float) and pd.isna(v):
                cell = ""
            else:
                cell = (
                    ""
                    if (v is None or (isinstance(v, str) and v.lower() == "nan"))
                    else str(v)
                )
            col_name = str(c)
            if col_name in _HIGHLIGHT_COLUMNS:
                inner = escape_cell_with_char_highlight(cell)
                out.append(f'<td class="cell-code">{inner}</td>')
            else:
                out.append(f"<td>{_escape_cell_plain(cell)}</td>")
        out.append("</tr>")
    out.append("</tbody></table>")
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
        f"<title>{safe_title}</title>\n"
        "<style>"
        "body{font-family:system-ui,Segoe UI,sans-serif;margin:1rem;line-height:1.35;"
        "background:#fafafa;color:#222}"
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
