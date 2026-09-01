from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING, AbstractSet, List, Optional, Tuple

import logger
from clean_alerts import analyze_token_alert, append_missing_tokens_log
from clean_arbiter import ParserCandidate, pick_best, vendor_pn_slots_from_string
from clean_types import (
    CleanConfig,
    canonical_pipeline_order,
    default_clean_config,
)
from parsers.cap_pars import parse_capacitor, parse_capacitor_token_fields
from parsers.constants import has_strict_chip_case_size
from parsers.ferrite_beads import extract_ferrite_bead_mpn
from parsers.formatting import apply_prefix, reformat_cleaned_pn
from parsers.ind_pars import parse_inductor, parse_inductor_token_fields
from parsers.inferit_pars import (
    parse_inferit_capacitor,
    parse_inferit_capacitor_fields,
    parse_inferit_inductor,
    parse_inferit_inductor_fields,
    parse_inferit_resistor,
    parse_inferit_resistor_fields,
)
from parsers.other_pars import clean_other
from parsers.res_pars import parse_resistor, parse_resistor_token_fields
from parsers.thermistors import extract_thermistor_mpn
from parsers.vendor_context_merge import enrich_vendor_cleaned_from_bom

if TYPE_CHECKING:
    import pandas as pd


def _default_config(config: Optional[CleanConfig]) -> CleanConfig:
    return default_clean_config(config)


def _norm_hanwha(s: str) -> str:
    """
    Hanwha compare key: remove spacer class only (+ - # _ whitespace), keep '.' so
    4.7K and 47K stay distinct (alnum-only folding used to merge them incorrectly).
    """
    t = str(s).strip().casefold()
    return re.sub(r"[\s+\-#_/]+", "", t)


def _hanwha_primary_match(
    comment: str,
    partnames: AbstractSet[str],
    *,
    partial_match: bool,
    footprint: str = "",
    part_groups: Optional[dict[str, str]] = None,
) -> Optional[Tuple[str, str]]:
    """
    Longest PARTNAME whose norm is a substring of norm(comment).

    If norm(part) == norm(comment) but the raw strings differ, or norm(part) is a
    substring of norm(comment) while the MDB PARTNAME is **not** a literal substring
    of the BOM (spacer / punctuation variants), mark ``PARTIAL hanwha_mdb`` when
    ``partial_match`` is True; otherwise ``hanwha_mdb``.
    """
    s = str(comment).strip()
    if not s or not partnames:
        return None
    nc = _norm_hanwha(s)
    if len(nc) < 2:
        return None
    groups = part_groups or {}
    fp = _norm_hanwha(footprint) if footprint else ""
    scored: list[tuple[int, int, int, str]] = []
    for pn in sorted(partnames, key=lambda x: str(x).casefold()):
        p = str(pn).strip()
        if len(p) < 2:
            continue
        np = _norm_hanwha(p)
        if len(np) < 2 or np not in nc:
            continue
        gnorm = _norm_hanwha(str(groups.get(p, "") or ""))
        bonus = 1 if fp and (fp in np or fp in gnorm) else 0
        scored.append((bonus, len(np), len(p), p))
    if not scored:
        return None
    scored.sort(reverse=True)
    top = scored[0]
    ties = [x for x in scored if x[0] == top[0] and x[1] == top[1]]
    best_pn = top[3]
    nbest = _norm_hanwha(best_pn)
    literal_in = best_pn.strip().casefold() in s.casefold()
    if len(ties) > 1:
        return (best_pn, "AMBIGUOUS hanwha_mdb")
    if nbest == nc:
        if partial_match and best_pn.strip() != s.strip():
            return (best_pn, "PARTIAL hanwha_mdb")
        return (best_pn, "hanwha_mdb")
    if partial_match and not literal_in:
        return (best_pn, "PARTIAL hanwha_mdb")
    return (best_pn, "hanwha_mdb")


def _hanwha_fuzzy_partial_best(
    comment: str,
    partnames: AbstractSet[str],
    *,
    score_cutoff: float,
    min_query_chars: int,
) -> Optional[Tuple[str, str, float]]:
    """
    Fallback when primary substring match failed: ``rapidfuzz.fuzz.partial_ratio`` on
    ``_norm_hanwha`` keys (tolerates small typos / OCR noise vs strict ``nc in np``).

    Returns ``(PARTNAME, PARTIAL hanwha_mdb, score)`` or None.
    """
    from rapidfuzz import fuzz

    if not comment or not partnames:
        return None
    s = str(comment).strip()
    if not s:
        return None
    nc = _norm_hanwha(s)
    if len(nc) < min_query_chars:
        return None
    best: Optional[Tuple[float, int, int, str]] = None
    # (score, len(np), len(raw pn), pn) — prefer higher score, longer norm, longer raw.
    for pn in sorted(partnames, key=lambda x: str(x).casefold()):
        p = str(pn).strip()
        if len(p) < 2:
            continue
        np = _norm_hanwha(p)
        if len(np) < 2:
            continue
        # Very short query vs very long PN: substring-style false positives (e.g. «00»).
        if len(nc) < 8 and len(np) > max(32, len(nc) * 8):
            continue
        sc = float(fuzz.partial_ratio(nc, np))
        if sc < score_cutoff:
            continue
        cand = (sc, len(np), len(p), p)
        if best is None or cand > best:
            best = cand
    if not best:
        return None
    _, _, _, pn = best
    return (pn, "PARTIAL hanwha_mdb", best[0])


