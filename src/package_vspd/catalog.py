# SPDX-License-Identifier: MIT
"""Load shipped VSPD tree and alias maps from JSON."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from parsers import regex_api as re

_CATALOG = Path(__file__).resolve().parent / "catalog"


def normalize_package_key(name: str) -> str:
    """Collapse punctuation so SOT23, SOT_23, and SOT-23 share one alias key."""
    s = (name or "").strip().lower().replace("\\", "/")
    return re.sub(r"[^a-z0-9.]+", "", s)


@lru_cache(maxsize=1)
def load_tree() -> dict[str, Any]:
    p = _CATALOG / "tree.json"
    with open(p, encoding="utf-8") as f:
        raw = json.load(f)
    return raw if isinstance(raw, dict) else {}


@lru_cache(maxsize=1)
def load_aliases() -> dict[str, str]:
    p = _CATALOG / "aliases.json"
    with open(p, encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in raw.items():
        if isinstance(k, str) and isinstance(v, str) and k and v:
            key = normalize_package_key(k)
            if key and key not in out:
                out[key] = v.strip()
    return out


def iter_seed_packages() -> list[dict[str, Any]]:
    """Flatten tree.json into package rows."""
    rows: list[dict[str, Any]] = []
    tree = load_tree()
    classes = tree.get("classes")
    if not isinstance(classes, dict):
        return rows
    for cls_name, families in classes.items():
        if not isinstance(families, dict):
            continue
        for fam_name, packages in families.items():
            if not isinstance(packages, list):
                continue
            for pkg in packages:
                if not isinstance(pkg, dict):
                    continue
                vid = str(pkg.get("id") or "").strip()
                if not vid:
                    continue
                body = pkg.get("body_mm") or [0.0, 0.0, 0.0]
                if not isinstance(body, list) or len(body) < 2:
                    body = [0.0, 0.0, 0.0]
                rows.append(
                    {
                        "vspd_id": vid,
                        "class": str(cls_name),
                        "family": str(fam_name),
                        "display_name": str(pkg.get("display") or vid),
                        "body_l": float(body[0]),
                        "body_w": float(body[1]),
                        "body_h": float(body[2] if len(body) > 2 else 0.0),
                    }
                )
    return rows
