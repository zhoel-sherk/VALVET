"""Load Figma-exportable design tokens and emit a small QSS fragment (appended after qdarkstyle)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _token_path() -> Path:
    return Path(__file__).resolve().with_name("design_tokens.json")


def load_tokens() -> dict[str, Any]:
    p = _token_path()
    if not p.is_file():
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def extra_application_stylesheet() -> str:
    """Append after base QSS (qdarkstyle); values from ``design_tokens.json``."""
    t = load_tokens()
    colors = t.get("colors") if isinstance(t.get("colors"), dict) else {}
    bg = colors.get("wip_banner_bg", "#fff3cd")
    fg = colors.get("wip_banner_fg", "#664d03")
    r = int(t.get("radius_sm_px", 4))
    m = int(t.get("groupbox_margin_px", 10))
    return f"""
    QLabel#WipBanner {{
        padding: {m}px;
        background-color: {bg};
        color: {fg};
        border-radius: {r}px;
    }}
    """
