# Kyocera AVX automotive MLCC — KAM series

Source: [`src/pn_original/kyocera_capacitor.py`](../src/pn_original/kyocera_capacitor.py),
from `doc/info/Kyocera_KAM_Series.pdf` ("HOW TO ORDER", p.1).

## field positions

`KAM` + size(2) + thickness(1) + dielectric(2) + voltage(2) + capacitance(3) + tolerance(1) + packaging(1)

| positions | field | example |
|---|---|---|
| 0-2 | series (`KAM`) | KAM |
| 3-4 | size | `31` = 1206, `15` = 0603 |
| 5 | thickness | not cleaned |
| 6-7 | dielectric | `R7` = X7R, `CG` = C0G |
| 8-9 | rated voltage | `1H` = 50V, `2J` = 630V |
| 10-12 | capacitance | `475` = 4.7uF, `1R5` = 1.5pF |
| 13 | capacitance tolerance | `K` = ±10%, `C` = ±0.25pF |
| 14 | packaging | not cleaned |

Every part number is 15 characters, so the spans are fixed.

Two things in the order block read like more than they are:

- **`0G` is a voltage code (4 V), not a dielectric.** It sits immediately to the
  right of `CG` in the same printed row and looks like an eighth entry in the
  dielectric list.
- **No X5R code is printed.** `R5` is not accepted.

`NP0` is listed as a KAM product line but the sheet never prints an order code
for it, so it is not claimed. `KAF` is the FLEXITERM series, a different
catalogue, and is likewise not claimed.

`CG` is the sheet's symbol for C0G and normalises to `C0G`, as every other codec
here does. The absolute class-1 grades `B`/`C`/`D` render as a bare pF magnitude.

The sheet prints each size both ways; the repo's vocabulary is the inch name:

| code | inch | metric (mm) |
|---|---|---|
| 03 | 0201 | 0603 |
| 05 | 0402 | 1005 |
| 15 | 0603 | 1608 |
| 21 | 0805 | 2012 |
| 31 | 1206 | 3216 |
| 32 | 1210 | 3225 |
| 42 | 1808 | 4520 |
| 43 | 1812 | 4532 |
| 55 | 2220 | 5750 |

`15` = 0603 is Kyocera's JIS code, so a codec assuming EIA digits here would
misread it as an unknown size.

## samples

All rows are real `KAM` part numbers printed in this sheet. `expected` is derived
from the field tables above, not from the parser.

| mpn_or_bom | ctype | expected | path |
| KAM03CT70J105KH | CAP | 0201_1uF_6.3V_X7T_10% | vendor |
| KAM05ACG1H0R5CH | CAP | 0402_0.5pF_50V_C0G_0.25pF | vendor |
| KAM05ACG1H390JH | CAP | 0402_39pF_50V_C0G_5% | vendor |
| KAM05AR71C103JH | CAP | 0402_10nF_16V_X7R_5% | vendor |
| KAM05AR71H561JH | CAP | 0402_560pF_50V_X7R_5% | vendor |
| KAM05CT70J225KH | CAP | 0402_2.2uF_6.3V_X7T_10% | vendor |
| KAM05CT70J475KH | CAP | 0402_4.7uF_6.3V_X7T_10% | vendor |
| KAM15ACG1E103JT | CAP | 0603_10nF_25V_C0G_5% | vendor |
| KAM15BR71E224KT | CAP | 0603_220nF_25V_X7R_10% | vendor |
| KAM15CT70J106KT | CAP | 0603_10uF_6.3V_X7T_10% | vendor |
| KAM15CT70J226KT | CAP | 0603_22uF_6.3V_X7T_10% | vendor |
| KAM21AT70J226KU | CAP | 0805_22uF_6.3V_X7T_10% | vendor |
| KAM21KR71H225KU | CAP | 0805_2.2uF_50V_X7R_10% | vendor |
| KAM31GCG2J103JU | CAP | 1206_10nF_630V_C0G_5% | vendor |
| KAM31GR71C106KU | CAP | 1206_10uF_16V_X7R_10% | vendor |
| KAM32LCG2J223JU | CAP | 1210_22nF_630V_C0G_5% | vendor |
| KAM32LCG3A103JU | CAP | 1210_10nF_1000V_C0G_5% | vendor |
| KAM32HR73A332KU | CAP | 1210_3.3nF_1000V_X7R_10% | vendor |
| KAM32LL81E106KU | CAP | 1210_10uF_25V_X8L_10% | vendor |
| KAM32LL81H475KU | CAP | 1210_4.7uF_50V_X8L_10% | vendor |

The sheet's own worked example is `KAM 31 G R7 1H 475 K U`
(`KAM31GR71H475KU` → `1206_4.7uF_50V_X7R_10%`), which is pinned separately in
`tests/test_pn_vendor_kyocera_tdk.py`.