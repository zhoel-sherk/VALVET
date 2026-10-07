# Walsin MLCC N/B/X/CG lines

Source: [`src/pn_original/walsin_mlcc_capacitor.py`](../src/pn_original/walsin_mlcc_capacitor.py)

Walsin's `B` (X7R), `X` (X5R) and `CG` (C0G) bodies share their layout with the
Fenghua MLCC lines, so a `...NT` part can be claimed by either codec. Walsin
carries `PARSER_PRIORITY = 100` against Fenghua's `86`, so Walsin wins ties and
its own token order (`size_value[_dielectric]_voltage_tolerance`) is what the
rows below record. Only the Walsin-specific `N` line and the `CT` tape suffix
are unambiguous; those are marked in the last column.

Rated-voltage codes here are EIA mantissa-exponent (`101` = 100 V, `202` = 2000 V),
per the Walsin "How to order" tables - see `eia_vol_code_to_v`.

## samples

| mpn_or_bom | ctype | expected | path |
| 0402N100J500CT | CAP | 0402_10pF_50V_5% | vendor |
| 0402B101K500CT | CAP | 0402_100pF_X7R_50V_10% | vendor |
| 0805X475M6R3CT | CAP | 0805_4.7uF_X5R_6.3V_20% | vendor |
| 1206X106K250CT | CAP | 1206_10uF_X5R_25V_10% | vendor |
| 0201X104K6R3NT | CAP | 0201_100nF_X5R_6.3V_10% | vendor |
| 0402CG100J500NT | CAP | 0402_10pF_C0G_5%_50V | vendor |
| 1206X106K250NT | CAP | 1206_10uF_X5R_10%_25V | vendor |
| 0402X224K160NT | CAP | 0402_220nF_X5R_10%_16V | vendor |
| 0603X226M100NT | CAP | 0603_22uF_X5R_20%_10V | vendor |
| 0402CG0R5C500NT | CAP | 0402_0.5pF_C0G_0.25pF_50V | vendor |
| 0402CG5R6C500NT | CAP | 0402_5.6pF_C0G_0.25pF_50V | vendor |
| 0402CG8R2C500NT | CAP | 0402_8.2pF_C0G_0.25pF_50V | vendor |
