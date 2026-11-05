"""Clean BOM profile payload: one dataclass owns the persisted contract."""

from __future__ import annotations

from ui.clean_prefs import CleanPrefs

DEFAULT_DICT = {
    "res_template": "nom,pack,watt,%",
    "cap_template": "nom,pack,film,%,V",
    "ind_template": "pack,nom,%,Imax,DCR",
    "cap_nf": False,
    "cap_uf_micro": False,
    "res_ohm_r_suffix": True,
    "infer_resistor_watt_from_package": False,
    "use_vendor": False,
    "from_db": True,
    "from_hanwha_mdb": False,
    "hanwha_partial_match": False,
    "regex_master_enabled": False,
    "regex_master_preview_scores": False,
    "prefix_use_separator": True,
    "res_prefix": "",
    "cap_prefix": "",
    "ind_prefix": "",
    "group_res": True,
    "group_cap": True,
    "group_ind": True,
    "group_pn": True,
    "combine_input_columns": False,
    "output_separator": "_",
    "mpn_search_provider": "digikey",
    "octopart_api_key": "",
    "options_expanded": False,
}

CUSTOM = CleanPrefs(
    res_template="nom,pack,watt,%,V",
    cap_template="nom,pack",
    ind_template="pack,nom",
    cap_nf=True,
    cap_uf_micro=True,
    res_ohm_r_suffix=False,
    infer_resistor_watt_from_package=True,
    use_vendor=True,
    from_db=False,
    from_hanwha_mdb=True,
    hanwha_partial_match=True,
    regex_master_enabled=True,
    regex_master_preview_scores=True,
    prefix_use_separator=False,
    res_prefix="R",
    cap_prefix="C",
    ind_prefix="L",
    group_res=False,
    group_cap=False,
    group_ind=False,
    group_pn=False,
    combine_input_columns=True,
    output_separator=" ",
    mpn_search_provider="octopart",
    octopart_api_key="secret",
    options_expanded=True,
)


def test_defaults_match_the_profile_contract() -> None:
    """Renaming or dropping a key breaks old profiles; this pins the format."""
    assert CleanPrefs().to_dict() == DEFAULT_DICT


def test_round_trip_keeps_every_field() -> None:
    assert CleanPrefs.from_dict(CUSTOM.to_dict()) == CUSTOM


def test_missing_keys_use_the_documented_defaults() -> None:
    assert CleanPrefs.from_dict({}) == CleanPrefs()


def test_string_and_integer_flags_are_coerced() -> None:
    prefs = CleanPrefs.from_dict(
        {"cap_nf": "true", "from_db": 0, "group_res": "False", "use_vendor": 1}
    )
    assert prefs.cap_nf is True
    assert prefs.from_db is False
    assert prefs.group_res is False
    assert prefs.use_vendor is True


def test_unknown_keys_are_ignored() -> None:
    assert CleanPrefs.from_dict({"removed_option": 1}) == CleanPrefs()


def test_to_dict_keeps_native_types() -> None:
    data = CUSTOM.to_dict()
    for key, default in DEFAULT_DICT.items():
        if isinstance(default, bool):
            assert isinstance(data[key], bool), key
    assert isinstance(data["res_template"], str)
