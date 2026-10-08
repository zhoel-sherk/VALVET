# Darfon (达方) MLCC, general purpose

Source: [`src/pn_original/darfon_capacitor.py`](../src/pn_original/darfon_capacitor.py)

Datasheet: Darfon "MLCC Catalogue / General Purpose", Rev. 202510 (retrieved
2026-10-04; local copy under the gitignored `datasheet/pdf/`), section
"Ordering Code":

```
C  1005  NP0  101  J  G  T  S  △
1   2    3    4    5  6  7  8  9
```

- **Size** is written either way round — the datasheet prints
  `0402(01005) 0603(0201) 1005(0402) 1608(0603) 2012(0805) 3216(1206)
  3225(1210) 4520(1808) 4532(1812)` — so both the EIA and the metric spelling
  are accepted and mapped.
- **T.C.** is three characters: `NP0` (class 1) plus `X8G X8R X7R X7S X7T X7U
  X6S X6T X5R`. `Y5V` is not in this catalogue.
- **Capacitance**: first two digits significant, third is the power of ten,
  except `9` = 1.0-9.9 pF and `8` = 0.20-0.99 pF (exponents -1 and -2).
- **Tolerance**: `A` ±0.05 pF, `B` ±0.1 pF, `C` ±0.25 pF, `D` ±0.5 pF
  (absolute, class 1) and `F` 1 %, `G` 2 %, `J` 5 %, `K` 10 %, `M` 20 %.
- **Voltage** is a single **letter**: `T` 2.5 V, `B` 4 V, `C` 6.3 V, `D` 10 V,
  `E` 16 V, `F` 25 V, `N` 35 V, `G` 50 V, `H` 100 V, `J` 200 V, `K` 250 V,
  `L` 500 V, `M` 630 V, `P` 1 kV, `Q` 2 kV, `R` 3 kV, `S` 4 kV.
- Packaging (7), application code (8) and thickness (9) are not part of the
  cleaned value.

All sample rows are part numbers printed in the catalogue's own tables.

## samples

| mpn_or_bom | ctype | expected | path |
| C0603NP0240JGT | CAP | 0201_24pF_C0G_5%_50V | vendor |
| C0603NP0201JGT | CAP | 0201_200pF_C0G_5%_50V | vendor |
| C0603NP0201JFT | CAP | 0201_200pF_C0G_5%_25V | vendor |
| C0603NP0271JGT | CAP | 0201_270pF_C0G_5%_50V | vendor |
| C0603NP0430JGT | CAP | 0201_43pF_C0G_5%_50V | vendor |
| C1005NP0508CGTS | CAP | 0402_0.5pF_C0G_0.25pF_50V | vendor |
| C0603X5R475MTT | CAP | 0201_4.7uF_X5R_20%_2.5V | vendor |
| C0603X5R155MBT | CAP | 0201_1.5uF_X5R_20%_4V | vendor |
| C0603X5R101KCT | CAP | 0201_100pF_X5R_10%_6.3V | vendor |
| C0603X5R182KDT | CAP | 0201_1.8nF_X5R_10%_10V | vendor |
| C0603X5R105MET | CAP | 0201_1uF_X5R_20%_16V | vendor |
| C0603X5R101KFT | CAP | 0201_100pF_X5R_10%_25V | vendor |
| C1005X5R224KNT | CAP | 0402_220nF_X5R_10%_35V | vendor |
| C0603X5R103KGT | CAP | 0201_10nF_X5R_10%_50V | vendor |
