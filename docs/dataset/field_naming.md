# Field-season data: layout and naming

How `beaver_dataset/` on the field-season drive is organised, so that the dataset pipeline
(`data_acquisition/catalog/build.py`) reads it with a plain summary: one date per folder, one
product per file, no dates or colonies to parse out of names.

`beaver_dataset/` is built from the original folders (`2018 Field Season/`, `2019 Field Season/`),
which are never changed. Files are **hard links** under new names (same data, no copy, read-only,
so the original is protected too). Geodatabase layers cannot be linked one by one, so each layer is
**exported** to its own GeoPackage, unchanged: same features, attributes, geometry type (Z and M
kept) and CRS. Every file in `beaver_dataset/` is traceable to its original through `manifest.csv`.

What goes where, and what is left out, is decided per site in a **layout file**,
`data_acquisition/field_layouts/<site>.yaml`, drafted by Claude from the inventory and reviewed by a
person, like a dataset summary.

## Layout

```
beaver_dataset/
  README.md, manifest.csv, excluded.csv
  sites/<site>/
    surveys/<YYYY-MM-DD>/
      photos/<camera folder>/<original photo name>     DJI photos, by EXIF capture date
      orthomosaic_part-<n>.tif                         one tile of that day's orthomosaic
      orthomosaic_part-<n>.tif.aux.xml, ..._part-<n>.tfwx   its sidecars, renamed with it
    annotations/<YYYY-MM-DD>/<name>.gpkg               layers mapped from one survey's imagery
    annotations/<YYYY>/<name>.gpkg                     layers for a season, without a day
```

## Names

**Sites:** `rumney_ranch`, `pilling_ranch`, `willow_creek`, `cut_bank_creek` (the slugs of
`data_acquisition/sites.yaml`).

**Dates:** the day the imagery was captured (EXIF of the photos), not the folder name nor the day
a layer was drawn. A layer whose name gives a day is placed in that day's folder; when that day is
not a survey day of the site, the layout file says why the date was kept or changed.

**Orthomosaic tiles:** `orthomosaic_part-<n>`, `<n>` the tile's number in its original name
(`Rumney3`, `RUMNEY_THREE` → `3`; suffixes kept: `2b`, `55`). Tile numbers are only meaningful
within one survey: the same number covers different areas on different days.

**Annotation files:** `<feature>[_<geometry>][_colony-<id>][_<variant>].gpkg`

| Part | Values |
|---|---|
| feature | `dams`, `canals`, `trails`, `ponds`, `lodges`, `colony_boundaries`, `dam_widths`, `dam_thicknesses`, `woody_vegetation`, `river_reach`, `stream` |
| geometry | `points` when the same feature is also mapped as polygons or lines on that date; omitted otherwise |
| colony | lowercase, one spelling per site: Rumney `a`–`h`, Pilling `1`–`5`, Willow `1`–`3` |
| variant | a second mapping of the same feature, colony and date (e.g. `pass-1` for an earlier, partial pass), or a layer derived from another (`vertices`, `spaced`, `merged`) |

The GeoPackage holds one layer, named as the file (without `.gpkg`).

## Left out, with a reason in `excluded.csv`

Decided by rule, for every site:
- photos that are byte-identical copies of another photo, and stray photos (fewer than 50 on a day
  and no orthomosaic);
- exported tiles without embedded georeferencing (`SmallChunks/`, world file only);
- files GDAL cannot open (corrupt GeoTIFFs, unreadable geodatabases);
- empty layers;
- drone videos and video frames, and folders of other projects.

Decided per file in the layout file: duplicates and alternative exports (the copy that is kept is
named), scratch and test layers.

## Not changed

CRS, units and georeferencing are kept as in the original (EPSG:4326, ESRI:102432
"WGS_1984_ARC_System_Zone_12", heights in US survey feet). The catalog flags them; reprojection is a
processing step, not part of the layout.
