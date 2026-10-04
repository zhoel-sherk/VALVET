# Changelog

Notable changes to VALVET. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/zhoel-sherk/VALVET/compare/v0.5.1...HEAD
[0.5.1]: https://github.com/zhoel-sherk/VALVET/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/zhoel-sherk/VALVET/releases/tag/v0.5.0
