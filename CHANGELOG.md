# Changelog

Notable changes to VALVET. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.5.1.2] — BETA - 2026-10-07

Fixes found by checking the part-number codecs against manufacturer datasheets,
plus release-pipeline hardening.

### Added

- **Ralec had no codec at all.** Every Ralec part number in a BOM fell through the
  vendor phase untouched. The "SMD Resistor Components" catalogue 2022 prints an
  `Explanation Of Part Numbers` section for 69 series — 23 of them chip resistors —
  each giving an example part number plus its own size, resistance, tolerance,
  packing and extra-field tables; product specification `IE-SP-010` covers RTT in
  full. The new codec covers the chip family: `prefix | size | resistance |
  [extra] | tolerance | packing`.

  Each prefix keeps its **own** table rather than sharing one, because the same six
  characters mean different sizes depending on the series — `RTW06100JTP` is 0612
  (wide-terminal) while `RTT06100JTH` is 1206. Ralec's size codes are its own and
  are *not* the inch codes: `02` is 0402 and `06` is 1206, where the usual inch
  reading would make 06 = 0603. Per-series patterns also remove a real ambiguity:
  with a free-form size group, `RAG061000FTP` splits as size `061` + resistance
  `000` — a jumper in a size that does not exist — instead of `06` + `1000`.

  Two series are deliberately refused. `RHW` prints two conflicting size tables
  under one prefix (page 62 gives `06`=1206, page 64 gives `06`=0612) and the part
  number cannot say which product it is, so it falls through rather than guessing.
  Resistor arrays (`RAA`, `RTA`, `RSA`, `FTA`, `RTN`) and the metal-alloy low-ohm
  and shunt families (`LR`, `LRE`, `LRH`, `LRS`) are different structures and are
  not implemented; the `LR` family uses *true inch* sizes where its `06` means
  0603, the opposite of the chip series, so merging the tables would attach the
  wrong size. Both gaps are recorded in the module and in `datasheet/ralec_resistor.md`.

- **Viking Tech was unhandled.** A new codec covers the `ARG` thin-film series,
  including the TCR field and the `4R70` sub-ohm spelling, from the manufacturer's
  `Thin Film Chip Resistor (ARG Series)` sheet.

### Fixed

- **Two vendor codecs decoded values the datasheets do not support.** Verified
  against manufacturer catalogues instead of distributor listings. Murata's GRM
  voltage field is two characters wide, and the pair after the temperature code
  *is* that field; the R7x pattern consumed the leading digit as part of the
  series and looked the bare letter up in a legacy one-character table, so
  `GRM155R71C104KA88D` reported 6.3 V instead of 16 V, `GRM155R71J104KA01D`
  reported 100 V instead of 63 V, `GRM188R60J106MA73D` reported 100 V instead of
  6.3 V, and `GRM188R62D106MA73D` reported 10 V instead of 200 V. Codes starting
  with `0` or `3` never matched at all, and `3B` (1.25 kV) was missing from the
  table. Understating a voltage is the dangerous direction. Royal Ohm / UniOhm
  turned out to be two *brands of one manufacturer* (Uniroyal Electronics
  Global Co., Ltd.), so both codecs mirror the same 14-code datasheet; power and
  tolerance are independent fields there, which made D=±0.5% and G=±2%
  unreachable and the two codecs disagree on the same part number. That
  datasheet also lists `M`/`N`/`P` as 10⁻⁴/10⁻⁵/10⁻⁶ power-of-ten codes; without
  them such parts fell through to the 3-digit rule, decoded up to 10⁶ times too
  high and lost their tolerance - a 0.01 Ω shunt read as 10 Ω. The Murata
  codec's own docstring had documented the correct 16 V while the code returned
  6.3 V, and a `## samples` row pinned the wrong value, so
  `tests/test_parser_generated.py` was asserting the defect.

