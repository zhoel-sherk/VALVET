"""Qt-free BOM/PnP project pair (``.valvet-project.json``)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROJECT_FILENAME = ".valvet-project.json"


def project_payload(
    *,
    bom_path: str = "",
    pnp_path: str = "",
    pnp_secondary_path: str = "",
    mdb_path: str = "",
) -> dict[str, str]:
    return {
        "version": 1,
        "bom_path": str(bom_path or ""),
        "pnp_path": str(pnp_path or ""),
        "pnp_secondary_path": str(pnp_secondary_path or ""),
        "mdb_path": str(mdb_path or ""),
    }


def save_project_file(path: str | Path, payload: dict[str, Any]) -> Path:
    p = Path(path)
    p.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return p


def load_project_file(path: str | Path) -> dict[str, str]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Project file is not a JSON object")
    return project_payload(
        bom_path=str(data.get("bom_path", "") or ""),
        pnp_path=str(data.get("pnp_path", "") or ""),
        pnp_secondary_path=str(data.get("pnp_secondary_path", "") or ""),
        mdb_path=str(data.get("mdb_path", "") or ""),
    )


def push_mru(paths: list[str], new_path: str, *, limit: int = 10) -> list[str]:
    p = str(new_path or "").strip()
    if not p:
        return list(paths)
    out = [p] + [x for x in paths if x != p]
    return out[:limit]
