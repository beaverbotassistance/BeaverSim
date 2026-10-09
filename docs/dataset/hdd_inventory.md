# Seagate field-season drive: inventory

Inspected 2026-10-09, read-only. Drive: Seagate Portable Drive, 3.6 TB NTFS,
2.9 TB used, about 97,000 files under `2018 Field Season/` and `2019 Field Season/`.

## Contents by category

| Category | Files | Size | Needed for the dataset? |
|---|---|---|---|
| Metashape projects + caches (`.psx`, `.files/`) | 17,636 | 1,072 GB | Only to re-export DEMs if Metashape becomes available |
| Exported orthomosaics + sidecars (`.tif`, `.tfwx`, `.lyr`, …) | 2,784 | 1,003 GB | One reference orthomosaic per survey (annotations were drawn on them) |
| Raw drone photos (`.JPG`, DJI FC6310) | ~74,000 | ~0.6 TB | **Yes**: the input for reprocessing |
| Annotations (`.gdb`, `.shp`, `.xls`) | 2,807 | < 0.1 GB | **Yes** |
| Drone videos | 81 | 170 GB | No |
| Other projects (ants, flocking, GoPro, promo) | 371 | 272 GB | No |
| Misc (meshes, Google Maps screenshots, kmz, …) | 6,254 | 48 GB | No |

Raw photos are not only in `NNNMEDIA/` folders: some are in `*_Leg<n> (<timestamp>)`,
`*_Images` or plain date folders, and some surveys are duplicated (e.g. Willow
`00. 05May2018 redo`). Photos must be identified by EXIF (camera model FC6310), not by
folder name.

## Sites

| Site | Centre (lat, lon) | Surveys | Annotations | Colonies |
|---|---|---|---|---|
| Rumney Ranch | 48.93, −113.12 | 13 (06 May – 22 Aug 2018) + 02 Sep 2019 | 10 gdb: Dams, DamDimensions, Lodges, Canals, Trails, Ponds, RiverReach, Vegetation, ColonyBoundaries | 8 (A–H), boundary polygons 2–23 ha |
| Pilling Ranch | 48.56, −113.09 | 17 (06 May – 21 Aug 2018) + 01 Sep 2019 | 6 gdb: Dams, Lodges, Canals, Trails, RiverReach, Stream | 5 (1–5) |
| Willow Creek | 48.66, −112.76 | 18 (05 May – 25 Aug 2018) + 31 Aug 2019 | 10 gdb + shapefiles: Dams, Lodges, Canals, Trails, Ponds, Elevation, FairyRings, profiles | 3 (1–3) |
| Cut Bank Creek | 48.66, −112.74 | 6 (09 Jul – 19 Aug 2018) + 01 Sep 2019 | none | unknown |
| BBC Drone Mimicry Site | — | 1 (15 Aug 2018) | 3 small layers ("false dams") | filming set-up, not a study site |

Annotation layers are mostly per survey date (e.g. `D13Aug2018_Dams_Pilling`,
`Colony4_Pilling_Canals_15July2018`): a weekly record of built structures per colony.
About 245 layers, about 70,000 features in total.

## Data-quality issues

1. **Almost no elevation rasters.** All 854 readable exported GeoTIFFs are 8-bit
   RGB/RGBA. DEMs exist only in 2 Willow Creek Metashape projects; dense point clouds
   exist in most projects, in Metashape's own format.
2. **Mixed CRSs**, even within one survey: EPSG:4326, ESRI "WGS_1984_ARC_System_Zone_12"
   (ESRI:102432), and a few local metric systems. Rumney annotations use NAVD88
   heights in US survey feet.
3. **~560 exported tiles (`SmallChunks/`) have no embedded georeferencing**, only
   ArcGIS `.tfwx` world files.
4. **6 corrupted GeoTIFFs** (e.g. `05June2018_Rumney1.tif`, `22Aug2018_Rumney7.tif`)
   and **2 unreadable geodatabases** (`Pilling 08. 20June2018/New File Geodatabase.gdb`,
   `Willow 17. 25Aug2018/25Aug2018_Willow.gdb`).
5. **Inconsistent naming**: `05June2018` / `05Jun2018`; colonies as letters (Rumney),
   numbers (Pilling), or `C3` / `Willow3` / `Colony3` (Willow).
6. **Consumer GPS only** (no RTK found): surveys are internally consistent but can be
   offset from each other by metres; they need co-registration.

## Relation to the repository

`data_acquisition/example_datasets/RUMNEY_RANCH_RGB/A2/` (weekly PNGs, June–August
2018) very likely comes from this dataset, probably Rumney colony A.
