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
- Crystals: `XTAL-3225` (metric LxW in tenths of mm).
- Circular hardware: `CIRCLE-D4.6` (body diameter mm); Hanwha `CHIP-Circle` maps to `CIRCLE-GENERIC` when no diameter is known.
- Unmatched strings stay `OTHER` until the user assigns a VSPD id.

Electrical type (`res` / `cap` / `ind` / `other`) is **orthogonal** to package family. A `CHIP-0402` can be any of those; ferrite beads use `CHIP-*` body ids with electrical `ind`.

## Class → Family → example ids

Eight top-level **classes** in `catalog/tree.json`. Family is the second key; ids are examples (not exhaustive).

| Class | Family | Example VSPD ids |
| --- | --- | --- |
| **PASSIVES** | CHIP | `CHIP-01005`, `CHIP-0402`, `CHIP-1206`, `CHIP-2512` |
| | ARRAY | `ARRAY-0402x4`, `ARRAY-0603x4` |
| | CAP-POL | `TANT-A`…`TANT-E`, `CAP-ALU-D6.3x5.4`, `CAP-ALU-D10x10.2` |
| | FUSE | `FUSE-0603`, `FUSE-1206` |
| | IND-PWR | `IND-SMD-4x4`, `IND-SMD-6x6`, `IND-SMD-12x12` |
| | LED | `LED-0603`, `LED-3535` |
| **DISCRETES** | DIODE-2P | `SOD-123`, `SOD-523`, `SOD-923`, `SOD-882`, `SMA`, `MELF`, `MiniMELF` |
| | SOT-SMALL | `SOT-23`, `SOT-23-8`, `SOT-323`, `SOT-723`, `TSOT-23-8` |
| | SOT-POWER | `SOT-223`, `SOT-89`, `TO-252`, `TO-277` |
| **IC-LEADED** | SOIC | `SOIC-8`, `SOIC-16W`, `SOIC-24` |
| | SOP-SMALL | `SSOP-8`, `MSOP-8`, `TSSOP-16`, `ESOP-8` |
| | QFP | `LQFP-48`, `LQFP-100`, `TQFP-44` |
| | PLCC | `PLCC-20`, `PLCC-44` |
| | SOJ | `SOJ-28`, `SOJ-32` |
| **IC-LEADLESS** | DFN | `DFN-8_2x2`, `DFN-10_3x3`, `DFN-56_5x6` |
| | QFN | `QFN-16_3x3`, `QFN-32_5x5`, `QFN-48_6x6`, `QFN-52_6x6` |
| | WSON | `WSON-8` |
| | LGA | `LGA-12_2x2`, `LGA-16_3x3` |
| **IC-ARRAY** | BGA | `BGA-0.8-64`, `BGA-0.8-256` |
| | FBGA | `FBGA-0.65-96`, `VFBGA-0.5-132` |
| | WLCSP | `WLCSP-9`, `WLCSP-15`, `WLCSP-16` |
| **ELECTROMECH** | CONN | `CONN-USB-C-16P`, `CONN-FPC-0.5-20P`, `CONN-GENERIC` |
| | SWITCH | `TACT-SW-6x6` |
| | CRYSTAL | `XTAL-1612`, `XTAL-2520`, `XTAL-3215`, `XTAL-3225`, `XTAL-5032` |
| **HARDWARE** | CIRCLE | `CIRCLE-D4.6`, `CIRCLE-GENERIC` |
| **ODD-FORM** | TRANSFORMER / MODULE / TRIMMER / SHIELD / OTHER | `TRIMMER`, `SHIELD`, `OTHER` |

### Grammar notes (new families)

