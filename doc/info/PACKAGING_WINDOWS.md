# Packaging VALVET on Windows

From the repo root (with `.venv` and `requirements-dev.txt`):

```text
pyinstaller valvet.spec
```

That produces an **onedir** folder `dist/VALVET/` (`VALVET.exe` plus Qt DLLs), not a single portable file. The freeze copies `img/icon.ico` and `img/icon-256.png` only (README screenshots stay out of the zip). Repo `examples/` (BOM/PnP fixtures, `UPD.MDB`, gerbers) is not bundled. Unused PySide6 modules (WebEngine, Qt3D, Charts, QML/Quick, …) are excluded. Smoke-check on a clean PC:

1. Launch `VALVET.exe` (or `python src/main.py --smoke` in CI).
2. Confirm the window icon and **Help → About**.
3. Open a small BOM/PnP pair; Clean Convert; Merge export CSV.

## Bundled data files

Frozen modules resolve data from `__file__`, which lands under `_MEIPASS`, so every
`datas` destination must mirror the `src/`-relative path the module computes:

| Source | `_MEIPASS` | Read by |
| --- | --- | --- |
| `lang/` | `lang` | `ui_i18n.py` |
| `src/fonts/*.ttf` | `fonts` | `themes/fonts_loader.py` |
| `src/themes/design_tokens.json` | `themes/` | `themes/__init__.py` |
| `src/themes/assets/` | `themes/assets/` | `themes/tab_icons.py`, `themes/apple_switch.py` |
| `src/package_vspd/catalog/` | `package_vspd/catalog/` | `package_vspd/catalog.py` |

A missing entry is a **startup crash** when the reading module runs during
`MainWindow` construction (`tree.json`) or a silent UI regression (tab icons,
switch states). `tests/test_frozen_bundle_data.py` parses `datas` and fails when
one of these pairs goes missing — run it after touching `valvet.spec`. The
`--smoke` gate in *Release Windows* is the backstop, since it builds the real
bundle before zipping.

Note: `collect_all("pyvista")`/`("pyvistaqt")` in the spec bundle VTK **whenever
those packages are importable**, so a venv with `requirements-step3d.txt`
installed produces a far larger `dist/` than the CI runner (which installs only
`requirements.txt` + dev).

## GitHub Actions zip

Manual workflow **Release Windows** (`.github/workflows/release-windows.yml`): Actions → Run workflow.

- Builds with PyInstaller, runs `dist/VALVET/VALVET.exe --smoke`, zips `dist/VALVET` as `VALVET-<version>-windows-x64.zip`.
- Uploads the zip as a workflow artifact.
- Optional GitHub Release (`v<version>`, **draft** by default) and Sigstore **build provenance** (`actions/attest-build-provenance`).
- Does **not** run on every push. ACE ODBC and pythonocc are not bundled.

First run: keep **draft**, install from the artifact locally, then publish the Release if you want WinGet / public downloads.

Unsigned exe: SmartScreen may warn. WinGet community packages use the zip **SHA256**, not Authenticode.

## WinGet

See [`winget/README.md`](../../winget/README.md). Package id **ZhoelSherk.VALVET**. Use zip + portable + `ArchiveBinariesDependOnPath` (DLL yes). Inno/NSIS are not required for the first submission.

**Data directories** (not next to the exe): Roaming `%APPDATA%\VALVET\VALVET\` for autosave, optional user parsers, PCB preview cache (`src/app_paths.py`).

Hanwha `.mdb` in-place save needs the Microsoft Access Database Engine (ACE) ODBC driver. Frozen builds do not ship ACE.

Step 3D tessellation via **pythonocc** is an optional extra (`requirements-step3d-occ.txt`, typically **conda-forge**). It is not compiled per machine and is **not** in the default freeze; frozen users can set an external STEP→mesh CLI instead.