def match_hanwha_mdb_partname(
    comment: str,
    partnames: AbstractSet[str],
    *,
    partial_match: bool = False,
    fuzzy_cutoff: Optional[float] = None,
    fuzzy_min_query: Optional[int] = None,
    footprint: str = "",
    part_groups: Optional[dict[str, str]] = None,
) -> Optional[Tuple[str, str]]:
    """
    Match BOM comment to a Hanwha MDB PARTNAME.

    Normalization collapses ``+ - # _`` and whitespace only (case-insensitive), keeping
    ``.`` so e.g. 47K and 4.7K do not collide.

    Primary: longest ``norm(PARTNAME)`` contained in ``norm(comment)``. When that is
    a full-string norm match but the raw BOM and PARTNAME strings differ, the source is
    ``PARTIAL hanwha_mdb`` if ``partial_match`` is enabled.

    When ``partial_match`` is True and primary finds nothing: **fuzzy** fallback on
    normalized keys (``rapidfuzz`` ``partial_ratio``, cutoff from ``CleanConfig`` when
    passed from the pipeline).
    """
    primary = _hanwha_primary_match(
        comment,
        partnames,
        partial_match=partial_match,
        footprint=footprint,
        part_groups=part_groups,
    )
    if primary:
        return primary
    if partial_match:
        fc = 88.0 if fuzzy_cutoff is None else float(fuzzy_cutoff)
        fm = 5 if fuzzy_min_query is None else int(fuzzy_min_query)
        hit = _hanwha_fuzzy_partial_best(
            comment,
            partnames,
            score_cutoff=fc,
            min_query_chars=fm,
        )
        if hit:
            return hit[0], hit[1]
    return None


def clean_component(
    part_type: str,
    spec: str,
    config: Optional[CleanConfig] = None,
    *,
    skip_inferit_presets: bool = False,
) -> str:
    """Main cleaning function."""
    if not spec:
        return ""

    spec = str(spec).strip()

    cfg = _default_config(config)
    if not part_type:
        return clean_other(spec)

    part_type = part_type.upper()

    if "RES" in part_type and not cfg.parse_resistors:
        return spec
    if ("CAP" in part_type or "CAPACITOR" in part_type) and not cfg.parse_capacitors:
        return spec
    if ("IND" in part_type or "INDUCTOR" in part_type) and not cfg.parse_inductors:
        return spec

    if "RES" in part_type:
        return parse_resistor(spec, cfg, skip_inferit_presets=skip_inferit_presets)
    if "CAP" in part_type or "CAPACITOR" in part_type:
        return parse_capacitor(spec, cfg, skip_inferit_presets=skip_inferit_presets)
    if "IND" in part_type or "INDUCTOR" in part_type:
        return parse_inductor(spec, cfg, skip_inferit_presets=skip_inferit_presets)
    return clean_other(spec)


