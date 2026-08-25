"""Hanwha case lint for cleaned BOM strings (check-only, no rewrite)."""

from __future__ import annotations

import re
from dataclasses import dataclass

_CAP_UF_WRONG = re.compile(r"(?<![A-Za-z])(?:UF|uf|uF)(?![A-Za-z])")
_RES_MIXED_OHM = re.compile(r"\d+(?:\.\d+)?(?:mOHM|Mohm|mOhm)")


@dataclass(frozen=True)
class CaseLintHit:
    code: str
    detail: str

    def as_text(self) -> str:
        return f"case={self.code}:{self.detail}"


def lint_cleaned_case(cleaned: str, type_tag: str) -> tuple[CaseLintHit, ...]:
    """Return zero or more lint hits. Does not modify ``cleaned``."""
    s = str(cleaned or "").strip()
    if not s:
        return ()
    kind = str(type_tag or "").strip().upper()
    hits: list[CaseLintHit] = []
    if kind == "OTHER" and any(ch.islower() for ch in s):
        hits.append(CaseLintHit("other_not_caps", "OTHER should be ALLCAPS"))
    if kind in {"CAP", "CAPACITOR"} and _CAP_UF_WRONG.search(s):
        hits.append(CaseLintHit("cap_uf", "use Uf (not UF/uF)"))
    if kind in {"RES", "RESISTOR"} and _RES_MIXED_OHM.search(s):
        hits.append(
            CaseLintHit("res_m_vs_M", "milliohm is m, megaohm is M")
        )
    return tuple(hits)


def case_lint_alert_text(cleaned: str, type_tag: str) -> str:
    hits = lint_cleaned_case(cleaned, type_tag)
    return ";".join(h.as_text() for h in hits)
