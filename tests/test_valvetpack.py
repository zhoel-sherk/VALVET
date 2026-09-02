"""Round-trip .valvetpack tables, profile JSON, and extra file members."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from valvetpack import ValvetpackError, load_valvetpack, save_valvetpack


def test_save_requires_something(tmp_path: Path) -> None:
    with pytest.raises(ValvetpackError):
        save_valvetpack(
            tmp_path / "empty.valvetpack",
            bom_df=None,
            pnp_df=None,
            merge_df=None,
        )


def test_save_load_profile_without_tables(tmp_path: Path) -> None:
    dest = tmp_path / "p.valvetpack"
    save_valvetpack(
        dest,
        bom_df=None,
        pnp_df=None,
        profile={"v": 1, "ui": {"language": "ru"}},
    )
    data = load_valvetpack(dest)
    assert data["bom_df"] is None
    assert data["profile"]["ui"]["language"] == "ru"
    assert data["manifest"]["members"]["profile"] == "profile.json"


def test_save_load_tables_and_extra_file(tmp_path: Path) -> None:
    dest = tmp_path / "t.valvetpack"
    bom = pd.DataFrame({"REF": ["R1"], "Comment": ["10k"]})
    save_valvetpack(
        dest,
        bom_df=bom,
        pnp_df=None,
        extra_members={"files/gerber/00_top.gbr": b"G04 dummy*\n"},
    )
    data = load_valvetpack(dest)
    assert list(data["bom_df"]["REF"]) == ["R1"]
    assert data["extra_members"]["files/gerber/00_top.gbr"] == b"G04 dummy*\n"
    assert data["manifest"]["gerber"] == ["files/gerber/00_top.gbr"]
