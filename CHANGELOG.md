# Changelog

Notable changes to VALVET. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **Excel/ODS workbooks now load the first _visible_ worksheet.** Previously the
  reader always took the first sheet, including hidden ones. Workbooks that hide
  an auxiliary sheet (ECN change log, production notes) loaded that sheet instead
  of the real data: `TechOne 27 (CO1271)/PNP/bom.xls` showed 39 ECN rows instead
  of the 266 rows on its visible `SKU3` sheet. Reported on the BOM tab.

### Added

- **Worksheet picker on the BOM and PnP tabs** — a `Sheet:` combo next to the
  delimiter, listing every sheet with hidden ones marked `(hidden)`. `"(auto)"`
  (the default) keeps the first-visible-sheet behaviour; any other entry pins a
  specific sheet. The chosen sheet and its row count are shown under the combo.
- `smt_processor.list_sheets(path)` returns sheet names with a visibility flag,
  and `smt_processor.default_sheet_name(sheets)` resolves the first visible sheet
  (falling back to the first sheet when all are hidden).
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

## [0.5.0] — BETA

Initial public BETA line: Project, BOM/PnP, Clean BOM, Merge/Export, Report,
PCB Preview, Step 3D, and Machine lib tabs.

[Unreleased]: https://github.com/zhoel-sherk/VALVET/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/zhoel-sherk/VALVET/releases/tag/v0.5.0
