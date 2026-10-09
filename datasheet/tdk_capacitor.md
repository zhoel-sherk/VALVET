# TDK automotive MLCC — CGA series

Source: [`src/pn_original/tdk_capacitor.py`](../src/pn_original/tdk_capacitor.py),
from `doc/info/TDK_mlcc_automotive_general_en.pdf` (automotive grade, general,
**up to 75 V**, June 2019).

## field positions

`CGA` + size(1) + thickness(1) + undecoded(1) + dielectric(3) + voltage(2) + capacitance(3) + tolerance(1) + dimension(3) + packaging(2)

Every part number in the catalogue is exactly 20 characters, which is what makes
the spans unambiguous.

| positions | field | example |
|---|---|---|
| 0-3 | series + size | `CGA1` = 0201, `CGA5` = 1206 |
| 4 | thickness | not cleaned |
| 5 | undecoded | not cleaned |
| 6-8 | dielectric (spelled in full) | `C0G`, `X7R`, `X5R`, `X7S`, `X7T` |
| 9-10 | rated voltage | `1H` = 50V, `1V` = 35V, `1N` = 75V |
| 11-13 | capacitance | `104` = 100nF, `1R5` = 1.5pF |
| 14 | capacitance tolerance | `K` = ±10%, `C` = ±0.25pF |
| 15-17 | dimension (mm ×10) | not cleaned |
| 18-19 | packaging | not cleaned |

The size table is printed on p.1 as *Dimensions code: JIS[EIA]*:

| code | metric (mm) | inch | repo name |
|---|---|---|---|
| CGA1 | 0603 | 0201 | 0201 |
| CGA2 | 1005 | 0402 | 0402 |
| CGA3 | 1608 | 0603 | 0603 |
| CGA4 | 2012 | 0805 | 0805 |
| CGA5 | 3216 | 1206 | 1206 |
| CGA6 | 3225 | 1210 | 1210 |
| CGA8 | 4532 | 1812 | 1812 |
| CGA9 | 5750 | 2220 | 2220 |

There is no `CGA7`. The repo's vocabulary is the inch name, so that is the one
used.

Rated voltage is a decade digit plus a decade character. The eight codes below
are every code this document prints, because it is scoped to 75 V and under —
**a 100 V-or-higher TDK part is not claimed here**, and would need the
full-range sheet:

`0G`=4 V, `0J`=6.3 V, `1A`=10 V, `1C`=16 V, `1E`=25 V, `1H`=50 V, `1V`=35 V,
`1N`=75 V.

Unlike Kyocera, TDK spells the dielectric out in the part number itself, so it
is read as written rather than from an abbreviation table.

## samples

Real `CGA` part numbers printed in this catalogue. `expected` is derived from
the field tables above, not from the parser. All 898 distinct part numbers in
the document decode; these rows cover every size × dielectric bucket at its
lowest and highest rated voltage.