def classify_component_type(orig: str) -> str:
    """
    Heuristic part family: FERRITE_BEAD, INDUCTOR, RESISTOR, CAP, OTHER.
    """
    if not orig:
        return "OTHER"
    t = str(orig).strip()
    t = re.sub(r"\s*<[gG]>\s*$", "", t).strip()
    t = re.sub(r"/\s+", "/", t)
    if extract_thermistor_mpn(t):
        return "OTHER"
    if extract_ferrite_bead_mpn(t):
        return "FERRITE_BEAD"
    t_mix = t
    t = t.upper()
    if re.search(r"\bFERRITE(?:[\s_-]*BEAD)?\b|\bBEAD\b", t):
        return "FERRITE_BEAD"
    if re.search(
        r"\b(CRYSTAL|POWER-IC|TYPEC\s+IC|QUICK\s+SWITCH\s+IC|MOSFET|DIODE|CONNECTOR)\b",
        t,
    ):
        return "OTHER"
    # Standalone IC / ESD / XTAL lines must not become RES via embedded R-codes.
    if re.search(r"(?:^|[\s|])IC[\s,]", t) or re.match(r"^IC[\s,]", t):
        return "OTHER"
    if re.search(r"\b(?:ESD|XTAL|CRYSTAL)\b", t):
        return "OTHER"
    # Power-inductor join (PL_1uH_…) and vendor families — before R-tail false positives
    if re.match(r"^PL_[\d.]", t_mix, re.I) or re.search(
        r"\b(?:SCCT|SCCB|STPI|SWAI|MCW|CCCA)[-\w]*\d",
        t_mix,
        re.I,
    ):
        if re.search(r"[\d.]+\s*(?:uH|nH|mH|H)(?![A-Za-z0-9])", t_mix, re.I):
            return "INDUCTOR"
    if re.search(r"\bSMD-INDUCTORS?\b", t, re.I):
        return "INDUCTOR"
    if (
        re.search(r"\bWIRE-WOUND\b|\bINDUCTOR\b", t)
        or re.search(r"[\d.]+\s*(?:UH|NH|MH|H)(?![A-Z0-9])", t)
        or re.search(r"(?<![A-Z0-9])(?:UH|NH|MH)(?![A-Z0-9])", t)
    ):
        return "INDUCTOR"
    if re.search(r"\b(?:POSCAP|POS)\b", t) and re.search(
        r"[\d.]+\s*(?:UF|NF|PF)\b|[\d.]+\s*U\s*/\s*[\d.]+\s*V\b", t
    ):
        return "CAP"
    if re.search(r"(?:/|^)CL[0-9]{2}[A-Z0-9]", t, re.I) or re.match(
        r"^CL[0-9]{2}[A-Z0-9]", t, re.I
    ):
        return "CAP"
    if re.search(r"(?:/|^)C0[24]\d{2}[BC]0G", t, re.I) or re.match(
        r"^C0\d{3}[A-Z0-9]{6,}", t, re.I
    ):
        return "CAP"
    if re.search(r"(?:/|^)V\d{3}K\d{4}X[57]R", t, re.I) or re.match(
        r"^V\d{3}K\d{4}X[57]R", t, re.I
    ):
        return "CAP"
    if re.search(r"(?:/|^)C1005NP", t, re.I) or re.match(r"^C1005NP", t, re.I):
        return "CAP"
    if re.search(r"(?:/|^)\d{4}(?:CG|B)\d{3}[A-Z]\d{3}NT", t, re.I):
        return "CAP"
    if re.search(r"(?:/|^)GRM[0-9A-Z]+", t, re.I):
        return "CAP"
    if re.search(r"(?:/|^)(E|J|T|U)MK[0-9]", t, re.I):
        return "CAP"
    if re.search(
        r"(?:/|^)(0201|0402|0603|0805|1206|1210|2010|2512)(B|N|X).",
        t,
        re.I,
    ):
        return "CAP"
    if "MLCC" not in t and re.search(
        r"/(RC[0-9]{2,4}[A-Z0-9-]*|RT[0-9]{2,4}[A-Z0-9-]*|RM|WR|RB)(?=[A-Z0-9-]|<| |$)",
        t,
        re.I,
    ):
        return "RESISTOR"
    if "MLCC" not in t and re.match(r"^(WR|RM|RB)[0-9]{2}[A-Z0-9-]*", t, re.I):
        return "RESISTOR"
    if "MLCC" not in t and re.match(
        r"^R[CT](0201|0402|0603|0805|1206|1210|2010|2512)(?:[A-Z]{1,2})?-",
        t,
    ):
        return "RESISTOR"
    if (
        "MLCC" not in t
        and not re.search(r"[\d.]+\s*(?:uH|nH|mH|H)(?![A-Za-z0-9])", t_mix, re.I)
        and not re.search(r"\b(?:SCCT|SCCB|STPI|SWAI|MCW|CCCA)[-\w]*\d", t_mix, re.I)
        and re.search(r"[-/][0-9]+(?:\.[0-9]+)?R[0-9](?:<|[A-Z]|[LJ]|$)", t, re.I)
    ):
        return "RESISTOR"
    if re.search(r"\bTHERMISTOR\b", t):
        return "OTHER"
    if re.search(r"\bNTC\b", t) and re.search(
        r"\([^)]*\b(?:ERTJ|NCP|NTCG)[A-Z0-9]", t_mix, re.I
    ):
        return "OTHER"
    if re.match(r"^RES[_ ]", t) or re.search(r"\bCHIP\s+RES", t, re.I):
        if has_strict_chip_case_size(t) or re.search(r"\d+[RKM](?!\w)|OHM|1/\d+W", t):
            return "RESISTOR"
    has_wattage = bool(re.search(r"1/\d+W", t))
    has_resistor_value = (
        bool(re.search(r"\d+[RKM](?!\w)", t)) and "X5R" not in t and "X7R" not in t
    )
    has_ohm = "OHM" in t
    if has_wattage or has_resistor_value or has_ohm:
        if has_strict_chip_case_size(t) or re.search(r"\bCHIP\s+RES", t, re.I):
            return "RESISTOR"
        return "OTHER"
    if re.search(r"\bMLCC[\s_]", t, re.I) or any(
        x in t for x in ("X7R", "X5R", "COG", "NPO", "NP0", "C0G")
    ):
        return "CAP"
    if any(m in t for m in ("UF", "NF", "PF")):
        if has_strict_chip_case_size(t):
            return "CAP"
        return "OTHER"
    return "OTHER"


def _type_tag_for_classify(ctype: str) -> str:
    if ctype == "RESISTOR":
        return "RESISTOR"
    if ctype == "CAP":
        return "CAP"
    if ctype == "INDUCTOR":
        return "INDUCTOR"
    if ctype == "FERRITE_BEAD":
        return "FERRITE_BEAD"
    return "OTHER"


def _map_classify_to_part_code(ctype: str) -> str:
    if ctype == "INDUCTOR":
        return "IND"
    if ctype == "RESISTOR":
        return "RES"
    if ctype == "CAP":
        return "CAP"
    if ctype == "FERRITE_BEAD":
        return "FB"
    return "OTHER"


