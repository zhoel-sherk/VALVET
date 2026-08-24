# Regex / inferit BOM tokens (vendor off)

Rules implemented in `res_pars`, `cap_pars`, `inferit_pars`, `chip_tokens`.

Noise variants (spaces, `+/-` vs `±`, extra SMD) are generated in `tools/gen_parser_fixtures.py`.

## samples

| mpn_or_bom | ctype | expected | path |
| RES_22K_+/-5%_1/16W_R0402_SMD | RES | 0402_22K_1/16W_5% | regex |
| RES_39K2_+/-1%_1/16W_R0402_SMD | RES | 0402_39.2K_1/16W_1% | regex |
| RES_4K7_+/-5%_1/16W_R0402_SMD | RES | 0402_4.7K_1/16W_5% | regex |
| RES_2K49_+/-1%_1/16W_R0402_SMD | RES | 0402_2.49K_1/16W_1% | regex |
| RES_2K2_+/-5%_1/16W_R0402_SMD | RES | 0402_2.2K_1/16W_5% | regex |
| RES_4K99_+/-1%_1/16W_R0402_SMD | RES | 0402_4.99K_1/16W_1% | regex |
| RES_0R_+/-5%_1/10W_R0603_SMD | RES | 0603_0R_1/10W_5% | regex |
| NETRES-SMD 0402-8P4R 33 OHM +/-5% LEAD-FREE - Y01 | RES | 0402_33R_5% | regex |
| CAP-SMD 1812 2200PF/3KV +/-10% X7R LEAD-FREE | CAP | 1812_2200pF_X7R_10%_3KV | regex |
| MLCC 22uF/6.3V 0603 X5R 20% | CAP | 0603_22uF_X5R_20%_6.3V | regex |
| RES 0402 10K OHM +/-1% | RES | 0402_10K_1% | regex |
