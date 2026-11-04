# 17. The field step, inside

[Chapter 11](11_field_data.md) explained what the field step does with a drive. This chapter opens
[`sources/field.py`](../../data_acquisition/sources/field.py) and
[`sources/field_alignment.py`](../../data_acquisition/sources/field_alignment.py): how the plan is made and carried
out, what protects the originals, how a layer's position is checked under two PROJ versions, how ArcGIS's
adjustment becomes a sidecar, and how the alignment is measured, step by step.

## You will learn

- How `plan`, `execute`, `prune` and `write_records` work together
- What protects the originals, and what does not
- How an export is checked, including its position under two PROJ versions
- How the ArcGIS adjustment is fitted and written
- The alignment measurement in full, and why single values are noisy

## 1. Plan, execute, prune, records

`main` runs four functions in order (only `plan` with `--dry-run`):

1. **`plan(drive, layout, inventory)`** returns the actions and the exclusions, touching nothing:
   - each orthomosaic of the layout: a `link`, plus its sidecars renamed with it (`_sidecars`: `.tif.aux.xml`,
     `.tfwx`, `.ovr`, ...); a sidecar with an ArcGIS adjustment becomes a `georef` action, and the original
     sidecar is linked as `<name>.arcgis.aux.xml`;
   - each photo the inventory includes: a `link` into `surveys/<capture date>/photos/<original folder>/`; a day
     with fewer than 50 photos and no orthomosaic is "stray photos", excluded (`MIN_SURVEY_PHOTOS`);
   - each annotation layer: an `export`;
   - everything left out, with its reason: the layout's `exclude`, and the inventory's rules;
   - two actions with the same target stop the plan.
2. **`execute(drive, actions, corrections)`** carries them out. A link already pointing to the same file is kept,
   so a build can be resumed; exported layers and written sidecars are made again. If any export differs from its
   source, it stops with the list.
3. **`prune(drive, site, actions)`** removes the files of the site folder that the plan no longer makes.
4. **`write_records`** writes `manifest.csv`, `excluded.csv`, `georeference.csv` and one `survey.json` per survey.

## 2. What protects the originals

