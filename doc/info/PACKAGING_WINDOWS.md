# Packaging VALVET on Windows

From the repo root (with `.venv` and `requirements-dev.txt`):

```text
pyinstaller valvet.spec
```

That produces an **onedir** folder `dist/VALVET/` (`VALVET.exe` plus Qt DLLs), not a single portable file. The freeze copies `img/icon.ico` and `img/icon-256.png` only (README screenshots stay out of the zip). Repo `examples/` (BOM/PnP fixtures, `UPD.MDB`, gerbers) is not bundled. Unused PySide6 modules (WebEngine, Qt3D, Charts, QML/Quick, …) are excluded. Smoke-check on a clean PC:

1. Launch `VALVET.exe` (or `python src/main.py --smoke` in CI).
2. Confirm the window icon and **Help → About**.
3. Open a small BOM/PnP pair; Clean Convert; Merge export CSV.

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
