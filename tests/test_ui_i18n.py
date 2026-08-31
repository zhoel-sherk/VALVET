"""ui_i18n: JSON language catalogs."""

from __future__ import annotations

import os
import sys

tests_path = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(tests_path), "src"))

from ui_i18n import SUPPORTED_UI_LOCALES, UiI18n, load_catalog


def test_load_catalog_sample_locales() -> None:
    en = load_catalog("en")
    ru = load_catalog("ru")
    assert en["tab.project"] == "Project"
    assert ru["tab.project"] == "Проект"
    assert load_catalog("pl")["tab.project"] == "Projekt"
    assert load_catalog("zh")["tab.project"] == "项目"
    assert load_catalog("de")["tab.project"] == "Projekt"
    assert load_catalog("pt")["tab.project"] == "Projeto"


def test_all_supported_catalogs_match_en_keys() -> None:
    en = load_catalog("en")
    en_keys = set(en.keys())
    for loc in SUPPORTED_UI_LOCALES:
        cat = load_catalog(loc)
        assert set(cat.keys()) == en_keys, loc


def test_ui_i18n_russian() -> None:
    i = UiI18n("ru")
    assert i.locale == "ru"
    assert i.tr("status.ready") == "Готово"


def test_ui_i18n_polish() -> None:
    i = UiI18n("pl")
    assert i.locale == "pl"
    assert i.tr("status.ready") == "Gotowe"


def test_unknown_locale_falls_back_en() -> None:
    i = UiI18n("xx")
    assert i.locale == "en"
