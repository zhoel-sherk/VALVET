"""CLI pipeline smoke: load example-like CSV, merge without GUI."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from cli.hanwha import format_tables
from cli.pipeline import (
    clean_comments,
    export_merge,
    export_mmd,
    load_bom,
    load_pnp,
    merge_and_check,
    write_report_html,
)
from cli.session import CliSession, load_session_file, save_session_file
from machine_library.hanwha_mdbtools import HanwhaMdbToolsError
from smt_processor import SMTFileNotFoundError

_ROOT = Path(__file__).resolve().parents[1]
_TABULAR = _ROOT / "tests" / "fixtures" / "clean_corpus" / "tabular_sample.csv"


def _write_pnp(path: Path) -> None:
    path.write_text(
        "Designator,Mid X,Mid Y,Rotation,Layer,Footprint\n"
        "R1,1.0,2.0,0,Top,0402\n"
        "C1,3.0,4.0,90,Top,0402\n",
        encoding="utf-8",
    )


def test_session_json_omits_dataframes(tmp_path: Path) -> None:
    session = CliSession(bom_path="a.csv", pnp_path="b.csv", coord_unit_mm=False)
    session.bom_df = pd.DataFrame({"x": [1]})
    dest = tmp_path / "sess.json"
    save_session_file(session, dest)
    loaded = load_session_file(dest)
    assert loaded.bom_path == "a.csv"
    assert loaded.pnp_path == "b.csv"
    assert loaded.coord_unit_mm is False
    assert loaded.bom_df is None


def test_pipeline_load_bom_missing_file(tmp_path: Path) -> None:
    session = CliSession()
    missing = tmp_path / "missing.csv"
    with pytest.raises(SMTFileNotFoundError):
        load_bom(session, str(missing), separator=",")


def test_pipeline_load_clean_merge_export(tmp_path: Path) -> None:
    assert _TABULAR.is_file()
    pnp_path = tmp_path / "pnp.csv"
    _write_pnp(pnp_path)
    session = CliSession(
        bom_mappings={"REF": "Ref", "Comment": "Comment"},
        pnp_mappings={
            "REF": "Designator",
            "X": "Mid X",
            "Y": "Mid Y",
            "Rotation": "Rotation",
            "Layer": "Layer",
            "Footprint": "Footprint",
        },
    )
    load_bom(session, str(_TABULAR), separator=",")
    load_pnp(session, str(pnp_path), separator=",")
    assert session.bom_df is not None
    assert "Comment" in session.bom_df.columns
    preview = clean_comments(session, apply=True)
    assert len(preview) == 2
    assert "comment" in session.bom_df.columns
    cleaned = session.bom_df["comment"].astype(str).tolist()
    assert any("0402" in c or "10" in c for c in cleaned)
    merge_df, report_df = merge_and_check(session)
    assert list(merge_df.columns) == [
        "Ref",
        "Value",
        "Footprint",
        "X",
        "Y",
        "Rotation",
        "Layer",
    ]
    assert set(merge_df["Ref"].astype(str)) == {"R1", "C1"}
    assert report_df is not None
    xlsx = tmp_path / "out.xlsx"
    export_merge(session, str(xlsx))
    assert xlsx.is_file()
    html = tmp_path / "report.html"
    write_report_html(session, str(html))
    assert "Cross-check" in html.read_text(encoding="utf-8")
    mmd = tmp_path / "out.mmd"
    export_mmd(session, str(mmd), layer="TOP")
    assert mmd.is_file()
    assert mmd.read_text(encoding="utf-8").strip() != ""


def test_hanwha_tables_skip_without_mdb() -> None:
    mdb = None
    for cand in (
        _ROOT / "examples" / "UPD.MDB",
        _ROOT.parent / "UPD.MDB",
    ):
        if cand.is_file():
            mdb = cand
            break
    if mdb is None:
        pytest.skip("UPD.MDB not present")
    try:
        text = format_tables(str(mdb))
    except HanwhaMdbToolsError as exc:
        pytest.skip(f"cannot read mdb: {exc}")
    assert text
    assert "PART_Det" in text or "part" in text.lower()
