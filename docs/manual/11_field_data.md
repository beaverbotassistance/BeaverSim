# 11. Field data: from a field drive to `beaver_dataset/`

Open datasets arrive organised by their publishers. Our own field data do not: the 2018-2019 Montana seasons
are about 97,000 files on an external drive, in folders named by hand, with duplicates, test flights, video
frames, files exported several times, and annotations in ArcGIS geodatabases whose layer names carry the dates
and colonies. Before the pipeline can describe them, they need a **layout step** that reorganises them, without
changing a single original. This chapter explains that step and the alignment check that follows it, with Rumney
Ranch as the case.

## You will learn

- Why field data need a layout step, and what it may and may not do
- How the drive is inventoried, and how a layout file decides where every file goes
- What the field step writes, and how it keeps the originals safe
- How the georeferencing and CRS of ArcGIS data are made explicit
- How well the annotations sit on their imagery, and why every one needs inspection

## 1. Inventory

```
python -m data_acquisition.sources.field_inventory --root <drive>
```

walks the whole drive once and writes `output/dataset/field_inventory.csv`
([`sources/field_inventory.py`](../../data_acquisition/sources/field_inventory.py)): one row per photo, video frame,
orthomosaic and annotation layer (73,763 rows for the 2018-2019 seasons; Metashape projects and other files are
not listed), with its role, site, survey date, whether to include it and why not, and, for photos, the EXIF
camera, capture time and position. A photo is dated by its **capture time**, not by the folder it was filed in,
and its GPS position overrides the folder's site when it lies more than 5 km from it and nearer another. Rules
exclude some files here: copies (the same capture time and size as another photo; the one that sorts last is kept), photos without GPS,
video frames (no EXIF), test flights and filming set-ups, unreadable orthomosaics. For photos and video frames
these rules are final; for orthomosaics they are a proposal, and the layout file decides. A companion tool, [`sources/field_audit.py`](../../data_acquisition/sources/field_audit.py), lists photos
that the original Metashape projects used but that are no longer on the drive
([`docs/dataset/missing_photos.csv`](../dataset/missing_photos.csv)).

## 2. The layout file and the naming policy

Where each orthomosaic and annotation layer goes, or why it is left out, is decided per site in a **layout file**,
[`data_acquisition/field_layouts/<site>.yaml`](../../data_acquisition/field_layouts/). Like a summary it is data,
drafted by Claude from the inventory and reviewed by a person:

```yaml
site: rumney_ranch
base: "2018 Field Season/Drone Flights/Rumney Ranch/"
photos: by_exif_date
crs_corrections: [{from: WGS_1984_ARC_System_Zone_12, to: "+proj=eqc ... +R=6378137 ...", reason: ...}]
orthomosaics:
  - {source: "10. 26July2018/26July2018_4.tif", to: surveys/2018-07-26/orthomosaic_part-4.tif}
  - {source: "10. 26July2018/SmallChunks/26July2018_4_3.tif", to: surveys/2018-07-26/orthomosaic_part-4_chunk-3.tif}
  - {source: "06. 21June2018/RUMNEY_SIX_21June2018.tif", exclude: "cannot be placed: an engineering CRS ..."}
annotations:
  - {source: Dams.gdb, layer: D26Jul2018_Dams_Rumney, to: annotations/2018-07-26/dams.gpkg, features: 56}
```

The target names follow a naming policy, so that the summary needs no parsing of names: one folder per survey
date, `orthomosaic_part-<n>[_chunk-<k>].tif`, `annotations/<date>/<feature>[_points][_colony-<id>][_<variant>].gpkg`
([`docs/dataset/field_naming.md`](../dataset/field_naming.md)). The field step refuses a name outside the policy.

## 3. The field step

```
python -m data_acquisition.sources.field --drive <drive> --site <site> [--dry-run]
```

([`sources/field.py`](../../data_acquisition/sources/field.py)) plans every action, writes the plan to
`output/dataset/field/<site>/`, and, only for a **reviewed** layout file and without `--dry-run`, builds
`beaver_dataset/sites/<site>/`:

| Action | Files | What it does |
|---|---|---|
| **link** | photos, orthomosaics and their sidecars | a hard link under the new name: the same data, no copy, made read-only (which also protects the original) |
| **export** | annotation layers | `ogr2ogr` writes one GeoPackage per layer, unchanged (features, attributes, Z and M, feature ids), its CRS corrected when the layout says so; each export is checked against its source: feature count, geometry type, extent and where its CRS puts it under two PROJ versions |
| **georef** | orthomosaics georeferenced in ArcGIS | its own `.tif.aux.xml` with ArcGIS's adjustment applied (chapter 3); the original sidecar kept as `<name>.arcgis.aux.xml` |

It then writes the site's records (`manifest.csv`, every file and its original; `excluded.csv`, what was left out
and why; `georeference.csv`, each applied fit; one `survey.json` per survey) and removes files a previous build made
but this plan no longer does (links and written files only). Nothing is ever written to the original folders.

## 4. The alignment check

Annotations are only as good as the imagery they sit on. The alignment check measures, for every polygon
annotation, how well its outline follows the edges of the image it lies on
([`sources/field_alignment.py`](../../data_acquisition/sources/field_alignment.py)):

1. the image is turned to grey and smoothed, and the strength of its edges is computed at every pixel (the
   gradient magnitude);
