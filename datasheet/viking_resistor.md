# Viking Tech ARG series thin film chip resistor

Source: [`src/pn_original/viking_resistor.py`](../src/pn_original/viking_resistor.py)

Datasheet: "Thin Film Chip Resistor (ARG Series)", REV.A6 dated 2022-01-22
(retrieved 2026-10-04; local copy under the gitignored `datasheet/pdf/`).

Ordering: `ARG` + size(2) + tolerance(1) + resistance(4) + TCR(1) + packaging(1).
Size codes are the inch-equivalent pair from the datasheet table
(`ARG02`=0402, `ARG03`=0603, `ARG05`=0805, `ARG06`=1206), so they need mapping
rather than reading as an EIA code. Tolerance B/C/D/F = ±0.1/0.25/0.5/1 %,
TCR C/D = ±25/50 ppm, packaging T=tape&reel / B=bulk. Resistance is four digits
with three significant figures plus a power of ten; sub-ohm values use the
`R`-decimal spelling the datasheet's own marking table shows (`4R70` = 4.7 Ω).

## samples

| mpn_or_bom | ctype | expected | path |
| ARG03C1002DT | RES | 0603_10K_0.25%_50ppm | vendor |
| ARG02F1001CT | RES | 0402_1K_1%_25ppm | vendor |
| ARG06D4R70CT | RES | 1206_4.7R_0.5%_25ppm | vendor |
| ARG05B0010CB | RES | 0805_1R_0.1%_25ppm | vendor |
| ARG05F1004DT | RES | 0805_1M_1%_50ppm | vendor |
