"""Load Figma-exportable design tokens and emit a small QSS fragment (appended after qdarkstyle)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from themes.apple_switch import switch_qss
from themes.segmented import segmented_qss


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
    base = f"""
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
    QPushButton#cleanPrimaryImport:focus,
    QPushButton#cleanPrimaryConvert:focus,
    QPushButton#cleanPrimaryApply:focus,
    QPushButton#cleanSecondaryAction:focus {{
        border: 2px solid #ffffff;
    }}
    QPushButton#cleanPrimaryConvert[cleanStepState="stale"] {{
        border: 2px dashed #ef6c00;
        color: #ffcc80;
    }}
    QPushButton#cleanPrimaryImport[cleanStepState="done"],
    QPushButton#cleanPrimaryConvert[cleanStepState="done"],
    QPushButton#cleanPrimaryApply[cleanStepState="done"] {{
        border: 2px solid #43a047;
    }}
    QLabel#cleanStaleBadge {{
        background-color: rgba(239, 108, 0, 0.22);
        border: 1px solid #ef6c00;
        border-radius: 4px;
        color: #ffcc80;
        font-weight: 600;
        padding: 2px 8px;
    }}
    QFrame#cleanErrorStrip {{
        border-radius: 4px;
        padding: 4px 8px;
    }}
    QFrame#cleanErrorStrip[severity="warning"] {{
        background-color: rgba(239, 108, 0, 0.18);
        border: 1px solid #ef6c00;
    }}
    QFrame#cleanErrorStrip[severity="error"] {{
        background-color: rgba(198, 40, 40, 0.22);
        border: 1px solid #e57373;
    }}
    QLabel#cleanAlertIcon {{
        color: #ffcc80;
        font-weight: 700;
        border: none;
        background: transparent;
    }}
    QFrame#cleanErrorStrip QLabel {{
        border: none;
        background: transparent;
    }}
    QFrame#cleanEmptyState {{
        border: 1px dashed #4a5a6a;
        border-radius: 6px;
        background-color: rgba(38, 50, 62, 0.35);
    }}
    QLabel#cleanEmptyTitle {{
        font-weight: 700;
    }}
    QLabel#cleanRulesSummary {{
        color: #b0bec5;
    }}
    QFrame#cleanRclRow QLabel {{
        background: transparent;
        border: none;
    }}
    """
    return base + switch_qss() + segmented_qss()
