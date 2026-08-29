# Boomer Tools — testing guide

Structured pytest workflow for this repo. **Primary development OS is Windows 11** (daily runs). **Fedora 43** (or GitHub `ubuntu-latest`) remains the Linux regression check for paths, optional Step 3D / VTK, and Hanwha `.mdb` via **mdbtools** vs Windows ODBC — see [hanwha_mdb_editor.md](hanwha_mdb_editor.md).

Canonical commands below assume repository root `VALVET/` (the folder containing `src/`, `tests/`, `requirements.txt`).

---

## Level 0 — environment

1. Create a venv at repo root: **Windows** `python -m venv .venv` (or `py -3 -m venv .venv`); **Fedora** `python3 -m venv .venv`.
2. Upgrade pip: `python -m pip install -U pip` (use the venv’s `python`).
3. Install deps: `python -m pip install -r requirements.txt`
   Dev lint/coverage: `python -m pip install -r requirements-dev.txt` (`pytest-cov`, `pytest-mock`, `ruff`, `vulture`).
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
cd VALVET
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:PYTHONPATH = "src"
```

**Fedora / Bash:**

```bash
cd VALVET
source .venv/bin/activate
python -m pip install -r requirements.txt
export PYTHONPATH=src
```

`tests/conftest.py` sets `QT_QPA_PLATFORM=offscreen` before PySide6 imports so headless/CI runs do not need a display.

---

## Invariant rules (code + tests)

These apply to new production code **and** to pytest. A silent pass that hides a fallback, a leaked ODBC handle, or a `QThread` poking widgets is a failed review even if CI is green.

### Silent fallback → `logger`

A fallback (pygerber→gerbonara, ACE→mdbtools, path→legacy dir, regex after vendor PN) **must** log at `warning` (or `info` if the path is expected and frequent). Tests must spy `logger.warning` / `logger.info` and assert the message names the backend that failed **and** the one that ran. Bare `except: pass` or swallowing `AccessOdbcError` without a log is a defect.

Existing: [`tests/test_logger_fallbacks.py`](../../tests/test_logger_fallbacks.py) (`test_gerber_gerbonara_fallback_logs_warning`, `test_hanwha_odbc_fallback_logs_warning`).

### QThread → UI only via Qt signals

Worker `run()` must not touch widgets, models, or `QMessageBox`. Results, errors, and progress go out as `Signal` (`result_ready`, `progress`). The GUI slot runs on the GUI thread (`QueuedConnection`). Tests start the thread, pump events / `wait()`, and assert state **after** the slot — not by calling widget methods from the worker.

Existing pattern: [`src/app/workers.py`](../../src/app/workers.py), [`tests/test_machine_lib_open_reload.py`](../../tests/test_machine_lib_open_reload.py). Do not add `pytest-qt` only to violate this (no `qtbot` clicks inside `QThread.run`).

### Do not mix bare numbers and objects

A `Signal` payload, a preview tuple, or a return value is one contract: either a typed object (`DataFrame`, `FootprintBuildResult`) **or** a documented sentinel (`None` + `str` error), not `0` vs `{}` vs `""` for the same slot. Tests should `isinstance` the success object and treat error as a string. Packed tuples (`payload, image, viewbox`) must keep a fixed length and types — see `GerberLoadThread.result_ready`.

### Pint: `Quantity` vs `float`

[`src/parsers/si_units.py`](../../src/parsers/si_units.py) returns pint `Quantity` (`quantity_farads`, `quantity_ohms`, `quantity_volts`). Callers that do arithmetic must not add a raw `float` to a `Quantity` (and must not pass a `Quantity` into millimetre geometry). Geometry (`um_to_mm`) stays **floats**. Tests: invalid tokens return `None`; successful parses compare `.to("nanofarad").magnitude` (etc.), not `== 22` on the Quantity itself. Existing: `test_pint_*` in [`tests/test_parser_p0_vendor_off.py`](../../tests/test_parser_p0_vendor_off.py).

### natsort on dirty data

Natural sort of designators / filenames must not raise on empty strings, mixed types, NaN, or junk (`R1`, `R10`, `""`, `None`, `12`). If `natsort` (or a local natsort helper) is used, tests feed a dirty list and expect a stable list out — never an uncaught `TypeError`. Until a dedicated module exists, any new natsort call needs that fixture in the same PR.

### File import validation

Loaders (`read_file`, `_load_bom` / `_load_pnp`, Gerber, `.mdb`) must reject empty paths, missing files, and unreadable/unsupported content with a logged error or `SMTProcessorError` / equivalent — not a half-filled table. Tests: `tmp_path` missing file; optional tiny corrupt bytes. Happy path: [`tests/test_bom_pnp_window_load.py`](../../tests/test_bom_pnp_window_load.py) (`force_original=True`). Live `.mdb`: [`tests/mdb_paths.py`](../../tests/mdb_paths.py) `skip_if_mdb_unreadable`.

### pyodbc connections must close

Every `connect_mdb` needs `close()` in `finally` (see [`import_mdb_to_cache`](../../src/machine_library/hanwha_sqlite_cache.py)). Tests that mock `pyodbc.connect` should assert `close` was called on the connection mock after the function returns (success **and** mid-loop failure). Do not leave pooling on (`pooling = False` in [`access_odbc.py`](../../src/machine_library/access_odbc.py)).

### PySide6: no leftover widgets / cursors / threads

Headless tests: `try`/`finally` `win.close()`; if a tab set a wait cursor, `restoreOverrideCursor()`. `QThread`: `wait()` then `deleteLater()` (or equivalent) so the worker is not destroyed while `run()` is live. Do not create a second `QApplication` if one exists (`QApplication.instance()`). Module-scoped `qapp` in [`tests/test_app_startup.py`](../../tests/test_app_startup.py) is the model.

### No hardcoded machine paths

Production code uses [`src/app_paths.py`](../../src/app_paths.py) (`user_state_dir`, `hanwha_lib_cache_dir`, platformdirs). Tests use `tmp_path` / `tmp_path_factory` and repo-relative helpers ([`tests/mdb_paths.py`](../../tests/mdb_paths.py) — `examples/UPD.MDB` or `../UPD.MDB`), never `C:\Users\...` or `/home/runner/...`. Monkeypatch `hanwha_lib_cache_dir` when a test would otherwise write under the real profile dir ([`tests/test_machine_lib_open_reload.py`](../../tests/test_machine_lib_open_reload.py)).

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

Last recorded baseline (re-run after changes): **~450+ passed** on GitHub Actions Ubuntu Level 1 (`pytest tests -q --ignore=tests/test_pcb_preview_gerber.py`), with skips for missing optional fixtures. Counts depend on live `UPD.MDB` / example6 — see Level 3. Re-record `passed` / `skipped` after a local Level 1 run when updating this file.

### Level 1b — app startup (headless PySide6)

Automated smoke for **main-window tab construction** and **debug dialogs** (no file dialogs, Hanwha editor, or recovery prompts):

```bash
export PYTHONPATH=src   # Windows: $env:PYTHONPATH = "src"
python -m pytest tests/test_app_startup.py -q
```

Uses `tests/conftest.py` (`QT_QPA_PLATFORM=offscreen`). `MainWindow(settings=…)` accepts an isolated `QSettings` Ini file so tests do not touch the user registry. **PCB Preview is always created.** Step 3D is optional: **8** tabs when `experimental/enable_step_3d` is false; **9** when true. Step 3D tab construction does not require `requirements-step3d.txt`; VTK mesh load is not exercised here.

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
| `@pytest.mark.skipif` — `UPD.MDB` missing     | `tests/test_hanwha_mdbtools.py`, `tests/test_hanwha_mdb_edit_core.py`, `tests/test_hanwha_import_mdb_to_cache.py`, `tests/test_hanwha_upd_geometry_load.py`, `tests/test_machine_lib_open_reload.py` | **Skip** unless a sample `.mdb` is placed where tests expect it; do not treat as failure. Live import is `@pytest.mark.slow`. |
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
| Hanwha SQLite cache / import         | `tests/test_hanwha_sqlite_cache.py`, `tests/test_hanwha_import_mdb_to_cache.py`                                  |
| UPD footprint builder                | `tests/test_upd_footprint_builder.py`, `tests/test_hanwha_upd_geometry_load.py`                                  |
| Machine Lib tab (headless Open)      | `tests/test_machine_lib_open_reload.py`                                                                           |
| Paths / session links                | `tests/test_app_paths.py`                                                                                         |
| HTML report                          | `tests/test_report_html.py`                                                                                       |
| UI i18n catalogs                     | `tests/test_ui_i18n.py`                                                                                           |
| Step 3D (conversion + optional mesh) | `tests/test_step_3d.py`                                                                                           |
| Gerber → SVG core                    | `tests/test_pcb_preview_gerber.py`                                                                                |
| Vendor PN / example6                 | `tests/test_pn_example6.py`, `tests/test_use_vendor_gate.py`                                                      |
| Clean BOM golden corpus              | `tests/test_clean_corpus_golden.py`, `tests/test_clean_corpus_harvest.py`, `tests/test_hanwha_partname_filter.py` |
| GUI-free services (`src/services/`)  | `tests/test_services.py`                                                                                          |
| App startup / tabs (headless Qt)     | `tests/test_app_startup.py`                                                                                       |
| Silent fallback logging              | `tests/test_logger_fallbacks.py`                                                                                  |
| Access ODBC (no timeout / close)     | `tests/test_access_odbc.py`                                                                                       |
| Pint SI helpers                      | `tests/test_parser_p0_vendor_off.py` (`test_pint_*`)                                                               |
| BOM/PnP load via MainWindow          | `tests/test_bom_pnp_window_load.py`, `tests/test_cli_pipeline.py`                                                  |
| PCB Preview tab Gerber layer         | `tests/test_pcb_preview_tab_gerber.py`                                                                            |


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

- **Invariant gaps:** natsort dirty-input fixture (when natural sort is added); `pyodbc` connection mock asserting `.close()` on failure paths in `hanwha_mdb_edit` saves; missing-file / corrupt import tests for BOM/PnP/Gerber beyond happy path.
- **Machine library / Yamaha:** Qt-free services + fixtures before large UI wiring (Phase 5).
- `**app_pyside6.py`:** BOM/PnP load, language, and file dialogs still need manual smoke; main tabs and debug dialogs are covered by `tests/test_app_startup.py` (Level 1b). Headless load-by-path: `tests/test_bom_pnp_window_load.py`. Optional future `pytest-qt` for modal file/recovery flows (not in `requirements-dev.txt` yet). `pytest-mock` is in `requirements-dev.txt` for spies; keep `monkeypatch.setenv` for env vars.

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