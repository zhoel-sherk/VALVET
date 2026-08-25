"""Guess Gerber layer kind from filename (Allegro .art, Protel, etc.)."""

from __future__ import annotations

from pathlib import Path

LayerKind = str  # copper | mask | paste | silk | other

_KIND_Z = {
    "copper": -50.0,
    "other": -40.0,
    "mask": -32.0,
    "paste": -22.0,
    "silk": -12.0,
}

_KIND_RGB = {
    "copper": (196, 92, 48),
    "mask": (32, 148, 72),
    "paste": (180, 180, 190),
    "silk": (220, 220, 228),
    "other": (120, 160, 200),
}

_KIND_OPACITY = {
    "copper": 0.78,
    "mask": 0.45,
    "paste": 0.55,
    "silk": 0.92,
    "other": 0.80,
}


def guess_layer_kind(path: str) -> LayerKind:
    n = Path(path).name.lower()
    if any(
        s in n
        for s in (
            "silk",
            "silkscreen",
            ".gto",
            ".gbo",
            "sst",
            "ssb",
            "ass-silk",
        )
    ):
        return "silk"
    if any(s in n for s in ("paste", "pastemask", ".gtp", ".gbp")):
        return "paste"
    if any(s in n for s in ("mask", "soldermask", ".gts", ".gbs")):
        return "mask"
    if any(
        s in n
        for s in (
            "copper",
            "topcopper",
            "botcopper",
            ".gtl",
            ".gbl",
            "g1.",
            "g2.",
        )
    ):
        return "copper"
    return "other"


def layer_default_z(kind: LayerKind) -> float:
    return float(_KIND_Z.get(kind, _KIND_Z["other"]))


def layer_default_rgb(kind: LayerKind) -> tuple[int, int, int]:
    return _KIND_RGB.get(kind, _KIND_RGB["other"])


def layer_default_opacity(kind: LayerKind) -> float:
    return float(_KIND_OPACITY.get(kind, _KIND_OPACITY["other"]))
