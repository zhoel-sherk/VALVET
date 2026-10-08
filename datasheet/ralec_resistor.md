# Ralec chip resistors

Source: [`src/pn_original/ralec_resistor.py`](../src/pn_original/ralec_resistor.py)

Datasheets: the Ralec "SMD Resistor Components" catalogue 2022 (retrieved
2026-10-04; local copy under the gitignored `datasheet/pdf/`) plus the RTT
thick-film product specification `IE-SP-010`. The catalogue prints an
**"Explanation Of Part Numbers"** section for every series — 69 in total, of
which 23 are the chip-resistor family handled here. Each prints an example part
number plus the size, resistance, tolerance, packing and (where applicable)
extra-field tables. Every row below is one of the catalogue's own printed
examples or a value it states explicitly.

```
RTT  02   100   J  TH
 1   2     3    4  5
prefix size ohm tol packing
```

- **Size** — two digits, Ralec's own code, **not** the inch code: `02` = 0402 and
  `06` = **1206**. Wide-terminal series use a different table: `05`=0508,
  `06`=0612, `18`=1218, `20`=1020, `25`=1225.
- **Resistance** — 3 digits, or 4 in the low-resistance ranges, `R` for the
  decimal point: `100`=10 Ω, `4R7`=4.7 Ω, `000`=jumper, `10R2`=10.2 Ω,
  `1002`=10 kΩ, `0000`=jumper, `R050`=0.05 Ω, `R100`=0.1 Ω, `R240`=0.24 Ω.
- **Tolerance** — `B` ±0.1 %, `C` ±0.25 % (thin film only), `D` ±0.5 %, `F` ±1 %,
  `G` ±2 %, `J` ±5 %.
- **Extra field** — thin-film series carry a TCR letter after the tolerance
  (`RTX021002BDTH`: `B` tolerance, `D` TCR); the FoS-test series carry that
  letter instead (`RST02100JATH`: `J` tolerance, `A` FoS).
- **Packing** — `TH` 2 mm carrier tape, `TP` 4 mm tape, `TE` 4 mm embossed.

## Why each prefix has its own table

The same six characters carry different sizes depending on the series:

```
RTW06100JTP  ->  0612_10R_5%     wide-terminal series, 06 = 0612
RTT06100JTH  ->  1206_10R_5%     standard series,      06 = 1206
```

A single shared size table would attach 1206 to a wide-terminal part, so each
prefix keeps the codes its own catalogue page prints.

Two places where the catalogue contradicts itself, and how each is handled:

- `FTT` page 80 lists only `TP` and `TE` as packing, yet its own printed example
  is `FTT02100JTH`. The example is part of the datasheet, so `TH` is accepted —
  the table on that page is incomplete, not the example wrong.
- `RHW` prints **two conflicting size tables under one prefix**: page 62 gives
  `06`=1206 (high-power low-resistance) and page 64 gives `06`=0612 (wide
  terminal). A part number does not say which product it is, so `RHW` returns
  `None` rather than attach a guessed imperial size.

## Not implemented

- `RAA` / `RTA` / `RSA` / `FTA` / `RTN` — resistor **arrays**, which insert a
  circuit count and a terminal-type field (`RAA02-4D100JTH`). Different structure.
- `LR` / `LRE` / `LRH` / `LRS` and their `-A` automotive variants — the
  **metal-alloy low-ohm and shunt** families. Different structure again
  (`LR2512-21R001F4` = prefix, inch size, terminal count, power, milli-ohm code,
  tolerance, packing), and they use *true inch* sizes where `LR`'s `06` means
  0603 — the opposite of the chip series. Mixing the tables would attach the
  wrong size, so this is a separate pass.

## samples

| mpn_or_bom | ctype | expected | path |
| RTT02100JTH | RES | 0402_10R_5% | vendor |
| RTT02R100FTH | RES | 0402_0.1R_1% | vendor |
| RTT18100JTP | RES | 1812_10R_5% | vendor |
| RTT02000JTH | RES | 0402_0R_5% | vendor |
| RTT024R7FTH | RES | 0402_4.7R_1% | vendor |
| RTT021002FTH | RES | 0402_10K_1% | vendor |
| RTW06100JTP | RES | 0612_10R_5% | vendor |
| RTW06R240FTP | RES | 0612_0.24R_1% | vendor |
| RAW18100JTP | RES | 1218_10R_5% | vendor |
| RAW18R100FTP | RES | 1218_0.1R_1% | vendor |
| RTX021002BDTH | RES | 0402_10K_0.1% | vendor |
| ARTX021002BDTH | RES | 0402_10K_0.1% | vendor |
| RST02100JATH | RES | 0402_10R_5% | vendor |
| AHW25R200FTE | RES | 1225_0.2R_1% | vendor |
| AHH03R050JTP | RES | 0603_0.05R_5% | vendor |
| RAT02100JTH | RES | 0402_10R_5% | vendor |
| RAH06103JTP | RES | 1206_10K_5% | vendor |
| RAR051002FTP | RES | 0805_10K_1% | vendor |
| RAG061000FTP | RES | 1206_100R_1% | vendor |
| RTR011002DTH | RES | 0201_10K_0.5% | vendor |
| RSR051002FTP | RES | 0805_10K_1% | vendor |
| ARST051002FTP | RES | 0805_10K_1% | vendor |
| RAV05100JTP | RES | 0805_10R_5% | vendor |
| RSV03100JTP | RES | 0603_10R_5% | vendor |
| RTV03100JTP | RES | 0603_10R_5% | vendor |
| RTH02100JTH | RES | 0402_10R_5% | vendor |
| RTG05100JTP | RES | 0805_10R_5% | vendor |
| RTG25R100FTE | RES | 2512_0.1R_1% | vendor |
| FTG06100JTP | RES | 1206_10R_5% | vendor |
| FTH06100JTP | RES | 1206_10R_5% | vendor |
| FTT02100JTH | RES | 0402_10R_5% | vendor |
| FTT02R100FTH | RES | 0402_0.1R_1% | vendor |