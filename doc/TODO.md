# VALVET roadmap

Desktop-first SMT prep: BOM/PnP on disk, mapping, Clean, cross-check, merge/export, optional PCB Preview / Step 3D / machine libraries. No server required.

**Core vs GUI:** parsers, cleaning, merge, machine-library I/O stay Qt-free (`src/smt_processor.py`, `src/pcb_preview/`, `src/machine_library/`, `src/step_3d/occ_load.py`, `src/services/`). PySide6 orchestrates threads, `QSettings`, and dialogs (`src/app/window.py`, `src/ui/`).

BETA **0.5.2.0** — [TESTING.md](info/TESTING.md). This file is the live backlog only.

**Shipped (one line):** profiles + per-path mapping; Clean/Merge including `.mmd`; PCB Preview Gerber+PnP overlay (nudge, not 2-point auto-align); Step 3D optional (default off); Machine lib Hanwha + Wave 1 footprint preview from UPD vision tables (SQLite cache after Open); PyInstaller `valvet.spec`.

## Now (product vector)

1. **Wave 1 — Machine Lib footprint preview** — validate Hanwha UPD geometry in the right-hand pane ([MACHINE_LIB_FOOTPRINT_PREVIEW.md](info/MACHINE_LIB_FOOTPRINT_PREVIEW.md), [UPD_MDB_Footprint_Geometry_Report.md](info/UPD_MDB_Footprint_Geometry_Report.md)).
2. **Machine library matching** — Hanwha `PART_Det`/`PARTNAME` plus Part Group name (`UPDPARTGROUPNAME`, Chip-*). Parent profile (`PARENTPROFILE`) is not the component class. See [hanwha_UPD_mdb_schema.md](info/hanwha_UPD_mdb_schema.md) and [hanwha_mdb_editor.md](info/hanwha_mdb_editor.md). Yamaha `.Tou` / `DevLibEd*.Lib` uses the same matcher ([yedytor notes](info/machine_lib_yedytor_notes.md)).
3. **Real boards** — QA on production files; not a code deliverable.
4. **Packaging smoke** — frozen `valvet.spec` ([PACKAGING_WINDOWS.md](info/PACKAGING_WINDOWS.md)).

## Parked (not this vector)

- **Wave 2 — Hanwha footprints in PCB Preview** — `FootprintStore` MDB import, overlay lookup, QGraphicsView instancing/LOD. Start only after Wave 1 visual OK.
- **Step 3D B/C** and a default STEP→OBJ CLI: later. Tab is **off by default** (`experimental/enable_step_3d=false`). Do not expand freeze for VTK/pythonocc.
- **User Parts DB / SQLite / learn-all bulk:** far corner; txt + Learn selected is enough.
- **First/Last row in GUI:** removed; do not restore. `read_file(..., first_row, last_row)` remains for tests/API only.
- **CSV column presets / vendor export profiles:** not needed for current machine CSV/XLSX/MMD.
- **2-point Gerber align:** nudge is the shipped path.
- **Apply package table** — DATA · Package → mapped PnP/Merge Footprint column → PCB Preview overlay by `vspd_id` (catalog is isolated; Apply is a stub). See [VSPD.md](info/VSPD.md).

## Tests

Do not pin stale pass counts here. Daily/PR: [TESTING.md](info/TESTING.md).

### Tighten `test_datasheet_sample_row` to strict equality

`tests/test_parser_generated.py` asserts `out == expected or expected in out`.
The substring fallback makes the whole datasheet sample set a weak gate: every
`expected` is a prefix of the cleaned string, so a codec that appends a **bogus**
token still passes. It hid a real defect — `WR08X000PTL` emitted
`0805_0R_5%` with an invented 5% while the datasheet says `0805_0R`, and the row
passed because `"0805_0R" in "0805_0R_5%"`.

Replace the containment branch with `==` and re-run the whole
`datasheet/*.md` corpus; expect a batch of latent over-emissions to surface (each
is a codec inventing a spec the part number never states, the same shape as the
`WR` jumper). The `regex` path already uses `==`, so this only concerns the
`vendor` path. Tracked separately because the fallout is wide and each hit needs
a judgement call — emit the field, drop the field, or fix the codec.

### Samsung land-grid size codes have no repo vocabulary entry

`samsung_capacitor` registers `L6`=0610, `01`=0816, `19`=1209 and `L5`=0510
under the code `Samsung_MLCC_2512.pdf` p.6 prints, so `clean` keeps returning a
value rather than refusing the part. The size is real but not yet a footprint:
`src/parsers/constants.py` knows 01005/0201/0402/0603/0805/1206/1210/1812/2010/2512
and nothing here. Decide whether these get proper names and land patterns, or
stay sheet-codes.

`samsung_automative_mlcc.pdf` is also unparsed — it is a third Samsung document
whose part-number tables have not been transcribed, so the two catalogues in
`datasheet/samsung_capacitor.md` are not yet confirmed to cover it.

### Resistors accept a two-digit `R` fraction; capacitors refuse it

`decode_ohms_suffix` collapses a trailing zero, so `4R7` and `4R70` both clean to
`4.7R` — a chip-resistor sheet prints those trailing zeros, so they are one part
and `1R00` → `1R`.

Every capacitor codec here uses `^(\d)R(\d)$`, so `1R00`, `0R50` and `1R05` are
refused. That is currently deliberate rather than accidental: no capacitor sheet
in `doc/info` prints a two-digit fraction, only the `dRd` form the datasheets
document (`1R5` = 1.5 pF). Pinned in
`tests/test_pn_vendor_kyocera_tdk.py::test_multi_digit_r_decimal_is_refused`.

If a real BOM part ever turns up in that form, the fix belongs in a shared
capacitance decoder (currently each codec open-codes the same two lines) rather
than in three separate regexes.

## Vocabulary

Component Library, User Parts DB, canonical name, Internal Part Number, Footprint/Package, Feeder Library, Machine Component Library / matching / name, Yamaha `.Tou` / `DevLibEd.Lib`, Hanwha `.mdb`, Part Group (`UPDPARTGROUPNAME`), parent profile (`PARENTPROFILE`), Pick-and-Place, Top/Bottom, mirror side.
