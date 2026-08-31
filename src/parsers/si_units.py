"""SI conversion for already-classified Clean slots (no RKM parsing, no Pint)."""

from __future__ import annotations

from dataclasses import dataclass

import logger
from parsers.regex_api import I, match

_CAP_TO_FARAD = {"PF": 1e-12, "NF": 1e-9, "UF": 1e-6, "F": 1.0}
_OHM_MULT = {"R": 1.0, "K": 1e3, "M": 1e6}
_TO_FROM_F = {
    "farad": 1.0,
    "f": 1.0,
    "microfarad": 1e6,
    "uf": 1e6,
    "nanofarad": 1e9,
    "nf": 1e9,
    "picofarad": 1e12,
    "pf": 1e12,
}
_TO_FROM_OHM = {"ohm": 1.0, "ohms": 1.0}
_TO_FROM_V = {"volt": 1.0, "v": 1.0, "kilovolt": 1e-3, "kv": 1e-3}


@dataclass(frozen=True)
class SiQuantity:
    """Value in SI base units (farad, ohm, or volt). ``to`` returns the same dim."""

    magnitude: float
    dim: str

    def to(self, unit: str) -> SiQuantity:
        key = str(unit).strip().lower()
        if self.dim == "F":
            factor = _TO_FROM_F.get(key)
        elif self.dim == "ohm":
            factor = _TO_FROM_OHM.get(key)
        else:
            factor = _TO_FROM_V.get(key)
        if factor is None:
            raise ValueError(f"unknown unit {unit!r} for dim {self.dim}")
        return SiQuantity(self.magnitude * factor, self.dim)


def _as_float(s: str) -> float:
    return float(s)


def convert_nf_token_to_uf(value: str) -> str:
    """``1000NF`` → ``1UF``, ``22NF`` → ``0.022UF``. Empty/unparsed → original."""
    m = match(r"^([\d.]+)NF$", str(value).strip(), I)
    if not m:
        return value
    try:
        uf = _as_float(m.group(1)) / 1000.0
    except Exception as exc:
        logger.warning(
            "convert_nf_token_to_uf failed for %r; keeping original token: %s",
            value,
            exc,
        )
        return value
    if uf == int(uf):
        return f"{int(uf)}UF"
    t = f"{uf:.6f}".rstrip("0").rstrip(".")
    return f"{t}UF"


def quantity_farads(value_token: str) -> SiQuantity | None:
    s = str(value_token).strip()
    m = match(r"^([\d.]+)(PF|NF|UF|F)$", s, I)
    if not m:
        return None
    try:
        n = _as_float(m.group(1))
    except ValueError:
        return None
    unit = m.group(2).upper()
    return SiQuantity(n * _CAP_TO_FARAD[unit], "F")


def quantity_ohms(value_token: str) -> SiQuantity | None:
    s = str(value_token).strip()
    m = match(r"^([\d.]+)([RKM])?$", s)
    if not m:
        return None
    try:
        n = _as_float(m.group(1))
    except ValueError:
        return None
    letter = (m.group(2) or "R").upper()
    return SiQuantity(n * _OHM_MULT[letter], "ohm")


def quantity_volts(voltage_token: str) -> SiQuantity | None:
    s = str(voltage_token).strip()
    m = match(r"^([\d.]+)\s*(KV|V)$", s, I)
    if not m:
        return None
    try:
        n = _as_float(m.group(1))
    except ValueError:
        return None
    if m.group(2).upper() == "KV":
        return SiQuantity(n * 1000.0, "V")
    return SiQuantity(n, "V")
