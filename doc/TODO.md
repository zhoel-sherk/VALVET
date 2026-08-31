# VALVET roadmap

Desktop-first SMT prep: BOM/PnP on disk, mapping, Clean, cross-check, merge/export, optional PCB Preview / Step 3D / machine libraries. No server required.

**Core vs GUI:** parsers, cleaning, merge, machine-library I/O stay Qt-free (`src/smt_processor.py`, `src/pcb_preview/`, `src/machine_library/`, `src/step_3d/occ_load.py`, `src/services/`). PySide6 orchestrates threads, `QSettings`, and dialogs (`src/app/window.py`, `src/ui/`).

ALPHA **v0.2.0** — [TESTING.md](info/TESTING.md). This file is the live backlog only.

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

## Vocabulary

Component Library, User Parts DB, canonical name, Internal Part Number, Footprint/Package, Feeder Library, Machine Component Library / matching / name, Yamaha `.Tou` / `DevLibEd.Lib`, Hanwha `.mdb`, Part Group (`UPDPARTGROUPNAME`), parent profile (`PARENTPROFILE`), Pick-and-Place, Top/Bottom, mirror side.
