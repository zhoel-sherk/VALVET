"""Persisted CLI session: paths and mappings only (DataFrames stay in memory)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

DEFAULT_SESSION_PATH = ".valvet-cli-session.json"


@dataclass
class CliSession:
    bom_path: str = ""
    pnp_path: str = ""
    bom_sep: str = "auto"
    pnp_sep: str = "auto"
    coord_unit_mm: bool = True
    bom_mappings: dict[str, str] = field(default_factory=dict)
    pnp_mappings: dict[str, str] = field(default_factory=dict)
    bom_df: pd.DataFrame | None = field(default=None, repr=False, compare=False)
    pnp_df: pd.DataFrame | None = field(default=None, repr=False, compare=False)
    merge_df: pd.DataFrame | None = field(default=None, repr=False, compare=False)
    report_df: pd.DataFrame | None = field(default=None, repr=False, compare=False)
    last_clean_preview: list[tuple] | None = field(
        default=None, repr=False, compare=False
    )

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "bom_path": self.bom_path,
            "pnp_path": self.pnp_path,
            "bom_sep": self.bom_sep,
            "pnp_sep": self.pnp_sep,
            "coord_unit_mm": self.coord_unit_mm,
            "bom_mappings": dict(self.bom_mappings),
            "pnp_mappings": dict(self.pnp_mappings),
        }

    @classmethod
    def from_json_dict(cls, data: dict[str, Any]) -> CliSession:
        return cls(
            bom_path=str(data.get("bom_path", "") or ""),
            pnp_path=str(data.get("pnp_path", "") or ""),
            bom_sep=str(data.get("bom_sep", "auto") or "auto"),
            pnp_sep=str(data.get("pnp_sep", "auto") or "auto"),
            coord_unit_mm=bool(data.get("coord_unit_mm", True)),
            bom_mappings=dict(data.get("bom_mappings") or {}),
            pnp_mappings=dict(data.get("pnp_mappings") or {}),
        )


def load_session_file(path: str | Path) -> CliSession:
    p = Path(path)
    if not p.is_file():
        return CliSession()
    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return CliSession()
    return CliSession.from_json_dict(raw)


def save_session_file(session: CliSession, path: str | Path) -> None:
    p = Path(path)
    p.write_text(
        json.dumps(session.to_json_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
