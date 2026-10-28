# T-OLP export format (Scan tab input)

A Hanwha T-OLP job exported for the line is a folder with a machine feeder
base (`.mfb`), often together with the job (`.eoj`) and per-machine programs
(`.PCB`):

```
C:\PCB\
  TechOne_top_182_Rev0001.eoj      # CWorkShop job container
  mb_top.mfb                       # machine feeder base (primary for Scan)
  M1\TechOne_top_1.PCB             # machine 1 program (fallback)
  M2\TechOne_top_2.PCB
  ...
```

Measured on `T-OLP V17.201.0.2`.

## `.mfb` — primary source (attachment position)

`CFeederBase` container, serialized with length-prefixed strings. It is split
into sections, one per machine and side:

```
CFeederBase ... M1 ... F ... 60 ... M1 ... R ... M2 ... F ...
```

Each section lists feeders in attachment order; each feeder carries a type
token (`TapeFeeder8mmSME`, `TapeFeeder24mmSME`, `STF-100D` for a pallet/tray
feeder) and a part name (`0201_10K_1%`, `I3_1220P`).

**Slot = attachment position (the T-OLP `No.` column).** A wide feeder consumes
the following positions, so the next part is placed after its width:

| feeder type | positions consumed |
| --- | --- |
| 8 mm | 1 |
| 12 mm | 2 |
| 16 mm | 2 |
| 24 mm | 3 |
| 36 mm | 4 |
| 44 mm | 4 |
| 56 mm | 5 |
| 88 mm | 7 |
| Tray / pallet (`STF-…`) | 2 |

Examples from the reference job:

- M1 Front (all 8 mm): parts at 1, 2, 3, 4, 5, 6, 7 …
- M3 Front: 44 mm at 1, 24 mm at 5, 16 mm at 8, 10, 12, 14, 16, 18 …
- M4 Rear (tray, `I3_1220P` ×6): 1, 3, 5, 7, 9, 11.

The explicit slot field inside an `.mfb` record has a type-dependent offset; the
parser therefore uses the attachment order + the width table above, which was
verified against the T-OLP `FeederBase` screen. When several `.mfb` files are
present, the newest file wins per machine/side (older files only fill sides the
newest does not contain).

## `.eoj` — machine names/models

Header `27 02 00 00`, length-prefixed strings `CWorkShop`, version, `T-OLP`.
One `CMachine` record per machine (`M1`…`M7`) with its model (`DECANS2`,
`DECANF2FS`, `DECANL2`, `SM485P`). It has **no feeder table** and no `IN-…`
inventory codes; it only names machines and lists the `.PCB` files.

## `.PCB` — fallback and cross-check

Binary object stream (`CPcb`, `CPCBHeader`, machine model, `T-OLP`). Feeder
records are 204-byte objects anchored by `CFeeder\x00` + `CBHeader` within 40
bytes:

| offset | size | field |
| --- | --- | --- |
| 44 | 2 | slot, little-endian `uint16` |
| 46 | 1 | side byte: 1 or 2 (Front/Rear) |
| 60 | 64 | part name, NUL-padded ASCII |

Two feeder bases per machine file (`CFeederBaseSlot` + `CDeviceTape` per side).
Parsing rules: require slot `1..999` and side `1|2`, reject control characters,
keep the first duplicate slot with a warning, and warn (not fail) when a file
yields no records — a new T-OLP version may have changed the layout.

When both `.mfb` and `.PCB` are present, the Scan parser uses `.mfb` and logs a
warning if the two disagree on a part they both contain.

## Matching

T-OLP stores the library part name (`0201_10K_1%`, `FH82HM770`), never the 1C
code. The Scan tab chains:

```
scanned IN-…  ->  BOM/Merge row (Custom column)  ->  part name  ->  feeder slots
```

Part comparison collapses whitespace and case, keeps punctuation.

## Probe

```
python tools/tolp_probe.py C:\PCB
python tools/tolp_probe.py examples\tolp_mfb\Techbook_C --json
```

`Source: MFB` means the feeder base was used; `Source: PCB` means the fallback.
