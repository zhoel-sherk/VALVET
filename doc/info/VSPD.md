# VSPD — VALVET Simple Package Definition

VSPD is a **package** (корпус) naming standard: short human-readable ids for kitting and production (`SOIC-8`, `CHIP-0402`). It is **not** a CAD footprint / land-pattern library.

| Concept | What it is |
| --- | --- |
| **Package (VSPD)** | Body family + pin count / chip size. Canonical id in `package_vspd`. |
| **Footprint (CAD)** | Copper land pattern, courtyard, 3D. KiCad `.kicad_mod`, Gerber. |
| **PnP “Footprint” column** | Vendor/CAD string. Treated as an **alias** of a VSPD package until Apply is wired. |

Many KiCad footprint files (density `_N`/`_L`, thermal pad `_EP`, pad-stack variants) map to **one** VSPD id unless body size or pin count actually differs (`SOIC-8` vs `SOIC-16W`).

## Token grammar

`FAMILY-variant`, uppercase, hyphen between family and variant.

- Chips: `CHIP-0402` (imperial EIA). Metric EIA-96 style `CAPC1005` aliases to the same id.
- Arrays: `ARRAY-0402x4`.
- Leaded ICs: `SOIC-8`, `SOIC-16W` (`W` = wide / ~208 mil body), `MSOP-8`, `LQFP-48`.
- Size suffix when the family needs it: `QFN-32_5x5`, `DFN-8_3x3`.
- `_EP` is an exposed-pad **alias** of the same package unless the catalog lists a distinct id (`SOIC-8_EP`).
- BGA: `BGA-<pitch_mm>-<balls>` (`BGA-0.8-256`).
- Unmatched strings stay `OTHER` until the user assigns a VSPD id.

Electrical type (`res` / `cap` / `ind` / `other`) is **orthogonal** to package family. A `CHIP-0402` can be any of those.

## Mapping examples

| Source | Example | VSPD |
| --- | --- | --- |
| IPC compact | `SOIC127P600X175-8N` | `SOIC-8` (density `L`/`M` folded) |
| JEDEC | `MS-012` | `SOIC-8` |
| JEITA | `SOP-8` | `SOIC-8` **with warning**: JEITA SOP-8 is often 208 mil wide; VSPD `SOIC-8` is 150 mil narrow |
| IEC | `014T01` | `SOIC-8` |
| GOST | `4301.8-1` | `SOIC-8` |
| KiCad KLC | `SOIC-8_3.9x4.9mm_P1.27mm` | `SOIC-8` |
| Hanwha group | `Chip-R1005(0402)` (paren = imperial), `Chip-Tantal`, `TR2` | `CHIP-0402`, `TANT-A`, `SOT-23` |
| PARTDESC корпус | User-entered `SOIC-8` / `QFN-32` on the part row | same VSPD; vision class `SOP`/`QFP` is not a package |
| Metric EIA | `CAPC1005` | `CHIP-0402` |
| TI orderable / drawing | `NE555D`, `D0008A` | `SOIC-8` (vendor-local letters; not global) |
| Microchip suffix | `…/SN` vs `…/SM` | `SOIC-8` vs `SOIC-16W` |

Vendor one-letter suffixes (`D`, `PW`, …) are catalogued **with pin-count context**. Lone `D` on a resistor is not a package.

## Geometry source

On-tab silhouettes come from stored `outline_json` (imported `.kicad_mod` pads + F.Fab), then VSPD body heuristics (`CHIP-0402` pads, SOIC body box). CadQuery / `kicad-packages3D-generator` parameter dumps are **not** the VSPD geometry source: they are GPL-3, schema-inconsistent, and 3D-oriented. Use that clone only as a finding aid under `user_temp/`. Do not vendor `KicadModTree` / `kilibs`.

TI Find Packages / Product Information API are useful for **offline** alias harvest. VALVET does not call TI at runtime or scrape the HTML catalog.

## Isolation / Apply

The DATA · Package tab owns ids, aliases, classification, and **on-tab** preview. It does not rewrite PnP/Merge columns or PCB Preview `FootprintStore` until **Apply package table** is implemented (stub buttons today). After Apply, the same `vspd_id` / `outline_json` can feed Gerber overlay.
