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
    QPushButton#cleanPrimaryImport,
    QPushButton#cleanPrimaryConvert,
    QPushButton#cleanPrimaryApply,
    QPushButton#cleanSecondaryAction {{
        min-height: 32px;
        min-width: 137px;
        padding: 5px 12px;
        border-radius: 6px;
        border: 2px solid transparent;
    }}
    QPushButton#cleanPrimaryImport,
    QPushButton#cleanPrimaryConvert,
    QPushButton#cleanPrimaryApply {{
        font-weight: 700;
    }}
    QPushButton#cleanPrimaryImport[cleanStep="active"] {{
        background-color: #1565c0;
        color: #ffffff;
        border: 2px solid #64b5f6;
    }}
    QPushButton#cleanPrimaryImport[cleanStep="active"]:hover {{
        background-color: #1976d2;
    }}
    QPushButton#cleanPrimaryConvert[cleanStep="active"] {{
        background-color: #ef6c00;
        color: #ffffff;
        border: 2px solid #ffcc80;
    }}
    QPushButton#cleanPrimaryConvert[cleanStep="active"]:hover {{
        background-color: #f57c00;
    }}
    QPushButton#cleanPrimaryApply[cleanStep="active"] {{
        background-color: #2e7d32;
        color: #ffffff;
        border: 2px solid #81c784;
    }}
    QPushButton#cleanPrimaryApply[cleanStep="active"]:hover {{
        background-color: #388e3c;
    }}
    QPushButton#cleanSecondaryAction {{
        font-weight: 600;
    }}
    QCheckBox#valvetSwitch {{
        spacing: 8px;
    }}
    QCheckBox#valvetSwitch::indicator {{
        width: 38px;
        height: 20px;
        border-radius: 10px;
        border: 1px solid #616161;
        background-color: #424242;
    }}
    QCheckBox#valvetSwitch::indicator:checked {{
        border: 1px solid #66bb6a;
        background-color: #2e7d32;
    }}
    QCheckBox#valvetSwitch::indicator:disabled {{
        background-color: #333333;
        border: 1px solid #444444;
    }}
    """