- **Clean BOM split a joined comment with a hardcoded separator.** The Clean
  options let you choose how PN columns are joined (`clean/double_comment_sep`),
  but five call sites split the joined cell back apart with a hardcoded
  `" | "`. With a non-default separator nothing was split, so the regex phase
  parsed the joined text and read the resistance out of the description. Joined
  with a space this turned `RES_100K… 0402WGF1004TCE` into `0402_100K_1%`
  instead of `0402_1M_1%`. `CleanConfig` now carries `double_comment_separator`
  and every split uses it; an unset separator resolves to the same default the
  join uses, so the two agree by construction. `import_bom_comments_for_clean`
  logs a warning when the chosen separator occurs inside a comment cell, making
  separators such as `"2"` (which appears inside `25V`) visible instead of
  silently corrupting the result.
- **Clean BOM inverted description and MPN when the columns were written
  backwards.** A joined cell was split positionally: first segment = prose,
  last segment = MPN. Joining the columns the other way round (`MPN |
  description`) fed the MPN to the classifier as if it were prose, so anchored
  rules such as `^RES[_ ]` missed and a reversed order collapsed vendor matches
  from 180 to 0 and RESISTOR classifications from 125 to 9. Role detection now
  examines the segments: a segment is treated as the MPN when it is shaped like
  a part number and is the only such segment in the first position; otherwise
  the positional rule is kept, so a normal `description | MPN` row is unchanged.
  For rows whose type has no decoder, the part number is used instead of the
  description, preventing fragments such as `H3.2` or `AL6063-T5_PAD` from
  leaking into `Cleaned`. The arbiter and legacy regex paths now both read the
  prose segment, so the two pipelines no longer disagree.
- **Royal Ohm / Uniohm 3-digit resistance values with a trailing `K` were off by
  a factor of ten.** The datasheet uses `J`/`K`/`L` as decimal multipliers
  (`J` = ×0.1, `K` = ×0.01, `L` = ×0.001) for the 3-digit value field, but the
  parser always divided by 10. `0402WGF330KTCE` is 3.3 Ω, not 33 Ω;
  `0402WGF511KTCE` is 5.11 Ω, not 51.1 Ω; `0603WAF220KT5E` is 2.2 Ω, not 22 Ω.
  Verified against the Royal Ohm thick-film chip resistor ordering guide and
  against LCSC product data.
- **Walsin MLCC 3-digit voltage codes were decoded as ÷10 instead of
  mantissa-exponent.** Codes such as `202` mean `20 × 10²` = 2000 V, `201` =
  200 V and `302` = 3000 V, matching the EIA-style capacitance convention used
  in the Walsin MLCC "How to order" tables. The parser now applies `XY × 10^Z`
  for 3-digit voltage codes while keeping direct values for two-digit codes.
  Sizes `1808` and `1812` were also added to the Walsin size table so
  high-voltage B-line parts are accepted.

- **Five of the eight Walsin MLCC dielectrics could not be parsed at all.** The
  product catalogue gives one ordering scheme for the whole range — `0805 B 104 K
  500 C T` — with eight dielectric letters, but the codec carried seven patterns,
  one per part-number shape seen in the wild, and reached only `N`, `B` and `X`.
  `G` (X8G), `R` (X8R), `A` (X7S), `S` (X6S) and `F` (Y5V) parts returned nothing,
  so X8G and X8R stock was reported as unparsed. The absolute class-1 tolerances
  `A`/`B`/`C`/`D` and the asymmetric `Z` were absent from the table entirely, so a
  part could decode "successfully" while silently losing ±0.05 pF…±0.5 pF. The
  `0612` low-inductance size was missing. The codec is now the single documented
  scheme with all eight dielectrics, all ten tolerances and the catalogue's full
  voltage list (`402`=4 kV, `502`=5 kV, `602`=6 kV).

- **The Walsin MLCC codec was decoding Fenghua's part numbers.** It had a `CG`
  branch, but `CG` is not a Walsin code — it is Fenghua's class-1 spelling, while
  Walsin's own class-1 letter is `N`. That branch is gone. Separately, the `N` line
  never read the dielectric at all, so a part whose letter already said NP0 cleaned
  to a string indistinguishable from one carrying no dielectric information; it now
  emits `C0G`, which is why the `0402N100J500CT` sample rows changed. A permissive
  `[A-Z]{2}` tail had also started accepting non-Walsin endings such as `…6R3PT`;
  the tail is now the catalogue's own `L`/`C` termination with `T`/`Q`/`G` reel.

