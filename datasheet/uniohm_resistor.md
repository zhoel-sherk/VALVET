# UniOhm / Royal-style 0402WG resistors

UniOhm and **RoyalOhm** are the two brands of Uniroyal Electronics Global Co.,
Ltd. (Kunshan, Jiangsu) and share one 14-code ordering procedure; see
[`royalohm_resistor.md`](royalohm_resistor.md) for the code layout. Power (codes
5-6) and tolerance (code 7) are independent fields, and the 11th code of the
resistance field is the power of ten, with `J`=10^-1 `K`=10^-2 `L`=10^-3
`M`=10^-4 `N`=10^-5 `P`=10^-6.

Source: [`src/pn_original/uniohm_resistor.py`](../src/pn_original/uniohm_resistor.py)

Watt in vendor output comes from the MPN watt/size code (not the Clean «W from size» checkbox).

## samples

| mpn_or_bom | ctype | expected | path |
| 0402WGJ0223TCE | RES | 0402_22K_5%_1/16W | vendor |
| 0402WGF3922TCE | RES | 0402_39.2K_1%_1/16W | vendor |
| 0402WGJ0472TCE | RES | 0402_4.7K_5%_1/16W | vendor |
| 0402WGF4991TCE | RES | 0402_4.99K_1%_1/16W | vendor |
| 0402WGJ0000TCE | RES | 0402_0R_5%_1/16W | vendor |
| 0402WGD1002TCE | RES | 0402_10K_0.5%_1/16W | vendor |
| 0402WGG1002TCE | RES | 0402_10K_2%_1/16W | vendor |
| 0402WGF100MTCE | RES | 0402_0.01R_1%_1/16W | vendor |
