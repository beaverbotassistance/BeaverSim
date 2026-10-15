# Field-season data: layout and naming

How `beaver_dataset/` on the field-season drive is organised, so that the dataset pipeline
(`data_acquisition/catalog/build.py`) reads it with a plain summary: one date per folder, one
product per file, no dates or colonies to parse out of names.

`beaver_dataset/` is built from the original folders (`2018 Field Season/`, `2019 Field Season/`),
which are never changed. Files are **hard links** under new names (same data, no copy, read-only,
so the original is protected too). Geodatabase layers cannot be linked one by one, so each layer is
**exported** to its own GeoPackage, unchanged: same features, attributes and geometry type (Z and M
kept). Every file in `beaver_dataset/` is traceable to its original through `manifest.csv`.

Two things are written rather than linked, so that every tool places the data where the software that
made it did (both are recorded, and the originals are kept):

- **Georeferencing done in ArcGIS.** An orthomosaic georeferenced in ArcGIS keeps the adjustment in its
  `.aux.xml` (`GeodataXform`), which GDAL does not apply. Its `beaver_dataset` copy gets its own
  `.aux.xml` with the adjustment applied as the file's georeferencing (the first-order fit through the
  same control points, the one ArcGIS displayed), so annotations drawn on it line up with it. No pixel
  is changed. The original sidecar is linked as `<name>.arcgis.aux.xml`; `georeference.csv` lists
  each tile's control points and residuals. In a chained adjustment, only the step fitted to control
  points is applied, and the others are reported.
- **CRS corrections.** A CRS that newer PROJ reads differently from the software that made the data is
  replaced, by `crs_corrections` in the layout file, each with its evidence. Rumney Ranch: ESRI's
  "WGS_1984_ARC_System_Zone_12", which ArcGIS evaluates on a sphere (newer PROJ: 25 km off).

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
      orthomosaic_part-<n>_chunk-<k>.tif               a piece of it, as georeferenced in ArcGIS
      orthomosaic_part-<n>.tif.aux.xml, ..._part-<n>.tfwx   its sidecars, renamed with it (the .aux.xml
                                                       written, when ArcGIS's adjustment is applied)
      orthomosaic_part-<n>.arcgis.aux.xml              the original ArcGIS sidecar, when one was written
    annotations/<YYYY-MM-DD>/<name>.gpkg               layers mapped from one survey's imagery
    annotations/<YYYY>/<name>.gpkg                     layers for a season, without a day
```

## Names

**Sites:** the slugs of `data_acquisition/sites.yaml`: `rumney_ranch`, `pilling_ranch`,
`cut_bank_creek`, and one still to choose for Montana's Willow Creek (`willow_creek` is the Alaska site).

**Dates:** the day the imagery was captured (EXIF of the photos), not the folder name nor the day
a layer was drawn. A layer whose name gives a day is placed in that day's folder; when that day is
not a survey day of the site, the layout file says why the date was kept or changed.

**Orthomosaic tiles:** `orthomosaic_part-<n>`, `<n>` the tile's number in its original name
(`Rumney3`, `RUMNEY_THREE` → `3`; suffixes kept: `2b`, `55`). Tile numbers are only meaningful
within one survey: the same number covers different areas on different days.

**Chunks:** `orthomosaic_part-<n>_chunk-<k>`, a piece of tile `<n>` as cut in ArcGIS (`SmallChunks/`;
`<k>` from its name: `3`, `2-1`, `3-b`). At Rumney Ranch the chunks were georeferenced again (January
2020) and are the imagery the annotations were drawn on; the full tiles carry an earlier georeferencing
and can differ from the annotations by up to 3 m. Chunks without any georeferencing are left out.

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

Coordinates, units and pixels are kept as in the original (EPSG:4326, the ARC zone in metres, heights
in US survey feet): only how they are placed is made explicit, as above. Reprojection and
co-registration between surveys are processing steps, not part of the layout.
