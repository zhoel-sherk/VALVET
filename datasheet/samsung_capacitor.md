# Samsung CL MLCC

Source: [`src/pn_original/samsung_capacitor.py`](../src/pn_original/samsung_capacitor.py)

## samples

| mpn_or_bom | ctype | expected | path |
| CL05A105KA5NQNC | CAP | 0402_1uF_25V_X5R_10% | vendor |
| CL05A105KQ5NNNC | CAP | 0402_1uF_6.3V_X5R_10% | vendor |
| CL05A225MQ5NSNC | CAP | 0402_2.2uF_6.3V_X5R_20% | vendor |
| CL05A474KA5NNNC | CAP | 0402_470nF_25V_X5R_10% | vendor |
| CL05A475MP5NRNC | CAP | 0402_4.7uF_10V_X5R_20% | vendor |
| CL05A475MQ5NRNC | CAP | 0402_4.7uF_6.3V_X5R_20% | vendor |
| CL05B104KA5NNNC | CAP | 0402_100nF_25V_X7R_10% | vendor |
| CL10A106MO8NQNC | CAP | 0603_10uF_16V_X5R_20% | vendor |
| CL10A106MQ8NNNC | CAP | 0603_10uF_6.3V_X5R_20% | vendor |
| CL10A226MO7JZNC | CAP | 0603_22uF_16V_X5R_20% | vendor |
| CL10A226MQ8NRNC | CAP | 0603_22uF_6.3V_X5R_20% | vendor |
| CL10A475KP8NNNC | CAP | 0603_4.7uF_10V_X5R_10% | vendor |
| CL10B104KB8NNNC | CAP | 0603_100nF_50V_X7R_10% | vendor |
| CL21A226MAYNNNE | CAP | 0805_22uF_25V_X5R_20% | vendor |

Every row is one of the 14 unique Samsung CL MPNs on sheet `SKU3` of the
CO1271 order BOM; `expected` is derived from that sheet's human description
(`MLCC_<nom>_<dielectric>_<voltage>_<tol>_<size>_...`), not from the parser.

## field positions

`CL + size(2) + temp(1) + capacitance(3) + tolerance(1) + voltage(1) + thickness(1) + ...`

| positions | field | example |
|---|---|---|
| 0-1 | series (`CL`) | CL |
| 2-3 | size code | `05` = 0402, `10` = 0603, `21` = 0805 |
| 4 | temperature class | `A` = X5R, `B` = X7R |
| 5-7 | EIA capacitance | `105` = 1uF |
| 8 | **capacitance tolerance** | `K` = ±10%, `M` = ±20% |
| 9 | **rated voltage** | `A` = 25V, `B` = 50V, `O` = 16V, `P` = 10V, `Q` = 6.3V |
| 10 | thickness (mm) | `5` = 0.5, `7` = 0.7, `8` = 0.8, `Y` = 1.25 |
| 11-14 | design, product, control, packaging | not cleaned |

The tolerance letter at index 8 and the voltage letter at index 9 are fixed by
the format: `CL10A106MO8NQNC` (10uF/16V) and `CL10A106MQ8NNNC` (10uF/6.3V) share
`...A106M...`, so both are ±20% and only the voltage letter differs.

## sources

Two catalogues are needed, because neither is a superset of the other:

| field | source | adds |
|---|---|---|
| size | `Samsung_MLCC_2512.pdf` p.6 (Automotive p.4 has a 9-code subset) | `R1` 0201, `42` 1808, `55` 2220, `L6`/`01`/`19`/`L5` land-grid |
| dielectric | `Samsung_MLCC_2512.pdf` p.6 + `MLCC_Automotive_2512.pdf` p.4 | Commercial adds `W` X6T, `K` X7R(S), `F` Y5V, `J` JIS-B; Automotive adds `D` X8R |
| tolerance | `Samsung_MLCC_2512.pdf` p.7 | — |
| voltage | `Samsung_MLCC_2512.pdf` p.7 + `MLCC_Automotive_2512.pdf` p.5 | Commercial adds `F` 350V, `K` 3kV; Automotive adds `T` 75V, `X` 1250V, `V` 1500V |

Where both catalogues print a letter they agree on its value, so the union is
unambiguous. `Samsung_MLCC_2512.pdf` is *Part I. Commercial/Industrial* and
`MLCC_Automotive_2512.pdf` is *Part II. Automotive*, both December 2025.

Notes:

- `C` is the sheet's C0G symbol and normalises to `C0G`, as every other codec
  here does, so a Samsung C0G part cleans the same as a Murata one.
- Capacitance accepts the `dRd` decimal the sheet prints for values below 10 pF
  (`1R5` = 1.5 pF), not just the 3-digit EIA form.
- The `F` tolerance is value-dependent per the sheet's footnote: ±1 pF below
  10 pF, ±1 % at or above.
- Absolute class-1 grades (`N`/`A`/`B`/`C`/`H`/`L`/`D`) render as a bare pF
  magnitude; the asymmetric ones (`V`/`U`/`Z`) as the sheet spells them.
- `L6`/`01`/`19`/`L5` are land-grid sizes with no entry in the repo's size
  vocabulary yet; they register under the code the sheet prints so `clean`
  keeps working. Tracked in `doc/TODO.md`.
- The four land-grid size codes register under the sheet's own code, so their
  footprint is not yet mapped to a land pattern.

## additional samples

Voltage, dielectric and tolerance letters not present in the CO1271 BOM, from
the same two catalogues.

| mpn_or_bom | ctype | expected | path |
| CL05A105MA5NNNC | CAP | 0402_1uF_25V_X5R_-5% | vendor |
| CL05B105MC5NNNC | CAP | 0402_1uF_25V_X7R_+5% | vendor |
| CL10B104MZ8NNNC | CAP | 0603_100nF_25V_X7R_+80%/-20% | vendor |
| CL10C101NANNNNC | CAP | 0603_100pF_25V_C0G_0.03pF | vendor |
| CL05C1R5JB5NNNC | CAP | 0402_1.5pF_50V_C0G_5% | vendor |
| CL10B105MH8NNNC | CAP | 0603_1uF_25V_X7R_0.5pF | vendor |
| CL31B106ML5NNNE | CAP | 1206_10uF_35V_X7R_20% | vendor |
| CL21B104KCFNNNE | CAP | 0805_100nF_100V_X7R_10% | vendor |
| CL32B106KHULNNE | CAP | 1210_10uF_630V_X7R_10% | vendor |
| CL31D106MH5NNNE | CAP | 1206_10uF_25V_X8R_20% | vendor |
| CL05C102JB5NNNC | CAP | 0402_1nF_50V_C0G_5% | vendor |
| CL10X105MJ8NNNC | CAP | 0603_1uF_25V_X6S_10% | vendor |