- **The Walsin WW pattern had no group for the type code, so it matched almost
  nothing.** Each approval sheet prints a `CATALOGUE NUMBERS` breakdown —
  `WW25 | N | R005 | J | T | L` — but the regex had no field for the letter, so it
  only matched the older `WW06RR005JT` shape: of the 13 real part numbers in the
  sheets, 2 parsed. The two digits are also a **series number, not the size**, and
  the mapping is not monotonic — the sheets give `WW10`=1210 while `WW12`=1206 — so
  `10` had to be added as 1210 rather than derived from the digits. `WW12` is
  deliberately **not** decoded: `WW12R.PDF` states `WW12: 0603` while `WW12R_V.PDF`
  states `WW12: 1206`, and the sheets contradict each other, so the part falls
  through instead of being given a guessed imperial size.

- **Darfon reported an oversized package for every `C0603` part.** The size field
  is L × W in units of 0.1 mm, so `0603` is a 0.6 × 0.3 mm body — EIA **0201** —
  while `1608` is a 1.6 × 0.8 mm body, EIA 0603. The catalogue's Ordering Code
  block lists all nine pairs in one run: `0402(01005) 0603(0201) 1005(0402)
  1608(0603) 2012(0805) 3216(1206) 3225(1210) 4520(1808) 4532(1812)`, and three
  more places agree (paper-tape column head `PRODUCT SIZE CODE C0603(0201)`, the
  series heading `C0603NP0 Series (EIA0201)`, and the 0201 tape pocket cannot
  physically take a 1.6 × 0.8 mm body). The size table was missing the two
  smallest pairs, and a fallback then treated the EIA column as if it were a size
  field, so `C0603…` came out as 0603 — a ~2.7× oversize package — on 293 part
  numbers in the catalogue. All nine pairs now resolve as printed and only the
  metric spelling is accepted. Cleaned output for `C0603` parts changes from
  `0603_…` to `0201_…`, so the `darfon_capacitor.md` sample rows move with it.

- **Darfon parsed none of the 632 part numbers in its own catalogue.** The codec
  was written against shapes that do not appear in the manufacturer's catalogue;
  measured against the 632 real part numbers, 0 matched. Rewritten against the
  Rev.202510 catalogue it now decodes 632/632, with the 17 letter voltage codes
  and both metric and EIA size forms the catalogue actually prints.

- **TCC's capacitor codec could not be verified at all.** The only document
  available is a "SPECIFICATION FOR APPROVAL" template from Chaozhou Three-Circle
  with image-only tables and no part-number section, so there is nothing to check
  the pattern against. Rather than guess a rewrite, the codec is **frozen** and its
  docstring now carries an explicit `UNVERIFIED` warning; its voltage convention is
  currently assumed to be V/10 and that assumption is recorded as unverified.

- **Fenghua's voltage field was read as V/10 but is EIA mantissa-exponent.** `101`
  means 100 V and `202` means 2 kV there, not 10.1 V and 20.2 V. The `X`/X5R branch
  was missing entirely, COG, R-decimal capacitances, absolute tolerances and the `S`
  code were all unreachable. The packaging pairs (ST/NT/SB/NB) are now enumerated
  explicitly so the pattern cannot claim Walsin `CT` parts.

- **Eyang and Viiyong dielectrics and tolerances were unreachable.** Eyang gained
  X7T/X7S/X6T and the `L`/`N` tolerances; Viiyong's pattern *required* the sequence
  `N…T`, so the manufacturer's own `NCT` and `NAT` examples in its datasheet did
  not match the datasheet they came from.
- **`tools/version.py sync` never updated `doc/TODO.md`.** The rewrite pattern
  required a `v` before the number (`BETA **v0.5.1.1**`) while the file has never
  carried one (`BETA **0.5.1.1**`), so the pattern matched nothing and `sync`
  reported success. It reports the file as untouched while leaving the stale
  number in place, so the one-entry-point guarantee held only because the drift
  happened not to matter. The `v` is now optional.