- **Hard links.** A [hard link](https://man7.org/linux/man-pages/man2/link.2.html) is a second name for the same
  data on disk: no copy, no extra space, and the same file whichever name you open. The drive must therefore be
  one filesystem (`os.link` fails across filesystems).
- **Read-only.** Every link is made read-only (`_read_only`). Since both names are one file, this also makes the
  original read-only: the only change the field step makes to the original's side, and a protective one.
- **Written files are separate files.** Exported layers and `georef` sidecars are new files (one link each,
  `st_nlink == 1`). `_clear` only ever unlinks a name or removes such a file, and never changes the permissions of
  a link.
- **`prune` removes names, not data**: unlinking a hard link leaves the original in place. But it removes **any**
  file in the site folder that the plan does not make, including files a person put there (finding 23 in
  [`course_findings.md`](../dataset/course_findings.md)): keep nothing of your own in `beaver_dataset/sites/`.

## 3. Exports and their checks

`export_layer` runs [`ogr2ogr`](https://gdal.org/en/stable/programs/ogr2ogr.html) with `-preserve_fid` (feature ids
kept, which later corrections refer to), names the layer after the file, writes a note into the layer's description,
and, when a `crs_corrections` entry matches the layer's horizontal CRS by name, assigns the corrected CRS
(`-a_srs`: the coordinates are not changed, only their description; `corrected_crs` keeps any vertical part).

The export is then compared with its source (`_layer_info`, from `ogrinfo -json`): feature count (and the layout's
`features`), geometry type including Z and M, extent to 10⁻⁶, and **place**. `_same_place` transforms the extent's
corners to longitude/latitude with the CRS the export should have, under pyproj's PROJ, and checks that the
written CRS gives the same points (within 10⁻⁸ degrees, about 1 mm) under **both** pyproj's PROJ and GDAL's
(rasterio's). It compares effects, not text, because GDAL rewrites a CRS's description when it writes a GeoPackage,
and because the two PROJ versions read the ARC zone differently ([chapter 2](02_coordinates.md)).

## 4. The ArcGIS adjustment as a sidecar

`georeference(tif, aux, dest, corrections)` reads the adjustment (`geotiff.arcgis_adjustment`,
[chapter 13](13_readers.md)), accepts only a first-order polynomial fitted to control points, and:

1. turns the control points' source coordinates into pixel coordinates, with the original file's own transform;
2. fits the six affine coefficients by least squares
   ([`numpy.linalg.lstsq`](https://numpy.org/doc/stable/reference/generated/numpy.linalg.lstsq.html)), pixel to
   target CRS: the same first-order fit ArcGIS makes
   ([Esri: transformations](https://pro.arcgis.com/en/pro-app/latest/help/data/imagery/overview-of-georeferencing.htm));
3. writes them as the file's `GeoTransform` in a new `.tif.aux.xml`
   ([GDAL PAM](https://gdal.org/en/stable/user/raster_data_model.html)), with the (corrected) CRS and a note giving
   the residuals; no pixel changes.

The residuals' rms and maximum go to `georeference.csv`; `main` reports fits whose control points miss by more
than 3 m (`GCP_WARN_M`) and chained steps that were not applied.

## 5. The alignment measurement

For each polygon annotation (dams, ponds, lodges, colony boundaries), on the first chunk and the first full tile
that hold it (`check`), `best_shift` does:

1. **Window.** It reads the outline's bounding box plus a margin (3 m and 20 pixels) from the image, and gives up
   (None) if the window leaves the image, exceeds 9 million pixels, or is more than 20 % black (outside the survey).
2. **Edges.** The three bands are averaged to grey, smoothed with a Gaussian of 2 pixels
   ([`gaussian_filter`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.gaussian_filter.html)),
   and the edge strength is the gradient magnitude from two
   [Sobel](https://docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.sobel.html) filters,
   √(Gx² + Gy²).
3. **Outline.** Points every ~2 pixels along the outer outline of each part (at least 20 per part; holes are
   not used).
4. **Score.** For a shift (dx, dy), the mean edge strength at the shifted points, read with bilinear interpolation
   ([`map_coordinates`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.map_coordinates.html)).
5. **Search.** Every shift on a 0.2 m grid within ±3 m (31 × 31 = 961 shifts), then a 0.05 m grid within ±0.2 m of
   the best (9 × 9 = 81). The best is the outline's fit; `fit_found` is false when it lies at the edge of the search.

**Why single values are noisy.** The score has several peaks: a dam's outline lies next to water edges, banks,
vegetation and its own shadow, any of which may score higher a metre away. A smooth outline drawn loosely, a
blurry image, or low contrast flatten the true peak, and a long feature (a dam) fixes a shift across it better
than along it. The measurement is right on average, so read the **median**
over many outlines per date and image kind; and look at the outlines (`--sheet`).

## 6. The inventory and the audit, in code

[`field_inventory.py`](../../data_acquisition/sources/field_inventory.py) turns hand-made names and files into rows.
Its functions come in two groups:

| Function | Takes | Returns |
|---|---|---|
| `parse_date(text, default_year=None)` | a folder or layer name | an ISO date; `Jul04` only with a default year; None if unsure or impossible |
| `season_of`, `site_of`, `survey_date_of` | a path from the drive's root | the season, the site slug (from `SITES`), the date in the flight folder |
| `site_km(lat, lon, site)` | a GPS position | the distance to a site's centre, to catch photos filed under the wrong site |
| `colony_of`, `feature_kind_of` | a layer name | the colony label, the kind of feature; None if unknown |
| `walk(root)`, `find_geodatabases(root)` | the drive | every file of the season folders (no Metashape caches, no `.gdb` internals); the geodatabases |
| `read_photo(path)`, `read_photos(...)` | photos | camera, time, position, size; `read_photos` reuses `exif_cache.csv`, and rewrites it with **only the photos it was given** |
| `photo_rows`, `ortho_rows`, `annotation_rows` | the walked files | the rows of each role |
| `build_inventory(root, out)` | the drive | all of them, sorted, written to the CSV |

**Of two copies, the one that sorts last is kept.** A copy is recognised by its capture time and size. `photo_rows` reads
photos in reverse path order, so the choice is the same on any disk, whatever order it lists files in.

[`field_audit.py`](../../data_acquisition/sources/field_audit.py) answers another question: which photos did the original
Metashape projects use that are no longer on the drive? `project_photos(root)` reads the list inside each project's
`frame.zip`, and `find_missing(root, exif_cache)` looks each one up by name and capture time, since `DJI_0139.JPG`
repeats in every survey. A photo is `present`, `present (moved)` or `missing`.

## Exercises

Notebook: [`notebooks/17_field_step_internals.ipynb`](notebooks/17_field_step_internals.ipynb) (work in a copy);
solutions in [`solutions/notebooks/17_field_step_internals.ipynb`](solutions/notebooks/17_field_step_internals.ipynb).

<!-- This list is generated by tools/build_notebooks.py, from the notebooks' prompts: edit it there. -->

1. **A drive in miniature.** Make a scratch drive from the extract (26 July: the full tile, the chunk, the photos,
   the dams), write a layout for it, and run `plan`, `execute` and `write_records`. Read every record.
2. **Links.** For one linked file, compare it with its original (`os.path.samefile`, `st_nlink`, permissions). Run
   `execute` again: what is done the second time?
3. **Pruning.** Drop the chunk from the layout, put a file of your own in the site folder, plan again and `prune`.
   What is removed, and what happens to the original chunk?
4. **Two PROJ versions.** With `field._same_place`, compare the extract layer's CRS with itself, and with the same
   CRS on the WGS 84 ellipsoid, over the layer's extent.
5. **The score surface.** Recompute `best_shift`'s score for the extract's dam on every shift of the coarse grid,
   on the chunk and on the full tile, and plot the two surfaces. Where are the peaks, and why are they stretched?
6. **Reading names.** The drive's meaning is in its folder and layer names. Try `field_inventory.parse_date` on
   `06May2018`, `05 June 2018`, `02Sept2019`, `31Feb2018`, `D26Jul2018_Dams_Rumney` and `Jul04` (with and without a
   default year). Take a photo's path through `season_of`, `site_of` and `survey_date_of`; measure it with
   `site_km`; and try `colony_of` and `feature_kind_of` on a few layer names.
7. **Scanning a drive.** Make a small drive named like the real one: photos, a copy of a photo, a photo in the
   `Yard` test folder, a `._` file as a Mac leaves, a good and a broken `.tif`, and a File Geodatabase made with
   `ogr2ogr`. Run `walk`, `find_geodatabases`, `read_photo`, then `build_inventory`, and read its rows. Which were
   excluded, and why? Then run `photo_rows` with the files in reverse order: does anything change?
8. **Exporting and georeferencing.** `field.source_path` for a relative and a full source. Write a GeoPackage
   carrying the ARC zone as ESRI writes it, and export it with `field.export_layer`: without a correction, with a
   wrong feature count, and with the correction. What does each answer? Then apply an ArcGIS adjustment with
   `field.georeference` to a small raster with a known fit, and open it.
9. **The alignment check, whole.** Lay out a small site folder (annotations and surveys) from the extract, run
   `field_alignment.check` and `field_alignment.summary`, and draw `field_alignment.contact_sheet`.
10. **The audit.** Metashape projects list the photos they used. Add a small project to the drive of exercise 7,
    listing one photo where it is, one under an old Windows path, and one that no longer exists. What do
    `field_audit.project_photos` and `field_audit.find_missing` report?

## Where this lives

- [`data_acquisition/sources/field.py`](../../data_acquisition/sources/field.py): `plan`, `_sidecars`, `execute`,
  `_clear`, `_read_only`, `export_layer`, `_layer_info`, `corrected_crs`, `_same_place`, `georeference`, `prune`,
  `write_records`, `main`.
- [`data_acquisition/sources/field_alignment.py`](../../data_acquisition/sources/field_alignment.py): `best_shift`,
  `check`, `summary`, `contact_sheet`, and the constants at the top.
- [`data_acquisition/sources/field_inventory.py`](../../data_acquisition/sources/field_inventory.py),
  [`field_audit.py`](../../data_acquisition/sources/field_audit.py): section 6.
- [`tests/dataset/test_field.py`](../../tests/dataset/test_field.py),
  [`test_alignment.py`](../../tests/dataset/test_alignment.py): their tests (none covers `plan`, `execute` or
  `prune` yet).

## Sources

- Linux man pages, [`link(2)`](https://man7.org/linux/man-pages/man2/link.2.html) (hard links)
- GDAL, [`ogr2ogr`](https://gdal.org/en/stable/programs/ogr2ogr.html) (`-preserve_fid`, `-a_srs`),
  [`ogrinfo`](https://gdal.org/en/stable/programs/ogrinfo.html)
- SciPy, [`ndimage`](https://docs.scipy.org/doc/scipy/reference/ndimage.html): Gaussian, Sobel, `map_coordinates`
- [Sobel operator](https://en.wikipedia.org/wiki/Sobel_operator) (edges as the gradient magnitude)
- Esri, [overview of georeferencing](https://pro.arcgis.com/en/pro-app/latest/help/data/imagery/overview-of-georeferencing.htm)
  (first-order polynomial, least-squares fit, residuals)
