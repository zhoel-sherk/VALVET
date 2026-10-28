"""Read a Hanwha T-OLP export folder (``.mfb`` / ``.eoj`` / per-machine ``.PCB``).

The primary source is the machine feeder base (``.mfb``): it names the machine
and side (Front/Rear) explicitly and lists the feeders in attachment order, so a
feeder's slot is its position in the T-OLP ``No.`` column, advanced by the
number of positions the feeder type occupies (8 mm = 1, 24 mm = 3, tray = 2 …).

Fallbacks / companions:

* the ``.eoj`` is the CWorkShop job container: it names the machines/models and
  lists their PCB files, but carries no feeder allocation and no ``IN-…`` codes;
* each ``.PCB`` is a binary object stream with its own feeder records
  (204-byte ``CFeeder`` objects) and is used when no ``.mfb`` is present, or to
  cross-check a machine feeder base.

The PCB format is proprietary and tied to the T-OLP version, so every field is
validated before it is trusted and unknown layouts fail loudly instead of
returning an empty list.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

#: Byte that starts every serialized feeder object in a ``.PCB`` file.
_FEEDER_MARKER = b"CFeeder\x00"
#: Every feeder object carries this header; used to reject stray markers.
_FEEDER_HEADER = b"CBHeader"
#: Serialized feeder object size, measured on T-OLP 17.x exports.
_FEEDER_RECORD_SIZE = 204
#: Absolute offsets inside one feeder record.
_SLOT_OFFSET = 44
_SIDE_OFFSET = 46
_PART_OFFSET = 60
#: Longest part name we accept (the serialized field is 64 bytes).
_PART_MAX = 64

SIDE_FRONT = "Front"
SIDE_REAR = "Rear"

_PRINTABLE_RUN = re.compile(rb"[\x20-\x7e]{2,}")
_MODEL_TOKEN = re.compile(r"^[A-Z][A-Z0-9_]{2,15}$")
_PCB_NAME = re.compile(rb"[\x20-\x7e]{4,}\.PCB")

# --- .mfb: machine feeder base ------------------------------------------------
# Sections are introduced by a length-prefixed machine name and side ("F"/"R").
_MFB_SECTION = re.compile(rb"\x02M(\d).{4}\x01([FR])", re.S)
# Feeder type tokens that carry the tape width in their name.
_MFB_TYPE = re.compile(
    rb"(?:TapeFeeder\d*mm[A-Z]*|TapeFeeder|STF-\d+[A-Z]?|TrayFeeder|Tray|StickFeeder|Stick)"
)
_MFB_PART = re.compile(r"[A-Za-z0-9_.%+/-]+")
#: Physical slots consumed by one feeder of that width (user-confirmed).
_TAPE_WIDTH = {8: 1, 12: 2, 16: 2, 24: 3, 36: 4, 44: 4, 56: 5, 88: 7}
_TRAY_WIDTH = 2
#: Tokens that look like parts but are feeder/nozzle/type names.
_NON_PART_PREFIXES = (
    "TapeFeeder",
    "Tray",
    "Stick",
    "STF-",
    "Return",
    "Internal",
    "SYSTEM",
    "USER",
    "Fix ",
    "CN0",
    "SMC0",
    "SMR0",
    "Camera",
    "Nozzle",
)


class TolpExportError(Exception):
    """Raised when a folder/file cannot be read as a T-OLP export."""


@dataclass(frozen=True)
class TolpFeeder:
    """One feeder slot: a machine, a side, a slot number and the part it holds."""

    machine: str
    model: str
    side: str
    slot: int
    part: str


@dataclass
class TolpExport:
    """Parsed export folder."""

    folder: Path
    feeders: tuple[TolpFeeder, ...] = ()
    machines: dict[str, str] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    #: ``"mfb"`` (machine feeder base), ``"pcb"`` (per-machine PCB) or ``""``.
    source: str = ""
    _by_part: dict[str, list[TolpFeeder]] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        index: dict[str, list[TolpFeeder]] = {}
        for feeder in self.feeders:
            index.setdefault(normalize_part_name(feeder.part), []).append(feeder)
        self._by_part = index

    def by_part(self, part: str) -> list[TolpFeeder]:
        """Feeders holding ``part`` (case/whitespace insensitive), sorted."""
        return list(self._by_part.get(normalize_part_name(part), ()))


def normalize_part_name(part: object) -> str:
    """Comparison key: collapse whitespace and case-fold, keep punctuation."""
    return " ".join(str(part or "").split()).casefold()


def _lp_string(data: bytes, pos: int) -> tuple[str, int] | None:
    """Read a one-byte-length-prefixed ASCII string from the ``.eoj`` stream."""
    if pos >= len(data):
        return None
    length = data[pos]
    if length == 0 or length == 0xFF:
        return None
    start = pos + 1
    end = start + length
    if end > len(data):
        return None
    raw = data[start:end]
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError:
        return None
    return text, end


def _parse_eoj(path: Path) -> tuple[list[tuple[str, str]], list[str], str, list[str]]:
    """Machine names/models, referenced PCB file names and the T-OLP version."""
    warnings: list[str] = []
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise TolpExportError(f"Cannot read {path.name}: {exc}") from exc

    version = ""
    head = data[:64]
    pos = head.find(b"CWorkShop")
    if pos >= 0:
        start = pos + len(b"CWorkShop")
        read = _lp_string(data, start)
        if read is not None:
            version = read[0]

    machines: list[tuple[str, str]] = []
    for match in re.finditer(b"CMachine", data):
        pos = match.end()
        read = _lp_string(data, pos)
        if read is None:
            continue
        name, pos = read
        read = _lp_string(data, pos)  # machine id
        if read is None:
            continue
        _machine_id, pos = read
        pos += 12  # three 4-byte counters between the id and the type
        read = _lp_string(data, pos)  # machine type, e.g. "Chip Mounter"
        if read is None:
            continue
        _machine_type, pos = read
        read = _lp_string(data, pos)  # id again
        if read is None:
            continue
        _id, pos = read
        read = _lp_string(data, pos)  # model, e.g. "DECANS2"
        if read is None:
            continue
        model, _pos = read
        if model and model != name:
            machines.append((name, model))

    pcb_files: list[str] = []
    for match in _PCB_NAME.finditer(data):
        name = match.group().decode("ascii")
        if name not in pcb_files:
            pcb_files.append(name)
    if not machines:
        warnings.append(f"{path.name}: no CMachine records found")
    return machines, pcb_files, version, warnings


def _pcb_model(data: bytes) -> str:
    """Machine model from the PCB header (first token after ``CPCBHeader``)."""
    head = data[:1024]
    pos = head.find(b"CPCBHeader")
    if pos < 0:
        pos = 0
    for match in re.finditer(rb"[\x20-\x7e]{3,}", head[pos:]):
        token = match.group().decode("ascii").strip()
        if token in ("CPCBHeader", "PCBHeader", "UPEDBProfile", "T-OLP"):
            continue
        if _MODEL_TOKEN.fullmatch(token):
            return token
    return ""


def _feeder_records(
    data: bytes,
    *,
    machine: str,
    model: str,
    front_is_one: bool,
) -> tuple[list[TolpFeeder], list[str]]:
    """Extract feeder slots from one PCB stream."""
    out: list[TolpFeeder] = []
    warnings: list[str] = []
    seen: set[tuple[str, int, int]] = set()
    for match in re.finditer(re.escape(_FEEDER_MARKER), data):
        start = match.start()
        record = data[start : start + _FEEDER_RECORD_SIZE]
        if len(record) < _PART_OFFSET + 4:
            continue
        if _FEEDER_HEADER not in record[:40]:
            continue
        slot = int.from_bytes(record[_SLOT_OFFSET : _SLOT_OFFSET + 2], "little")
        side_byte = record[_SIDE_OFFSET]
        if not (1 <= slot <= 999) or side_byte not in (1, 2):
            continue
        raw_part = record[_PART_OFFSET : _PART_OFFSET + _PART_MAX].split(b"\x00", 1)[0]
        try:
            part = raw_part.decode("ascii").strip()
        except UnicodeDecodeError:
            continue
        if not part or any(ch < " " for ch in part):
            continue
        side = SIDE_FRONT if (side_byte == 1) == front_is_one else SIDE_REAR
        key = (side, slot, 0)
        if key in seen:
            warnings.append(f"{machine}: duplicate {side} slot {slot} - kept the first")
            continue
        seen.add(key)
        out.append(
            TolpFeeder(machine=machine, model=model, side=side, slot=slot, part=part)
        )
    return out, warnings


def _machine_for_file(
    pcb: Path, machines: Sequence[tuple[str, str]], pcb_files: Sequence[str], root: Path
) -> tuple[str, str]:
    """Resolve ``(machine_name, model)`` for one PCB file."""
    try:
        rel = pcb.relative_to(root)
    except ValueError:
        rel = pcb
    if len(rel.parts) > 1:
        folder_name = rel.parts[0]
    else:
        folder_name = pcb.parent.name if pcb.parent.name not in ("", ".") else ""
    by_name = {name: model for name, model in machines}
    for i, name in enumerate(pcb_files):
        if Path(name).name != pcb.name:
            continue
        if i < len(machines):
            machine, model = machines[i]
            return machine, model
    if folder_name and folder_name in by_name:
        return folder_name, by_name[folder_name]
    if folder_name:
        return folder_name, ""
    return pcb.stem, ""


def _iter_pcb(folder: Path) -> list[Path]:
    files = sorted(
        (p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() == ".pcb"),
        key=lambda p: (p.parent.name.casefold(), p.name.casefold()),
    )
    return files


def _is_part_name(text: str) -> bool:
    if any(text.startswith(prefix) for prefix in _NON_PART_PREFIXES):
        return False
    if not 4 <= len(text) <= 48 or _MFB_PART.fullmatch(text) is None:
        return False
    if not any(ch.isdigit() for ch in text):
        return False
    if not any(ch.isalpha() for ch in text) and "_" not in text:
        return False
    if text.startswith("000"):
        return False
    return text not in {"1692", "1693", "1695", "333333", "ffffff"}


def _mfb_part_names(data: bytes, start: int, end: int) -> list[tuple[int, str]]:
    """Length-prefixed part names in one ``.mfb`` section, in file order."""
    out: list[tuple[int, str]] = []
    i = start
    while i < end - 1:
        length = data[i]
        if 4 <= length <= 48:
            raw = data[i + 1 : i + 1 + length]
            if len(raw) == length and all(32 <= b < 127 for b in raw):
                text = raw.decode("ascii")
                if _is_part_name(text):
                    out.append((i, text))
                    i += 1 + length
                    continue
        i += 1
    return out


def _mfb_width(type_name: str) -> int:
    if not type_name:
        return 1
    match = re.search(r"(\d+)mm", type_name)
    if match:
        return _TAPE_WIDTH.get(int(match.group(1)), 1)
    if type_name.startswith("STF-") or "Tray" in type_name or "Stick" in type_name:
        return _TRAY_WIDTH
    return 1


def _mfb_start_slot(
    data: bytes,
    part_offset: int,
    type_name: str,
) -> int | None:
    """Explicit slot of the first feeder, when its record layout is known."""
    if "8mm" in type_name:
        offset, size = 273, 4
    elif type_name.startswith("STF-") or "Tray" in type_name:
        offset, size = 116, 4
    else:
        return None
    pos = part_offset - offset
    if pos < 0:
        return None
    value = int.from_bytes(data[pos : pos + size], "little")
    return value if 1 <= value <= 999 else None


def _specific_mfb_type(token: bytes) -> bool:
    """A width-bearing type; the bare ``TapeFeeder`` token is a generic marker."""
    text = token.decode("ascii", "ignore")
    return "mm" in text or text.startswith("STF-") or "Tray" in text or "Stick" in text


def _parse_mfb_file(
    path: Path, *, front_is_one: bool
) -> tuple[list[TolpFeeder], dict[str, str], list[str]]:
    """Parse one ``.mfb`` feeder-base file."""
    data = path.read_bytes()
    sections = [
        (m.start(), f"M{m.group(1).decode()}", m.group(2).decode())
        for m in _MFB_SECTION.finditer(data)
    ]
    feeders: list[TolpFeeder] = []
    machines: dict[str, str] = {}
    warnings: list[str] = []
    for index, (start, machine, raw_side) in enumerate(sections):
        end = sections[index + 1][0] if index + 1 < len(sections) else len(data)
        side = SIDE_FRONT if (raw_side == "F") == front_is_one else SIDE_REAR
        parts = _mfb_part_names(data, start, end)
        if not parts:
            continue
        types = list(_MFB_TYPE.finditer(data, start, end))
        rows: list[tuple[int, str, str]] = []
        for part_offset, part in parts:
            before = [t for t in types if t.start() < part_offset]
            specific = [t for t in before if _specific_mfb_type(t.group())]
            chosen = specific[-1] if specific else (before[-1] if before else None)
            type_name = chosen.group().decode("ascii") if chosen is not None else ""
            rows.append((part_offset, part, type_name))
        first_type = rows[0][2]
        slot = _mfb_start_slot(data, rows[0][0], first_type) or 1
        for part_offset, part, type_name in rows:
            if "Camera" in type_name:
                continue
            feeders.append(
                TolpFeeder(machine=machine, model="", side=side, slot=slot, part=part)
            )
            slot += _mfb_width(type_name)
        machines.setdefault(machine, "")
    return feeders, machines, warnings


def _iter_mfb(folder: Path) -> list[Path]:
    return sorted(
        (p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() == ".mfb"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def _load_mfb_export(
    folder: Path,
    *,
    front_is_one: bool,
    machines_eoj: Sequence[tuple[str, str]],
) -> tuple[list[TolpFeeder], dict[str, str], list[str]]:
    """Merge sections from the newest ``.mfb`` file (newest wins per side)."""
    files = _iter_mfb(folder)
    if not files:
        return [], {}, []
    by_name = {name: model for name, model in machines_eoj}
    seen: set[tuple[str, str]] = set()
    feeders: list[TolpFeeder] = []
    machines: dict[str, str] = {}
    warnings: list[str] = []
    for path in files:
        try:
            file_feeders, file_machines, file_warnings = _parse_mfb_file(
                path, front_is_one=front_is_one
            )
        except OSError as exc:
            warnings.append(f"{path.name}: cannot read ({exc})")
            continue
        warnings.extend(file_warnings)
        fresh = [f for f in file_feeders if (f.machine, f.side) not in seen]
        if not fresh:
            continue
        for feeder in fresh:
            feeders.append(
                TolpFeeder(
                    machine=feeder.machine,
                    model=by_name.get(feeder.machine, feeder.model),
                    side=feeder.side,
                    slot=feeder.slot,
                    part=feeder.part,
                )
            )
        for feeder in fresh:
            seen.add((feeder.machine, feeder.side))
        machines.update(file_machines)
    if not feeders:
        warnings.append("no feeder sections found in .mfb files")
    return feeders, machines, warnings


def _parse_pcb_paths(
    pcb_paths: Sequence[Path],
    *,
    folder: Path,
    machines: Sequence[tuple[str, str]],
    pcb_files: Sequence[str],
    front_is_one: bool,
    warnings: list[str],
    version: str,
) -> tuple[list[TolpFeeder], dict[str, str]]:
    feeders: list[TolpFeeder] = []
    machine_models: dict[str, str] = {}
    for pcb in pcb_paths:
        try:
            data = pcb.read_bytes()
        except OSError as exc:
            warnings.append(f"{pcb.name}: cannot read ({exc})")
            continue
        machine, eoj_model = _machine_for_file(pcb, machines, pcb_files, folder)
        model = _pcb_model(data) or eoj_model
        machine_models.setdefault(machine, model)
        records, rec_warnings = _feeder_records(
            data, machine=machine, model=model, front_is_one=front_is_one
        )
        warnings.extend(rec_warnings)
        if not records:
            warnings.append(
                f"{pcb.name}: no feeder records parsed "
                f"(T-OLP version {version or 'unknown'})"
            )
        feeders.extend(records)
    return feeders, machine_models


def _compare_feeder_sets(
    mfb_feeders: Sequence[TolpFeeder], pcb_feeders: Sequence[TolpFeeder]
) -> list[str]:
    """Warn when the two sources disagree on a part they both contain."""
    mfb_map = {(f.machine, f.side, f.part): f.slot for f in mfb_feeders}
    pcb_map = {(f.machine, f.side, f.part): f.slot for f in pcb_feeders}
    common = set(mfb_map) & set(pcb_map)
    diffs = [
        (key, mfb_map[key], pcb_map[key])
        for key in common
        if mfb_map[key] != pcb_map[key]
    ]
    if not diffs:
        return []
    sample = ", ".join(
        f"{machine}/{side} {part}: mfb {slot_a} vs pcb {slot_b}"
        for (machine, side, part), slot_a, slot_b in diffs[:5]
    )
    return [
        f".mfb and .PCB disagree on {len(diffs)} feeder slot(s); using .mfb ({sample})"
    ]


def load_tolp_export(path: str | Path, *, front_is_one: bool = True) -> TolpExport:
    """Parse a T-OLP export folder (or a single ``.mfb`` / ``.eoj`` / ``.PCB``).

    ``.mfb`` (machine feeder base) is the primary source: it names the machine
    and side explicitly and lists the feeders in attachment order, so the slot
    is the physical attachment position (wide feeders consume the following
    positions). ``.PCB`` remains the fallback and a cross-check.

    ``front_is_one`` maps side byte 1 to Front; flip it when the job numbers
    the rear base first.
    """
    raw = Path(path).expanduser()
    if not raw.exists():
        raise TolpExportError(f"Path does not exist: {raw}")
    folder = raw.parent if raw.is_file() else raw
    eoj_files = sorted(folder.glob("*.eoj"))
    if raw.is_file() and raw.suffix.lower() == ".eoj":
        eoj_files = [raw]

    machines: list[tuple[str, str]] = []
    pcb_files: list[str] = []
    warnings: list[str] = []
    version = ""
    for eoj in eoj_files:
        try:
            m, f, v, w = _parse_eoj(eoj)
        except TolpExportError:
            raise
        machines.extend(m)
        for name in f:
            if name not in pcb_files:
                pcb_files.append(name)
        version = version or v
        warnings.extend(w)

    if raw.is_file() and raw.suffix.lower() == ".pcb":
        pcb_paths = [raw]
    else:
        pcb_paths = _iter_pcb(folder)

    mfb_feeders: list[TolpFeeder] = []
    mfb_machines: dict[str, str] = {}
    mfb_warnings: list[str] = []
    if raw.is_file() and raw.suffix.lower() == ".mfb":
        mfb_feeders, mfb_machines, mfb_warnings = _parse_mfb_file(
            raw, front_is_one=front_is_one
        )
    elif not (raw.is_file() and raw.suffix.lower() == ".pcb"):
        mfb_feeders, mfb_machines, mfb_warnings = _load_mfb_export(
            folder, front_is_one=front_is_one, machines_eoj=machines
        )
    warnings.extend(mfb_warnings)

    if mfb_feeders:
        feeders = mfb_feeders
        machine_models = dict(mfb_machines)
        for name, model in machines:
            if name in machine_models and model:
                machine_models[name] = model
        if pcb_paths:
            pcb_feeders, _pcb_machines = _parse_pcb_paths(
                pcb_paths,
                folder=folder,
                machines=machines,
                pcb_files=pcb_files,
                front_is_one=front_is_one,
                warnings=warnings,
                version=version,
            )
            warnings.extend(_compare_feeder_sets(mfb_feeders, pcb_feeders))
        source = "mfb"
    else:
        if not pcb_paths:
            raise TolpExportError(
                f"No .mfb or .PCB machine files found under {folder}. "
                "Export the T-OLP job and pick that folder."
            )
        feeders, machine_models = _parse_pcb_paths(
            pcb_paths,
            folder=folder,
            machines=machines,
            pcb_files=pcb_files,
            front_is_one=front_is_one,
            warnings=warnings,
            version=version,
        )
        source = "pcb"

    feeders.sort(key=lambda f: (f.machine, 0 if f.side == SIDE_FRONT else 1, f.slot))
    return TolpExport(
        folder=folder,
        feeders=tuple(feeders),
        machines=machine_models,
        warnings=tuple(warnings),
        source=source,
    )


def places_for_parts(export: TolpExport, parts: Iterable[str]) -> list[TolpFeeder]:
    """All feeders holding any of ``parts``, deduplicated and sorted."""
    out: list[TolpFeeder] = []
    seen: set[tuple[str, str, int, str]] = set()
    for part in parts:
        for feeder in export.by_part(part):
            key = (feeder.machine, feeder.side, feeder.slot, feeder.part)
            if key in seen:
                continue
            seen.add(key)
            out.append(feeder)
    return out
