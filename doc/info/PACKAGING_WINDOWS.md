# Packaging VALVET on Windows

From the repo root (with `.venv` and `requirements-dev.txt`):

```text
pyinstaller valvet.spec
```

That produces an onedir build under `dist/`. Smoke-check on a clean PC:

1. Launch `VALVET.exe` (or `python src/main.py --smoke` in CI).
2. Confirm the window icon and **Help → About**.
3. Open a small BOM/PnP pair; Clean Convert; Merge export CSV.

**Data directories** (not next to the exe): Roaming `%APPDATA%\VALVET\VALVET\` for autosave, optional user parsers, PCB preview cache (`src/app_paths.py`).

Hanwha `.mdb` in-place save needs the Microsoft Access Database Engine (ACE) ODBC driver. Frozen builds do not ship ACE.

Step 3D / pythonocc are **optional** extras (`requirements-step3d*.txt`) and are not required in the default freeze.
