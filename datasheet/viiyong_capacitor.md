# Viiyong MLCC, general purpose

Source: [`src/pn_original/viiyong_capacitor.py`](../src/pn_original/viiyong_capacitor.py)

Datasheet: "Multi-layer Ceramic Chip Capacitor - Product Specification for
General Purpose (Reference Sheet)", V2 dated 2023-11-10 (retrieved 2026-10-04;
local copy under the gitignored `datasheet/pdf/`).

Ordering (section 2 "Part Number System"), 9 fields:

```
(1) V   (2) 226   (3) M   (4) 0402   (5) X5R   (6) 6R3   (7) N   (8) C   (9) T
```

`V226M0402X5R6R3NCT` = 0402, X5R, 22 uF, ±20 %, 6.3 V, Ni-Sn terminal.
The sheet's two printed examples both end in `NCT`/`NAT`, because the thickness
and control codes follow the terminal; a pattern that stopped at `N…T` matched
neither.

Rated voltage accepts the `dRd` decimal (`6R3` → 6.3 V) and a 3-digit V/10 block
(`160` → 16 V), as the other China-vendor catalogues do — not the EIA exponent
form.

## samples

| mpn_or_bom | ctype | expected | path |
| V226M0402X5R6R3NCT | CAP | 0402_22uF_X5R_20%_6.3V | vendor |
| V180J0201C0G500NAT | CAP | 0201_18pF_C0G_5%_50V | vendor |
| V105K0201X5R160NXT | CAP | 0201_1uF_X5R_10%_16V | vendor |
| V475M0805X7R6R3NCT | CAP | 0805_4.7uF_X7R_20%_6.3V | vendor |
| V104K0402Y5V6R3NCT | CAP | 0402_100nF_Y5V_10%_6.3V | vendor |
