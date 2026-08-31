"""Token-completeness alerts for Clean BOM preview (non-blocking).

Accuracy-first policy:
- no auto-fix or auto-rewrite of cleaned strings;
- fuzzy matching is diagnostics-only (hints), never parser selection.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import logger
from parsers.regex_api import I, compile

_CAP_FILMS = (
    "C0G",
    "NP0",
    "NPO",
    "X5R",
    "X5S",
    "X6S",
    "X7R",
    "X7S",
    "X7T",
    "Y5V",
    "Z5U",
)

_PKG_RE = compile(r"^(?:01R5|01005|0201|0402|0603|0805|1206|1210|1812|2010|2512)$", I)
_CAP_NOM_RE = compile(r"^[0-9]+(?:\.[0-9]+)?(?:P|N|U|µ)F$", I)
_RES_NOM_RE = compile(r"^(?:[0-9]+(?:\.[0-9]+)?(?:R|K|M)|0R)$", I)
_TOL_RE = compile(r"^(?:[0-9]+(?:\.[0-9]+)?%|[0-9]+(?:\.[0-9]+)?PF)$", I)
_VOLT_RE = compile(r"^[0-9]+(?:\.[0-9]+)?V$", I)


@dataclass(frozen=True)
class TokenAlert:
    missing: tuple[str, ...]
    present_count: int
    expected_count: int
    hint: str = ""

    @property
    def is_alert(self) -> bool:
        return bool(self.missing)

    def as_text(self) -> str:
        if not self.missing:
            return ""
        base = (
            f"missing={','.join(self.missing)};"
            f"present={self.present_count}/{self.expected_count}"
        )
        if self.hint:
            return f"{base};hint={self.hint}"
        return base


def _tokens(cleaned: str, separator: str) -> list[str]:
    s = str(cleaned).strip()
    if not s:
        return []
    sep = str(separator or "_")
    if not sep:
        sep = "_"
    return [t.strip() for t in s.split(sep) if t and t.strip()]


def _best_film_hint(tokens: Iterable[str]) -> str:
    unknown = [str(t).upper() for t in tokens if t]
    if not unknown:
        return ""
    try:
        from rapidfuzz import fuzz
    except Exception as exc:
        logger.warning(
            "rapidfuzz unavailable for film hint; skipping fuzzy match: %s", exc
        )
        return ""
    best_token = ""
    best_target = ""
    best_score = 0.0
    for tok in unknown:
        if tok in _CAP_FILMS:
            continue
        for film in _CAP_FILMS:
            score = float(fuzz.ratio(tok, film))
            if score > best_score:
                best_score = score
                best_token = tok
                best_target = film
    if best_score >= 85.0 and best_token and best_target:
        return f"film:{best_token}->{best_target}({best_score:.0f})"
    return ""


def analyze_token_alert(
    cleaned: str,
    type_tag: str,
    *,
    separator: str = "_",
) -> TokenAlert:
    toks = _tokens(cleaned, separator)
    if not toks:
        return TokenAlert(("empty_cleaned",), 0, 0)
    tt = str(type_tag or "").strip().upper()

    has_pack = any(_PKG_RE.match(t) for t in toks)
    has_tol = any(_TOL_RE.match(t) for t in toks)

    if tt == "CAP":
        has_nom = any(_CAP_NOM_RE.match(t) for t in toks)
        has_vol = any(_VOLT_RE.match(t) for t in toks)
        has_film = any(str(t).upper() in _CAP_FILMS for t in toks)
        missing: list[str] = []
        if not has_pack:
            missing.append("package")
        if not has_nom:
            missing.append("nominal")
        if not has_vol:
            missing.append("voltage")
        if not has_film:
            missing.append("film")
        if not has_tol:
            missing.append("tolerance")
        hint = _best_film_hint(toks) if "film" in missing else ""
        present = 5 - len(missing)
        return TokenAlert(tuple(missing), present, 5, hint=hint)

    if tt == "RESISTOR":
        has_nom = any(_RES_NOM_RE.match(t) for t in toks)
        missing = []
        if not has_pack:
            missing.append("package")
        if not has_nom:
            missing.append("nominal")
        if not has_tol:
            missing.append("tolerance")
        present = 3 - len(missing)
        return TokenAlert(tuple(missing), present, 3)

    return TokenAlert((), 0, 0)


def append_missing_tokens_log(payload: dict) -> None:
    """Append one JSON line for token-missing alerts."""
    p = dict(payload)
    p.setdefault("ts", datetime.now(timezone.utc).isoformat())
    log_path = (
        os.environ.get("VALVET_MISSING_TOKENS_LOG", "").strip()
        or os.environ.get("BOOMER_MISSING_TOKENS_LOG", "").strip()
    )
    if log_path:
        out = Path(log_path)
    else:
        from app_paths import user_state_dir

        out = user_state_dir() / "logs" / "missing_tokens.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(p, ensure_ascii=False) + "\n")
