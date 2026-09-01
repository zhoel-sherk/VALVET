"""
.valvetpack — ZIP restore bundle (manifest + pickled DataFrames).

Legacy .boomerpack files use the same on-disk format (format_version unchanged).
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import pandas as pd

VALVETPACK_FORMAT_VERSION = 1
BOOMERPACK_FORMAT_VERSION = VALVETPACK_FORMAT_VERSION
MANIFEST_NAME = "manifest.json"
META_NAME = "meta.json"
BOM_PKL = "bom.pkl"
PNP_PKL = "pnp.pkl"
MERGE_PKL = "merge.pkl"
VALVETPACK_EXT = ".valvetpack"
LEGACY_PACK_EXT = ".boomerpack"
OPEN_FILTER = "Valvetpack (*.valvetpack);;Legacy Valvetpack (*.boomerpack);;All (*)"
SAVE_FILTER = "Valvetpack (*.valvetpack);;All (*)"


class ValvetpackError(Exception):
    pass


BoomerpackError = ValvetpackError


def save_valvetpack(
    path: str | Path,
    *,
    bom_df: Optional[pd.DataFrame],
    pnp_df: Optional[pd.DataFrame],
    merge_df: Optional[pd.DataFrame] = None,
    meta: Optional[dict[str, Any]] = None,
    manifest_extras: Optional[dict[str, Any]] = None,
) -> None:
    """Write a .valvetpack zip. At least one of bom_df / pnp_df / merge_df must be non-empty."""
    has_bom = bom_df is not None and not bom_df.empty
    has_pnp = pnp_df is not None and not pnp_df.empty
    has_merge = merge_df is not None and not merge_df.empty
    if not (has_bom or has_pnp or has_merge):
        raise ValvetpackError(
            "Nothing to save: BOM, PnP, and Merge tables are all empty."
        )
    p = Path(path)
    lower = str(p).lower()
    if not lower.endswith(VALVETPACK_EXT) and not lower.endswith(LEGACY_PACK_EXT):
        p = p.with_suffix(VALVETPACK_EXT)
    manifest: dict[str, Any] = {
        "format_version": VALVETPACK_FORMAT_VERSION,
        "app": "VALVET",
        "members": {
            "bom": BOM_PKL if bom_df is not None and not bom_df.empty else None,
            "pnp": PNP_PKL if pnp_df is not None and not pnp_df.empty else None,
            "merge": MERGE_PKL if merge_df is not None and not merge_df.empty else None,
        },
        "gerber": [],
    }
    if manifest_extras:
        manifest.update(manifest_extras)
    user_meta = dict(meta or {})
    user_meta.setdefault("saved_at", datetime.now(timezone.utc).isoformat())

    with zipfile.ZipFile(p, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, indent=2))
        zf.writestr(META_NAME, json.dumps(user_meta, ensure_ascii=False, indent=2))
        if bom_df is not None and not bom_df.empty:
            bio = io.BytesIO()
            bom_df.to_pickle(bio)
            zf.writestr(BOM_PKL, bio.getvalue())
        if pnp_df is not None and not pnp_df.empty:
            bio = io.BytesIO()
            pnp_df.to_pickle(bio)
            zf.writestr(PNP_PKL, bio.getvalue())
        if merge_df is not None and not merge_df.empty:
            bio = io.BytesIO()
            merge_df.to_pickle(bio)
            zf.writestr(MERGE_PKL, bio.getvalue())


def load_valvetpack(path: str | Path) -> dict[str, Any]:
    """
    Read .valvetpack or legacy .boomerpack. Returns keys: manifest, meta, bom_df,
    pnp_df, merge_df (optional Nones).
    """
    p = Path(path)
    if not p.is_file():
        raise ValvetpackError(f"Not a file: {p}")
    with zipfile.ZipFile(p, "r") as zf:
        names = set(zf.namelist())
        if MANIFEST_NAME not in names:
            raise ValvetpackError(f"Missing {MANIFEST_NAME}")
        manifest = json.loads(zf.read(MANIFEST_NAME).decode("utf-8"))
        fv = int(manifest.get("format_version", 0))
        if fv != VALVETPACK_FORMAT_VERSION:
            raise ValvetpackError(
                f"Unsupported format_version {fv!r} (this build expects {VALVETPACK_FORMAT_VERSION})"
            )
        meta: dict[str, Any] = {}
        if META_NAME in names:
            meta = json.loads(zf.read(META_NAME).decode("utf-8"))
        bom_df = None
        pnp_df = None
        merge_df = None
        if BOM_PKL in names:
            bom_df = pd.read_pickle(io.BytesIO(zf.read(BOM_PKL)))
        if PNP_PKL in names:
            pnp_df = pd.read_pickle(io.BytesIO(zf.read(PNP_PKL)))
        if MERGE_PKL in names:
            merge_df = pd.read_pickle(io.BytesIO(zf.read(MERGE_PKL)))
    return {
        "manifest": manifest,
        "meta": meta,
        "bom_df": bom_df,
        "pnp_df": pnp_df,
        "merge_df": merge_df,
    }


def save_boomerpack(
    path: str | Path,
    *,
    bom_df: Optional[pd.DataFrame],
    pnp_df: Optional[pd.DataFrame],
    merge_df: Optional[pd.DataFrame] = None,
    meta: Optional[dict[str, Any]] = None,
    manifest_extras: Optional[dict[str, Any]] = None,
) -> None:
    save_valvetpack(
        path,
        bom_df=bom_df,
        pnp_df=pnp_df,
        merge_df=merge_df,
        meta=meta,
        manifest_extras=manifest_extras,
    )


def load_boomerpack(path: str | Path) -> dict[str, Any]:
    return load_valvetpack(path)