2. the outline is shifted on a grid, up to 3 m in each direction, first in steps of 20 cm and then of 5 cm around
   the best one, and for each shift the average edge strength along the outline is computed;
3. the shift with the strongest edges is the outline's **best fit**. A best fit near zero means the outline was
   drawn on that image as it is placed; a shift at the edge of the search means no fit was found.

Single values are noisy: an outline can follow a nearby edge (vegetation, a bank) better than its own. Read the
**median per date and image kind** (`alignment.csv`, and the summary the command prints), and look at the
outlines themselves with `--sheet`, a contact sheet of one feature per date and type on its chunk and its tile.
One caution when joining `alignment.csv` to the layers: its `fid` column is the feature's row position in the
layer (from 0), not the GeoPackage feature id (finding 14 in
[`course_findings.md`](../dataset/course_findings.md)); read a layer with `fid_as_index=True` to get the ids.
[Chapter 17](17_field_step_internals.md) goes through the method in detail.

## Case: Rumney Ranch

From about 97,000 files on the drive, the inventory found the Rumney ones; the layout file decided the place of
417 orthomosaics (113 left out, each with a reason) and 107 annotation layers (3 left out, empty). The field step
then made 27,990 photo links in 12 surveys, 77 full tiles and 227 chunks with their sidecars, 283 georeferencing
sidecars and 104 exported layers, and listed 1,783 originals left out (among them 968 video frames, 694 duplicate
photos and 103 chunks without any georeferencing).

On the way it found what the drive did not say: the ARC zone is read on a sphere by ArcGIS and on an ellipsoid by
newer PROJ (30 km apart, chapter 2); the annotations were drawn on the chunks, georeferenced again in January 2020,
not on the full tiles; one chunk's georeferencing was broken, and one tile could not be placed at all. The
alignment check then gave, per date, a median best fit of 0.11-0.36 m on the chunks (0.70 m on 22 August 2018)
and 0.53-1.94 m on the full tiles, except on 14 August, a date with no chunks, where the full tiles give 0.20 m.
That is why every Rumney annotation carries `needs_inspection`, and why a tool to inspect and correct annotations
is a later milestone.

## Exercises

These use the Montana extract and the Rumney layout file; none needs the drive.

Notebook: [`notebooks/11_field_data.ipynb`](notebooks/11_field_data.ipynb) (work in a copy); solutions in
[`solutions/notebooks/11_field_data.ipynb`](solutions/notebooks/11_field_data.ipynb).

<!-- This list is generated by tools/build_notebooks.py, from the notebooks' prompts: edit it there. -->

1. **The layout file.** Load
   [`data_acquisition/field_layouts/rumney_ranch.yaml`](../../data_acquisition/field_layouts/rumney_ranch.yaml)
   (the notebook's `LAYOUT`). For 26 July 2018, list where the orthomosaics and the annotation layers go. Find, in
   the extract's `extract.json`, which of them the extract was cut from.
2. **Names.** Check five names against the naming policy with `field.ORTHO_NAME` and `field.LAYER_NAME`, three that
   follow it and two that do not. Then check a copy of the layout with one bad name and one target used twice,
   using `field.check_layout`.
3. **A CRS correction.** Apply the layout's `crs_corrections` to the ARC zone's ESRI definition (`ESRI:102432`)
   with `field.corrected_crs`. What does the result say about the sphere? Then place the centre of the extract's
   box with the declared and the corrected CRS, under the PROJ of pyproj and that of rasterio.
4. **Alignment.** Measure the best-fit shift of the extract's dam (26 July and 6 August) on the chunk and on the
   full tile with `field_alignment.best_shift`, and compare with the full-resolution rows in `extract.json`. Which
   image was it drawn on?
5. **Find it in the code.** Which function plans the actions, which carries them out, and which removes files a
   previous build left?

## Where this lives

- [`data_acquisition/sources/field_inventory.py`](../../data_acquisition/sources/field_inventory.py),
  [`field_audit.py`](../../data_acquisition/sources/field_audit.py): the inventory and the audit.
- [`data_acquisition/sources/field.py`](../../data_acquisition/sources/field.py): `check_layout`, `plan`, `execute`,
  `export_layer`, `georeference`, `corrected_crs`, `prune`, `write_records`.
- [`data_acquisition/sources/field_alignment.py`](../../data_acquisition/sources/field_alignment.py): `best_shift`,
  `check`, `contact_sheet`.
- [`data_acquisition/field_layouts/`](../../data_acquisition/field_layouts/): the layout files.
- [`docs/dataset/field_naming.md`](../dataset/field_naming.md), [`docs/dataset/hdd_inventory.md`](../dataset/hdd_inventory.md).

## Sources

- GDAL, [ogr2ogr](https://gdal.org/en/stable/programs/ogr2ogr.html), [GeoPackage](https://gdal.org/en/stable/drivers/vector/gpkg.html)
- Esri, [overview of georeferencing](https://doc.esri.com/en/arcgis-pro/latest/help/data/imagery/overview-of-georeferencing.html)
- SciPy, [`scipy.ndimage.gaussian_filter`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.gaussian_filter.html)
  (the smoothing) and [`scipy.ndimage.sobel`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.sobel.html)
  (the edges, combined into the gradient magnitude)
- pyogrio, [`read_dataframe`](https://pyogrio.readthedocs.io/en/stable/api.html#pyogrio.read_dataframe) (`fid_as_index`)
