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
PROFILE_JSON = "profile.json"
FILES_PREFIX = "files/"
VALVETPACK_EXT = ".valvetpack"
LEGACY_PACK_EXT = ".boomerpack"
OPEN_FILTER = "Valvetpack (*.valvetpack);;Legacy Valvetpack (*.boomerpack);;All (*)"
SAVE_FILTER = "Valvetpack (*.valvetpack);;All (*)"


class ValvetpackError(Exception):
    pass


BoomerpackError = ValvetpackError

PACK_INCLUDE_KEYS = (
    "tables",
    "profile",
    "mdb",
    "sql_cache",
    "sql_db",
    "excel",
    "gerber",
    "yamaha",
)

PACK_INCLUDE_DEFAULTS: dict[str, bool] = {
    "tables": True,
    "profile": True,
    "mdb": False,
    "sql_cache": False,
    "sql_db": False,
    "excel": False,
    "gerber": False,
    "yamaha": False,
}


def _df_nonempty(df: Optional[pd.DataFrame]) -> bool:
    return df is not None and not df.empty


def save_valvetpack(
    path: str | Path,
    *,
    bom_df: Optional[pd.DataFrame],
    pnp_df: Optional[pd.DataFrame],
    merge_df: Optional[pd.DataFrame] = None,
    meta: Optional[dict[str, Any]] = None,
    manifest_extras: Optional[dict[str, Any]] = None,
    profile: Optional[dict[str, Any]] = None,
    extra_members: Optional[dict[str, bytes]] = None,
) -> None:
    """Write a .valvetpack zip. Need at least one table, profile, or extra file."""
    has_bom = _df_nonempty(bom_df)
    has_pnp = _df_nonempty(pnp_df)
    has_merge = _df_nonempty(merge_df)
    extras = {str(k): bytes(v) for k, v in (extra_members or {}).items() if v}
    has_profile = bool(profile)
    if not (has_bom or has_pnp or has_merge or has_profile or extras):
        raise ValvetpackError(
            "Nothing to save: no tables, profile, or extra files selected."
        )
    p = Path(path)
    lower = str(p).lower()
    if not lower.endswith(VALVETPACK_EXT) and not lower.endswith(LEGACY_PACK_EXT):
        p = p.with_suffix(VALVETPACK_EXT)
    gerber_arcs = sorted(n for n in extras if n.startswith(f"{FILES_PREFIX}gerber/"))
    manifest: dict[str, Any] = {
        "format_version": VALVETPACK_FORMAT_VERSION,
        "app": "VALVET",
        "members": {
            "bom": BOM_PKL if has_bom else None,
            "pnp": PNP_PKL if has_pnp else None,
            "merge": MERGE_PKL if has_merge else None,
            "profile": PROFILE_JSON if has_profile else None,
        },
        "gerber": gerber_arcs,
        "files": sorted(extras),
    }
    if manifest_extras:
        manifest.update(manifest_extras)
    user_meta = dict(meta or {})
    user_meta.setdefault("saved_at", datetime.now(timezone.utc).isoformat())

    with zipfile.ZipFile(p, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, indent=2))
        zf.writestr(META_NAME, json.dumps(user_meta, ensure_ascii=False, indent=2))
        if has_bom:
            bio = io.BytesIO()
            bom_df.to_pickle(bio)
            zf.writestr(BOM_PKL, bio.getvalue())
        if has_pnp:
            bio = io.BytesIO()
            pnp_df.to_pickle(bio)
            zf.writestr(PNP_PKL, bio.getvalue())
        if has_merge:
            bio = io.BytesIO()
            merge_df.to_pickle(bio)
            zf.writestr(MERGE_PKL, bio.getvalue())
        if has_profile:
            zf.writestr(
                PROFILE_JSON,
                json.dumps(profile, ensure_ascii=False, indent=2),
            )
        for arc, blob in extras.items():
            zf.writestr(arc.replace("\\", "/"), blob)


def load_valvetpack(path: str | Path) -> dict[str, Any]:
    """
    Read .valvetpack or legacy .boomerpack. Returns keys: manifest, meta, bom_df,
    pnp_df, merge_df, profile, extra_members (optional Nones / empty).
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
        profile: dict[str, Any] | None = None
        if PROFILE_JSON in names:
            raw_p = json.loads(zf.read(PROFILE_JSON).decode("utf-8"))
            if isinstance(raw_p, dict):
                profile = raw_p
        extra_members: dict[str, bytes] = {}
        for n in names:
            nn = n.replace("\\", "/")
            if nn.startswith(FILES_PREFIX) and not nn.endswith("/"):
                extra_members[nn] = zf.read(n)
    return {
        "manifest": manifest,
        "meta": meta,
        "bom_df": bom_df,
        "pnp_df": pnp_df,
        "merge_df": merge_df,
        "profile": profile,
        "extra_members": extra_members,
    }


def save_boomerpack(
    path: str | Path,
    *,
    bom_df: Optional[pd.DataFrame],
    pnp_df: Optional[pd.DataFrame],
    merge_df: Optional[pd.DataFrame] = None,
    meta: Optional[dict[str, Any]] = None,
    manifest_extras: Optional[dict[str, Any]] = None,
    profile: Optional[dict[str, Any]] = None,
    extra_members: Optional[dict[str, bytes]] = None,
) -> None:
    save_valvetpack(
        path,
        bom_df=bom_df,
        pnp_df=pnp_df,
        merge_df=merge_df,
        meta=meta,
        manifest_extras=manifest_extras,
        profile=profile,
        extra_members=extra_members,
    )


def load_boomerpack(path: str | Path) -> dict[str, Any]:
    return load_valvetpack(path)