def _ensure_src_on_path() -> None:
    import os
    import sys

    d = os.path.dirname(os.path.abspath(__file__))
    if d not in sys.path:
        sys.path.insert(0, d)


def _try_parse_vendor_pn(
    orig: str, classify_type: str, config: CleanConfig
) -> Optional[str]:
    if not config.use_pn_codecs or classify_type not in ("RESISTOR", "CAP"):
        return None
    if classify_type == "RESISTOR" and not config.parse_resistors:
        return None
    if classify_type == "CAP" and not config.parse_capacitors:
        return None
    ct = "RES" if classify_type == "RESISTOR" else "CAP"
    try:
        _ensure_src_on_path()
        from parsers.bom_text_utils import joined_clean_comment_mpn
        from pn_original import parse_pn

        mpn = joined_clean_comment_mpn(orig)
        return parse_pn(mpn.strip(), ct, config)
    except Exception as e:
        logger.debug(f"parse_pn failed: {e}")
        return None


def _try_parse_vendor_pn_res_cap_any(
    orig: str, config: CleanConfig, hint: str
) -> Optional[Tuple[str, str]]:
    if not config.use_pn_codecs:
        return None
    if extract_thermistor_mpn(str(orig).strip()):
        return None
    if hint in ("RESISTOR", "CAP"):
        order = [hint, "CAP" if hint == "RESISTOR" else "RESISTOR"]
    else:
        order = ["CAP", "RESISTOR"]
    for cls in order:
        out = _try_parse_vendor_pn(orig, cls, config)
        if out:
            return (out, cls)
    return None


def _clean_one_try_library(
    s: str, cfg: CleanConfig
) -> Optional[Tuple[str, str, str, str]]:
    if not cfg.use_component_library:
        return None
    try:
        from component_library import lookup_component

        lib_path = cfg.component_library_path or None
        lib_entry = lookup_component(s, lib_path)
    except Exception as e:
        logger.debug(f"component library lookup failed: {e}")
        return None
    if not lib_entry:
        return None
    eff = str(lib_entry.type or "OTHER").upper()
    c_eff = (
        "CAP"
        if eff in ("CAP", "CAPACITOR")
        else "RESISTOR"
        if eff in ("RES", "RESISTOR")
        else "INDUCTOR"
        if eff in ("IND", "INDUCTOR")
        else eff
    )
    if c_eff not in ("RESISTOR", "CAP", "INDUCTOR", "OTHER"):
        c_eff = "OTHER"
    cleaned = str(lib_entry.cleaned)
    if c_eff == "RESISTOR":
        cleaned = apply_prefix(cleaned, cfg.resistor_prefix, cfg)
    elif c_eff == "CAP":
        cleaned = apply_prefix(cleaned, cfg.cap_prefix, cfg)
    elif c_eff == "INDUCTOR":
        cleaned = apply_prefix(cleaned, cfg.inductor_prefix, cfg)
    return (
        cleaned,
        _type_tag_for_classify(c_eff),
        _map_classify_to_part_code(c_eff),
        "library",
    )


def _clean_one_regex_phase(
    s: str,
    ctype: str,
    cfg: CleanConfig,
    inferit_executed: bool,
) -> Tuple[str, str, str, str]:
    from parsers.bom_text_utils import joined_clean_comment_bom_prose

    bom = joined_clean_comment_bom_prose(s)
    parse_target = bom or s
    if ctype == "RESISTOR" and not cfg.parse_resistors:
        return s, "RESISTOR", "RES", "off"
    if ctype == "CAP" and not cfg.parse_capacitors:
        return s, "CAP", "CAP", "off"
    if ctype == "INDUCTOR" and not cfg.parse_inductors:
        cleaned_o = clean_other(s)
        if cleaned_o:
            return cleaned_o, "INDUCTOR", "OTHER", "regex"
        return s, "INDUCTOR", "OTHER", "other"
    part_code = _map_classify_to_part_code(ctype)
    note = "regex" if ctype in ("RESISTOR", "CAP", "INDUCTOR") else "other"
    return (
        clean_component(
            part_code,
            parse_target,
            cfg,
            skip_inferit_presets=inferit_executed,
        ),
        _type_tag_for_classify(ctype),
        part_code,
        note,
    )


def _clean_one_skip_regex(
    s: str, ctype: str, cfg: CleanConfig
) -> Tuple[str, str, str, str]:
    if ctype == "RESISTOR" and not cfg.parse_resistors:
        return s, "RESISTOR", "RES", "off"
    if ctype == "CAP" and not cfg.parse_capacitors:
        return s, "CAP", "CAP", "off"
    if ctype == "INDUCTOR" and not cfg.parse_inductors:
        return s, "INDUCTOR", "OTHER", "other"
    part_code = _map_classify_to_part_code(ctype)
    return s, _type_tag_for_classify(ctype), part_code, "other"