| mpn_or_bom | ctype | expected | path |
| CGA1A2C0G1E010C030BA | CAP | 0201_1pF_25V_C0G_0.25pF | vendor |
| CGA1A2C0G1H101J030BA | CAP | 0201_100pF_50V_C0G_5% | vendor |
| CGA2B2C0G1H010C050BA | CAP | 0402_1pF_50V_C0G_0.25pF | vendor |
| CGA2B2C0G1H102J050BA | CAP | 0402_1nF_50V_C0G_5% | vendor |
| CGA3E2C0G1H010C080AA | CAP | 0603_1pF_50V_C0G_0.25pF | vendor |
| CGA3E2C0G1H103J080AA | CAP | 0603_10nF_50V_C0G_5% | vendor |
| CGA4C2C0G1H102J060AA | CAP | 0805_1nF_50V_C0G_5% | vendor |
| CGA4J2C0G1H333J125AA | CAP | 0805_33nF_50V_C0G_5% | vendor |
| CGA5C2C0G1H472J060AA | CAP | 1206_4.7nF_50V_C0G_5% | vendor |
| CGA5L2C0G1H104J160AA | CAP | 1206_100nF_50V_C0G_5% | vendor |
| CGA6J2C0G1H223J125AA | CAP | 1210_22nF_50V_C0G_5% | vendor |
| CGA6P2C0G1H104J250AA | CAP | 1210_100nF_50V_C0G_5% | vendor |
| CGA8L2C0G1H473J160KA | CAP | 1812_47nF_50V_C0G_5% | vendor |
| CGA8R2C0G1H224J320KA | CAP | 1812_220nF_50V_C0G_5% | vendor |
| CGA2B2X5R1A104K050BA | CAP | 0402_100nF_10V_X5R_10% | vendor |
| CGA2B3X5R1V104M050BB | CAP | 0402_100nF_35V_X5R_20% | vendor |
| CGA3E3X5R0J335K080AB | CAP | 0603_3.3uF_6.3V_X5R_10% | vendor |
| CGA3E3X5R1V105M080AB | CAP | 0603_1uF_35V_X5R_20% | vendor |
| CGA4J2X5R1A155K125AA | CAP | 0805_1.5uF_10V_X5R_10% | vendor |
| CGA4J3X5R1V475M125AB | CAP | 0805_4.7uF_35V_X5R_20% | vendor |
| CGA5L2X5R1C475K160AA | CAP | 1206_4.7uF_16V_X5R_10% | vendor |
| CGA5L3X5R1V106M160AB | CAP | 1206_10uF_35V_X5R_20% | vendor |
| CGA1A2X7R0J103K030BA | CAP | 0201_10nF_6.3V_X7R_10% | vendor |
| CGA1A2X7R1H471M030BA | CAP | 0201_470pF_50V_X7R_20% | vendor |
| CGA2B3X7R0J154K050BB | CAP | 0402_150nF_6.3V_X7R_10% | vendor |
| CGA2B1X7R1V224M050BC | CAP | 0402_220nF_35V_X7R_20% | vendor |
| CGA3E1X7R0J155K080AC | CAP | 0603_1.5uF_6.3V_X7R_10% | vendor |
| CGA3E1X7R1V105M080AC | CAP | 0603_1uF_35V_X7R_20% | vendor |
| CGA4J1X7R0J685K125AC | CAP | 0805_6.8uF_6.3V_X7R_10% | vendor |
| CGA4J1X7R1V475M125AC | CAP | 0805_4.7uF_35V_X7R_20% | vendor |
| CGA5L1X7R0J226M160AC | CAP | 1206_22uF_6.3V_X7R_20% | vendor |
| CGA5L1X7R1V106M160AC | CAP | 1206_10uF_35V_X7R_20% | vendor |
| CGA6M3X7R1C106K200AB | CAP | 1210_10uF_16V_X7R_10% | vendor |
| CGA6P1X7R1N106M250AC | CAP | 1210_10uF_75V_X7R_20% | vendor |
| CGA8N3X7R1C226M230KB | CAP | 1812_22uF_16V_X7R_20% | vendor |
| CGA8P3X7R1H685K250KB | CAP | 1812_6.8uF_50V_X7R_10% | vendor |
| CGA9N3X7R1C476M230KB | CAP | 2220_47uF_16V_X7R_20% | vendor |
| CGA9P3X7R1H226M250KB | CAP | 2220_22uF_50V_X7R_20% | vendor |
| CGA2B3X7S1A334K050BB | CAP | 0402_330nF_10V_X7S_10% | vendor |
| CGA2B1X7S1C474M050BC | CAP | 0402_470nF_16V_X7S_20% | vendor |
| CGA3E1X7S0G106M080AC | CAP | 0603_10uF_4V_X7S_20% | vendor |
| CGA3E1X7S1C225M080AC | CAP | 0603_2.2uF_16V_X7S_20% | vendor |
| CGA6P1X7S0J336M250AC | CAP | 1210_33uF_6.3V_X7S_20% | vendor |
| CGA6P3X7S1H106M250AB | CAP | 1210_10uF_50V_X7S_20% | vendor |
| CGA4J3X7S1A685K125AB | CAP | 0805_6.8uF_10V_X7S_10% | vendor |
| CGA4J1X7S1E106K125AC | CAP | 0805_10uF_25V_X7S_10% | vendor |
| CGA5L1X7S1A156M160AC | CAP | 1206_15uF_10V_X7S_20% | vendor |
| CGA5L1X7S1A226M160AC | CAP | 1206_22uF_10V_X7S_20% | vendor |
| CGA1A1X7T0G104M030BC | CAP | 0201_100nF_4V_X7T_20% | vendor |
| CGA3E1X7T0G106M080AC | CAP | 0603_10uF_4V_X7T_20% | vendor |