# Machine lib / yedytor notes

Yamaha `.Tou` and `DevLibEd*.Lib` formats: use [yedytor](https://github.com/marmidr/yedytor) (MIT) as a **reference for on-disk layouts and UX ideas**, not as a UI port.

VALVET matching for Yamaha names shares the same Clean BOM matcher as Hanwha (`machine_partname_set()`).

## `.Tou` layout (best-effort; not an official Yamaha spec)

Record size **320** bytes, no file header. yedytor only documented the name field.

| Offset | Size | Field (observed on `examples/yamaha/tou/*.Tou`) |
|--------|------|--------------------------------------------------|
| 0 | 40 | Component name, NUL-padded |
| 40 | 16 | Refdes, NUL-padded (`C41`, `R12`) |
| 56 | 4 | Board X, `int32` LE, **0.001 mm** |
| 60 | 4 | Board Y, `int32` LE, **0.001 mm** |
| 68 | 4 | Rotation, `int32` LE, **millidegrees** (180000 → 180°) |
| 82 | 40 | Comment / value (`10nF`, `100k 1206`) |
| 40–319 remainder | | Opaque (no body L×W found vs 1206 / CAPC1005 names) |

Example job files (from yedytor):

- `examples/yamaha/tou/TGV-FLOOR2-V4_RCC-Top_opt.Tou` — 29 unique name keys
- `examples/yamaha/tou/TGV-FLOOR2-V4_RCC-BOT_opt.Tou` — 49 unique name keys

Footprint preview uses package tokens in the **name** (imperial `1206`/`0603`/… or metric `CAPC1005` → 1.0×0.5 mm), plus placement metadata from the table above. Treat XY/rotation as **best-effort**.

## `DevLibEd.Lib` / `DevLibEd2.Lib`

| Offset | Size | Field |
|--------|------|--------|
| 0 | 6 | ASCII `Ver500` |
| 160 | | First record |
| record+0 | 82 | Component name |
| record+82 | 44 | Basename (yedytor defined this; VALVET reads it) |
| stride | 640 (v1) or 2048 (Ed2) | Auto-detected like yedytor |

No `DevLibEd.Lib` sample is shipped with yedytor. Geometry is name-heuristic only for Lib rows.
