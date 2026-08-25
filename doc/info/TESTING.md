# Boomer Tools — testing guide

Structured pytest workflow for this repo. **Primary development OS is Windows 11** (daily runs). **Fedora 43** (or GitHub `ubuntu-latest`) remains the Linux regression check for paths, optional Step 3D / VTK, and Hanwha `.mdb` via **mdbtools** vs Windows ODBC — see [hanwha_mdb_editor.md](hanwha_mdb_editor.md).

Canonical commands below assume repository root `boomer/` (the folder containing `src/`, `tests/`, `requirements.txt`).

---

## Level 0 — environment

1. Create a venv at repo root: **Windows** `python -m venv .venv` (or `py -3 -m venv .venv`); **Fedora** `python3 -m venv .venv`.
2. Upgrade pip: `python -m pip install -U pip` (use the venv’s `python`).
3. Install deps: `python -m pip install -r requirements.txt`
   Dev lint/coverage: `python -m pip install -r requirements-dev.txt`.
  Optional Step 3D viewer tests: `python -m pip install -r requirements-step3d.txt`.
4. `**PYTHONPATH=src`** is required so tests resolve `smt_processor`, `pcb_preview`, etc.

### Lint (optional)

Install dev tools: `python -m pip install -r requirements-dev.txt` (`[requirements-dev.txt](requirements-dev.txt)`).

```bash
export PYTHONPATH=src   # Windows: $env:PYTHONPATH = "src"
python -m ruff format src tests
python -m ruff check src tests
python -m vulture
```

CI runs `ruff check` (rules `E`/`F`, ignoring E501/E402). **Vulture is non-blocking** in GitHub Actions (`continue-on-error`); Qt slots and dynamic calls produce false positives at `min_confidence = 80`.

Hypothesis and mutmut are **not** part of the default stack.

`[pyproject.toml](pyproject.toml)` configures Ruff, Vulture, and coverage omit for GUI packages (`src/app/`, `src/ui/`, `src/hanwha_mdb_edit/gui/`). Lower vulture confidence (`--min-confidence 60`) reports many more false positives.

**Windows (PowerShell 7):**

```powershell
cd boomer
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:PYTHONPATH = "src"
```

**Fedora / Bash:**

```bash
cd boomer
source .venv/bin/activate
python -m pip install -r requirements.txt
export PYTHONPATH=src
```

`tests/conftest.py` sets `QT_QPA_PLATFORM=offscreen` before PySide6 imports so headless/CI runs do not need a display.

---

## Level 1 — fast smoke (every commit / PR)

Expect **0 failed**. Record `passed` / `skipped` / OS / Python version when updating [TODO.md](../TODO.md) or [CHANGELOG.md](../../CHANGELOG.md).

```bash
python -m compileall -q src
python -m pytest tests -q --ignore=tests/test_pcb_preview_gerber.py
```

Coverage (no fail-under; omit GUI paths via `[tool.coverage.run]`):

```bash
python -m pytest tests -q --ignore=tests/test_pcb_preview_gerber.py --cov=src --cov-report=term-missing:skip-covered
```

**`--debug` vs the Debug dialog:** `python src/main.py --debug`, `VALVET_DEBUG=1`, and the Project tab **Debug logs** checkbox all call `logger.set_debug_mode` (dated file under `logs/` plus stderr). Unchecking the box turns file logging off. **Debug / advanced…** is a separate dialog (snapshots, fonts, experimental tabs). CLI: `python -m cli --debug …`.

Last recorded baseline (re-run after changes): **258 passed, 9 skipped** for Level 1 (`pytest tests -q --ignore=tests/test_pcb_preview_gerber.py`). **259 passed, 9 skipped** for `pytest tests -q` (adds the Gerber file test). Counts depend on optional fixtures (`.mdb`, example6) — see Level 3.

### Level 1b — app startup (headless PySide6)

Automated smoke for **main-window tab construction** and **debug dialogs** (no file dialogs, Hanwha editor, or recovery prompts):

```bash
export PYTHONPATH=src   # Windows: $env:PYTHONPATH = "src"
python -m pytest tests/test_app_startup.py -q
```

