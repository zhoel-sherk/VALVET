# SPDX-License-Identifier: MIT
"""iOS-style QCheckBox track+knob (QSS + SVG). Qt-free."""

from __future__ import annotations

from pathlib import Path


def assets_dir() -> Path:
    return Path(__file__).resolve().parent / "assets"


def _qss_url(path: Path) -> str:
    return f'url("{path.resolve().as_posix()}")'


def switch_qss() -> str:
    """Global QCheckBox indicator: 36x20 switch, no system checkmark."""
    d = assets_dir()
    off = _qss_url(d / "switch_off.svg")
    on = _qss_url(d / "switch_on.svg")
    off_d = _qss_url(d / "switch_off_disabled.svg")
    on_d = _qss_url(d / "switch_on_disabled.svg")
    off_h = _qss_url(d / "switch_hovered.svg")
    on_h = _qss_url(d / "switch_on_hovered.svg")
    # Hover/focus/pressed must be explicit: qdarkstyle otherwise paints a square checkbox
    # and :focus stays after a click until another widget is focused.
    return f"""
    QCheckBox {{
        spacing: 8px;
        outline: none;
    }}
    QCheckBox::indicator {{
        width: 36px;
        height: 20px;
        border: none;
        background: transparent;
        image: {off};
    }}
    QCheckBox::indicator:unchecked {{
        image: {off};
    }}
    QCheckBox::indicator:checked {{
        image: {on};
    }}
    QCheckBox::indicator:disabled {{
        image: {off_d};
    }}
    QCheckBox::indicator:unchecked:disabled {{
        image: {off_d};
    }}
    QCheckBox::indicator:checked:disabled {{
        image: {on_d};
    }}
    QCheckBox::indicator:hover,
    QCheckBox::indicator:focus,
    QCheckBox::indicator:pressed,
    QCheckBox::indicator:unchecked:hover,
    QCheckBox::indicator:unchecked:focus,
    QCheckBox::indicator:unchecked:pressed {{
        image: {off_h};
    }}
    QCheckBox::indicator:checked:hover,
    QCheckBox::indicator:checked:focus,
    QCheckBox::indicator:checked:pressed {{
        image: {on_h};
    }}
    """
