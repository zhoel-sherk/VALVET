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

The tolerance letter at index 8 and the voltage letter at index 9 are fixed by
the format: `CL10A106MO8NQNC` (10uF/16V) and `CL10A106MQ8NNNC` (10uF/6.3V) share
`...A106M...`, so both are ±20% and only the voltage letter differs.