- **`winget/README.md` was outside the version check entirely.** The same file
  is the one that previously advertised `0.5.0` while the app reported `0.5.1`,
  and `STALE_FILES` still did not list it, so it drifted again unnoticed. It is
  now checked and rewritten. The rewrite is deliberately not a blanket literal
  swap: the file also carries `0.2.0` (the newest published package folder) and
  `ManifestVersion: 1.12.0` (the winget manifest schema), neither of which is
  this project's version, so only the two hand-written mentions are rewritten and
  both foreign literals are allow-listed.

#


## [0.5.1.1] — BETA - 2026-10-06

Audit release: the version now has one source of truth, the release zip no
longer ships user data, and the part-number parsers were re-checked against the
real TechOne 27 (CO1271) order and against vendor datasheets.

### Added

- **`src/__version__.py` is the single source of truth for the version.** The
  number lived in nine places and had already drifted: `winget/README.md`
  advertised `0.5.0` while the app reported `0.5.1`, and the window title
  carried its own copy in all six locale catalogs. The file holds
  `__version__ = "0.5.1.1"` plus an `X.Y.Z.B` validator and `bump(part)`,
  which increments the requested component and resets every lower one
  (`bump("Y", "0.5.1.1")` → `0.6.0.0`). `APP_VERSION` re-exports it, the app
  sets it on `QApplication`, and `app.window_title` is now a
  `"{version}"` placeholder substituted at runtime with a fallback to a plain
  title if a catalog is missing.
- **`tools/version.py`** with `show` / `check` / `bump` / `sync`, importable
  as both `python -m tools.version` and `python tools/version.py`, stdlib-only
  at import time so CI can run it before installing dependencies. `check`
  fails the build when a tracked file still hardcodes a stale version; `sync`
  rewrites the derived copies (both READMEs, `doc/TODO.md`, the workflow
  default). CI runs the check before pytest.
- **Vendor datasheet sample coverage.** Eleven vendors had exactly one sample
  line each, which meant a single shadowed parser would silently lose all
  coverage without any test failing. Forty verified rows were added across ten
  `datasheet/*.md` files; every row is executed by `tests/test_parser_generated.py`,
  so they are assertions rather than documentation.
- **Tests for `pcb_preview/footprint_db.py` and `footprint_heuristic.py`.**
  These 175 lines of pure silhouette logic had no references from the test
  suite at all, and a break there corrupts the rendered PCB outline instead of
  raising. 57 tests now cover key normalisation, all three alias separators,
  mtime cache invalidation, schema idempotence and the centered body geometry.

### Fixed

- **Fixed-width placement files were split on whitespace, corrupting the
  `Layer` column.** `place_txt-Body_Center.txt` is fixed-width (75 characters)
  with the `Layer` column empty on every top-side row, so `str.split()` collapsed
  it there and `Footprint` landed in the `Layer` slot while `Layer` moved one
  place right. The padded frame still came out `2382 × 6`, which is why nothing
  looked wrong: measured on the real file, 2326 rows split into 5 tokens and 56
  into 6, and the `Layer` column contained footprints such as `LQFP48_P5`
  instead of side markers. `smt_processor` now detects the layout and reads it
  positionally, using character ranges no token ever touches — start-offset
  clustering is defeated by right-aligned numbers — and the detection declines
  to whitespace splitting unless slicing reproduces every row's tokens exactly
  (0 mismatches over all 2382 rows).
- **"Not in the BOM" was treated as DNP.** `merge_bom_pnp` dropped any
  placement absent from the BOM under the same condition as a marked DNP part,
  with no message, so all 56 bottom-side placements disappeared silently — the
  bottom side is missing from `bom.xlsx` entirely (confirmed against the
  `ASS-BOT` assembly PDF and against all 17 workbooks in the order folder, so
  this is a supplier data gap, not a wrong-file import). The two reasons are now
  counted apart and exposed as `last_merge_not_in_bom_refs` /
  `last_merge_dnp_refs`, warned about in the log, and reported in the Merge tab
  with the count and the first references. Output rows are unchanged.
