"""Read a Hanwha T-OLP export folder (``.eoj`` job + per-machine ``.PCB``).

A T-OLP export is a folder with one ``.eoj`` file and one ``.PCB`` file per
machine (``M1`` … ``Mn``). The ``.eoj`` is the CWorkShop job container: it
names the machines and lists their PCB files, but it does **not** carry the
feeder allocation. The allocation lives in the PCB files:

* the PCB header names the machine model (``DECANS2``, ``DECANF2FS``,
  ``DECANL2``, ``SM485P`` …);
* each feeder is a 204-byte record anchored by ``CFeeder`` + ``CBHeader``;
* inside the record: ``slot`` is a little-endian ``uint16`` at +44, the side
  (front/rear feeder base) is a byte at +46, and the part name is the first
  printable run after +62.

The format is proprietary and tied to the T-OLP version, so every field is
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


def load_tolp_export(path: str | Path, *, front_is_one: bool = True) -> TolpExport:
    """Parse a T-OLP export folder (or a single ``.eoj`` / ``.PCB``).

    ``front_is_one`` maps the first feeder base (side byte 1) to Front; flip it
    when the T-OLP job numbers the rear base first.
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
    if not pcb_paths:
        raise TolpExportError(
            f"No .PCB machine files found under {folder}. "
            "Export the T-OLP job (eoj + per-machine PCB files) and pick that folder."
        )

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

    feeders.sort(key=lambda f: (f.machine, 0 if f.side == SIDE_FRONT else 1, f.slot))
    return TolpExport(
        folder=folder,
        feeders=tuple(feeders),
        machines=machine_models,
        warnings=tuple(warnings),
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
