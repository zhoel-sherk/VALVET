"""Shared Clean BOM configuration types (no parser implementations).

Split out so `parsers/*` can import `CleanConfig` without circular imports
against `clean_component`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Set, Tuple

DEFAULT_CLEAN_PIPELINE: Tuple[str, ...] = (
    "inferit",
    "vendor",
    "library",
    "hanwha",
    "regex",
)
_PIPELINE_STEP_IDS = frozenset(DEFAULT_CLEAN_PIPELINE)


def canonical_pipeline_order(seq: Sequence[str] | None) -> Tuple[str, ...]:
    """Normalize user ordering: unique known steps, append any missing defaults."""
    if not seq:
        return DEFAULT_CLEAN_PIPELINE
    seen: set[str] = set()
    out: list[str] = []
    for raw in seq:
        k = str(raw).strip().lower()
        if k in _PIPELINE_STEP_IDS and k not in seen:
            seen.add(k)
            out.append(k)
    for k in DEFAULT_CLEAN_PIPELINE:
        if k not in seen:
            seen.add(k)
            out.append(k)
    return tuple(out)


class CleanSettings:
    """Deprecated: use CleanConfig. Kept for any legacy references."""

    resistor_include_tolerance = True
    resistor_include_package = True
    resistor_custom_regex = ""
    cap_include_voltage = True
    cap_include_dielectric = True
    cap_custom_regex = ""
    other_custom_regex = ""


@dataclass
class CleanConfig:
    """
    Per-run settings for Clean BOM. Mirrors classic app checkboxes and adds vendor PN.
    When a field is False, that segment is dropped from the normalized string (underscore-joined).
    """

    resistor_include_package: bool = True
    resistor_include_tolerance: bool = True
    cap_include_package: bool = True
    cap_include_voltage: bool = True
    cap_include_dielectric: bool = True
    cap_include_tolerance: bool = True
    cap_convert_nf_to_uf: bool = False
    # When True: show µF (micro sign) instead of ASCII uF in capacitor nominals.
    cap_uf_micro_sign: bool = False
    # When False: strip trailing plain-ohms «R» only (12.5R→12.5); does not affect K/M.
    resistor_include_ohm_r_suffix: bool = True
    # When True and watt slot empty: fill 0402→1/16W etc. (regex/inferit only).
    infer_resistor_watt_from_package: bool = False
    inductor_template: Tuple[str, ...] = ("pack", "nom", "%", "Imax", "DCR")
    use_pn_codecs: bool = True
    use_vendor_pn: bool = False
    parse_resistors: bool = True
    parse_capacitors: bool = True
    parse_inductors: bool = True
    output_separator: str = "_"
    resistor_template: Tuple[str, ...] = ("pack", "nom", "%")
    cap_template: Tuple[str, ...] = ("pack", "nom", "V", "film", "%")
    resistor_prefix: str = ""
    cap_prefix: str = ""
    inductor_prefix: str = ""
    prefix_use_separator: bool = True
    use_component_library: bool = True
    use_hanwha_mdb: bool = False
    hanwha_partial_match: bool = False
    # Hanwha «Partial match» fallback (after primary substring match): fuzzy alignment on
    # ``_norm_hanwha`` keys via ``rapidfuzz.fuzz.partial_ratio``.
    hanwha_partial_fuzzy_cutoff: float = 88.0
    hanwha_partial_fuzzy_min_query: int = 5
    hanwha_partnames: Optional[Set[str]] = None
    clean_pipeline_order: Tuple[str, ...] = DEFAULT_CLEAN_PIPELINE
    clean_pipeline_disabled: Tuple[str, ...] = ()
    component_library_path: Optional[str] = None
    regex_master_enabled: bool = False
    regex_master_preview_scores: bool = False


def default_clean_config(config: Optional[CleanConfig]) -> CleanConfig:
    if config is None:
        return CleanConfig()
    tpl = getattr(config, "cap_template", ())
    if tpl:
        from dataclasses import replace

        new_tpl = tuple("V" if x in ("W", "V (volt)") else x for x in tpl)
        if new_tpl != tpl:
            return replace(config, cap_template=new_tpl)
    return config