| Family | Id pattern | Notes |
| --- | --- | --- |
| **CIRCLE** | `CIRCLE-D<diam>` | Round SMT hardware (nuts, washers, fiducials). `body_mm` = `[D, D, H]`. Machine Lib `CHIP-Circle` draws a circle from TYPSIZE; VSPD tab uses the same heuristic. |
| **FUSE** | `FUSE-<imperial>` | Chip-style SMT fuses; same imperial codes as `CHIP-*`. |
| **MELF** | `MELF` | Standard metal-electrode leadless face (DO-214M class); `MiniMELF` is the smaller variant. |
| **SOD-923 / SOD-882** | `SOD-<JEDEC>` | Sub-1 mm SOD flat-lead diodes (IPC `SODFL`). |
| **SOT-723** | `SOT-723` | SC-100 / 1.2 mm square; distinct from `SOT-523`. |
| **SOT-23-8 / TSOT-23-8** | `SOT-23-8`, `TSOT-23-8` | Eight-pin variants of SOT-23 body. |
| **WSON** | `WSON-<pins>` | Wide SON (e.g. SPI flash); not counted in the BGA family. |
| **XTAL-####** | metric L×W | `XTAL-3225` = 3.2 × 2.5 mm ceramic crystal. |
| **QFN/DFN** | `QFN-<pins>_<L>x<W>` | Body size required when pin count alone is ambiguous. Parser accepts `QFN-16(3mmx3mm)` and `DFN2x2-8`. |
| **TANT-E** | `TANT-E` | SP-CAP / polymer case ~7.3 × 4.3 mm (lower profile than `TANT-D`). |
| **POSCAP case codes** | alias | `3528` → `TANT-B`, `7343` → `TANT-D`. |

## Hanwha `UPDPARTGROUPNAME` → VSPD

From `examples/UPD.MDB` `PARTGROUP_Map` (45 distinct names, Aug 2026).

| UPDPARTGROUPNAME | VSPD | Notes |
| --- | --- | --- |
| `Chip-R0201` … `Chip-R3216(1206)` | `CHIP-0201` … `CHIP-1206` | `Chip-C*` mirrors `Chip-R*` sizes |
| `Chip-R03015` / `Chip-C03015` | `CHIP-01005` | metric 03015 |
| `Chip-Tantal` | `TANT-A` | vision type chip, polar body |
| `Chip-Aluminum` | `CAP-ALU-D6.3x5.4` | default alu can; override per part if needed |
| **CHIP-Circle** | **`CIRCLE-GENERIC`** | Round body; Machine Lib uses `is_chip_circle` + TYPSIZE diameter |
| `CHIP-Rect` | `CHIP-0402` | Rectangular chip placeholder (size from part row) |
| `TR` / `TR2` | `SOT-23` | Hanwha transistor group |
| `SOP` | `OTHER` | Too generic without pin count |
| `SOP2` | `SOIC-16W` | 208 mil wide SOP |
| `SOJ` / `SOJ2` | `SOJ-28` / `SOJ-32` | |
| `QFP` | `LQFP-48` | Default mid QFP; pin-specific rows override |
| `PLCC` / `PLCC (Body)` | `PLCC-44` | |
| `BGA` / `Multi BGA` | `BGA-0.8-256` | Ball count not inferred from group name |
| `Flip Chip` | `WLCSP-16` | |
| `Melf` | `MELF` | |
| `LED` / `LED PAD` | `LED-0603` | |
| `Connector` / `INSERT` / `Small SOP/Connector` | `CONN-GENERIC` | |
| `ShieldCap` | `SHIELD` | |
| `Trimmer` | `TRIMMER` | |
| `Polygon` | `OTHER` | Custom polygon vision; no single VSPD body |
| `Odd Form` | `OTHER` | |
| `User IC` | `OTHER` | User-defined geometry |
| `Hemt` | `SOT-89` | Common default for RF discretes |
| `NONE` | `OTHER` | Unassigned group |

## Mapping examples

