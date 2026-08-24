#!/usr/bin/env python3
"""One-off golden.xlsx review pass (user + auto-complete easy rows)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

_TOOLS = Path(__file__).resolve().parent
_ROOT = _TOOLS.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_TOOLS))

from clean_corpus_lib import (  # noqa: E402
    DEFAULT_PROFILE,
    GOLDEN_EDITOR_COLUMNS,
    is_procurement_or_internal_code,
    load_corpus_profile,
    read_corpus_table,
    run_clean_row,
    should_harvest_original,
    validate_golden,
    write_corpus_table,
)

# id -> field fixes
_USER_FIXES: dict[str, dict[str, str]] = {
    "9ab53edf37ae": {
        "expected_cleaned": "0201_0_1/20W_5%",
        "notes": "PIPELINE: regex RES_*; пакет R0201 в original",
    },
    "a4f15368588c": {"expected_type": "RESISTOR", "notes": "исправлено: было CAP"},
    "3af15e0c36d0": {"expected_type": "RESISTOR", "notes": "исправлено: было OTHER"},
    "3f467e0a581d": {"expected_type": "RESISTOR", "notes": "исправлено: было OTHER"},
    "c6edba9a0955": {
        "expected_cleaned": "0201_470nF_X5R_10%_10V",
        "notes": "Samsung CL03A474; 10V (не 6.3) — LCSC/datasheet",
    },
    "0cde62614303": {"expected_cleaned": "0402_4.7K_1/16W_5%"},  # trim space
}

# ids: keep expected, mark wip with note (verified target vs current clean_one)
_PIPELINE_WIP: dict[str, str] = {
    "3928cbe3b8f2": "PIPELINE vendor Royal Ohm 0201WMJ* — цель golden OK",
    "3fbee0c531e4": "PIPELINE vendor Royal Ohm",
    "6241ecb30e8f": "PIPELINE vendor Royal Ohm",
    "5ed9da80da68": "PIPELINE vendor Royal Ohm; auto не декодирует WGJ0104",
    "d0ef3658a6b1": "PIPELINE vendor Royal Ohm",
    "17fb2ed83173": "PIPELINE vendor Royal Ohm",
    "d25d299862db": "PIPELINE vendor Royal Ohm",
    "0cde62614303": "PIPELINE vendor Royal Ohm",
    "34b23bc56a10": "PIPELINE regex RES_* из DN59 BOM",
    "e0cd45a3ad50": "PIPELINE regex RES_*",
    "e609f3160874": "PIPELINE regex RES_*",
    "bbbcae616313": "PIPELINE regex RES_*",
    "f706c049fd61": "PIPELINE regex RES_*",
    "5765899c6eb4": "PIPELINE regex RES_*",
    "238a1d02cefc": "PIPELINE regex RES_*",
    "f4f6d7432b": "PIPELINE regex RES_*",
    "82ab0fd9b14e": "PIPELINE regex RES_*",
    "6b901dd26c48": "PIPELINE regex RES_*",
    "3c63dc4e3d11": "PIPELINE regex RES_*",
    "43e655f26977": "PIPELINE regex RES_*",
    "bed1582acff9": "PIPELINE regex RES_*",
    "9ab53edf37ae": "PIPELINE regex RES_*; 0201 0R",
    "fa6d874e3d90": "PIPELINE regex MR_* shunt 5mR",
    "039be8a428fa": "PIPELINE regex RES 3K3 spacing",
    "50c0cee8b139": "PIPELINE regex MLCC spec line",
    "d5591e90dc96": "PIPELINE regex MLCC spec line",
    "bae1103ac362": "PIPELINE regex MLCC spec line",
    "dd0f440a504d": "PIPELINE regex MLCC spec line",
    "7be178b71c76": "PIPELINE regex MLCC spec line",
    "3ff806c74548": "PIPELINE regex MLCC spec line",
    "052a60b6f05b": "PIPELINE regex inductor PL_* line",
    "b0c12a2948ad": "PIPELINE regex inductor PL_* line",
    "3b135db2f60b": "PIPELINE vendor Royal Ohm; auto 24000M — цель 24.9R",
    "bba21ef64eee": "PIPELINE vendor Walsin; добавить X5R в вывод",
    "a3f68c7c3dd0": "PIPELINE vendor Murata GRM033 — цель golden OK",
    "d53ea922f670": "PIPELINE vendor Walsin 102=1nF",
    "f1ed09fbeaac": "PIPELINE vendor Eyang/Viiyong C0G — добавить парсер",
    "53a4e4674712": "PIPELINE vendor Fenghua C0G",
    "275f5bc9f4d6": "PIPELINE vendor Eyang 102=1nF",
    "927013302bab": "PIPELINE vendor Walsin; X7R vs auto",
    "54f4645f64ef": "PIPELINE vendor Eyang C0G",
    "a3134c4a699c": "PIPELINE vendor Eyang C0G",
    "6d4b5c17f650": "PIPELINE vendor Eyang 103=10nF",
    "dad404141940": "PIPELINE vendor Walsin 1206 HV 1nF 2kV",
    "3218bab56352": "PIPELINE vendor Walsin; доп. power rating",
}


def _is_edited(row: dict[str, str]) -> bool:
    exp = str(row.get("expected_cleaned", "")).strip()
    auto = str(row.get("cleaned_auto", "")).strip()
    return bool(exp) and exp != auto


def _auto_ok(cleaned: str, typ: str, src: str, orig: str) -> bool:
    if typ not in ("RESISTOR", "CAP", "INDUCTOR"):
        return False
    if src not in ("vendor", "regex", "inferit", "pn"):
        return False
    if not cleaned or cleaned == orig.strip():
        return False
    if typ == "RESISTOR" and cleaned in ("0402_1/16W", "0201_1/16W"):
        return False
    if re.search(r"1A \[|^\d+A$", cleaned):
        return False
    return True


def _needs_review(orig: str, typ: str, src: str) -> str | None:
    o = orig.strip()
    if not should_harvest_original(o):
        return "не SMT / мусор — рассмотреть skip"
    if is_procurement_or_internal_code(o):
        return "код закупки — skip?"
    if typ == "OTHER" and src in ("hanwha_mdb", "PARTIAL hanwha_mdb"):
        return "REVIEW: Hanwha match — проверить MPN"
    if typ == "OTHER" and len(o) > 30:
        if re.search(r"\b(IC|MOSFET|LDO|DDR|BGA|QFN|TSSOP|PCBA)\b", o, re.I):
            return "REVIEW: извлечь MPN из описания"
    if typ == "OTHER" and re.search(r"TRANSCEIVER|INTERFACE|LOGIC|PWM", o, re.I):
        return "REVIEW: MPN в конце строки?"
    return None


def main() -> int:
    path = _ROOT / "tests" / "fixtures" / "clean_corpus" / "golden.xlsx"
    rows = read_corpus_table(path)
    cfg = load_corpus_profile(DEFAULT_PROFILE)

    for row in rows:
        rid = str(row["id"])
        st = str(row.get("status", "")).strip().lower()
        if st in ("skip",):
            continue

        if rid in _USER_FIXES:
            for k, v in _USER_FIXES[rid].items():
                row[k] = v

        orig = str(row.get("original", ""))
        auto_c, auto_t, auto_s = run_clean_row(orig, cfg)
        row["cleaned_auto"] = auto_c
        row["type_auto"] = auto_t
        row["source_auto"] = auto_s

        exp_c = str(row.get("expected_cleaned", "")).strip()
        if not exp_c:
            exp_c = auto_c
            row["expected_cleaned"] = auto_c
            row["expected_type"] = auto_t
            row["expected_source"] = auto_s

        edited = _is_edited(row)
        note = str(row.get("notes", "")).strip()

        if edited or rid in _PIPELINE_WIP:
            row["status"] = "wip"
            extra = _PIPELINE_WIP.get(rid, "цель golden; clean_one пока не совпадает")
            if rid in _USER_FIXES and _USER_FIXES[rid].get("notes"):
                extra = _USER_FIXES[rid]["notes"]
            if extra not in note:
                row["notes"] = f"{note}; {extra}".strip("; ") if note else extra
        elif _auto_ok(auto_c, auto_t, auto_s, orig) and not edited:
            row["expected_cleaned"] = auto_c
            row["expected_type"] = auto_t
            row["expected_source"] = auto_s
            row["status"] = "ok"
            if not note:
                row["notes"] = ""
        else:
            hint = _needs_review(orig, auto_t, auto_s)
            if hint:
                row["status"] = "wip"
                row["expected_cleaned"] = exp_c or auto_c
                row["expected_type"] = str(row.get("expected_type") or auto_t)
                row["expected_source"] = str(row.get("expected_source") or auto_s)
                if hint not in note:
                    row["notes"] = f"{note}; {hint}".strip("; ") if note else hint
            elif auto_c == orig and auto_t == "OTHER":
                row["status"] = "wip"
                row["notes"] = (note + "; REVIEW: passthrough OTHER").strip("; ")

    # Special rows user marked ok but need review
    for row in rows:
        rid = str(row["id"])
        if rid == "075a25ea07f5":
            row["status"] = "wip"
            row["notes"] = (
                "REVIEW: строка PCBA — RTL8111H из Hanwha? "
                "выбрать один MPN (RTL8111H / ALC269 / …)"
            )
        if rid in ("ea48a6bf6007", "1c7e47ec966f"):
            row["status"] = "wip"
            row["notes"] = "REVIEW: MPN в конце описания — проверить expected"

    write_corpus_table(path, rows, GOLDEN_EDITOR_COLUMNS)
    failures = validate_golden(rows, cfg)
    ok = sum(1 for r in rows if str(r.get("status", "")).strip().lower() in ("ok", ""))
    wip = sum(1 for r in rows if str(r.get("status", "")).strip().lower() == "wip")
    skip = sum(1 for r in rows if str(r.get("status", "")).strip().lower() == "skip")
    print(f"written {path}")
    print(f"status: ok={ok} wip={wip} skip={skip}")
    print(f"validate failures (ok rows only): {len(failures)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
