"""Pure helpers for the Clean BOM tab (no Qt widgets)."""

from __future__ import annotations

import pandas as pd

_CLEAN_PRESET_SMT = {
    "res": ("nom", "pack", "watt", "%"),
    "cap": ("nom", "pack", "film", "%", "V"),
    "ind": ("pack", "nom", "%", "Imax", "DCR"),
}
_CLEAN_PRESET_COMPACT = {
    "res": ("nom", "pack", "none", "none"),
    "cap": ("nom", "pack", "none", "none", "none"),
    "ind": ("pack", "nom", "none", "none", "none"),
}


def _clean_input_cells(item: object) -> tuple[str, ...]:
    if isinstance(item, str):
        return (item,)
    return tuple(str(cell) for cell in item)


def _clean_int_list(raw: object) -> list[int]:
    """QSettings can hand back a list, a tuple or a comma string; keep only ints."""
    values: list[object]
    if raw is None:
        return []
    if isinstance(raw, str):
        values = raw.split(",")
    elif isinstance(raw, (list, tuple)):
        values = list(raw)
    else:
        try:
            values = list(raw)  # type: ignore[arg-type]
        except TypeError:
            # Not a stored sequence: the correct contract is "no saved sizes".
            return []
    out: list[int] = []
    for value in values:
        try:
            out.append(int(str(value).strip()))
        except (TypeError, ValueError):
            # Malformed stored layout: the correct fallback is "no saved sizes";
            # the splitter then uses its default or collapsed geometry.
            return []
    return out


def _clean_preview_frame(
    inputs: list[object], results: list[dict] | None, *, combined_label: str
) -> pd.DataFrame:
    """Build preview columns without serialising alternatives into one string."""
    rows = []
    input_count = max((len(_clean_input_cells(item)) for item in inputs), default=1)
    for i, item in enumerate(inputs):
        cells = _clean_input_cells(item)
        record = {"#": i + 1}
        for col_index in range(input_count):
            name = "Original" if col_index == 0 else f"Original {col_index + 1}"
            record[name] = cells[col_index] if col_index < len(cells) else ""
        if results is None:
            record.update({"Cleaned": "—", "Type": "—", "Source": "—"})
        else:
            result = results[i]
            record["Cleaned"] = result["Cleaned"]
            record["Type"] = result["Type"]
            if input_count > 1:
                if result.get("combined"):
                    record["Input"] = combined_label
                else:
                    winner = result.get("input_index")
                    record["Input"] = (
                        "Original" if winner == 0 else f"Original {int(winner) + 1}"
                    )
            for key in ("Source", "Arbiter", "Win%", "Alert"):
                if key in result:
                    record[key] = result[key]
        rows.append(record)
    return pd.DataFrame(rows)
