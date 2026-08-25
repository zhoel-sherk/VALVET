# Hanwha UPD `.mdb` schema notes

Shop library (example: `examples/UPD.MDB`). Names below are Jet/Access table and column names.

## Two different “BASE” concepts

| Shop / UI language | MDB field | Meaning |
|---|---|---|
| Component **class** (Chip-0201, Trimmer, Tantal, Connector, User IC) | `PARTGROUP_Map.UPDPARTGROUPNAME` | Plaintext group name |
| Editor **Bulk parent profile** (old label «Bulk BASE») | `PROFILE_Det.PARENTPROFILE` | Parent **profile** template (`3301-…`, `_M_…`), not Chip-* |

Join for class name:

`PART_Det.PROFILENAME` → `PROFILE_Det.UPDPARTGROUPID` → `PARTGROUP_Map`.

`UPDPARTGROUPID` alone looks like a code; the name is ordinary Text, not encrypted.

## Confidence and library axes (orthogonal)

- **`PART_Det.CONFIDENCE_LEVEL`** (T-OLP ST): 0 / 10 / 20 / 40. **0 is not MASTER vs STANDART.** In the sample UPD it is mostly `_New*` templates (`LIBRARY_TYPE=0`). Some `_NewC0201` / `_NewR0201` rows are conf 10. There is no `_Trimmer` row; `_NewTrimmer` maps to group `Trimmer`.
- **`PROFILE_Det.LIBRARY_TYPE`**: 0 = working library (majority); 1 = small Inferit-like set (often conf 10).
- **S (vendor standard)**: not a column. Heuristic in VALVET: `PARTNAME` starts with `__` or `[STDVER.` in `PARTDESC`. That set may be empty on a given UPD.

This file does **not** store strings `MASTER` / `STANDART`. Do not invent gold/hollow columns.

## Matching junk

Skip `_New*`, `__` padding, package-only tokens. See `src/machine_library/hanwha_partnames.py`.