Uses `tests/conftest.py` (`QT_QPA_PLATFORM=offscreen`). `MainWindow(settings=…)` accepts an isolated `QSettings` Ini file so tests do not touch the user registry. Experimental tabs: **7** tabs when all `experimental/enable_*` are false; **9** when all true (`pcb_preview`, `step_3d`). Step 3D tab construction does not require `requirements-step3d.txt`; VTK mesh load is not exercised here.

GUI-free service unit tests: `tests/test_services.py` (same Level 1 run).

Parser / alert regressions added to Level 1:

```bash
python -m pytest tests/test_clean_alerts.py tests/test_pn_vendor_verified_rules.py -q
```

---

## Level 2 — include Gerber core test

Run before release or after edits under `src/pcb_preview/`:

```bash
export PYTHONPATH=src   # or $env:PYTHONPATH="src" on Windows
python -m pytest tests -q
```

Or explicitly:

```bash
python -m pytest tests/test_pcb_preview_gerber.py -q
```

Run **on Windows 11 and on Linux** (Fedora 43 locally or `ubuntu-latest` in CI) so Gerber + path behavior stays aligned.

---

## Level 3 — skips and optional deps (CI matrix expectations)


| Mechanism                                     | Location / reason                                                                                                                                          | CI expectation                                                                                                                       |
| --------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `@pytest.mark.skipif` — `UPD.MDB` missing     | `tests/test_hanwha_mdbtools.py`, `tests/test_hanwha_mdb_edit_core.py`                                                                                      | **Skip** unless a sample `.mdb` is placed where tests expect it; do not treat as failure.                                            |
| `@pytest.mark.skipif` — example6 xlsx missing | `tests/test_pn_example6.py`                                                                                                                                | **Skip** if `examples/example6/original_gen3_bom.xlsx` absent.                                                                       |
| `pytest.skip(...)` — example6 / cmp missing   | `tests/test_clean_component.py`, `tests/test_smt_processor_formats.py`                                                                                     | **Skip** at runtime if paths missing.                                                                                                |
| `pytest.importorskip("PySide6")`              | `tests/test_qsettings_bom_pnp_persist.py`, `tests/test_working_copy_ui.py`, `tests/test_hanwha_column_labels_and_filters.py`, `test_step_3d.py` (one test) | Minimal env **without** PySide6: those modules skip; full `requirements.txt` includes PySide6 — CI should install full requirements. |
| `pytest.importorskip("pyvista")`              | `tests/test_step_3d.py`                                                                                                                                    | **Skip** mesh read test unless `requirements-step3d.txt` installed; use optional job to install Step3D stack.                        |
| `@pytest.mark.skip` — Python 3.14 + xlsx      | `tests/test_smt_processor.py`                                                                                                                              | **Skipped** on 3.14 (xlrd/xlsx); matrix should document supported Python versions.                                                   |
| `pytest.importorskip("pandas")` / `openpyxl`  | Several tests                                                                                                                                              | Use full `requirements.txt` in CI.                                                                                                   |


Fedora / Wayland: for **interactive** Step 3D (not pytest), operators may need `QT_QPA_PLATFORM=xcb` — see [README.md](README.md). Passing Step3D-related tests on Windows alone is **not** sufficient proof for Linux VTK stacks.

---

## Level 4 — module → pytest mapping

When you touch an area listed in [LLM.md](LLM.md) **Important Files**, run the matching tests first.


