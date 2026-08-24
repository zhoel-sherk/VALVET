"""Shared rated-voltage helpers for China/Taiwan MLCC PN families (500 → 50V, 6R3 → 6.3V)."""

from __future__ import annotations

from parsers.regex_api import I, match


def china_mlcc_vol_from_digits(code: str) -> str:
    """3-digit trailing voltage (500 → 50V, 250 → 25V, 160 → 16V)."""
    c = str(code or "").strip()
    if not c.isdigit():
        return ""
    n = int(c)
    if 100 <= n <= 9990 and n % 10 == 0:
        return f"{n // 10}V"
    if 1 <= n <= 99:
        return f"{n}V"
    return f"{n}V"


def china_mlcc_vol_token(token: str) -> str:
    """``6R3`` → ``6.3V``, else digit block via :func:`china_mlcc_vol_from_digits`."""
    t = str(token or "").strip().upper()
    mr = match(r"^(\d)R(\d)$", t, I)
    if mr:
        return f"{mr.group(1)}.{mr.group(2)}V"
    return china_mlcc_vol_from_digits(t)


def metric_size_to_imperial(metric: str) -> str:
    """Metric L×W code (1005) → EIA (0402)."""
    m = {
        "1005": "0402",
        "1608": "0603",
        "2012": "0805",
        "3216": "1206",
        "3225": "1210",
    }
    return m.get(str(metric).strip(), "")
