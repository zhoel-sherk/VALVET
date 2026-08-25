"""Qt-free Clean BOM pipeline / debug flags from settings storage."""

from __future__ import annotations

import json
from typing import Iterable, Protocol, Union

from clean_types import DEFAULT_CLEAN_PIPELINE, canonical_pipeline_order


class _SettingsReader(Protocol):
    def __call__(self, key: str, default: object = ...) -> object: ...


def _read_bool_setting(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    sl = str(value).strip().lower()
    if sl in ("true", "1", "yes", "on"):
        return True
    if sl in ("false", "0", "no", "off", ""):
        return False
    return default


def _setting(
    settings: Union[_SettingsReader, object, None],
    key: str,
    default: object = "",
) -> object:
    if settings is None:
        return default
    if callable(settings):
        return settings(key, default)
    getter = getattr(settings, "value", None)
    if callable(getter):
        return getter(key, default)
    return default


def load_clean_debug_extras(
    settings: Union[_SettingsReader, object, None],
) -> tuple[bool, bool]:
    """Regex master flags from settings (preview scores only when master is on)."""
    rm = _read_bool_setting(
        _setting(settings, "clean/regex_master_enabled", False), False
    )
    pv = _read_bool_setting(
        _setting(settings, "clean/regex_master_preview_scores", False), False
    )
    if not rm:
        pv = False
    return rm, pv


def load_pipeline_from_settings(
    settings: Union[_SettingsReader, object, None],
) -> tuple[tuple[str, ...], frozenset[str]]:
    """Return ``(order, disabled_set)`` from persisted pipeline JSON."""
    raw_o = str(_setting(settings, "clean/pipeline_order", "") or "").strip()
    raw_d = str(_setting(settings, "clean/pipeline_disabled", "") or "").strip()
    order: Iterable[str] = DEFAULT_CLEAN_PIPELINE
    if raw_o:
        try:
            parsed = json.loads(raw_o)
            if isinstance(parsed, list) and parsed:
                order = canonical_pipeline_order([str(x) for x in parsed])
        except (json.JSONDecodeError, TypeError):
            pass
    disabled: set[str] = set()
    if raw_d:
        try:
            parsed = json.loads(raw_d)
            if isinstance(parsed, list):
                disabled = {str(x).strip().lower() for x in parsed}
        except (json.JSONDecodeError, TypeError):
            pass
    return tuple(order), frozenset(disabled)
