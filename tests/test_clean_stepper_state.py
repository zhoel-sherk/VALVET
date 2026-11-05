"""Stepper state machine: rules pinned without a window."""

from __future__ import annotations

import pytest

from ui.clean_stepper import StepperInput, stepper_states


def _state(**kwargs: bool) -> StepperInput:
    base = {
        "imported": False,
        "has_preview": False,
        "stale": False,
        "applied": False,
        "convert_enabled": False,
        "apply_enabled": False,
    }
    base.update(kwargs)
    return StepperInput(**base)


def test_empty_bom_points_at_import() -> None:
    view = stepper_states(_state())
    assert view["import"].state == "next"
    assert view["import"].active is True
    assert view["import"].tooltip_key is None
    assert view["convert"].state == "idle"
    assert view["convert"].active is False
    assert view["convert"].tooltip_key == "clean.btn_convert_disabled_import"
    assert view["apply"].state == "idle"
    assert view["apply"].tooltip_key == "clean.btn_apply_disabled_convert"


def test_imported_points_at_convert() -> None:
    view = stepper_states(_state(imported=True, convert_enabled=True))
    assert view["import"].state == "done"
    assert view["import"].active is False
    assert view["convert"].state == "next"
    assert view["convert"].active is True
    assert view["convert"].tooltip_key == "clean.btn_convert_tip"
    assert view["apply"].tooltip_key == "clean.btn_apply_disabled_convert"


def test_preview_points_at_apply() -> None:
    view = stepper_states(
        _state(
            imported=True, convert_enabled=True, has_preview=True, apply_enabled=True
        )
    )
    assert view["convert"].state == "done"
    assert view["convert"].active is False
    assert view["apply"].state == "next"
    assert view["apply"].active is True
    assert view["apply"].tooltip_key == "clean.btn_apply_tip"


def test_stale_preview_marks_convert_and_warns_on_apply() -> None:
    view = stepper_states(
        _state(
            imported=True,
            convert_enabled=True,
            has_preview=True,
            apply_enabled=True,
            stale=True,
        )
    )
    assert view["convert"].state == "stale"
    assert view["apply"].tooltip_key == "clean.btn_apply_disabled_stale"


def test_applied_preview_marks_apply_done() -> None:
    view = stepper_states(
        _state(
            imported=True,
            convert_enabled=True,
            has_preview=True,
            apply_enabled=True,
            applied=True,
        )
    )
    assert view["apply"].state == "done"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"stale": True},
        {"applied": True},
    ],
)
def test_flags_without_preview_are_ignored(kwargs: dict[str, bool]) -> None:
    view = stepper_states(_state(imported=True, convert_enabled=True, **kwargs))
    assert view["convert"].state == "next"
    assert view["apply"].state == "idle"


def test_imported_without_mapped_column_explains_convert() -> None:
    view = stepper_states(_state(imported=True))
    assert view["convert"].state == "idle"
    assert view["convert"].tooltip_key == "clean.btn_convert_disabled_map"


def test_widget_enabled_state_decides_active_step() -> None:
    """Several callers enable the buttons directly; the stepper follows them."""
    view = stepper_states(_state(convert_enabled=True))
    assert view["convert"].active is True
    assert view["import"].active is False
