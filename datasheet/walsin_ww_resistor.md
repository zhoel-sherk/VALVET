# Walsin WW current-sense / low-ohm

Source: [`src/pn_original/walsin_ww_resistor.py`](../src/pn_original/walsin_ww_resistor.py)

Datasheets: the Walsin WW approval sheets (retrieved 2026-10-04; local copies
under the gitignored `datasheet/pdf/`). Each prints a **CATALOGUE NUMBERS**
section with the full field breakdown, e.g. `WW25N_V16`:

```
WW25  N   R005  J  T  L
size  type  ohm  tol pack term
```

- **Size code**, stated per sheet: `WW10` = 1210, `WW20` = 2010, `WW25` = 2512,
  `WW06` = 0603.
- **Type code**: `N` 2 W sensing, `X` thick film, `R` metal low-ohm power, plus
  `A`/`B`/`P`/`D`/`W`.
- **Resistance code**: "R is first digit followed by 3 significant digits" —
  `R010` = 0.010 Ω, `R005` = 0.005 Ω, `R100` = 0.1 Ω, `R976` = 0.976 Ω.
- **Tolerance**: `J` ±5 %, `F` ±1 %.
- **Packaging / termination**: `T` 7" reeled taping, `L` Sn-base lead-free.

All rows below are part numbers printed in the sheets' own catalogue sections.

`WW12` is **deliberately not decoded**: `WW12R.PDF` states `WW12: 0603` while
`WW12R_V.PDF` states `WW12: 1206`. The two sheets contradict each other, so the
codec returns `None` rather than attach a guessed imperial size to a
current-sense resistor. The `WW…C` family (0201…1206, no separate type letter)
is likewise not decoded — its sheets print no type code.

## samples

| mpn_or_bom | ctype | expected | path |
| WW06RR005JTLS | RES | 0603_0.005R_5% | vendor |
| WW10XR100JTLS | RES | 1210_0.1R_5% | vendor |
| WW10PR500JTLS | RES | 1210_0.5R_5% | vendor |
| WW20NR005JTLS | RES | 2010_0.005R_5% | vendor |
| WW20PR100JTLJS | RES | 2010_0.1R_5% | vendor |
| WW25NR005JTLS | RES | 2512_0.005R_5% | vendor |
| WW25AR005JTLS | RES | 2512_0.005R_5% | vendor |
| WW25BR005FTLS | RES | 2512_0.005R_1% | vendor |
| WW25RR050FTL | RES | 2512_0.05R_1% | vendor |
| WW08RR000FTL | RES | 0805_0R_1% | vendor |
