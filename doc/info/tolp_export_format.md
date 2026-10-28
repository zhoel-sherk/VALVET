# T-OLP export format (Scan tab input)

A Hanwha T-OLP job exported for the line is a folder like:

```
C:\PCB\
  TechOne_top_182_Rev0001.eoj      # CWorkShop job container
  TechOne_top_182_Rev0001.zip      # optional archive of the .eoj
  M1\TechOne_top_1.PCB             # machine 1 program
  M2\TechOne_top_2.PCB
  M3\TechOne_top_3.PCB
  M4\TechOne_top_4.PCB
```

Measured on `CWorkShop 17.201.0.2` / `T-OLP`.

## What the `.eoj` holds

- Header: `27 02 00 00`, then length-prefixed strings `CWorkShop`,
  `17.201.0.2`, `T-OLP`.
- One `CMachine` record per machine:
  `CMachine`, `M1`, machine id, three `uint32`, `Chip Mounter`, id, model
  (`DECANS2`, `DECANF2FS`, `DECANL2`, `SM485P`), id.
- At the end, the machine-PCB file list (`TechOne_top_1.PCB` …).
- It contains the part list and placements, but **no feeder slot table** and no
  `IN-…` inventory codes. The feeder allocation lives in the `.PCB` files.

## What a `.PCB` holds

Binary object stream (`CPcb`, `CPCBHeader`, `DECANS2`/`SM485P`, `T-OLP`).
Feeder records are 204-byte objects, anchored by `CFeeder\x00` followed within
40 bytes by `CBHeader`:

| offset | size | field |
| --- | --- | --- |
| 0 | 22 | marker (`CFeeder`, small strings, `CBHeader`) |
| 44 | 2 | slot number, little-endian `uint16` (1…60 per side) |
| 46 | 1 | side/base byte: 1 or 2 (Front/Rear) |
| 60 | 64 | part name, NUL-padded ASCII |
| 124 | 80 | unused (zeros) |

Each machine file contains two feeder bases: one `CFeederBaseSlot` +
`CDeviceTape` section per side, each followed by its `CFeeder` records.
Other sections (`CDeviceStick`, `CDeviceTray`, `CDeviceAnc`) are not feeders.

Parsing rules used by `src/parsers/tolp_export.py`:

- accept a record only when `CFeeder` and `CBHeader` are present;
- require `1 <= slot <= 999` and `side in (1, 2)`;
- decode the part name as ASCII and reject control characters;
- keep the first record when a `(machine, side, slot)` repeats, and warn;
- warn (do not fail) when a file yields no records: a new T-OLP version may
  have changed the layout, and a silent empty list would look like "no parts".

Side byte 1 is shown as **Front** by default; `front_is_one=False`
(`--rear-first` in the probe, the "swap" switch in the Scan tab) maps it to
Rear.

## Probe

```
python tools/tolp_probe.py C:\PCB
python tools/tolp_probe.py C:\PCB --json
```

Golden numbers for the reference export: 207 feeders —
M1 51+9, M2 20+52, M3 44+12, M4 19 (Front+Rear).

## Matching

T-OLP stores the library part name (`0201_10K_1%`, `FH82HM770`), never the 1C
code. The Scan tab chains:

```
scanned IN-…  ->  BOM/Merge row (Custom column)  ->  part name  ->  feeder slots
```

Part comparison collapses whitespace and case, keeps punctuation.
