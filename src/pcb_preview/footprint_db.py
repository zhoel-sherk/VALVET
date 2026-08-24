"""SQLite-backed footprint cache + key normalization (no Qt/pandas)."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Optional

from pcb_preview.footprint_heuristic import heuristic_footprint_outline
from pcb_preview.types import (
    BBoxMM,
    FootprintOutlineMM,
    PadRectMM,
    StrokeCircleMM,
    StrokeLineMM,
)


def default_data_dir(base: Optional[Path] = None) -> Path:
    if base is not None:
        root = base
    else:
        from app_paths import pcb_preview_data_root

        root = pcb_preview_data_root()
    (root / "footprints").mkdir(parents=True, exist_ok=True)
    return root


def normalize_footprint_key(name: str) -> str:
    s = (name or "").strip()
    s = s.replace("\\", "/")
    s = re.sub(r"\s+", " ", s)
    return s.lower()


class FootprintStore:
    """
    SQLite-backed footprint outline cache + key normalization.

    Resolution order: exact key → normalized key → user aliases (from_key → to_key)
    → heuristic outline (Tier A).
    """

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self._root = default_data_dir(data_dir)
        self._db_path = self._root / "footprints.sqlite3"
        self._aliases_path = self._root / "aliases.txt"
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS footprints (
                key TEXT PRIMARY KEY,
                norm_key TEXT,
                source_path TEXT,
                sha256 TEXT,
                outline_json TEXT,
                min_x REAL, min_y REAL, max_x REAL, max_y REAL
            )"""
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_norm ON footprints(norm_key)"
        )
        self._aliases_cache: dict[str, str] | None = None
        self._aliases_mtime: float | None = None

    def close(self) -> None:
        self._conn.close()

    def _aliases(self) -> dict[str, str]:
        mtime: float | None = None
        if self._aliases_path.is_file():
            mtime = self._aliases_path.stat().st_mtime
        if self._aliases_cache is not None and self._aliases_mtime == mtime:
            return self._aliases_cache
        out: dict[str, str] = {}
        if not self._aliases_path.is_file():
            self._aliases_cache = out
            self._aliases_mtime = mtime
            return out
        for line in self._aliases_path.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=>" in line:
                a, b = line.split("=>", 1)
            elif "\t" in line:
                a, b = line.split("\t", 1)
            else:
                parts = line.split(None, 1)
                if len(parts) != 2:
                    continue
                a, b = parts
            out[normalize_footprint_key(a.strip())] = b.strip()
        self._aliases_cache = out
        self._aliases_mtime = mtime
        return out

    @staticmethod
    def _outline_from_dict(d: dict[str, Any]) -> FootprintOutlineMM:
        lines = tuple(StrokeLineMM(**x) for x in d.get("lines", []))
        circles = tuple(StrokeCircleMM(**x) for x in d.get("circles", []))
        pads = tuple(PadRectMM(**x) for x in d.get("pads", []))
        bb = d.get("bbox", {})
        bbox = BBoxMM(
            float(bb["min_x"]),
            float(bb["min_y"]),
            float(bb["max_x"]),
            float(bb["max_y"]),
        )
        return FootprintOutlineMM(
            lines=lines,
            circles=circles,
            pads=pads,
            bbox=bbox,
            source=d.get("source", "none"),  # type: ignore[arg-type]
        )

    def _row_to_outline(self, row: tuple[Any, ...]) -> FootprintOutlineMM:
        d = json.loads(str(row[0]))
        return self._outline_from_dict(d)

    def lookup_outline(self, footprint_name: str) -> FootprintOutlineMM:
        """Resolve outline: DB (legacy cached outlines) → Tier A heuristic."""
        raw = (footprint_name or "").strip()
        if not raw:
            return FootprintOutlineMM(source="none")
        aliases = self._aliases()
        chain = [raw]
        nk = normalize_footprint_key(raw)
        if nk in aliases:
            chain.append(aliases[nk])

        for key in chain:
            cur = self._conn.execute(
                "SELECT outline_json FROM footprints WHERE key = ? OR norm_key = ?",
                (key, normalize_footprint_key(key)),
            ).fetchone()
            if cur:
                return self._row_to_outline(cur)

        h = heuristic_footprint_outline(raw)
        if h is not None:
            return h
        return FootprintOutlineMM(source="none")
