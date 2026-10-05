# Murata GRM MLCC

Source: [`src/pn_original/murata_capacitor.py`](../src/pn_original/murata_capacitor.py)

## samples

| mpn_or_bom | ctype | expected | path |
| GRM1555C1H100JA01D | CAP | 0402_10pF_50V_C0G_5% | vendor |
| GRM155R71C104KA88D | CAP | 0402_100nF_6.3V_X7R_10% | vendor |
| GRM188R71H102KA01D | CAP | 0603_1nF_50V_X7R_10% | vendor |
| GRM188R6YA106MA73D | CAP | 0603_10uF_35V_X5R_20% | vendor |
| GRM155R61C105KA12D | CAP | 0402_1uF_6.3V_X5R_10% | vendor |
| GRM188R6YA475KE15J | CAP | 0603_4.7uF_35V_X5R_10% | vendor |
| GRM188R61A106MA73D | CAP | 0603_10uF_10V_X5R_20% | vendor |
| GRM188R60H106MA73D | CAP | 0603_10uF_50V_X5R_20% | vendor |

## Rated voltage codes

Source: Murata datasheet **C02E21**, "Chip Multilayer Ceramic Capacitors for
General", section 6 "Rated Voltage". These are the published two-character codes
and they are what `_VOLT_2CH` in the parser mirrors verbatim:

| code | voltage | | code | voltage | | code | voltage |
|---|---|---|---|---|---|---|---|
| 0E | 2.5V | | 2A | 100V | | 3F | 3.15kV |
| 0G | 4V | | 2D | 200V | | BB | 350V |
| 0J | 6.3V | | 2E | 250V | | E2 | AC250V |
| 1A | 10V | | 2W | 450V | | GB | Y3 AC250V |
| 1C | 16V | | 2H | 500V | | GD | Y2/X1/Y2 AC250V |
| 1E | 25V | | 2J | 630V | | GF | X2 AC250V |
| 1H | 50V | | 3A | 1kV | | **YA** | **35V** |
| 1J | 63V | | 3D | 2kV | | | |
| 1K | 80V | | | | | | |

`YA = DC35V` is the entry that confirms the R6Y line
(`GRM188R6YA106MA73D` = 0603 10 uF 35 V X5R +/-20 %), and it is why the
voltage field for this family cannot be expressed in a one-character map.

Field order for this numbering:

```
GR  M  188  8  R6  YA  106  M  A73  D
1   2  3    4  5   6   7    8  9   suffix
product  size dim series VOL cap tol spec
```

Series codes in this table are the temperature-characteristic codes
(R6 = X5R, R7 = X7R), so the pair following them is the voltage field.
Safety-standard types (E2/GB/GD/GF) are AC 250V certified parts and are not
general-purpose GRM line parts.
