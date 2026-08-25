# VALVET roadmap

Desktop-first SMT prep: BOM/PnP on disk, mapping, Clean, cross-check, merge/export, optional PCB Preview / Step 3D / machine libraries. No server required.

**Core vs GUI:** parsers, cleaning, merge, machine-library I/O stay Qt-free (`src/smt_processor.py`, `src/pcb_preview/`, `src/machine_library/`, `src/step_3d/occ_load.py`, `src/services/`). PySide6 orchestrates threads, `QSettings`, and dialogs (`src/app/window.py`, `src/ui/`).

ALPHA **v0.2.0** — [TESTING.md](info/TESTING.md). This file is the live backlog only.

**Shipped (one line):** profiles + per-path mapping; Clean/Merge including `.mmd`; PCB Preview Gerber+PnP overlay (nudge, not 2-point auto-align); Step 3D phase A (optional pythonocc + PyVista, CLI fallback, OCC not in core deps / not frozen by default); Machine lib Hanwha WIP; PyInstaller `valvet.spec`.

## Now (product vector)

1. **Machine library matching** — Hanwha `PART_Det`/`PARTNAME` plus Part Group name (`UPDPARTGROUPNAME`, Chip-*). Parent profile (`PARENTPROFILE`) is not the component class. See [hanwha_UPD_mdb_schema.md](info/hanwha_UPD_mdb_schema.md) and [hanwha_mdb_editor.md](info/hanwha_mdb_editor.md). Yamaha `.Tou` / `DevLibEd*.Lib` uses the same matcher ([yedytor notes](info/machine_lib_yedytor_notes.md)).
2. **Real boards** — QA on production files; not a code deliverable.
3. **Packaging smoke** — frozen `valvet.spec` ([PACKAGING_WINDOWS.md](info/PACKAGING_WINDOWS.md)).
4. **README screenshots** — tracked `img/`.

## Parked (not this vector)

- **Step 3D B/C** and a default STEP→OBJ CLI: later. Viewer phase A stays as shipped.
- **User Parts DB / SQLite / learn-all bulk:** far corner; txt + Learn selected is enough.
- **First/Last row in GUI:** removed; do not restore. `read_file(..., first_row, last_row)` remains for tests/API only.
- **CSV column presets / vendor export profiles:** not needed for current machine CSV/XLSX/MMD.
- **2-point Gerber align:** nudge is the shipped path.

## Tests

Do not pin stale pass counts here. Daily/PR: [TESTING.md](info/TESTING.md).

## Vocabulary

Component Library, User Parts DB, canonical name, Internal Part Number, Footprint/Package, Feeder Library, Machine Component Library / matching / name, Yamaha `.Tou` / `DevLibEd.Lib`, Hanwha `.mdb`, Part Group (`UPDPARTGROUPNAME`), parent profile (`PARENTPROFILE`), Pick-and-Place, Top/Bottom, mirror side.