def _collect_inferit_arbiter_candidates(
    s: str, ctype: str, cfg: CleanConfig, disabled: frozenset[str]
) -> List[ParserCandidate]:
    if "inferit" in disabled:
        return []
    out: List[ParserCandidate] = []
    if ctype == "RESISTOR" and cfg.parse_resistors:
        detail = parse_inferit_resistor_fields(s, cfg)
        if detail:
            raw_f, formatted = detail
            if formatted:
                out.append(
                    ParserCandidate(
                        "inferit_res",
                        "inferit",
                        formatted,
                        "RESISTOR",
                        "RES",
                        "regex",
                        dict(raw_f),
                    )
                )
    elif ctype == "CAP" and cfg.parse_capacitors:
        detail = parse_inferit_capacitor_fields(s, cfg)
        if detail:
            raw_f, formatted = detail
            if formatted:
                out.append(
                    ParserCandidate(
                        "inferit_cap",
                        "inferit",
                        formatted,
                        "CAP",
                        "CAP",
                        "regex",
                        dict(raw_f),
                    )
                )
    elif ctype == "INDUCTOR" and cfg.parse_inductors:
        detail = parse_inferit_inductor_fields(s, cfg)
        if detail:
            raw_f, formatted = detail
            if formatted:
                out.append(
                    ParserCandidate(
                        "inferit_ind",
                        "inferit",
                        formatted,
                        "INDUCTOR",
                        "IND",
                        "regex",
                        dict(raw_f),
                    )
                )
    return out


def _try_thermistor_clean(s: str) -> Optional[Tuple[str, str, str, str]]:
    mpn = extract_thermistor_mpn(s.strip())
    if not mpn:
        return None
    return (mpn, "OTHER", "OTHER", "thermistor")


def _try_ferrite_bead_clean(s: str) -> Optional[Tuple[str, str, str, str]]:
    mpn = extract_ferrite_bead_mpn(s.strip())
    if not mpn:
        return None
    return (mpn, "FERRITE_BEAD", "FB", "ferrite_bead")


def _ferrite_bead_passthrough(s: str) -> Tuple[str, str, str, str]:
    """Keep FERRITE_BEAD type even when series MPN is unknown (no RES/IND fallthrough)."""
    hit = _try_ferrite_bead_clean(s)
    if hit:
        return hit
    from parsers.bom_text_utils import joined_clean_comment_mpn

    tail = joined_clean_comment_mpn(s).strip()
    cleaned = tail or str(s).strip()
    return (cleaned, "FERRITE_BEAD", "FB", "other")


def _try_special_other_clean(s: str) -> Optional[Tuple[str, str, str, str]]:
    return _try_ferrite_bead_clean(s) or _try_thermistor_clean(s)


def _collect_thermistor_arbiter_candidates(s: str) -> List[ParserCandidate]:
    mpn = extract_thermistor_mpn(s.strip())
    if not mpn:
        return []
    return [
        ParserCandidate(
            name="thermistor",
            tier="thermistor",
            cleaned=mpn,
            type_tag="OTHER",
            part_code="OTHER",
            source_note="thermistor",
            slots={"mpn": mpn},
        )
    ]


def _collect_ferrite_bead_arbiter_candidates(s: str) -> List[ParserCandidate]:
    mpn = extract_ferrite_bead_mpn(s.strip())
    if not mpn:
        return []
    return [
        ParserCandidate(
            name="ferrite_bead",
            tier="ferrite_bead",
            cleaned=mpn,
            type_tag="FERRITE_BEAD",
            part_code="FB",
            source_note="ferrite_bead",
            slots={"mpn": mpn},
        )
    ]


def _collect_special_other_arbiter_candidates(s: str) -> List[ParserCandidate]:
    return _collect_ferrite_bead_arbiter_candidates(
        s
    ) + _collect_thermistor_arbiter_candidates(s)


def _collect_hanwha_partial_arbiter_candidate(
    s: str, cfg: CleanConfig
) -> Optional[ParserCandidate]:
    if not (cfg.hanwha_partial_match and cfg.use_hanwha_mdb and cfg.hanwha_partnames):
        return None
    if _hanwha_primary_match(
        s, cfg.hanwha_partnames, partial_match=cfg.hanwha_partial_match
    ):
        return None
    hit = _hanwha_fuzzy_partial_best(
        s,
        cfg.hanwha_partnames,
        score_cutoff=cfg.hanwha_partial_fuzzy_cutoff,
        min_query_chars=cfg.hanwha_partial_fuzzy_min_query,
    )
    if not hit:
        return None
    pn, src, sc = hit
    return ParserCandidate(
        name="hanwha_partial",
        tier="hanwha_partial",
        cleaned=pn,
        type_tag="OTHER",
        part_code="OTHER",
        source_note=src,
        slots={"mpn": pn, "fuzzy_score": f"{sc:.1f}"},
    )


