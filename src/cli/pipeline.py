"""Headless load / clean / merge / export (no Qt)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from clean_component import clean_preview
from clean_types import CleanConfig
from cli.session import CliSession
from mmd_export import merge_dataframe_to_mmd_mercury
from report_html import result_dataframe_to_html
from services.clean_apply import apply_clean_preview_to_bom
from services.clean_import import import_bom_comments_for_clean
from services.file_loading import read_pnp_dataframe
from services.processor_config import build_processor_config
from smt_processor import read_file


def _read_cli_table(path: str, separator: str) -> pd.DataFrame:
    """Load with file headers so mappings use column names (not GUI index labels)."""
    if separator == "spaces":
        return read_pnp_dataframe(path, "spaces", 0, -1)
    sep = None if separator in ("", "auto") else separator
    return read_file(
        path,
        first_row=0,
        last_row=-1,
        separator=sep,
        column_headers_from_file=True,
    )


def load_bom(session: CliSession, path: str, *, separator: str | None = None) -> None:
    sep = separator if separator is not None else session.bom_sep
    session.bom_path = str(path)
    session.bom_sep = sep
    session.bom_df = _read_cli_table(path, sep)


def load_pnp(session: CliSession, path: str, *, separator: str | None = None) -> None:
    sep = separator if separator is not None else session.pnp_sep
    session.pnp_path = str(path)
    session.pnp_sep = sep
    session.pnp_df = _read_cli_table(path, sep)


def reload_tables(session: CliSession) -> None:
    if session.bom_path:
        load_bom(session, session.bom_path, separator=session.bom_sep)
    if session.pnp_path:
        load_pnp(session, session.pnp_path, separator=session.pnp_sep)


def apply_map_json(session: CliSession, data: dict) -> None:
    bom = data.get("bom")
    pnp = data.get("pnp")
    if isinstance(bom, dict):
        session.bom_mappings = {str(k): str(v) for k, v in bom.items() if v}
    if isinstance(pnp, dict):
        session.pnp_mappings = {str(k): str(v) for k, v in pnp.items() if v}


def comment_column(session: CliSession) -> str:
    col = session.bom_mappings.get("Comment") or session.bom_mappings.get("comment")
    if col and session.bom_df is not None and col in session.bom_df.columns:
        return col
    if session.bom_df is None or session.bom_df.empty:
        raise ValueError("BOM is not loaded")
    for name in session.bom_df.columns:
        u = str(name).upper()
        if "COMMENT" in u or "VALUE" in u or "DESC" in u:
            return str(name)
    return str(session.bom_df.columns[-1])


def clean_comments(
    session: CliSession, *, apply: bool = False, config: CleanConfig | None = None
) -> list[tuple]:
    if session.bom_df is None:
        raise ValueError("BOM is not loaded")
    col = comment_column(session)
    indices = list(range(len(session.bom_df)))
    comments = import_bom_comments_for_clean(session.bom_df, [col], indices)
    preview = clean_preview(comments, config)
    session.last_clean_preview = preview
    if apply:
        session.bom_df = apply_clean_preview_to_bom(
            session.bom_df, preview, indices, col, replace_source=False
        )
    return preview


def merge_and_check(
    session: CliSession, *, overlap: bool = False
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if session.bom_df is None or session.pnp_df is None:
        raise ValueError("BOM and PnP must be loaded")
    proc = build_processor_config(
        session.bom_df,
        session.pnp_df,
        session.bom_mappings,
        session.pnp_mappings,
        pnp_xy_are_mils=not session.coord_unit_mm,
        check_overlap=overlap,
    )
    session.merge_df = proc.merge_bom_pnp(include_dnp=True)
    session.report_df = proc.cross_check()
    return session.merge_df, session.report_df


def export_merge(session: CliSession, path: str) -> None:
    if session.merge_df is None:
        raise ValueError("Nothing to export; run merge first")
    p = Path(path)
    proc = build_processor_config(
        session.bom_df if session.bom_df is not None else pd.DataFrame(),
        session.pnp_df if session.pnp_df is not None else pd.DataFrame(),
        session.bom_mappings,
        session.pnp_mappings,
        pnp_xy_are_mils=not session.coord_unit_mm,
    )
    if p.suffix.lower() in (".xlsx", ".xls"):
        proc.export_excel(session.merge_df, str(p))
    else:
        proc.export_csv(session.merge_df, str(p))


def write_report_html(session: CliSession, path: str) -> None:
    if session.report_df is None:
        raise ValueError("Nothing to report; run merge first")
    html = result_dataframe_to_html(
        session.report_df, bom_path=session.bom_path, pnp_path=session.pnp_path
    )
    Path(path).write_text(html, encoding="utf-8")


def export_mmd(session: CliSession, path: str, *, layer: str = "") -> None:
    if session.merge_df is None:
        raise ValueError("Nothing to export; run merge first")
    df = session.merge_df
    if layer and "Layer" in df.columns:
        want = layer.strip().upper()
        df = df[df["Layer"].astype(str).str.upper().str.contains(want, na=False)]
    text = merge_dataframe_to_mmd_mercury(df, pnp_xy_are_mm=session.coord_unit_mm)
    Path(path).write_text(text, encoding="utf-8")
