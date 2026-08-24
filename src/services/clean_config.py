"""Build ``CleanConfig`` from plain widget values (no Qt).

Replaces ``MainWindow._clean_config_from_ui()`` and ``_save_clean_settings()``.
"""

from __future__ import annotations

from typing import Callable

from clean_pipeline_settings import load_clean_debug_extras, load_pipeline_from_settings
from clean_types import CleanConfig


def build_clean_config(
    *,
    res_template: tuple[str, ...],
    cap_template: tuple[str, ...],
    ind_template: tuple[str, ...],
    cap_nf_to_uf: bool = False,
    cap_uf_micro_sign: bool = False,
    res_ohm_r_suffix: bool = False,
    use_pn_codecs: bool = True,
    use_vendor_pn: bool = True,
    parse_resistors: bool = True,
    parse_capacitors: bool = True,
    parse_inductors: bool = True,
    output_separator: str = "",
    res_prefix: str = "",
    cap_prefix: str = "",
    ind_prefix: str = "",
    prefix_use_separator: bool = True,
    use_component_library: bool = True,
    use_hanwha_mdb: bool = False,
    hanwha_partial_match: bool = False,
    hanwha_partnames: set[str] | None = None,
    clean_pipeline_order: tuple[str, ...] = (),
    clean_pipeline_disabled: tuple[str, ...] = (),
    component_library_path: str | None = None,
    regex_master_enabled: bool = False,
    regex_master_preview_scores: bool = False,
    settings_getter: Callable[[str, str], str] | None = None,
) -> CleanConfig:
    cap_template = tuple("V" if x == "V (volt)" else x for x in cap_template)
    pipe_order, pipe_disabled = clean_pipeline_order, clean_pipeline_disabled
    if not pipe_order and settings_getter is not None:
        pipe_order, pipe_disabled = load_pipeline_from_settings(settings_getter)
    if not pipe_order:
        pipe_order, pipe_disabled = load_pipeline_from_settings(None)
    lib_raw = ""
    if settings_getter is not None:
        lib_raw = str(settings_getter("clean/components_txt_path", "") or "").strip()
    if component_library_path is None and lib_raw:
        component_library_path = lib_raw
    if not regex_master_enabled and settings_getter is not None:
        regex_master_enabled, regex_master_preview_scores = load_clean_debug_extras(
            settings_getter
        )

    return CleanConfig(
        resistor_include_package="pack" in res_template,
        resistor_include_tolerance="%" in res_template,
        cap_include_package="pack" in cap_template,
        cap_include_voltage="V" in cap_template,
        cap_include_dielectric="film" in cap_template,
        cap_include_tolerance="%" in cap_template,
        cap_convert_nf_to_uf=cap_nf_to_uf,
        cap_uf_micro_sign=cap_uf_micro_sign,
        resistor_include_ohm_r_suffix=res_ohm_r_suffix,
        use_pn_codecs=use_pn_codecs,
        use_vendor_pn=use_vendor_pn,
        parse_resistors=parse_resistors,
        parse_capacitors=parse_capacitors,
        parse_inductors=parse_inductors,
        output_separator=output_separator,
        resistor_template=res_template,
        cap_template=cap_template,
        inductor_template=ind_template if ind_template else CleanConfig.inductor_template,
        resistor_prefix=res_prefix,
        cap_prefix=cap_prefix,
        inductor_prefix=ind_prefix,
        prefix_use_separator=prefix_use_separator,
        use_component_library=use_component_library,
        use_hanwha_mdb=use_hanwha_mdb,
        hanwha_partial_match=hanwha_partial_match,
        hanwha_partnames=hanwha_partnames,
        clean_pipeline_order=pipe_order,
        clean_pipeline_disabled=tuple(sorted(pipe_disabled)),
        component_library_path=component_library_path if component_library_path else None,
        regex_master_enabled=regex_master_enabled,
        regex_master_preview_scores=regex_master_preview_scores,
    )