| Source | Example | VSPD |
| --- | --- | --- |
| IPC compact | `SOIC127P600X175-8N` | `SOIC-8` (density `L`/`M` folded) |
| JEDEC | `MS-012` | `SOIC-8` |
| JEITA | `SOP-8` | `SOIC-8` **with warning**: JEITA SOP-8 is often 208 mil wide; VSPD `SOIC-8` is 150 mil narrow |
| IEC | `014T01` | `SOIC-8` |
| GOST | `4301.8-1` | `SOIC-8` |
| KiCad KLC | `SOIC-8_3.9x4.9mm_P1.27mm` | `SOIC-8` |
| Hanwha group | `Chip-R1005(0402)`, `Chip-Tantal`, `TR2`, **`CHIP-Circle`** | `CHIP-0402`, `TANT-A`, `SOT-23`, **`CIRCLE-GENERIC`** |
| SC-70 | `SN74LVC1G08DCKR SC-70` | `SOT-323` |
| POSCAP | `POSCAP 100uF (3528/B)` | `TANT-B` |
| Nut | `Copper Nut M2.0x4.6x2.8` | `CIRCLE-D4.6` |
| Crystal | `CRYSTAL 38.4MHz 3.2*2.5mm` | `XTAL-3225` |
| PARTDESC корпус | User-entered `SOIC-8` / `QFN-32` on the part row | same VSPD; vision class `SOP`/`QFP` is not a package |
| Metric EIA | `CAPC1005` | `CHIP-0402` |
| TI orderable / drawing | `NE555D`, `D0008A` | `SOIC-8` (vendor-local letters; not global) |
| Microchip suffix | `…/SN` vs `…/SM` | `SOIC-8` vs `SOIC-16W` |

Vendor one-letter suffixes (`D`, `PW`, …) are catalogued **with pin-count context**. Lone `D` on a resistor is not a package.

## Added vs left as OTHER

**Added in this catalog pass** (from UPD.MDB, `user_temp/component_test.xlsx`, IPC/JEDEC staples):

- Class **HARDWARE** / family **CIRCLE** (`CIRCLE-D2.0` … `CIRCLE-GENERIC`)
- **FUSE** family; **MELF** (full-size); **SOD-923**, **SOD-882**; **SOT-723**, **SOT-23-8**, **TSOT-23-8**
- **ESOP-8**; **WSON-8**; **WLCSP-15**
- More **DFN/QFN** sizes (`DFN-8_2x2`, `QFN-16_3x3`, `QFN-52_6x6`, …)
- **XTAL-1612**, **XTAL-2520**; more **IND-SMD** and **CAP-ALU** sizes; **TANT-E**
- Hanwha group aliases including **CHIP-Circle**; POSCAP case codes; SC-70 → SOT-323

**Still `OTHER`** (by design or needs custom row):

- Custom **connectors** (DDR sockets, M.2, HDMI, USB-A, FPC, RJ45, battery, …) — hundreds of mechanical variants
- **CPU / large BGA** with non-catalog ball counts (`BGA1744`, `BGA96`, …)
- **Polygon**, **User IC**, **Odd Form**, bare **SOP** without pins
- **Through-hole** or mixed-technology parts (audio jack DIP, EEPROM files)
- Long BOM description lines with no extractable package token
- `component_test.xlsx`: **142 / 993** unique strings still `OTHER` (~86% mapped)

## Geometry source

On-tab silhouettes come from stored `outline_json` (imported `.kicad_mod` pads + F.Fab), then VSPD body heuristics (`CHIP-0402` pads, SOIC body box, **`CIRCLE-*` circle body**). CadQuery / `kicad-packages3D-generator` parameter dumps are **not** the VSPD geometry source: they are GPL-3, schema-inconsistent, and 3D-oriented. Use that clone only as a finding aid under `user_temp/`. Do not vendor `KicadModTree` / `kilibs`.

TI Find Packages / Product Information API are useful for **offline** alias harvest. VALVET does not call TI at runtime or scrape the HTML catalog.

## Isolation / Apply

The DATA · Package tab owns ids, aliases, classification, and **on-tab** preview. It does not rewrite PnP/Merge columns or PCB Preview `FootprintStore` until **Apply package table** is implemented (stub buttons today). After Apply, the same `vspd_id` / `outline_json` can feed Gerber overlay.