def _collect_vendor_arbiter_candidate(
    s: str, eff_vendor: str, cfg: CleanConfig, disabled: frozenset[str]
) -> Optional[ParserCandidate]:
    if "vendor" in disabled or not cfg.use_pn_codecs:
        return None
    if eff_vendor not in ("RESISTOR", "CAP", "OTHER"):
        return None
    pnr = _try_parse_vendor_pn_res_cap_any(s, cfg, eff_vendor)
    if not pnr:
        return None
    pnv, eff = pnr[0], pnr[1]

    pnv = enrich_vendor_cleaned_from_bom(s, pnv, eff, cfg)
    pnv = reformat_cleaned_pn(pnv, eff, cfg)
    src_note = "vendor" if cfg.use_vendor_pn else "pn"
    slots = vendor_pn_slots_from_string(pnv, cfg.output_separator)
    return ParserCandidate(
        name="vendor_pn",
        tier="vendor",
        cleaned=str(pnv).strip(),
        type_tag=_type_tag_for_classify(eff),
        part_code=_map_classify_to_part_code(eff),
        source_note=src_note,
        slots=slots,
    )


def _collect_regex_arbiter_candidates(
    s: str, ctype: str, cfg: CleanConfig
) -> List[ParserCandidate]:
    cands: List[ParserCandidate] = []
    if ctype == "RESISTOR" and cfg.parse_resistors:
        sl, cleaned = parse_resistor_token_fields(s, cfg)
        if str(cleaned).strip():
            cands.append(
                ParserCandidate(
                    "regex_res",
                    "regex_rcl",
                    cleaned,
                    "RESISTOR",
                    "RES",
                    "regex",
                    sl,
                )
            )
    elif ctype == "CAP" and cfg.parse_capacitors:
        sl, cleaned = parse_capacitor_token_fields(s, cfg)
        if str(cleaned).strip():
            cands.append(
                ParserCandidate(
                    "regex_cap",
                    "regex_rcl",
                    cleaned,
                    "CAP",
                    "CAP",
                    "regex",
                    sl,
                )
            )
    elif ctype == "INDUCTOR" and cfg.parse_inductors:
        sl, cleaned = parse_inductor_token_fields(s, cfg)
        if str(cleaned).strip():
            cands.append(
                ParserCandidate(
                    "regex_ind",
                    "regex_rcl",
                    cleaned,
                    "INDUCTOR",
                    "IND",
                    "regex",
                    sl,
                )
            )
    else:
        co = clean_other(s)
        if str(co).strip():
            cands.append(
                ParserCandidate(
                    "regex_other",
                    "regex_other",
                    co,
                    "OTHER",
                    "OTHER",
                    "other",
                    {"mpn": co},
                )
            )
    return cands


def _clean_one_regex_master(
    s: str,
    ctype: str,
    eff_vendor: str,
    cfg: CleanConfig,
) -> Tuple[str, str, str, str, str, Optional[float]]:
    """
    Like clean_one but inferit/vendor/regex compete via arbiter; library/hanwha strict.
    Returns (cleaned, type_tag, part_code, source, score_debug, arbiter_win_score or None).
    """
    order = canonical_pipeline_order(cfg.clean_pipeline_order)
    disabled = frozenset(x.strip().lower() for x in cfg.clean_pipeline_disabled if x)
    inferit_pipeline_on = "inferit" not in disabled
    master_candidates: List[ParserCandidate] = []

    for step in order:
        sid = str(step).strip().lower()
        if sid in disabled:
            continue
        if sid == "inferit":
            master_candidates.extend(
                _collect_inferit_arbiter_candidates(s, ctype, cfg, disabled)
            )
        elif sid == "vendor":
            vc = _collect_vendor_arbiter_candidate(s, eff_vendor, cfg, disabled)
            if vc:
                master_candidates.append(vc)
        elif sid == "library":
            lib_hit = _clean_one_try_library(s, cfg)
            if lib_hit:
                return (*lib_hit, "", None)
        elif sid == "hanwha":
            sp = _try_special_other_clean(s)
            if sp:
                return (sp[0], sp[1], sp[2], sp[3], "", None)
            if ctype != "OTHER":
                continue
            if cfg.use_hanwha_mdb and cfg.hanwha_partnames:
                hit = match_hanwha_mdb_partname(
                    s,
                    cfg.hanwha_partnames,
                    partial_match=cfg.hanwha_partial_match,
                    fuzzy_cutoff=cfg.hanwha_partial_fuzzy_cutoff,
                    fuzzy_min_query=cfg.hanwha_partial_fuzzy_min_query,
                )
                if hit:
                    return hit[0], "OTHER", "OTHER", hit[1], "", None
        elif sid == "regex":
            master_candidates.extend(_collect_special_other_arbiter_candidates(s))
            hp = _collect_hanwha_partial_arbiter_candidate(s, cfg)
            if hp and ctype == "OTHER":
                master_candidates.append(hp)
            master_candidates.extend(_collect_regex_arbiter_candidates(s, ctype, cfg))
            picked = pick_best(master_candidates)
            if picked:
                winner, score, dbg = picked
                return (
                    winner.cleaned,
                    winner.type_tag,
                    winner.part_code,
                    winner.source_note,
                    f"win={score:.0f} | {dbg}",
                    float(score),
                )
            if "regex" in disabled:
                sp = _try_special_other_clean(s)
                if sp:
                    return (*sp, "", None)
                z = _clean_one_skip_regex(s, ctype, cfg)
                return (*z, "", None)
            ph = _clean_one_regex_phase(
                s, ctype, cfg, inferit_executed=inferit_pipeline_on
            )
            return (*ph, "", None)

    if "regex" in disabled:
        sp = _try_special_other_clean(s)
        if sp:
            return (*sp, "", None)
        z = _clean_one_skip_regex(s, ctype, cfg)
        return (*z, "", None)
    ph = _clean_one_regex_phase(s, ctype, cfg, inferit_executed=inferit_pipeline_on)
    return (*ph, "", None)