| Area                                 | Suggested pytest targets                                                                                          |
| ------------------------------------ | ----------------------------------------------------------------------------------------------------------------- |
| Clean BOM / regex master             | `tests/test_clean_component.py`, `tests/test_clean_arbiter.py`                                                    |
| SMT / merge / XY / cross-check       | `tests/test_smt_processor.py`, `tests/test_smt_processor_formats.py`, `tests/test_duplicate/`                     |
| MMD export                           | `tests/test_mmd_export.py`                                                                                        |
| Yamaha `.Tou` / DevLib               | `tests/test_yamaha_tou.py`, `tests/test_yamaha_devlib.py`                                                         |
| Hanwha `.mdb` (Qt-free tools)        | `tests/test_hanwha_mdbtools.py`                                                                                   |
| Paths / session links                | `tests/test_app_paths.py`                                                                                         |
| HTML report                          | `tests/test_report_html.py`                                                                                       |
| UI i18n catalogs                     | `tests/test_ui_i18n.py`                                                                                           |
| Step 3D (conversion + optional mesh) | `tests/test_step_3d.py`                                                                                           |
| Gerber → SVG core                    | `tests/test_pcb_preview_gerber.py`                                                                                |
| Vendor PN / example6                 | `tests/test_pn_example6.py`, `tests/test_use_vendor_gate.py`                                                      |
| Clean BOM golden corpus              | `tests/test_clean_corpus_golden.py`, `tests/test_clean_corpus_harvest.py`, `tests/test_hanwha_partname_filter.py` |
| GUI-free services (`src/services/`)  | `tests/test_services.py`                                                                                          |
| App startup / tabs (headless Qt)     | `tests/test_app_startup.py`                                                                                       |


**Clean BOM golden corpus** (`tests/fixtures/clean_corpus/`):

```powershell
$env:PYTHONPATH='src'
python tools/clean_corpus.py mdb-export --mdb examples/UPD.MDB
python tools/clean_corpus.py harvest --limit 500
python tools/clean_corpus.py draft
python tools/clean_corpus.py test
python tools/clean_corpus.py report
pytest tests/test_clean_corpus_golden.py -q
```

On failure, `report` prints structured got/want blocks for each `id`. Rebuild Hanwha snapshot after `UPD.MDB` changes. See `tests/fixtures/clean_corpus/README.md`.

**Clean BOM preview tracing:** set `BOOMER_CLEAN_PREVIEW_LOG=1` in the environment before launching the app; each **Convert!** run logs one INFO line per preview row (`row`, `type`, `source`, `cleaned`, truncated `Original`).

**Missing-token alerts (non-blocking):**

- Preview now includes `Alert` column (`missing=...;present=...`), including regex-master mode (`Arbiter`, `Win%`, `Alert`).
- Missing-token events are appended to JSONL log:
  - default: `<user_state_dir>/logs/missing_tokens.jsonl`
  - override: env `BOOMER_MISSING_TOKENS_LOG=/absolute/path/missing_tokens.jsonl`
- Designed for triage/debug; does not block Clean Apply.

Full discovery: `python -m pytest tests --collect-only -q`.

---

## Level 5 — backlog (not required for green pytest today)

Tracked in [TODO.md](../TODO.md) in more detail:

- **PCB Preview:** more Qt-free fixtures (small Gerber + PnP) beyond the minimal Gerber roundtrip.
- **Machine library / Yamaha:** Qt-free services + fixtures before large UI wiring (Phase 5).
- `**app_pyside6.py`:** BOM/PnP load, language, and file dialogs still need manual smoke; main tabs and debug dialogs are covered by `tests/test_app_startup.py` (Level 1b). Optional future `pytest-qt` for modal file/recovery flows.

---

## OS reconciliation (Fedora vs Windows)

After **large** changes (paths, `app_paths`, `pcb_preview`, `step_3d`, `machine_library`, subprocess/converter templates):

1. Run **Level 1** and **Level 2** on **Windows 11** (primary dev machine).
2. Repeat on **Fedora 43** (or Linux CI job) with the same Python major as CI when possible.
3. Compare `passed` / `skipped` and failure output. If counts differ only due to optional fixtures (`.mdb`, example6), document that next to the numbers in [TODO.md](../TODO.md).
4. If behavior diverges by OS, file a note in [CHANGELOG.md](../../CHANGELOG.md) **Unreleased** and/or open an issue with both logs.

---

## GitHub Actions

Workflow `[.github/workflows/ci.yml](.github/workflows/ci.yml)` runs on **windows-latest** and **ubuntu-latest**: `ruff check`, Level 1 pytest (coverage report on Ubuntu only, no fail-under), Gerber test, `compileall`, `requirements.txt` + `requirements-dev.txt`, `PYTHONPATH=src`. Vulture runs on Ubuntu and does not fail the job.