- **Samsung CL capacitors read their voltage and tolerance from the wrong
  positions.** Voltage came from the index holding the tolerance letter and
  tolerance from the index holding the thickness digit, so depending on the part
  one or both were wrong. Five of the fourteen real parts were affected — for
  example `CL05A105KA5NQNC` reported `1uF_10V_20%` where the BOM states
  `1uF_X5R_25V_±10%`, and `CL10A226MO7JZNC` lost the tolerance entirely. All
  fourteen are now pinned against the description column of the BOM, which is
  authoritative over the module docstring.
- **Nine `TCC0402*` capacitors had no parser at all.** They were classified
  correctly as capacitors but fell through to the generic regex phase with
  `source=regex` and a byte-identical output, i.e. a capacitor delivered with
  no value. New `src/pn_original/tcc_capacitor.py`, accepting both the `C0G`
  and `COG` spellings the real data uses.
- **Walsin sub-10 pF capacitors were never attempted.** `0402CG0R5C500NT`,
  `0402CG5R6C500NT` and `0402CG8R2C500NT` classified as `OTHER`, so the vendor
  step never ran: the value is written as an `R`-decimal (`0R5`) below 10 pF
  and as a 3-digit EIA code above it. The classifier and the Walsin parser now
  accept both.
- **Walsin `NT` tape suffix and Murata `R6Y` series did not parse.** Three
  Walsin patterns required a literal `CT$` and missed `NT`, and Murata's `R6`
  group required a digit, so the `R6Y` series was unreachable. `R6Y` is a real
  35 V X5R line: `GRM188R6YA106MA73D` is now `0603_10uF_35V_X5R_20%`, verified
  against Murata datasheet C02E21 (`YA` = DC35V) and against LCSC C194427.
  The two-character rated-voltage table from that datasheet is now mirrored
  verbatim (24 codes, asserted exactly in a test), which is why `YA` cannot be
  expressed in a one-character map at all. Existing `CT`, `R60` and `R61`
  values are unchanged.
- **A vendor parser crash silently let another vendor win.** The per-module
  `except Exception -> return None` handlers in four vendors made a raise
  indistinguishable from "not my format", so the arbiter's registry-level
  logging could not see it. The handlers were dead weight (every path already
  returned `None` explicitly) and are gone; a raise now logs with a traceback
  naming the vendor.
- **The Clean preview score tint was unreadable in the dark theme.** The green
  fill is hardcoded light while the text kept the theme colour, giving roughly
  1.05:1 contrast. Foreground is now derived from the fill's own WCAG relative
  luminance, paired with the fill through a shared helper so the two cannot
  drift; minimum contrast across a full 0–100 sweep is 12.17. The amber row
  highlight had the same defect and is fixed the same way (5.93:1 and 7.07:1).
- **`_check_overlapping` reported every pair twice.** The dedup bookkeeping was
  inverted, so the reverse iteration never saw the pair it was checking: three
  unique pairs produced six records. Rewritten as a single pass with a set of
  normalised pairs, which also removes the O(n³) shape. The repro now yields
  exactly three records.
- **File logging could crash startup and leaked user paths.** Creating the log
  directory without `exist_ok` and without an `OSError` guard raised inside
  `MainWindow.__init__` on a read-only install; `delay=True` now defers file
  creation, handlers are closed rather than merely detached (Windows was left
  holding the dated log), configuration targets the root logger with the right
  `stacklevel` so `pathname`/`lineno` point at the real caller, and the session
  log wraps its write in `try/except OSError`.
- **Absolute paths and customer BOM comments were written to a log that ships
  inside the release zip.** `ui/files.py` and `ui/clean_tab.py` logged
  `os.path.abspath()` of the loaded files and echoed component comment text;
  both now log only the file name, and comment text became
  `sample row N: N char(s) imported`. The `clean_alerts` missing-token log is
  behind an env flag and records lengths instead of component text.
- **`logger.error(str(e))` inside `except` discarded the traceback** at ten
  sites across `app/`, `step_3d/`, `pcb_preview` and `machine_library_tab`;
  converted to `logger.exception()` with a structural test so it cannot
  regress.