def _clean_one_pipeline_legacy(
    s: str,
    ctype: str,
    eff_vendor: str,
    cfg: CleanConfig,
) -> Tuple[str, str, str, str]:
    """First-match wins over pipeline steps (no regex_master)."""
    from parsers.bom_text_utils import joined_clean_comment_bom_prose

    bom = joined_clean_comment_bom_prose(s)
    order = canonical_pipeline_order(cfg.clean_pipeline_order)
    disabled = frozenset(x.strip().lower() for x in cfg.clean_pipeline_disabled if x)
    inferit_executed = False

    for step in order:
        sid = str(step).strip().lower()
        if sid in disabled:
            continue
        if sid == "inferit":
            inferit_executed = True
            preset_cleaned = None
            parse_bom = bom or s
            if ctype == "RESISTOR" and cfg.parse_resistors:
                preset_cleaned = parse_inferit_resistor(parse_bom, cfg)
            elif ctype == "CAP" and cfg.parse_capacitors:
                preset_cleaned = parse_inferit_capacitor(parse_bom, cfg)
            elif ctype == "INDUCTOR" and cfg.parse_inductors:
                preset_cleaned = parse_inferit_inductor(parse_bom, cfg)
            if preset_cleaned:
                return (
                    preset_cleaned,
                    _type_tag_for_classify(ctype),
                    _map_classify_to_part_code(ctype),
                    "regex",
                )
        elif sid == "vendor":
            pnr: Optional[Tuple[str, str]] = None
            if eff_vendor in ("RESISTOR", "CAP", "OTHER"):
                pnr = _try_parse_vendor_pn_res_cap_any(s, cfg, eff_vendor)
            if pnr:
                pnv, eff = pnr[0], pnr[1]
                pnv = enrich_vendor_cleaned_from_bom(s, pnv, eff, cfg)
                pnv = reformat_cleaned_pn(pnv, eff, cfg)
                src = "vendor" if cfg.use_vendor_pn else "pn"
                return (
                    pnv,
                    _type_tag_for_classify(eff),
                    _map_classify_to_part_code(eff),
                    src,
                )
        elif sid == "library":
            lib_hit = _clean_one_try_library(s, cfg)
            if lib_hit:
                return lib_hit
        elif sid == "hanwha":
            sp = _try_special_other_clean(s)
            if sp:
                return sp
            if ctype != "OTHER":
                continue
            if cfg.use_hanwha_mdb and cfg.hanwha_partnames:
                hit = match_hanwha_mdb_partname(
                    s,
                    cfg.hanwha_partnames,
                    partial_match=cfg.hanwha_partial_match,
                    fuzzy_cutoff=cfg.hanwha_partial_fuzzy_cutoff,
                    fuzzy_min_query=cfg.hanwha_partial_fuzzy_min_query,
                )
                if hit:
                    return hit[0], "OTHER", "OTHER", hit[1]
        elif sid == "regex":
            sp = _try_special_other_clean(s)
            if sp:
                return sp
            return _clean_one_regex_phase(s, ctype, cfg, inferit_executed)

    if "regex" in disabled:
        sp = _try_special_other_clean(s)
        if sp:
            return sp
        return _clean_one_skip_regex(s, ctype, cfg)

    sp = _try_special_other_clean(s)
    if sp:
        return sp
    return _clean_one_regex_phase(s, ctype, cfg, inferit_executed)


def clean_one(
    orig: str, config: Optional[CleanConfig] = None
) -> Tuple[str, str, str, str]:
    """
    One BOM comment → cleaned string, display type, part code, source note.

    Source: '' | 'vendor' | 'pn' | 'library' | 'regex' | 'other' | 'off' | 'hanwha_mdb'
      | 'PARTIAL hanwha_mdb' | 'thermistor' | 'ferrite_bead'
    """
    cfg = _default_config(config)
    if not str(orig).strip():
        return "", "OTHER", "OTHER", ""
    s = str(orig).strip()
    from parsers.bom_text_utils import joined_clean_comment_bom_prose

    bom_prose = joined_clean_comment_bom_prose(s)
    ctype = classify_component_type(bom_prose or s)
    if ctype == "FERRITE_BEAD":
        return _ferrite_bead_passthrough(s)
    eff_vendor = ctype
    if ctype == "INDUCTOR" and not cfg.parse_inductors:
        eff_vendor = "OTHER"

    if cfg.regex_master_enabled:
        quad = _clean_one_regex_master(s, ctype, eff_vendor, cfg)
        return quad[0], quad[1], quad[2], quad[3]

    return _clean_one_pipeline_legacy(s, ctype, eff_vendor, cfg)


def clean_bom_column(
    comments: list[str], config: Optional[CleanConfig] = None
) -> List[Tuple[str, str, str, str]]:
    """List of (cleaned, type_tag, part_code, vendor_note) per row."""
    return [clean_one(c, config) for c in comments]


