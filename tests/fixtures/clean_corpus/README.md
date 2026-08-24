# Clean BOM golden corpus

Regression strings for `clean_one()` — used by `tools/clean_corpus.py` and `tests/test_clean_corpus_golden.py`.

## Primary source (curated)

Operator-maintained SMT list: **`user_temp/component_test.xlsx`** (~1600+ rows).

Default import uses **join-mode**: first **3 columns** merged with ` | ` (same as Clean BOM «Double Comment»), e.g. `FERRITE BEAD… | VENDOR/MPN`.

```powershell
$env:PYTHONPATH='src'
python tools/clean_corpus.py import-curated --draft --golden
# single column only:  python tools/clean_corpus.py import-curated --no-join-mode ...
```

This writes `manifest.jsonl`, runs `clean_one` into `draft.xlsx`, and bootstraps **`golden.xlsx`** (`status=wip`, `notes` remind to review). Edit `expected_*` in Excel, set `status=ok`, then `python tools/clean_corpus.py test`.

Legacy auto-harvest from mixed BOM files under `user_temp/` (noisy) remains as `harvest` — prefer **import-curated** for the golden set.

## Files

| File | Role |
|------|------|
| `profile.json` | Frozen `CleanConfig` |
| `hanwha_partnames_cl40.json` | Hanwha PARTNAME snapshot (ICs/specials, no chip R/C) |
| **`golden.xlsx`** | Expected output per row (`status=ok` rows are tested) |
| `draft.xlsx` | Latest `clean_one` on manifest |
| `manifest.jsonl` | Import/harvest manifest |

## Hanwha snapshot

```powershell
python tools/clean_corpus.py mdb-export --mdb examples/UPD.MDB
```

## Validate

```powershell
python tools/clean_corpus.py test
python tools/clean_corpus.py report
pytest tests/test_clean_corpus_golden.py -q
```

## Environment

- `BOOMER_CLEAN_CORPUS_GOLDEN` — alternate golden path
- `BOOMER_CLEAN_CORPUS_PROFILE` — alternate profile

## Manual golden review (operator)

After regenerating draft, review these themes before setting `status=ok` (parser fixes leave semantics to you):

- Walsin 0Ω tolerance vs BOM `1%` on JUMP / `0 OHM` rows
- NETRES incomplete cleans (value+tol without package)
- CAP package dropped from cleaned while BOM has 0402/0603
- HV CAP nearly empty (e.g. only `X7R_10%`)
- `PL_*` inductor join mangling
- POSCAP: case size `3528/B` vs Sanyo/Panasonic MPN
- Sunlord `SDNT*` thermistor (hanwha vs dedicated series)

Ferrite rows should show `type_auto=FERRITE_BEAD` with cleaned = original MPN.
