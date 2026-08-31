# Machine Lib footprint preview (Wave 1)

Hanwha UPD `.mdb` stores **machine-vision profiles**, not copper land patterns. Wave 1 draws that geometry in **VIEW · Machine Lib** so an operator can check bodies, leads, and BGA grids before Wave 2 overlays them on PCB Preview.

Geometry decode: [UPD_MDB_Footprint_Geometry_Report.md](UPD_MDB_Footprint_Geometry_Report.md). Units in the MDB are **micrometres** (÷1000 → mm).

## How to use

1. Open **VIEW · Machine Lib**, vendor **Hanwha / Samsung**.
2. **Open .mdb…** — VALVET copies the file to the current QSettings profile folder (`…/profiles/{id}/hanwha_lib/library.mdb`) and dumps vision tables to `vision.sqlite` (one ACE/ODBC or mdbtools pass). **Reload** re-imports.
3. Click a row in the table. The **right pane** reads **SQLite only** (no new ODBC handshake). Geometry is the profile named by `PART_Det.PROFILENAME`.
4. Wheel zoom, drag pan. Metadata under the canvas: VISIONTYPE, SIZE X/Y/Z, source, warnings.

Yamaha mode shows **N/A** in the pane (no UPD vision tables).

PCB Preview is **unchanged** in Wave 1 (Gerber + heuristic PnP outlines only).

## What you should see

| Family | VISIONTYPE | Canvas |
| --- | --- | --- |
| Chip 0402 / 0603 / 0805 | 3 | Body rectangle; **two heuristic pads** (lands are not in the MDB) |
| TR / TR2 / SOT-23 | 3 | Same chip-lead slots: `EXPARAM15`/`16` left/right counts (0 = unused). Thickness `11`/`12`, length `13`/`14`. `EXPARAM18`/`19` is **first-to-last span** (µm), not adjacent pitch when there are 3+ leads. SOT-223 is 1+3 (tab+row); SOD923 1+1; SOT-23 1+2. |
| SOIC / SOP | 1 | Body + reconstructed leads |
| QFP | 1 | Four lead rows |
| User IC | 1 | Asymmetric lead groups. If clusters sit off-axis (`TANCENTER`) they are rotated 90° onto the long body axis (same rule as FPC). |
| BGA | 2 | Body + ball grid (missing-ball blocks approximated) |
| Polygon / shield can | 6 | Polyline body; **no pads** |

Blue = body, green = pads/leads, orange = balls, dashed = bbox. **Red dot + «1»** = pin 1 when the part is polar (first reconstructed lead, or `PIN1XPOS/YPOS` if set). Chip-R / Chip-C with `PIN1INDICATOR < 0` are non-polar — no pin 1.

## Manual QA checklist

- [ ] Chip body for 0402 / 0603 / 0805 matches expected millimetres
- [ ] SOIC-8: two opposing lead rows
- [ ] QFP-48: four sides, 12 leads each
- [ ] User IC: clustered leads, not a uniform QFP
- [ ] BGA: grid fills the body (spot-check pitch vs datasheet)
- [ ] Polygon shield: outline with cutouts if present
- [ ] Fast scroll does not freeze the UI (debounce + background load)

If a lead side looks mirrored, note `PROFILENAME` — `ANGLE` / `RADCENTER` / `TANCENTER` are reverse-engineered.

## Wave 2 (parked)

Import into `FootprintStore`, PCB Preview overlay, instancing/LOD. Do not implement until this preview looks right on a real UPD.
