"""Clean BOM stepper: pure state machine, no Qt.

The three primary buttons (Import / Convert / Apply) carry two properties:
``cleanStep`` (active or idle, the original QSS contract) and ``cleanStepState``
(done / next / stale / idle). Both are decided here from plain booleans so the
rules can be tested in milliseconds and the widget method only applies them.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StepperInput:
    """Everything the stepper reads today.

    ``convert_enabled`` / ``apply_enabled`` are the buttons' own enabled state
    and stay an input on purpose: the widget is the source of truth for
    "active", and several callers set it directly.
    """

    imported: bool
    has_preview: bool
    stale: bool
    applied: bool
    convert_enabled: bool
    apply_enabled: bool


@dataclass(frozen=True)
class StepView:
    state: str
    active: bool
    tooltip_key: str | None


def stepper_states(state: StepperInput) -> dict[str, StepView]:
    """Return the visible state of each primary step."""
    stale = state.stale and state.has_preview
    applied = state.applied and state.has_preview

    import_active = not state.convert_enabled and not state.apply_enabled
    convert_active = state.convert_enabled and not state.apply_enabled
    apply_active = state.apply_enabled
    if not state.convert_enabled:
        next_key = "apply" if state.apply_enabled else "import"
    elif not state.apply_enabled:
        next_key = "convert"
    else:
        next_key = "apply"

    convert_tooltip = (
        "clean.btn_convert_tip"
        if state.convert_enabled
        else (
            "clean.btn_convert_disabled_map"
            if state.imported
            else "clean.btn_convert_disabled_import"
        )
    )
    if not state.apply_enabled:
        apply_tooltip = (
            "clean.btn_apply_disabled_convert"
            if not state.has_preview
            else (
                "clean.btn_apply_disabled_stale"
                if stale
                else "clean.btn_apply_disabled_none"
            )
        )
    elif stale:
        apply_tooltip = "clean.btn_apply_disabled_stale"
    else:
        apply_tooltip = "clean.btn_apply_tip"

    return {
        "import": StepView(
            state="done" if state.imported else ("next" if import_active else "idle"),
            active=import_active,
            tooltip_key=None,
        ),
        "convert": StepView(
            state=(
                "stale"
                if stale
                else (
                    "done"
                    if state.has_preview
                    else ("next" if next_key == "convert" else "idle")
                )
            ),
            active=convert_active,
            tooltip_key=convert_tooltip,
        ),
        "apply": StepView(
            state=(
                "done"
                if applied
                else ("next" if next_key == "apply" and state.apply_enabled else "idle")
            ),
            active=apply_active,
            tooltip_key=apply_tooltip,
        ),
    }
