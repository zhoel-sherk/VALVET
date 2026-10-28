"""T-OLP export parser: feeder slots per machine from .eoj + .PCB."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "src")
)

from parsers.tolp_export import (  # noqa: E402
    SIDE_FRONT,
    SIDE_REAR,
    TolpExportError,
    load_tolp_export,
    places_for_parts,
)

_RECORD = 204
_PART_OFFSET = 60


def _lp(text: str) -> bytes:
    raw = text.encode("ascii")
    assert len(raw) < 0xFF
    return bytes([len(raw)]) + raw


def _feeder(slot: int, side: int, part: str) -> bytes:
    """One serialized CFeeder record (layout measured on T-OLP 17.x)."""
    rec = bytearray(_RECORD)
    rec[0:8] = b"CFeeder\x00"
    rec[14:22] = b"CBHeader"
    rec[44:46] = slot.to_bytes(2, "little")
    rec[46] = side
    raw = part.encode("ascii")[:_PART_OFFSET]
    rec[_PART_OFFSET : _PART_OFFSET + len(raw)] = raw
    return bytes(rec)


def _pcb(model: str, feeders: list[tuple[int, int, str]]) -> bytes:
    head = (
        b"CPcb\x00\x00\x00\x00CPCBHeader\x00\x00"
        + model.encode("ascii")
        + b"\x00T-OLP\x00"
    )
    return head + b"".join(_feeder(*f) for f in feeders) + b"\x00" * 32


def _eoj(machines: list[tuple[str, str]], pcb_names: list[str]) -> bytes:
    out = bytearray(b"\x27\x02\x00\x00")
    out += _lp("CWorkShop") + _lp("17.201.0.2") + _lp("T-OLP")
    for name, model in machines:
        out += b"CMachine"
        out += _lp(name) + _lp("0000000005")
        out += b"\x01\x00\x00\x00" * 3
        out += _lp("Chip Mounter") + _lp("0000000005") + _lp(model) + _lp("0000000056")
    for i, pcb in enumerate(pcb_names, start=1):
        out += i.to_bytes(4, "little") + _lp(pcb)
    return bytes(out)


def _make_export(root: Path) -> Path:
    (root / "M1").mkdir(parents=True)
    (root / "M2").mkdir(parents=True)
    (root / "TechOne.eoj").write_bytes(
        _eoj(
            [("M1", "DECANS2"), ("M2", "SM485P")],
            ["TechOne_1.PCB", "TechOne_2.PCB"],
        )
    )
    (root / "M1" / "TechOne_1.PCB").write_bytes(
        _pcb(
            "DECANS2",
            [
                (8, 1, "0201_220_1%"),
                (18, 2, "0201_10K_1%"),
                (18, 2, "duplicate-slot"),
            ],
        )
    )
    (root / "M2" / "TechOne_2.PCB").write_bytes(
        _pcb("SM485P", [(1, 1, "i5_13500HX"), (5, 2, "FH82HM770")])
    )
    return root


def test_parses_machines_models_and_slots(tmp_path: Path) -> None:
    export = load_tolp_export(_make_export(tmp_path / "export"))

    assert export.machines == {"M1": "DECANS2", "M2": "SM485P"}
    assert len(export.feeders) == 4
    assert [(f.machine, f.side, f.slot, f.part) for f in export.feeders] == [
        ("M1", SIDE_FRONT, 8, "0201_220_1%"),
        ("M1", SIDE_REAR, 18, "0201_10K_1%"),
        ("M2", SIDE_FRONT, 1, "i5_13500HX"),
        ("M2", SIDE_REAR, 5, "FH82HM770"),
    ]


def test_duplicate_slot_keeps_first_and_warns(tmp_path: Path) -> None:
    export = load_tolp_export(_make_export(tmp_path / "export"))
    assert "duplicate" not in " ".join(f.part for f in export.feeders)
    assert any("duplicate Rear slot 18" in w for w in export.warnings)


def test_by_part_is_case_and_space_insensitive(tmp_path: Path) -> None:
    export = load_tolp_export(_make_export(tmp_path / "export"))
    assert export.by_part(" 0201_10k_1% ") == export.by_part("0201_10K_1%")
    assert [f.slot for f in export.by_part("0201_10K_1%")] == [18]


def test_front_rear_can_be_swapped(tmp_path: Path) -> None:
    export = load_tolp_export(_make_export(tmp_path / "export"), front_is_one=False)
    sides = {(f.machine, f.slot): f.side for f in export.feeders}
    assert sides[("M1", 8)] == SIDE_REAR
    assert sides[("M1", 18)] == SIDE_FRONT


def test_places_for_parts_deduplicates(tmp_path: Path) -> None:
    export = load_tolp_export(_make_export(tmp_path / "export"))
    places = places_for_parts(export, ["0201_10K_1%", "0201_10k_1%", ""])
    assert [(p.machine, p.side, p.slot) for p in places] == [("M1", "Rear", 18)]


def test_single_pcb_file_parses_without_eoj(tmp_path: Path) -> None:
    folder = _make_export(tmp_path / "export")
    export = load_tolp_export(folder / "M1" / "TechOne_1.PCB")
    assert export.machines == {"M1": "DECANS2"}
    assert len(export.feeders) == 2


def test_missing_path_raises() -> None:
    with pytest.raises(TolpExportError):
        load_tolp_export("C:/definitely/not/a/tolp/export")


def test_folder_without_pcb_raises(tmp_path: Path) -> None:
    (tmp_path / "empty").mkdir()
    (tmp_path / "empty" / "job.eoj").write_bytes(_eoj([("M1", "DECANS2")], ["x.PCB"]))
    with pytest.raises(TolpExportError, match="No \\.mfb or \\.PCB"):
        load_tolp_export(tmp_path / "empty")


def test_garbage_pcb_warns_instead_of_guessing(tmp_path: Path) -> None:
    folder = tmp_path / "bad"
    folder.mkdir()
    (folder / "M1").mkdir()
    (folder / "M1" / "x.PCB").write_bytes(b"not a tolP file")
    export = load_tolp_export(folder)
    assert export.feeders == ()
    assert any("no feeder records" in w for w in export.warnings)


def test_header_only_pcb_is_not_a_feeder(tmp_path: Path) -> None:
    folder = tmp_path / "hdr"
    folder.mkdir()
    (folder / "M1").mkdir()
    # "CFeeder" without the CBHeader anchor must be ignored.
    (folder / "M1" / "x.PCB").write_bytes(b"CFeeder\x00" + b"\x00" * 300)
    export = load_tolp_export(folder)
    assert export.feeders == ()
