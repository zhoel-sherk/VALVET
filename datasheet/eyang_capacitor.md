# Eyang (宇阳) MLCC, general purpose

Source: [`src/pn_original/eyang_capacitor.py`](../src/pn_original/eyang_capacitor.py)

Datasheet: Eyang "Multilayer Ceramic Chip Capacitors for General Purpose"
(retrieved 2026-10-04; local copy under the gitignored `datasheet/pdf/`).

Part number, sections 1-8 of the datasheet's "Part Number System":

```
C + size(4) + temperature characteristic + capacitance(3) + tolerance(1)
  + rated voltage + termination + packaging
C  0402    C0G              120           J         500         N        T
```

- **Temperature characteristics** (1.1): class 1 `C0G`; class 2 `X7R X7T X7S
  X6S X6T X5R`.
- **Size codes** (1.2): `A8A4`(008004) `0105` `0201` `0402` `0603` `0805`
  `1206` `1210`.
- **Rated voltage** (1.4, section 6): DC 2.5 V to 63 V. Codes are a plain V/10
  scaling for the digit forms — `100`=10 V, `160`=16 V, `250`=25 V, `350`=35 V,
  `500`=50 V, `630`=63 V — plus the decimal spellings `4R0`=4.0 V, `2R5`=2.5 V,
  `6R3`=6.3 V. Not an EIA exponent form.
- **Tolerance** (section 5): `F` 1 %, `G` 2 %, `J` 5 %, `K` 10 %, `L` 15 %,
  `M` 20 %, `N` 30 %, plus absolute-pF codes `A`/`B`/`C`/`D`/`P` and the
  asymmetric `S`/`X`/`Y`/`Z`. The absolute and asymmetric codes cannot be
  rendered as a percentage and are deliberately not decoded.

## samples

| mpn_or_bom | ctype | expected | path |
| C0402C0G180J500NTB | CAP | 0402_18pF_C0G_5%_50V | vendor |
| C0402X7R221K500NTB | CAP | 0402_220pF_X7R_10%_50V | vendor |
| C0201X5R334M6R3NTJ | CAP | 0201_330nF_X5R_20%_6.3V | vendor |
| C0402X7T120L250NTB | CAP | 0402_12pF_X7T_15%_25V | vendor |
| C0402X6T105M630NTB | CAP | 0402_1uF_X6T_20%_63V | vendor |
| C0402X7S330K100NTB | CAP | 0402_33pF_X7S_10%_10V | vendor |
| C0402C0G120N500NTB | CAP | 0402_12pF_C0G_30%_50V | vendor |
| C0402C0G120J630NTB | CAP | 0402_12pF_C0G_5%_63V | vendor |
| C0402C0G120J350NTB | CAP | 0402_12pF_C0G_5%_35V | vendor |
| C0402C0G120J2R5NTB | CAP | 0402_12pF_C0G_5%_2.5V | vendor |
