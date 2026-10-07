# Walsin MLCC

Source: [`src/pn_original/walsin_mlcc_capacitor.py`](../src/pn_original/walsin_mlcc_capacitor.py)

Datasheet: Walsin "MLCC Product Catalog" (retrieved 2026-10-04; local copy under
the gitignored `datasheet/pdf/`), page "How To Order and Packaging
Dimension/Quantity". The catalogue gives **one** scheme for everything:

```
0805   B    104   K   500   C   T
size  diel  cap  tol  volt  term  pack
```

- **Size** (inch): `01R5` 0201 0402 0603 0805 1206 1210 1808 1812 1825 2220 2225.
- **Dielectric**, one letter: `N`=NP0, `G`=X8G, `R`=X8R, `B`=X7R, `A`=X7S,
  `S`=X6S, `X`=X5R, `F`=Y5V.
- **Capacitance**: two significant digits plus a zero count, `R` for the decimal
  point — `R47`=0.47 pF, `0R5`=0.5 pF, `1R0`=1 pF, `100`=10 pF, `104`=0.1 µF,
  `107`=100 µF.
- **Tolerance**: `A` ±0.05 pF, `B` ±0.1 pF, `C` ±0.25 pF, `D` ±0.5 pF (absolute,
  class 1) and `F` 1 %, `G` 2 %, `J` 5 %, `K` 10 %, `M` 20 %, `Z` −20 %/+80 %.
- **Voltage**: `4R0`=4 V, `6R3`=6.3 V, then EIA mantissa-exponent — `100`=10 V,
  `500`=50 V, `101`=100 V, `631`=630 V, `102`=1 kV, `302`=3 kV. **Not** the V/10
  form the other China-vendor catalogues use.
- **Termination + packaging**: `C` = Ni/Sn lead-free, then `T` 7" / `Q` 10" /
  `G` 13" reel. Validated but not part of the cleaned value.

`CG` is **not** a Walsin dielectric code — it is Fenghua's class-1 spelling, and
Walsin's own class-1 letter is `N`. Walsin's `B`/`X`/`CG` bodies therefore
overlap Fenghua's, so a `…NT` part can be claimed by either codec; Walsin has the
higher `PARSER_PRIORITY` (65 vs 86 in the registry's ordering — see the note in
`walsin_wr_resistor.md`) but no longer claims `CG` at all, so those rows live in
[`fenghua_capacitor.md`](fenghua_capacitor.md).

## samples

| mpn_or_bom | ctype | expected | path |
| 0402N100J500CT | CAP | 0402_10pF_C0G_50V_5% | vendor |
| 0402B101K500CT | CAP | 0402_100pF_X7R_50V_10% | vendor |
| 0402B102K500CT | CAP | 0402_1nF_X7R_50V_10% | vendor |
| 0805X475M6R3CT | CAP | 0805_4.7uF_X5R_6.3V_20% | vendor |
| 1206X106K250CT | CAP | 1206_10uF_X5R_25V_10% | vendor |
| 0805G104K500CT | CAP | 0805_100nF_X8G_50V_10% | vendor |
| 0805R106M631CT | CAP | 0805_10uF_X8R_630V_20% | vendor |
| 0805A104D500CT | CAP | 0805_100nF_X7S_50V_0.5pF | vendor |
| 0805S105K6R3CT | CAP | 0805_1uF_X6S_6.3V_10% | vendor |
| 0805F104Z500CT | CAP | 0805_100nF_Y5V_50V_-20%/+80% | vendor |
| 1206B471K202CT | CAP | 1206_470pF_X7R_2000V_10% | vendor |
| 0402N1R0B500CT | CAP | 0402_1pF_C0G_50V_0.1pF | vendor |
