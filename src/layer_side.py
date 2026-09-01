"""Board-side tokens: Merge display/filter vs PCB Preview overlay.

Two semantics on purpose — do not collapse them into one function:

* Merge export combos use ``display_layer_value`` (empty → ``"None"``) and
  exact-match filtering. Token helpers pick Top/Bot combo defaults.
* PCB Preview uses ``parse_board_side`` (empty / unrecognized → ``"top"``).
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from pcb_preview.types import BoardSide

_BOT_TOKENS = frozenset(
    (
        "m",
        "b",
        "bot",
        "bottom",
        "bottomlayer",
        "mirror",
    )
)
_TOP_TOKENS = frozenset(("t", "top", "toplayer"))


def display_layer_value(value: Any) -> str:
    """Normalize a Merge/PnP Layer cell for combo labels and exact export filter."""
    if pd.isna(value):
        return "None"
    text = str(value).strip()
    if not text or text.lower() in ("nan", "none"):
        return "None"
    return text


def is_bot_layer_token(value: str) -> bool:
    return value.strip().lower() in _BOT_TOKENS


def is_top_layer_token(value: str) -> bool:
    return value.strip().lower() in _TOP_TOKENS


def select_merge_layer_defaults(
    values: list[str],
) -> tuple[str | None, str | None]:
    """Pick default Top/Bot combo items (first-seen order, same as Merge tab)."""
    if not values:
        return None, None
    top = next((v for v in values if is_top_layer_token(v)), None)
    bot = next((v for v in values if is_bot_layer_token(v)), None)
    if top is None and "None" in values:
        top = "None"
    if bot is None:
        bot = next((v for v in values if v != top), None)
    if top is None:
        top = next((v for v in values if v != bot), values[0])
    return top, bot


def parse_board_side(value: Any) -> BoardSide:
    """Map a Layer cell to PCB Preview overlay side (empty/unknown → top)."""
    if pd.isna(value):
        return "top"
    text = str(value).strip()
    if not text or text.lower() in ("nan", "none"):
        return "top"
    if is_bot_layer_token(text):
        return "bottom"
    if is_top_layer_token(text):
        return "top"
    lv = text.upper()
    if "BOT" in lv or "BOTTOM" in lv or "B." in lv:
        return "bottom"
    if "TOP" in lv or "T." in lv or "F." in lv:
        return "top"
    return "top"
