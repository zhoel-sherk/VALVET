# Hanwha MDB editor

Package: `src/hanwha_mdb_edit/`. Opens from the Machine lib tab.

## What it edits today

- Grid: `PART_Det` plus joined `PROFILE_Det` (`PARENTPROFILE`, `UPDPARTGROUPID`, `LIBRARY_TYPE`), `PARTGROUP_Map.UPDPARTGROUPNAME` (read-only name), feeding / Q speed levels.
- Bulk **parent profile** rewrites `PARENTPROFILE` (not Chip-* class).
- Save: PART_Det + `PARENTPROFILE` / `UPDPARTGROUPID` on PROFILE_Det (CSV sidecars always; ODBC on Windows when ACE is present). Group **name** is not written back to `PARTGROUP_Map`.

## What it is not

- Parent profile ≠ component class (`Chip-R0603(0201)`, `Trimmer`, …).
- Hide S is a view filter (`__` / `[STDVER.]`); it does not delete rows.
- Confidence 0 is templates / not placement-ready, not “standard library”.

See [hanwha_UPD_mdb_schema.md](hanwha_UPD_mdb_schema.md). Footprint / vision geometry (µm): [UPD_MDB_Footprint_Geometry_Report.md](UPD_MDB_Footprint_Geometry_Report.md). Machine Lib canvas: [MACHINE_LIB_FOOTPRINT_PREVIEW.md](MACHINE_LIB_FOOTPRINT_PREVIEW.md).
