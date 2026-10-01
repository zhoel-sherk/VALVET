# Taiyo Yuden EMK/UMK/MLCC

Source: [`src/pn_original/taiyo_mlcc_capacitor.py`](../src/pn_original/taiyo_mlcc_capacitor.py)

Decoding tables come from the manufacturer catalogue
[`doc/info/DOC012627480.pdf`](../doc/info/DOC012627480.pdf) (PARTS NUMBER pages).
The rated voltage is the **first letter** of the part number, and the
series-code -> dielectric mapping was verified against LCSC product data.

## samples

| mpn_or_bom | ctype | expected | path |
| TAIYO/UMK105CH120JV-F | CAP | 12pF | vendor |
| TAIYO/TMK107BBJ106MA-T | CAP | 0603_10uF_25V_X5R_20% | vendor |
| TAIYO/TMK316ABJ106KD-T | CAP | 1206_10uF_25V_X5R_10% | vendor |
| TAIYO/JDK107BBJ226MA-T | CAP | 0603_22uF_6.3V_X5R_20% | vendor |
| TAIYO/LMK105BJ105KV-F | CAP | 0402_1uF_10V_X5R_10% | vendor |
| TAIYO/LMK105B7104KV-F | CAP | 0402_100nF_10V_X7R_10% | vendor |
| TAIYO/LMK063C6273KP-F | CAP | 0201_27nF_10V_X6S_10% | vendor |
