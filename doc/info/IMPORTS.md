# VALVET import conventions

PEP 8 plus this repo’s stack (pandas, numpy, PySide6, PyPI `regex`) and Ruff (`I` isort, `ICN` import-conventions). An alias must make the file **easier to read**, not merely shorter. A colleague (or a model) should know what `NNN` is on first sight.

Ruff: `[tool.ruff.lint]` in [`pyproject.toml`](../../pyproject.toml) (`select` includes `I` and `ICN`). Fix order and pandas/numpy aliases with:

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

## 3. Do not alias to save two letters

An alias is justified only if:

1. The name is long and the alias is **universal** (`matplotlib.pyplot` → `plt`; `numpy` → `np`).
2. Two modules would otherwise clash (two different `utils`).
3. You swap implementations behind a stable name (`regex` behind `regex_api`, not `import regex as re` in every file).

**Bad:** `import platformdirs as pdirs`. **Good:** `import platformdirs` or `from platformdirs import user_data_dir` (see [`src/app_paths.py`](../../src/app_paths.py)).

Do not invent `import logger as log` or `import pandas as pan`.

---

## 4. Ruff isort (`I`) and conventions (`ICN`)

`I` groups and sorts imports (stdlib, third-party, first-party). `ICN` requires `numpy` → `np` and `pandas` → `pd` (see `flake8-import-conventions.aliases` in `pyproject.toml`).

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

Relative imports (`from .foo import bar`) only inside a package that already uses them (`hanwha_mdb_edit`, `pcb_preview.engine`, …). Do not start using relative imports in the flat `src/*.py` layout.

---

## Checklist (review / agents)

- [ ] `pandas` / `numpy` only as `pd` / `np`
- [ ] No `import *` from Qt or elsewhere
- [ ] Qt: `from PySide6 import QtWidgets` (etc.), not `as qtw`
- [ ] No cute aliases (`pdirs`, `pan`, `log`)
- [ ] Parser regex via `parsers.regex_api`, not `import regex as re`
- [ ] `ruff check src tests` clean for `E`, `F`, `I`, `ICN`
