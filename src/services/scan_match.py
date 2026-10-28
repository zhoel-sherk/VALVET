"""Map a scanned Custom code to its component and its T-OLP feeder slots."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from parsers.tolp_export import TolpExport, TolpFeeder, places_for_parts

STATE_OK = "ok"
STATE_UNKNOWN_CODE = "unknown_code"
STATE_PART_MISSING = "part_missing"


@dataclass(frozen=True)
class ScanEntry:
    """One BOM/Merge component carrying the scanned code."""

    code: str
    part: str
    refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScanResult:
    """Outcome of one scan."""

    code: str
    state: str
    entries: tuple[ScanEntry, ...] = ()
    feeders: tuple[TolpFeeder, ...] = ()

    @property
    def ok(self) -> bool:
        return self.state == STATE_OK


def normalize_code(code: object) -> str:
    """Barcode text to lookup key: collapse whitespace, keep case."""
    return " ".join(str(code or "").split())


def build_code_index(
    rows: Iterable[Mapping[str, object]],
    code_key: str,
    part_keys: Sequence[str],
    *,
    ref_key: str = "Ref",
) -> dict[str, tuple[ScanEntry, ...]]:
    """``code -> entries`` from merge/BOM rows.

    ``part_keys`` is tried in order (merge ``Value`` first, then a cleaned
    comment); every distinct non-empty value is kept so a code whose BOM row was
    cleaned and one that was not both resolve.
    """
    grouped: dict[tuple[str, str], list[str]] = {}
    for row in rows:
        code = normalize_code(row.get(code_key))
        if not code:
            continue
        parts: list[str] = []
        for key in part_keys:
            value = normalize_code(row.get(key))
            if value and value not in parts:
                parts.append(value)
        if not parts:
            continue
        refs_raw = row.get(ref_key)
        refs = [normalize_code(refs_raw)] if refs_raw is not None else []
        for part in parts:
            bucket = grouped.setdefault((code, part), [])
            for ref in refs:
                if ref and ref not in bucket:
                    bucket.append(ref)

    out: dict[str, list[ScanEntry]] = {}
    for (code, part), refs in sorted(grouped.items()):
        out.setdefault(code, []).append(
            ScanEntry(code=code, part=part, refs=tuple(refs))
        )
    return {code: tuple(entries) for code, entries in out.items()}


def resolve_scan(
    code: str,
    index: Mapping[str, Sequence[ScanEntry]],
    export: TolpExport | None,
) -> ScanResult:
    """Look up ``code`` and the feeder slots of every part it maps to."""
    key = normalize_code(code)
    entries = tuple(index.get(key, ()))
    if not entries:
        return ScanResult(code=key, state=STATE_UNKNOWN_CODE)
    if export is None:
        return ScanResult(code=key, state=STATE_PART_MISSING, entries=entries)
    parts: list[str] = []
    for entry in entries:
        if entry.part and entry.part not in parts:
            parts.append(entry.part)
    feeders = tuple(places_for_parts(export, parts))
    if not feeders:
        return ScanResult(code=key, state=STATE_PART_MISSING, entries=entries)
    return ScanResult(code=key, state=STATE_OK, entries=entries, feeders=feeders)
