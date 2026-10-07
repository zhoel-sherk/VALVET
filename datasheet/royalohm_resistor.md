# Royal Ohm

RoyalOhm is one of the two brands of **Uniroyal Electronics Global Co., Ltd.**
(Kunshan, Jiangsu) - the other is UniOhm - and both use the same 14-code
ordering procedure, so both codecs mirror this one datasheet.

Source: [`src/pn_original/royalohm_resistor.py`](../src/pn_original/royalohm_resistor.py)

Datasheet layout (codes 1-14): size(4) + power(2) + tolerance(1) + resistance(4)
+ packaging(3). Power and tolerance are **independent** fields, and the 11th
code of the resistance field is the power of ten: digits 0-6 mean 10^0..10^6 and
`J`=10^-1 `K`=10^-2 `L`=10^-3 `M`=10^-4 `N`=10^-5 `P`=10^-6.

## samples

| mpn_or_bom | ctype | expected | path |
| 0603WAF220KT5E | RES | 0603_2.2R_1%_1/10W | vendor |
| 0402WGF100JTCE | RES | 0402_10R_1%_1/16W | vendor |
| 0402WGF1004TCE | RES | 0402_1M_1%_1/16W | vendor |
| 0805W8J472JTCE | RES | 0805_47.2R_5%_1/8W | vendor |
| 1206W4F220JTCE | RES | 1206_22R_1%_1/4W | vendor |
| 0805W8J0103T5E | RES | 0805_10K_5%_1/8W | vendor |
| 0402WGD1002TCE | RES | 0402_10K_0.5%_1/16W | vendor |
| 0402WGG1002TCE | RES | 0402_10K_2%_1/16W | vendor |
| 0603WAD1001T5E | RES | 0603_1K_0.5%_1/10W | vendor |
| 0402WGF100MTCE | RES | 0402_0.01R_1%_1/16W | vendor |
