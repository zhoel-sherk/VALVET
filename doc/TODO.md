# VALVET roadmap

Desktop-first SMT prep: BOM/PnP on disk, mapping, Clean, cross-check, merge/export, optional PCB Preview / Step 3D / machine libraries. No server required.

**Core vs GUI:** parsers, cleaning, merge, machine-library I/O stay Qt-free (`src/smt_processor.py`, `src/pcb_preview/`, `src/machine_library/`, `src/step_3d/occ_load.py`, `src/services/`). PySide6 orchestrates threads, `QSettings`, and dialogs (`src/app/window.py`, `src/ui/`).

ALPHA **v0.1.3** — [CHANGELOG.md](../CHANGELOG.md), [TESTING.md](info/TESTING.md). Historical Boomer checklists live under `doc/working_on/` and `doc/legacy_artifacts/` if needed; this file is the active list only.

## Now (product vector)

1. **Machine library matching** — Hanwha `PART_Det`/`PARTNAME` is the current shop path (Machine lib tab + Qt-free readers). Next: sanitized fixtures (never commit full `.mdb`), auto-match from Clean+footprint, row status, MRU, optional strict export. **Yamaha** `.Tou` / `DevLibEd*.Lib` second ([yedytor](https://github.com/marmidr/yedytor) for formats/UX ideas, not a UI port).
2. **Real boards** — BOM → PnP → map → Clean → apply → cross-check → merge → Top/Bot (and MMD) on production files; collect OTHER/regex fallbacks; note UX pain (errors, missing project/MRU).
3. **Packaging smoke** — frozen `valvet.spec` on a clean Windows box ([PACKAGING_WINDOWS.md](info/PACKAGING_WINDOWS.md)); app icon / About if still missing in the bundle.

## Backlog (keep; does not fight the vector)

### Session and project

- [ ] Persisted **BOM/PnP pair** (MRU or `.valvet-project.json`). Paths are intentionally not restored today.
- [ ] Clearer import/mapping error messages.

### Clean BOM / parts DB

- [ ] First-class **ferrite bead** (`FERRITE_BEAD` / `FB`; no fall-through to RES/IND from OHM prose).
- [ ] Unresolved-row export (original, cleaned, type, source, bare MPN).
- [ ] Preview filters (source, type, regex-only, OTHER-only).
- [ ] Parser coverage from real BOMs (Murata, Walsin, Yageo, Taiyo, Samsung) + tests per promotion.
- [ ] User Parts DB: bulk import, learn-all OTHER, search/edit/delete, SQLite if `components.txt` outgrows; keep txt as interchange.

### PCB Preview

- [ ] Revisit 2-point Gerber↔PnP align (manual nudge is the shipped path).
- [ ] Focused tests + small Gerber/PnP fixtures for the Qt-free preview core.

### Step 3D (viewer is done)

In-process **pythonocc-core** tessellation + PyVista tree/pick; CLI→OBJ fallback. Optional extras: `requirements-step3d.txt`, `requirements-step3d-occ.txt`.

- [ ] **B:** B-rep measure, sections, solid export (CadQuery/OCC modeling).
- [ ] **C:** refdes highlight vs BOM/PnP; align with PCB Preview.
- [ ] Document or ship a default STEP→OBJ CLI when OCC is unavailable (license is the operator’s).

### Merge / machine export

- [ ] Confirm machine CSV column names; presets per vendor if layouts differ.
- [ ] Bottom-side mirror notes (UI vs filename vs sidecar).
- [ ] Coordinate transforms only when a real machine format needs them.
- [ ] Export profiles after Yamaha/Hanwha matching is stable.

### Architecture (when it unblocks the above)

- [ ] Remaining services: cross-check, merge orchestration, component-library management (not only widgets).
- [ ] Optional CI grep: no `PySide6` in agreed core paths.
- [ ] Finish splitting leftovers out of `window.py` if files keep growing.
- [ ] Compact Clean advanced settings; jump from Clean preview row to BOM row; copy/export selected table rows.
- [ ] Profiling-driven speed (large XLSX/merge/cross-check): `itertuples`/column loops, optional calamine/XlsxWriter/Parquet — **measure first**.
- [ ] CLI on the same services (`clean` / `check` / `merge` / `machine-match`).
- [ ] Web only after services are stable (no prototype in-tree).
- [ ] Remaining hardcoded UI strings → `lang/*.json`.
- [ ] README screenshots of the main tabs.
- [ ] Figma/QML tables stay out of scope; leftover notes: [DESIGN_TODO.md](legacy_artifacts/DESIGN_TODO.md).

## Tests

Do not pin stale pass counts here. Daily/PR: [TESTING.md](info/TESTING.md) (compileall + pytest; Gerber as extra job). After big `pcb_preview` / `step_3d` / `machine_library` changes, compare Windows vs Linux skips.

- [ ] Drop tests that only cover archived UI; add recovery / Replace PNP / layer-dropdown tests where logic is extracted.

## Vocabulary

Component Library, User Parts DB, canonical name, Internal Part Number, Footprint/Package, Feeder Library, Machine Component Library / matching / name, Yamaha `.Tou` / `DevLibEd.Lib`, Hanwha `.mdb`, Pick-and-Place, Top/Bottom, mirror side.
