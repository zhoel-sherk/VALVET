# VALVET import conventions

PEP 8 plus this repo’s stack (pandas, numpy, PySide6, PyPI `regex`) and Ruff (`I` isort, `ICN` import-conventions). An alias must make the file **easier to read**, not merely shorter. A colleague (or an agent) should know what `NNN` is on first sight.

Ruff: `[tool.ruff.lint]` in [`pyproject.toml`](../../pyproject.toml) (`select` includes `I` and `ICN`). `ruff format` matches Black (88 columns, double quotes). isort wrapping follows that line length; `combine-as-imports = true` is kept on purpose. Fix order and pandas/numpy aliases with:

```bash
python -m ruff check src tests --fix
```

---

## 1. Canonical third-party aliases

Use the community names. Other spellings (`import pandas as p`) fail review and `ICN`.

| Import | Alias | Notes |
|--------|--------|--------|
| `numpy` | `np` | Required wherever numpy is used |
| `pandas` | `pd` | Required wherever pandas is used |
| PyPI `regex` | — | **Do not** `import regex as re` in application code |

**PyPI `regex` vs stdlib `re`:** parsers need `regex` VERSION1. Call [`src/parsers/regex_api.py`](../../src/parsers/regex_api.py) (`compile`, `search`, `match`, flags `I`, `V1`, …). Only `regex_api.py` may `import regex as _r` so the private name does not collide with stdlib `re` in other modules. Do not replace stdlib `re` with `import regex as re` in GUI, CLI, or tests unless that file is explicitly migrating onto `regex_api`.

---

## 2. PySide6: protect the Qt namespace

- **Never** `from PySide6.QtWidgets import *` (or any Qt `import *`). It pollutes the module and hides bugs.
- **Do not** alias modules as `qtw` / `qtc` / `qtg`. That only saves a few letters (see §3) and this tree already uses the real names.

**Required form** (one line, modules not classes):

```python
from PySide6 import QtCore, QtGui, QtWidgets

button = QtWidgets.QPushButton("Click")
```

Import only the Qt packages the file uses (`QtCore` alone is fine in workers).

**Allowed exception:** a short `from PySide6.QtCore import QSettings` (or a handful of types) when the file is already full of those names. Prefer `QtCore.QSettings` in new files. Do not mix `from PySide6 import QtCore` and `from PySide6.QtCore import Qt` in the same file without a reason (keep one style per file).

---

## 3. Alias long modules; do not alias to save two letters

An alias is justified if:

1. The **module path is long** (three or more dotted parts, or a last segment of 18+ characters) **and** the alias is in the table below.
2. Two modules would otherwise clash (two different `utils`).
3. You swap implementations behind a stable name (`regex` behind `regex_api`, not `import regex as re` in every file).

**Do not** alias short, obvious names: `import platformdirs as pdirs`, `import logger as log`, `import pandas as pan`, `QtWidgets as qtw`.

### Canonical long first-party aliases

Use **exactly** these names. Import the module (or the parent’s submodule), then qualify symbols. Do not invent `hsc`, `ufb`, `pdirs`.

| Module | Alias / import |
|--------|----------------|
| `machine_library.hanwha_sqlite_cache` | `import machine_library.hanwha_sqlite_cache as hanwha_cache` |
| `machine_library.hanwha_mdbtools` | `import machine_library.hanwha_mdbtools as mdbtools` |
| `machine_library.upd_geometry_load` | `import machine_library.upd_geometry_load as upd_geom` |
| `pcb_preview.upd_footprint_builder` | `import pcb_preview.upd_footprint_builder as upd_fp` |
| `hanwha_mdb_edit.core.*` (from **outside** `core`) | `from hanwha_mdb_edit.core import save` then `save.save_enriched_library` (same for `column_labels`, `errors`, `part_bulk`, …) |
| `hanwha_mdb_edit.gui.*` (from **outside** `gui`) | `from hanwha_mdb_edit.gui import editor_window` then `editor_window.HanwhaMdbEditorWindow` |