- **Silent fallbacks that hid real failures.** Rows dropped by
  `on_bad_lines="skip"` are now counted and warned about; the dead `latin-1`
  branch (which cannot raise `UnicodeDecodeError`) is replaced by ordered trial
  decoding that handles real `cp932`/`gb18030` vendor exports; `_read_excel`'s
  CSV fallback validates its shape instead of returning a garbage frame; a
  `Y=0` coordinate is no longer treated as missing and `(0, 0)` is no longer
  excluded from duplicate detection; `registry.ensure_discovered` only marks
  done on success; `hanwha_sqlite_cache` returns `None` rather than an empty
  frame; `part_enriched` no longer increments its merge count when the merge
  failed.
- **A truncated working-copy snapshot escaped as an unhandled exception**
  because `load_snapshot` raised `JSONDecodeError`, which `find_snapshot`'s
  `except SnapshotLoadError` cannot catch. Also guarded the sort key against
  a non-string `saved_at`.
- **`str(x or "")` collapsed legitimate zeros and turned `NaN` into `"nan"`**;
  the Hanwha/Yamaha cell reads now go through the shared cell helper.
- **Layer edits bypassed the command layer** in `ui/files.py`, losing the dirty
  flag and autosave; they now go through the bulk-edit path.
- **`footprint_heuristic` picked the wrong imperial code.** Codes were matched
  in table order rather than by position, so a name containing two sizes
  resolved to whichever came first in the dictionary — and `C_1210_2010`
  resolved to `0201`, a code that only exists as the four characters straddling
  the boundary between the two real codes, drawing a 0.6 × 0.3 mm body for a
  1210 part. It now picks the earliest position, ties broken by longest, which
  matches the imperial-first convention of KiCad names (`C_0402_1005Metric`).

### Changed

- **The release workflow zips before the smoke test.** A frozen run creates
  `dist/VALVET/logs/`, which the zip built afterwards would capture — shipping
  the user's absolute paths. The workflow now builds the archive first, fails
  if it contains `VALVET/logs/`, and smoke-tests the unpacked zip instead of
  `dist/`, so the test exercises exactly what a user unpacks. The release
  version comes from `src/__version__.py`; the `workflow_dispatch` input is
  optional and validated, never authoritative.
- **Coverage now includes `src/ui/*`.** It was in the omit list, hiding roughly
  30% of the codebase — including the largest file in `src/`. There is no
  `fail_under` threshold, so this only makes the gap visible; suite total is
  71% of 20911 statements. The Gerber tests were excluded from the coverage
  step as well and are included now, since they are the only thing that
  exercises that pipeline.
- **Vulture is blocking.** It ran with `continue-on-error`, so dead code could
  accumulate freely; it now gates CI.
- **`qapp`, `import_parsers` and `corpus_cfg` moved to `tests/conftest.py`.**
  The first was a byte-identical private helper in sixteen files.

### Notes

- **Versioning.** `X.Y.Z.B`: `X` is the release line, `Y` a large feature, `Z`
  a smaller feature, `B` a bugfix; increasing a component resets everything
  below it.
- **Winget is deliberately out of scope for this release** and will be
  updated in a separate step after the release is published and manually
  tested, because `InstallerSha256` cannot be computed until the zip exists.
- Vendor codes were verified against Murata datasheet **C02E21**, Samsung
  **MLCC 2512** (53 pages), Yageo **UPY-AC / UPY-GPHC / PYU-RC**, Walsin
  **MLCC** (44 pages) and **WR12**. These are copyrighted manufacturer
  documents, excluded by `.gitignore`; `datasheet/*.md` states the decoding
  rules and cites the catalogue by name rather than by path.
- One pre-existing Qt timing test (`test_hanwha_sqlite_import_thread_missing_mdb`)
  flakes under full-suite load and passes in isolation; it is not covered by
  this work.

## [0.5.1] — BETA - 2026-10-04

### Added

