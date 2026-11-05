"""Clean BOM settings payload: profile JSON contract, no Qt.

``ui/profiles.py`` persists this dict per profile, so the keys and their
fallbacks are a format contract. One dataclass owns both directions, which
removes the hand-written mirror that used to drift between gather and apply.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class CleanPrefs:
    res_template: str = "nom,pack,watt,%"
    cap_template: str = "nom,pack,film,%,V"
    ind_template: str = "pack,nom,%,Imax,DCR"
    cap_nf: bool = False
    cap_uf_micro: bool = False
    res_ohm_r_suffix: bool = True
    infer_resistor_watt_from_package: bool = False
    use_vendor: bool = False
    from_db: bool = True
    from_hanwha_mdb: bool = False
    hanwha_partial_match: bool = False
    regex_master_enabled: bool = False
    regex_master_preview_scores: bool = False
    prefix_use_separator: bool = True
    res_prefix: str = ""
    cap_prefix: str = ""
    ind_prefix: str = ""
    group_res: bool = True
    group_cap: bool = True
    group_ind: bool = True
    group_pn: bool = True
    combine_input_columns: bool = False
    output_separator: str = "_"
    mpn_search_provider: str = "digikey"
    octopart_api_key: str = ""
    options_expanded: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> CleanPrefs:
        """Read older profile JSON: missing keys fall back, string bools coerce."""

        # Imported here so ``import ui.clean_prefs`` stays free of the app shell:
        # ``app/__init__`` imports ``app.window``, which imports ``ui.clean_tab``.
        from app.prefs import prefs_profile_bool

        def flag(key: str) -> bool:
            return prefs_profile_bool(raw.get(key), getattr(DEFAULTS, key))

        def text(key: str) -> str:
            return str(raw.get(key, getattr(DEFAULTS, key)))

        return cls(
            res_template=text("res_template"),
            cap_template=text("cap_template"),
            ind_template=text("ind_template"),
            cap_nf=flag("cap_nf"),
            cap_uf_micro=flag("cap_uf_micro"),
            res_ohm_r_suffix=flag("res_ohm_r_suffix"),
            infer_resistor_watt_from_package=flag("infer_resistor_watt_from_package"),
            use_vendor=flag("use_vendor"),
            from_db=flag("from_db"),
            from_hanwha_mdb=flag("from_hanwha_mdb"),
            hanwha_partial_match=flag("hanwha_partial_match"),
            regex_master_enabled=flag("regex_master_enabled"),
            regex_master_preview_scores=flag("regex_master_preview_scores"),
            prefix_use_separator=flag("prefix_use_separator"),
            res_prefix=text("res_prefix"),
            cap_prefix=text("cap_prefix"),
            ind_prefix=text("ind_prefix"),
            group_res=flag("group_res"),
            group_cap=flag("group_cap"),
            group_ind=flag("group_ind"),
            group_pn=flag("group_pn"),
            combine_input_columns=flag("combine_input_columns"),
            output_separator=text("output_separator"),
            mpn_search_provider=text("mpn_search_provider"),
            octopart_api_key=text("octopart_api_key"),
            options_expanded=flag("options_expanded"),
        )


DEFAULTS = CleanPrefs()
