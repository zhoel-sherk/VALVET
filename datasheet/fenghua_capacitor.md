# Fenghua (风华) MLCC

Source: [`src/pn_original/fenghua_capacitor.py`](../src/pn_original/fenghua_capacitor.py)

Datasheets: Fenghua "Multilayer Ceramic Capacitors – X7R" and "MLCC – NPO (COG)"
(retrieved 2026-10-04; local copies under the gitignored `datasheet/pdf/`).

Ordering, 7 fields:

```
A size(4)  B dielectric  C capacitance  D tolerance  E rated voltage  F termination  G packaging
0805       B              104            K             500             N             T
```

- **Dielectric** is a code: `CG`/`COG` class 1, `B` X7R, `X` X5R.
- **Capacitance** three EIA digits or an `R`-decimal (`0R5` = 0.5 pF, `1R0` = 1 pF).
- **Tolerance** `B` ±0.10 pF, `C` ±0.25 pF, `D` ±0.5 pF (absolute, class 1),
  `F` 1 %, `G` 2 %, `J` 5 %, `K` 10 %, `M` 20 %, `S` +50 %/−20 %.
- **Rated voltage** is the EIA mantissa-exponent code: `160`=16 V, `250`=25 V,
  `500`=50 V, `630`=63 V, `101`=100 V, `201`=200 V, `501`=500 V, `102`=1 kV,
  `202`=2 kV. This is **not** the V/10 form Eyang/TCC/Darfon/Viiyong use; the
  two agree only on codes ending in 0.
- **Rated voltage** also accepts the decimal spelling `4R0`=4 V, `6R3`=6.3 V.
  The table above is the sheet's own form, but this vendor prints the decimal
  one too, and it is the form the Walsin/Eyang/Viiyong catalogues use. Without
  it, an `…X…K6R3NT` part matched no codec at all (see below).
- **Termination + packaging** `N`/`S` and `T`/`B`.

The `B`/`X`/`CG` bodies are shared with the Walsin MLCC lines, but the two
vendors do not overlap on endings: Walsin's catalogue gives termination
`L`=Ag/Ni/Sn, `C`=Cu/Ni/Sn and `P`=Cu/polymer, while this sheet gives `N` and
`S`. Walsin therefore refuses `NT` on both datasheet grounds and this codec
owns that ending outright, whatever the `PARSER_PRIORITY` order. The two agree
on `ST`.

## samples

| mpn_or_bom | ctype | expected | path |
| 0402CG101J500NT | CAP | 0402_100pF_C0G_5%_50V | vendor |
| 0402B223K250NT | CAP | 0402_22nF_X7R_10%_25V | vendor |
| 0805B104K500NT | CAP | 0805_100nF_X7R_10%_50V | vendor |
| 0402X104M101NT | CAP | 0402_100nF_X5R_20%_100V | vendor |
| 0805COG102J630SB | CAP | 0805_1nF_C0G_5%_63V | vendor |
| 0402CG1R0B160SB | CAP | 0402_1pF_C0G_0.1pF_16V | vendor |
| 0805CG102M501NT | CAP | 0805_1nF_C0G_20%_500V | vendor |
| 0805CG102M202NT | CAP | 0805_1nF_C0G_20%_2000V | vendor |
| 0402B101S630NT | CAP | 0402_100pF_X7R_+50%/-20%_63V | vendor |
| 0805B201M101NT | CAP | 0805_200pF_X7R_20%_100V | vendor |
| 0201X104K6R3NT | CAP | 0201_100nF_X5R_10%_6.3V | vendor |
| 0805X475M6R3NT | CAP | 0805_4.7uF_X5R_20%_6.3V | vendor |