- **Highlight in the BOM tab** — a `Highlight` checkbox and a token field in the
  left rail. Every row whose any column contains one of the words (e.g. `DIP
  THT`) is tinted amber; the match count is written to the debug console.
  Matching is case-insensitive substring across all columns, which is what
  through-hole parts need: vendors write `DIP` inside descriptions such as
  `SCAP_100uF_PL_25V_±20%_ESR:35mOhm_red_6.3*5_DIP_2`, never as a standalone
  cell. Highlight is visual only — nothing is filtered, hidden or removed.
  Tokens and the on/off state are stored per file alongside the separator.
  Tokens shorter than two characters are ignored, since a single letter would
  match nearly every row.
- **Worksheet picker on the BOM and PnP tabs** — a `Sheet:` combo next to the
  delimiter, listing every sheet with hidden ones marked `(hidden)`. `"(auto)"`
  (the default) keeps the first-visible-sheet behaviour; any other entry pins a
  specific sheet. The chosen sheet and its row count are shown under the combo.
- `smt_processor.list_sheets(path)` returns sheet names with a visibility flag,
  and `smt_processor.default_sheet_name(sheets)` resolves the first visible sheet
  (falling back to the first sheet when all are hidden).

### Fixed

- **Uniohm / Royal Ohm chip resistors reported the wrong tolerance.** The letter
  after the resistance value was read through the IEC tolerance map (`J`→±5%,
  `K`→±10%), but the manufacturer numbering gives tolerance its **own**
  one-character field (`D`=±0.5%, `F`=±1%, `G`=±2%, `J`=±5%), alongside a
  separate wattage field (`WG`=1/16W, `WA`=1/10W, …). `WGF`/`WGJ`/`WAF`/`WAJ`
  therefore already carry the tolerance. Verified against the Uniohm catalogue
  and LCSC product data:

  | Part number | LCSC | was | now |
  |---|---|---|---|
  | `0402WGF200JTCE` | 20Ω ±1% | 5% | 1% |
  | `0402WGF549JTCE` | 54.9Ω ±1% | 5% | 1% |
  | `0402WGF499JTCE` | 49.9Ω ±1% | 5% | 1% |
  | `0402WGF511KTCE` | 5.11Ω ±1% | 10% | 1% |
  | `0603WAF220KT5E` | 2.2Ω ±1% | 10% | 1% |
  | `0402WGJ0223TCE` | 22kΩ ±5% | 5% | 5% |

  On the TechOne 27 (CO1271) SKU3 BOM this fixes 25 of 125 resistor rows whose
  decoded tolerance disagreed with the tolerance written in the BOM
  description. Datasheet sample rows that had recorded the wrong value are
  updated to the verified ones.
- **The Clean preview score tint vanished above ~90%.** `QColor` rejects
  channels above 255 and silently returns a fully transparent brush, so the
  green channel computed as 256–258 for high scores and the cell was left
  untinted. Channel values are now clamped.
- **Excel/ODS workbooks now load the first _visible_ worksheet.** Previously the
  reader always took the first sheet, including hidden ones. Workbooks that hide
  an auxiliary sheet (ECN change log, production notes) loaded that sheet instead
  of the real data: `TechOne 27 (CO1271)/PNP/bom.xls` showed 39 ECN rows instead
  of the 266 rows on its visible `SKU3` sheet. Reported on the BOM tab.
- **Toggling the highlight no longer marks the working copy as edited.** The BOM
  and PnP tables marked themselves dirty on *any* `dataChanged`, including the
  repaint-only emissions used for row colouring, so a purely visual change would
  have triggered an autosave of an unchanged table. `dataChanged` is now
  inspected for `DisplayRole`/`EditRole` before dirtying the working copy; real
  cell edits are unaffected.
- **Per-cell background tints now render at all.** The app stylesheet set
  `background-color` on `QTableView::item`, which takes priority over a model's
  `BackgroundRole` and silently suppressed every row colour. This also means the
  existing Clean preview score shading has never been visible. The item rules now
  set only `color`; row colours come from the view's own
  `background-color`/`alternate-background-color`, which the delegate still
  applies per row. Zebra striping is unchanged — verified pixel-identical
  against the previous stylesheet on the TechOne 27 BOM.
