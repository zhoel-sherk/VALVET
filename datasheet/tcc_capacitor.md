# TCC MLCC (TCC… prefix) — UNVERIFIED

Source: [`src/pn_original/tcc_capacitor.py`](../src/pn_original/tcc_capacitor.py)

> **No manufacturer catalogue.** These rows come from nine production rows of the
> CO1271 SKU3 BOM, where the BOM description column is the ground truth. The only
> CCTC document retrieved (2026-10-04) is a "Specification for Approval" template
> from Chaozhou Three-Circle (Group) Co., Ltd with image-only tables and no
> part-number section.
>
> Every 3-digit voltage code in these rows ends in `0` (`160` `250` `500`),
> and that is exactly the set where the assumed V/10 rule and the alternative EIA
> mantissa-exponent rule agree. The two `6R3` rows are an explicit decimal
> spelling and carry no information either way. **That is why this looks verified
> and is not:** nothing here discriminates between the two conventions. Until a
> catalogue turns up the voltage convention is an assumption, and so is the field
> layout. Do not add rows from parts whose 3-digit voltage code does not end in
> 0 — they would either prove the codec wrong or enshrine the assumption as if it
> were evidence.

## samples

| mpn_or_bom | ctype | expected | path |
| TCC0402X5R104K250AT | CAP | 0402_100nF_X5R_10%_25V | vendor |
| TCC0402X7R104K160AT | CAP | 0402_100nF_X7R_10%_16V | vendor |
| TCC0402X7R224K250AT | CAP | 0402_220nF_X7R_10%_25V | vendor |
| TCC0402X7R473K500AT | CAP | 0402_47nF_X7R_10%_50V | vendor |
| TCC0402X5R106M6R3ATR | CAP | 0402_10uF_X5R_20%_6.3V | vendor |
| TCC0402X5R225M6R3AT | CAP | 0402_2.2uF_X5R_20%_6.3V | vendor |
| TCC0402C0G101J500AT | CAP | 0402_100pF_C0G_5%_50V | vendor |
| TCC0402C0G820J500AT | CAP | 0402_82pF_C0G_5%_50V | vendor |
| TCC0402COG331J500AT | CAP | 0402_330pF_C0G_5%_50V | vendor |
