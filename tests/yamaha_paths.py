"""Paths to committed Yamaha ``.Tou`` examples (from yedytor)."""

from __future__ import annotations

from pathlib import Path

_EX = Path(__file__).resolve().parents[1] / "examples" / "yamaha" / "tou"

YAMAHA_TOU_TOP = _EX / "TGV-FLOOR2-V4_RCC-Top_opt.Tou"
YAMAHA_TOU_BOT = _EX / "TGV-FLOOR2-V4_RCC-BOT_opt.Tou"
