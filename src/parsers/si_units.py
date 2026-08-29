"""Pint-backed SI conversion for already-classified Clean slots (no RKM parsing)."""

from __future__ import annotations

from functools import lru_cache

import logger
from parsers.regex_api import I, match


@lru_cache(maxsize=1)
def unit_registry():
    import pint

    return pint.UnitRegistry()


def convert_nf_token_to_uf(value: str) -> str:
    """``1000NF`` → ``1UF``, ``22NF`` → ``0.022UF``. Empty/unparsed → original."""
    m = match(r"^([\d.]+)NF$", str(value).strip(), I)
    if not m:
        return value
    try:
        q = float(m.group(1)) * unit_registry().nanofarad
        uf = q.to("microfarad").magnitude
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


def quantity_farads(value_token: str):
    """Pint Quantity in farads, or None."""
    s = str(value_token).strip()
    m = match(r"^([\d.]+)(PF|NF|UF|F)$", s, I)
    if not m:
        return None
    num, unit = m.group(1), m.group(2).upper()
    ureg = unit_registry()
    try:
        n = float(num)
    except ValueError:
        return None
    if unit == "PF":
        return n * ureg.picofarad
    if unit == "NF":
        return n * ureg.nanofarad
    if unit == "UF":
        return n * ureg.microfarad
    return n * ureg.farad


def quantity_ohms(value_token: str):
    """Pint Quantity in ohms from a VALVET nom token (``10K``, ``4.7R``), or None."""
    s = str(value_token).strip()
    m = match(r"^([\d.]+)([RKM])?$", s)
    if not m:
        return None
    try:
        n = float(m.group(1))
    except ValueError:
        return None
    ureg = unit_registry()
    letter = (m.group(2) or "R").upper()
    if letter == "K":
        return n * 1000 * ureg.ohm
    if letter == "M":
        return n * 1_000_000 * ureg.ohm
    return n * ureg.ohm


def quantity_volts(voltage_token: str):
    s = str(voltage_token).strip()
    m = match(r"^([\d.]+)\s*(KV|V)$", s, I)
    if not m:
        return None
    try:
        n = float(m.group(1))
    except ValueError:
        return None
    ureg = unit_registry()
    if m.group(2).upper() == "KV":
        return n * ureg.kilovolt
    return n * ureg.volt
