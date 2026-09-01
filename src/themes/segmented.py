# SPDX-License-Identifier: MIT
"""iOS-style segmented control QSS (checkable QPushButton row). Qt-free."""

from __future__ import annotations


def segmented_qss() -> str:
    """Must follow qdarkstyle so :checked gets a real border (no hatch)."""
    return """
    QWidget#segmented {
        background-color: #2C2C2E;
        border: 1px solid #48484A;
        border-radius: 8px;
    }
    QWidget#segmented QPushButton {
        min-width: 0px;
        min-height: 24px;
        padding: 4px 6px;
        margin: 0px;
        border: 1px solid transparent;
        border-radius: 0px;
        background-color: transparent;
        color: #E5E5EA;
        font-weight: 500;
        outline: none;
    }
    QWidget#segmented QPushButton[seg="first"] {
        border-top-left-radius: 7px;
        border-bottom-left-radius: 7px;
    }
    QWidget#segmented QPushButton[seg="last"] {
        border-top-right-radius: 7px;
        border-bottom-right-radius: 7px;
    }
    QWidget#segmented QPushButton:hover,
    QWidget#segmented QPushButton:focus {
        background-color: #3A3A3C;
        border: 1px solid #636366;
    }
    QWidget#segmented QPushButton:pressed {
        background-color: #48484A;
        border: 1px solid #636366;
    }
    QWidget#segmented QPushButton:checked {
        background-color: #34C759;
        color: #ffffff;
        border: 1px solid #34C759;
    }
    QWidget#segmented QPushButton:checked:hover,
    QWidget#segmented QPushButton:checked:focus,
    QWidget#segmented QPushButton:checked:pressed {
        background-color: #30D158;
        color: #ffffff;
        border: 1px solid #D8F8DE;
    }
    QWidget#segmented QPushButton:disabled {
        color: #636366;
        background-color: transparent;
        border: 1px solid transparent;
    }
    QWidget#segmented QPushButton:checked:disabled {
        background-color: #1F6A32;
        color: #8E8E93;
        border: 1px solid #1F6A32;
    }
    """
