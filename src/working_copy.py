from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

import logger


class SnapshotLoadError(Exception):
    """Autosave pickle/meta exists but cannot be read (e.g. pandas dtype mismatch)."""


@dataclass(frozen=True)
class SnapshotIndex:
    """One autosave pair: meta JSON + pickle (path may differ from exact key if legacy)."""

    meta_path: Path
    pkl_path: Path
    meta: dict[str, Any]


@dataclass(frozen=True)
class Snapshot:
    meta: dict[str, Any]
    dataframe: pd.DataFrame


def source_fingerprint(path: str | os.PathLike[str]) -> dict[str, Any]:
    p = Path(path).expanduser()
    try:
        st = p.stat()
        size = int(st.st_size)
        mtime_ns = int(st.st_mtime_ns)
    except OSError:
        size = -1
        mtime_ns = -1
    return {
        "path": str(p.resolve() if p.exists() else p.absolute()),
        "name": p.name,
        "size": size,
        "mtime_ns": mtime_ns,
    }


def snapshot_key(path: str | os.PathLike[str], kind: str) -> str:
    fp = source_fingerprint(path)
    raw = f"{kind}|{fp['path']}|{fp['size']}|{fp['mtime_ns']}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _snapshot_paths(
    base_dir: str | os.PathLike[str], path: str | os.PathLike[str], kind: str
) -> tuple[Path, Path]:
    key = snapshot_key(path, kind)
    base = Path(base_dir)
    return base / f"{key}.json", base / f"{key}.pkl"


def save_snapshot(
    dataframe: pd.DataFrame,
    source_path: str | os.PathLike[str],
    kind: str,
    base_dir: str | os.PathLike[str],
    *,
    dirty: bool = True,
    extra: dict[str, Any] | None = None,
) -> Path:
    base = Path(base_dir)
    base.mkdir(parents=True, exist_ok=True)
    meta_path, data_path = _snapshot_paths(base, source_path, kind)
    tmp_meta = meta_path.with_suffix(".json.tmp")
    tmp_data = data_path.with_suffix(".pkl.tmp")
    meta = {
        "kind": kind,
        "source": source_fingerprint(source_path),
        "dirty": bool(dirty),
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "extra": extra or {},
    }
    _dataframe_for_pickle(dataframe).to_pickle(tmp_data)
    tmp_data.replace(data_path)
    tmp_meta.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    tmp_meta.replace(meta_path)
    return meta_path


def _dataframe_for_pickle(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Use object columns instead of pandas StringDtype (unpickle breaks across versions)."""
    out = dataframe.copy()
    for col in out.columns:
        dtype = out[col].dtype
        if isinstance(dtype, pd.StringDtype) or str(dtype).startswith("string"):
            out[col] = out[col].astype(object)
    return out


def _read_snapshot_pickle(data_path: Path) -> pd.DataFrame:
    try:
        df = pd.read_pickle(data_path)
    except Exception as exc:
        logger.warning(
            "Autosave pickle unreadable (%s); falling back to original file: %s",
            type(exc).__name__,
            data_path,
        )
        raise SnapshotLoadError(str(data_path)) from exc
    if not isinstance(df, pd.DataFrame):
        logger.warning(
            "Autosave pickle is not a DataFrame; falling back to original file: %s",
            data_path,
        )
        raise SnapshotLoadError(str(data_path))
    return df


def load_snapshot(meta_path: str | os.PathLike[str]) -> Snapshot:
    mp = Path(meta_path)
    meta = json.loads(mp.read_text(encoding="utf-8"))
    data_path = mp.with_suffix(".pkl")
    df = _read_snapshot_pickle(data_path)
    return Snapshot(meta=meta, dataframe=df)


def find_snapshot(
    source_path: str | os.PathLike[str],
    kind: str,
    base_dir: str | os.PathLike[str],
) -> Snapshot | None:
    base = Path(base_dir)
    if not base.exists():
        return None
    exact_meta, exact_data = _snapshot_paths(base, source_path, kind)
    skipped: set[Path] = set()
    if exact_meta.exists() and exact_data.exists():
        try:
            return load_snapshot(exact_meta)
        except SnapshotLoadError:
            skipped.add(exact_meta.resolve())

    fp = source_fingerprint(source_path)
    candidates: list[Path] = []
    for meta_path in base.glob("*.json"):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if meta.get("kind") != kind:
            continue
        source = meta.get("source") or {}
        if source.get("path") == fp["path"] and meta_path.with_suffix(".pkl").exists():
            if meta_path.resolve() in skipped:
                continue
            candidates.append(meta_path)
    if not candidates:
        return None
    candidates.sort(
        key=lambda p: json.loads(p.read_text(encoding="utf-8")).get("saved_at", ""),
        reverse=True,
    )
    for meta_path in candidates:
        try:
            return load_snapshot(meta_path)
        except SnapshotLoadError:
            continue
    return None


def list_snapshot_indices(base_dir: str | os.PathLike[str]) -> list[SnapshotIndex]:
    """All snapshot pairs under base_dir (newest first by meta saved_at)."""
    base = Path(base_dir)
    if not base.is_dir():
        return []
    out: list[SnapshotIndex] = []
    for meta_path in sorted(base.glob("*.json")):
        if meta_path.name.endswith(".tmp"):
            continue
        pkl_path = meta_path.with_suffix(".pkl")
        if not pkl_path.is_file():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(meta, dict) or "kind" not in meta:
            continue
        out.append(SnapshotIndex(meta_path=meta_path, pkl_path=pkl_path, meta=meta))
    out.sort(key=lambda si: str(si.meta.get("saved_at", "")), reverse=True)
    return out


def delete_snapshot_pair(meta_path: str | os.PathLike[str]) -> None:
    mp = Path(meta_path)
    pkl = mp.with_suffix(".pkl")
    for p in (mp, pkl):
        try:
            p.unlink(missing_ok=True)
        except OSError:
            pass