**Inside** `hanwha_mdb_edit.core` / `.gui`, keep sibling imports (`from .errors import …` or a single leaf `from hanwha_mdb_edit.core.errors import HanwhaSaveError`). Package `__init__.py` re-exports may still `from … import Name`.

**Package `__init__.py` re-exports** (`from machine_library.hanwha_mdbtools import Name` into `__all__`) stay as name imports.

```python
# Good — one name
from machine_library.hanwha_mdbtools import HanwhaMdbToolsError

# Good — many names
import machine_library.hanwha_sqlite_cache as hanwha_cache

hanwha_cache.import_mdb_to_cache(src, dest)
```

### Do not invent `from … import LongName as Short`

`from parsers.si_units import SiQuantity as SiQty` (or `FpResult`, `HanwhaEditorWindow`, `parse_si`, `get_col_label`) is **not** used in this tree and is **not** a repo convention. Types and functions keep their real names:

```python
from pcb_preview.upd_footprint_builder import FootprintBuildResult
from parsers.si_units import convert_nf_token_to_uf
from hanwha_mdb_edit.gui.editor_window import HanwhaMdbEditorWindow
```

Ruff `ICN` does **not** enforce `from module import Class as Alias`. `[tool.ruff.lint.flake8-import-conventions.aliases]` only applies to **whole-module** imports (`import pandas as pd`, `import machine_library.hanwha_mdbtools as mdbtools`). Putting `FootprintBuildResult = "FpResult"` in that map would flag every unaliased import and force a mass rename — do not add it.

If a type alias is ever needed, add a row here **and** migrate every call site in the same change. Until then: no one-off `as SiQ` / `as FBR` / `as Sq`.

---

## 4. Ruff isort (`I`) and conventions (`ICN`)

`I` groups and sorts imports (stdlib, third-party, first-party). Ruff isort wrapping uses `line-length = 88` (Black-compatible); `combine-as-imports = true` is a repo preference. `ICN` requires `numpy` → `np`, `pandas` → `pd`, and the long-module aliases in [`pyproject.toml`](../../pyproject.toml) (`hanwha_cache`, `mdbtools`, `upd_geom`, `upd_fp`) when those modules are imported as a whole (`import … as …`). It does not lint class/function `as` aliases.

After edits:

```bash
python -m ruff check src tests --fix
python -m ruff format src tests
```

Do not add `"PySide6.QtWidgets" = "qtw"` to aliases: that would contradict §2–§3.

---

## 5. Three blocks, then alphabetical

Even with aliases, the top of a file is three blocks (blank line between). Inside a block, Ruff sorts names.

```python
"""Module docstring."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from PySide6 import QtCore, QtWidgets

from app_paths import hanwha_lib_cache_dir
from smt_processor import SMTProcessorError
```

1. Standard library (`os`, `sys`, `pathlib`, …).
2. Third-party (`numpy`, `pandas`, `PySide6`, `pytest`, …).
3. First-party VALVET modules (`app_paths`, `smt_processor`, `cli`, `parsers`, …). `src/` is on `PYTHONPATH`; do not use `src.` prefixes.

`from __future__ import annotations` stays immediately under the docstring (Ruff `I` keeps it there).

**Relative imports** (`from .foo import bar`) only inside packages that already use them (`hanwha_mdb_edit`, `pcb_preview`, `parsers`, `pn_original`, `step_3d`, …). Do not start using relative imports in the flat `src/*.py` layout.

---

## Checklist (review / agents)

- [ ] `pandas` / `numpy` only as `pd` / `np`
- [ ] No `import *` from Qt or elsewhere
- [ ] Qt: `from PySide6 import QtWidgets` (etc.), not `as qtw`
- [ ] No cute aliases (`pdirs`, `pan`, `log`)
- [ ] Parser regex via `parsers.regex_api`, not `import regex as re`
- [ ] Two or more names from a long first-party module → alias table (§3)
- [ ] Types/functions keep their real names (no `SiQty` / `FpResult` unless listed in this file)
- [ ] `ruff check src tests` clean for `E`, `F`, `I`, `ICN`
