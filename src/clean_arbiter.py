"""
Regex master / parser arbiter for Clean BOM (Qt-free).

When enabled, competes inferit, vendor PN, and token-regex paths by slot coverage
instead of first-match-wins inside those steps. Library and Hanwha remain strict
early exits in clean_one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


# Tie-break priority: lower = preferred when scores equal
_TIER_ORDER = {
    "thermistor": -1,
    "ferrite_bead": -1,
    "vendor": 0,
    "inferit": 1,
    "regex_rcl": 2,
    "regex_other": 3,
    "hanwha_partial": 4,
}


@dataclass(frozen=True)
class ParserCandidate:
    """One cleaning hypothesis for arbiter scoring."""

    name: str
    tier: str
    cleaned: str
    type_tag: str
    part_code: str
    source_note: str
    slots: Dict[str, str]


@dataclass
class ArbiterOutcome:
    """Winner + per-candidate scores for optional UI."""

    cleaned: str
    type_tag: str
    part_code: str
    source_note: str
    win_score: float
    score_breakdown: str  # compact text / tooltip


def vendor_pn_slots_from_string(cleaned: str, sep: str) -> Dict[str, str]:
    parts = [p for p in str(cleaned).split(sep) if str(p).strip()]
    return {f"p{i}": p for i, p in enumerate(parts)}


def _score_res_slots(slots: Dict[str, str], cap: float) -> float:
    nom = bool(str(slots.get("nom", "")).strip())
    pack = bool(str(slots.get("pack", "")).strip())
    watt = bool(str(slots.get("watt", "")).strip())
    tol = bool(str(slots.get("%", "")).strip())
    primary = int(nom) + int(pack)
    secondary = int(watt) + int(tol)
    # Lone tolerance without nominal/package is a weak resistor hypothesis
    if primary == 0 and tol and not watt:
        return min(cap * 0.28, cap)
    if primary == 0:
        return min(cap * 0.35, cap)
    base = primary * (cap * 0.45) + secondary * (cap * 0.125)
    return min(cap, base)


def _score_cap_slots(slots: Dict[str, str], cap: float) -> float:
    nom = bool(str(slots.get("nom", "")).strip())
    pack = bool(str(slots.get("pack", "")).strip())
    w = bool(str(slots.get("V", "")).strip() or str(slots.get("W", "")).strip())
    film = bool(str(slots.get("film", "")).strip())
    tol = bool(str(slots.get("%", "")).strip())
    primary = int(nom) + int(pack)
    secondary = int(w) + int(film) + int(tol)
    if primary == 0 and tol:
        return min(cap * 0.28, cap)
    if primary == 0:
        return min(cap * 0.35, cap)
    base = primary * (cap * 0.42) + secondary * (cap * 0.12)
    return min(cap, base)


def _score_ind_slots(slots: Dict[str, str], cap: float) -> float:
    nom = bool(str(slots.get("nom", "")).strip())
    pack = bool(str(slots.get("pack", "")).strip())
    rest = sum(1 for k in ("%", "Imax", "DCR") if str(slots.get(k, "")).strip())
    if not nom and not pack:
        return min(cap * 0.3, cap)
    base = int(nom) * (cap * 0.42) + int(pack) * (cap * 0.35) + rest * (cap * 0.1)
    return min(cap, base)


def score_candidate(candidate: ParserCandidate, cap_for_regex: float = 90.0) -> float:
    tier = candidate.tier
    tag = candidate.type_tag
    slots = candidate.slots

    if tier == "vendor":
        parts = len([p for p in slots.values() if str(p).strip()])
        if parts <= 0:
            return 70.0
        return min(100.0, 80.0 + 5.0 * min(parts, 4))

    if tier == "thermistor":
        return min(100.0, 92.0)

    if tier == "ferrite_bead":
        return min(100.0, 92.0)

    if tier == "hanwha_partial":
        try:
            fs = float(str(slots.get("fuzzy_score", "0") or "0"))
        except ValueError:
            fs = 0.0
        if fs <= 0.0:
            return min(cap_for_regex, 50.0)
        return min(cap_for_regex, 40.0 + fs * 0.25)

    cap = cap_for_regex
    if tier == "inferit":
        cap = cap_for_regex
    elif tier == "regex_rcl":
        cap = cap_for_regex
    elif tier == "regex_other":
        if not str(candidate.cleaned).strip():
            return 0.0
        return min(cap_for_regex, 38.0 + min(52.0, 18.0 * len(slots)))

    if tag == "RESISTOR":
        return _score_res_slots(slots, cap)
    if tag == "CAP":
        return _score_cap_slots(slots, cap)
    if tag == "INDUCTOR":
        return _score_ind_slots(slots, cap)
    return min(cap_for_regex, 40.0)


def pick_best(
    candidates: List[ParserCandidate], *, cap_for_regex: float = 90.0
) -> Optional[Tuple[ParserCandidate, float, str]]:
    if not candidates:
        return None
    scored: List[Tuple[ParserCandidate, float, str]] = []
    for c in candidates:
        sc = score_candidate(c, cap_for_regex)
        breakdown = f"{c.name}:{sc:.0f}"
        scored.append((c, sc, breakdown))

    scored.sort(key=lambda t: (-t[1], _TIER_ORDER.get(t[0].tier, 99), t[0].name))
    best_c, best_s, _ = scored[0]
    dbg = "; ".join(x[2] for x in sorted(scored, key=lambda x: -x[1])[:8])
    return best_c, best_s, dbg