def clean_preview(
    comments: list[str], config: Optional[CleanConfig] = None
) -> list[tuple]:
    """
    One row =
      (#, original, cleaned, type_tag, source, alert)
      or (#, original, cleaned, type_tag, source, arbiter_detail, win_score_str, alert).

    Trailing Arbiter / Win%% columns appear when both regex_master_enabled and
    regex_master_preview_scores are True.
    """
    cfg = default_clean_config(config)
    want_extra = cfg.regex_master_enabled and cfg.regex_master_preview_scores
    results: list[tuple] = []
    echo_preview = (
        os.environ.get("VALVET_CLEAN_PREVIEW_LOG", "").strip().lower()
        or os.environ.get("BOOMER_CLEAN_PREVIEW_LOG", "").strip().lower()
    ) in (
        "1",
        "true",
        "yes",
        "on",
    )
    for i, comment in enumerate(comments):
        orig = str(comment) if comment is not None else ""
        if not (orig and str(orig).strip()):
            row = (
                (i + 1, orig, "", "OTHER", "", "", "", "")
                if want_extra
                else (i + 1, orig, "", "OTHER", "", "")
            )
            results.append(row)
            if echo_preview:
                logger.info(
                    "clean_preview row=%s type=%s source=%r cleaned=%r orig=%.120r",
                    row[0],
                    row[3],
                    row[4],
                    row[2],
                    row[1],
                )
            continue
        raw = str(orig).strip()
        from parsers.bom_text_utils import joined_clean_comment_bom_prose

        bom_prose = joined_clean_comment_bom_prose(raw)
        ctype = classify_component_type(bom_prose or raw)
        if ctype == "FERRITE_BEAD":
            a, b, _pc, d = _ferrite_bead_passthrough(raw)
            alert = analyze_token_alert(a, b, separator=cfg.output_separator).as_text()
            if alert:
                append_missing_tokens_log(
                    {
                        "row": i + 1,
                        "type": b,
                        "source": d,
                        "original": raw,
                        "cleaned": a,
                        "alert": alert,
                    }
                )
            row = (
                (i + 1, raw, a, b, d, "", "", alert)
                if want_extra
                else (i + 1, raw, a, b, d, alert)
            )
            results.append(row)
            if echo_preview:
                logger.info(
                    "clean_preview row=%s type=%s source=%r cleaned=%r orig=%.120r",
                    row[0],
                    row[3],
                    row[4],
                    row[2],
                    row[1],
                )
            continue
        eff_vendor = (
            ctype if not (ctype == "INDUCTOR" and not cfg.parse_inductors) else "OTHER"
        )
        if cfg.regex_master_enabled:
            a, b, c, d, dbg, wsc = _clean_one_regex_master(raw, ctype, eff_vendor, cfg)
            alert = analyze_token_alert(a, b, separator=cfg.output_separator).as_text()
            if alert:
                append_missing_tokens_log(
                    {
                        "row": i + 1,
                        "type": b,
                        "source": d,
                        "original": raw,
                        "cleaned": a,
                        "alert": alert,
                    }
                )
            if want_extra:
                w_s = "" if wsc is None else f"{wsc:.0f}"
                row = (i + 1, raw, a, b, d, dbg, w_s, alert)
            else:
                row = (i + 1, raw, a, b, d, alert)
            results.append(row)
            if echo_preview:
                logger.info(
                    "clean_preview row=%s type=%s source=%r cleaned=%r orig=%.120r",
                    row[0],
                    row[3],
                    row[4],
                    row[2],
                    row[1],
                )
        else:
            cleaned, typ, _pc, vnote = _clean_one_pipeline_legacy(
                raw, ctype, eff_vendor, cfg
            )
            alert = analyze_token_alert(
                cleaned, typ, separator=cfg.output_separator
            ).as_text()
            if alert:
                append_missing_tokens_log(
                    {
                        "row": i + 1,
                        "type": typ,
                        "source": vnote,
                        "original": raw,
                        "cleaned": cleaned,
                        "alert": alert,
                    }
                )
            row = (i + 1, raw, cleaned, typ, vnote, alert)
            results.append(row)
            if echo_preview:
                logger.info(
                    "clean_preview row=%s type=%s source=%r cleaned=%r orig=%.120r",
                    row[0],
                    row[3],
                    row[4],
                    row[2],
                    row[1],
                )
    return results


def clean_bom_dataframe(
    df: "pd.DataFrame", comment_col: str, config: Optional[CleanConfig] = None
) -> "pd.DataFrame":
    """
    Add columns: Comment_cleaned (or {comment_col}_cleaned), clean_type, clean_part_code, clean_vendor.
    """

    if comment_col not in df.columns:
        raise ValueError(f"Column {comment_col!r} not in DataFrame")
    series = [clean_one(x, config) for x in df[comment_col].astype(str).tolist()]
    out = df.copy()
    out[f"{comment_col}_cleaned"] = [r[0] for r in series]
    out["clean_type"] = [r[1] for r in series]
    out["clean_part_code"] = [r[2] for r in series]
    out["clean_vendor"] = [r[3] for r in series]
    return out