- **Taiyo Yuden part numbers now decode their rated voltage from the first
  letter**, per the Taiyo Yuden multilayer ceramic capacitor catalogue.
  `TMK107BBJ106MA-T` did not parse at all, and `JDK`/`LMK` series were
  unhandled — `JDK` did not even classify as a capacitor. The old `BJ` branch
  hardcoded `6.3V`, which only happened to be right for the `J` prefix, so other
  `TMK`/`LMK`/`EMK` parts were decoded with the wrong voltage. A bare `B` series
  code is `X7R`, not `X5R` (`EMK105B7223KV-F` was reported as X5R). Expected
  values were verified against LCSC product data for each affected part number.
- `SMTSheetNotFoundError` is now actually raised for a missing sheet name. It
  previously existed but was never thrown, so a bad sheet name fell through to
  the CSV fallback and surfaced as "rename the file to .txt/.csv".
- **The frozen Windows build crashed on startup and shipped no tab icons.**
  `valvet.spec` did not bundle `src/package_vspd/catalog/` (`tree.json`,
  `aliases.json`), which `package_vspd/catalog.py` resolves from `__file__`, so
  the Package tab raised `FileNotFoundError` while `MainWindow` was still
  building — the app never reached `show()`. `src/themes/assets/` (10 main-tab
  icons plus 6 switch-state SVGs) was missing too, so every tab icon and the
  Project "Debug logs" switch rendered unstyled. Both directories are now in
  `datas` at the paths the frozen modules compute, and
  `tests/test_frozen_bundle_data.py` keeps the spec in step with the modules.

### Notes

- The vendor codecs are now documented against their manufacturer catalogues:
  the **Taiyo Yuden multilayer ceramic capacitor catalogue** (2018, 26 pages —
  supplies the rated-voltage, series-code and size tables) and the **Uniohm
  thick film chip resistor catalogue** (supplies the wattage and tolerance code
  tables and the part-number ordering example). Both PDFs are copyrighted
  vendor literature and are excluded by `.gitignore`; the code and
  `datasheet/*.md` state the decoding rules in prose and cite the catalogue by
  name rather than by path.
- The Uniohm catalogue documents only a **four-digit** value field in the
  ordering code ("the 1st to 3rd digits are the significant figures and the 4th
  indicates the number of zeros following"), which the parser handles and which
  matches LCSC for every four-digit part checked.
- **Known limitation:** some part numbers carry a three-digit value field
  instead. For those the deci-ohm reading is used (`200` → 20Ω), which the
  manufacturer's own ordering example confirms (`1206W4J012JT5E` → 1.2Ω). A few
  LCSC listings disagree by a decade — `0603WAF220JT5E` is listed as 22Ω but
  `0603WAF220KT5E` as 2.2Ω, i.e. the same digits with a different trailing
  letter. Since the trailing letter cannot physically change the magnitude by
  10×, that data is self-inconsistent and no rule could be derived from it, so
  the three-digit reading was left unchanged. Affects only part numbers that
  are not built to the documented four-digit layout.
- The selected sheet is stored **by name**, so it survives reordering or
  inserting sheets in the workbook. Auto-saved working copies are unchanged:
  the snapshot key still covers path/size/mtime, so existing autosaves keep
  working.
- If a remembered sheet no longer exists (the file was replaced), the tab logs a
  warning to the debug console and falls back to auto instead of failing.
- The clean corpus row for `JDK107BBJ226MA-T` now resolves through the Taiyo
  vendor codec instead of the prose-regex fallback. The cleaned string is
  unchanged; only `expected_source` moved from `regex` to `vendor`.

## [0.5.0] — BETA

Initial public BETA line: Project, BOM/PnP, Clean BOM, Merge/Export, Report,
PCB Preview, Step 3D, and Machine lib tabs.

[Unreleased]: https://github.com/zhoel-sherk/VALVET/compare/v0.5.1.2...HEAD
[0.5.1.2]: https://github.com/zhoel-sherk/VALVET/compare/v0.5.1.1...v0.5.1.2
[0.5.1.1]: https://github.com/zhoel-sherk/VALVET/compare/v0.5.1...v0.5.1.1
[0.5.1]: https://github.com/zhoel-sherk/VALVET/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/zhoel-sherk/VALVET/releases/tag/v0.5.0
