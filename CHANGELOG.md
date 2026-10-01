# Changelog

Notable changes to VALVET. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
- **Taiyo Yuden part numbers now decode their rated voltage from the first
  letter**, per the manufacturer catalogue (`doc/info/DOC012627480.pdf`).
  `TMK107BBJ106MA-T` did not parse at all, and `JDK`/`LMK` series were
  unhandled — `JDK` did not even classify as a capacitor. The old `BJ` branch
  hardcoded `6.3V`, which only happened to be right for the `J` prefix, so other
  `TMK`/`LMK`/`EMK` parts were decoded with the wrong voltage. A bare `B` series
  code is `X7R`, not `X5R` (`EMK105B7223KV-F` was reported as X5R). Expected
  values were verified against LCSC product data for each affected part number.
- `SMTSheetNotFoundError` is now actually raised for a missing sheet name. It
  previously existed but was never thrown, so a bad sheet name fell through to
  the CSV fallback and surfaced as "rename the file to .txt/.csv".

### Notes

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

[Unreleased]: https://github.com/zhoel-sherk/VALVET/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/zhoel-sherk/VALVET/releases/tag/v0.5.0
