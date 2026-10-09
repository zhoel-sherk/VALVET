# Walsin WR thick-film resistors

Source: [`src/pn_original/walsin_wr_resistor.py`](../src/pn_original/walsin_wr_resistor.py)
PDF: https://www.passivecomponent.com/ — WR/WF guides.

## size_map

Read off the "Size code" row of each catalogue's own table. The two series
numbers are *not* ordered by size, which is why `10` is a 1210 and `12` is a
1206 — assuming monotonicity here is what produced the wrong-body bug.

`ASC_WR_TR_V07`, p.3 and p.5:

| pn | inch | mm |
| 04 | 0402 | 1005 |
| 06 | 0603 | 1608 |
| 08 | 0805 | 2012 |
| 10 | 1210 | 3225 |
| 12 | 1206 | 3216 |

`WR18-20-25X(W)_V14`, p.3 and p.5:

| pn | inch | mm |
| 18 | 1218 | 3248 |
| 20 | 2010 | 5025 |
| 25 | 2512 | 6432 |

`02` is in neither sheet, but it is not invented either: the CO1271 production
corpus carries `WR02X3301FTL` with the description `RES_3K3 ±1%_1/20W_R0201_SMD`
and the jumper `WR02X000 PAL` with `RES 0 OHM 1/20W (0201) 1%`. A 0201-specific
sheet is simply not in the local set.

## tolerance

| letter | pct |
| F | 1% |
| J | 5% |

`P` is a jumper and carries no percentage — see the `WR08X000PTL` row.

## samples

| mpn_or_bom | ctype | expected | path |
| WR04X1001FTL | RES | 0402_1K_1% | vendor |
| WR04X68R0FTL | RES | 0402_68R_1% | vendor |
| WR04X6201FTL | RES | 0402_6.2K_1% | vendor |
| WR04X2491FTL | RES | 0402_2.49K_1% | vendor |
| WR06X472JTL | RES | 0603_4.7K_5% | vendor |
| WR10X1001FTL | RES | 1210_1K_1% | vendor |
| WR12X1001FTL | RES | 1206_1K_1% | vendor |
| WR18X472JTL | RES | 1218_4.7K_5% | vendor |
| WR20X472JTL | RES | 2010_4.7K_5% | vendor |
| WR25X1001FTL | RES | 2512_1K_1% | vendor |
| WR06X4754FTL | RES | 0603_4.75M_1% | vendor |
| WR06X4R70FTL | RES | 0603_4.7R_1% | vendor |
| WR08X000PTL | RES | 0805_0R | vendor |
