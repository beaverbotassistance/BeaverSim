# 13. Readers

Part 3 opens the pipeline. Its lowest layer is the **readers**: small modules that turn a file into facts, one per
kind of data and one per metadata standard. Everything above them (evidence, the builder, `curate`) works from
what they return. This chapter goes through each, what it returns, and the rules they all follow.

## You will learn

- The readers by data type and by metadata standard, and what each returns
- How the record readers share one shape, and how a new standard is added
- How ArcGIS's georeferencing is read from a sidecar
- What a reader must never do, and how to test an edge case

## 1. By data type

All in [`data_acquisition/readers/`](../../data_acquisition/readers/):

| Module | Reads | Main functions | Returns |
|---|---|---|---|
| [`geotiff.py`](../../data_acquisition/readers/geotiff.py) | any raster GDAL opens (GeoTIFF, ESRI ASCII grid, ...) | `is_raster`, `info`, `declared_bands`, `sample` | the header: CRS (EPSG code, or WKT2 when there is none), bounds, shape, transform, resolution, bands, data types, nodata, colour interpretation, overviews, driver; `sample` reads the central 1024 × 1024 window |
| [`vector.py`](../../data_acquisition/readers/vector.py) | GeoPackage, shapefile, GeoJSON, KML/KMZ, File Geodatabase, FlatGeobuf, GPX | `is_vector`, `info`, `one_layer` | per layer: geometry type, feature count, fields, horizontal CRS, vertical CRS (a compound CRS is split), bounds; the layers' common CRS and bounds when they share one |
| [`table.py`](../../data_acquisition/readers/table.py) | CSV/TSV, as the summary's `table` spec says | `read`, `info`, `rows_info` | the same shape as `vector.info`: a point layer, or a non-spatial table without coordinates |
| [`photos.py`](../../data_acquisition/readers/photos.py) | a folder of JPEG photos | `exif`, `info` | per photo: camera, capture time, longitude, latitude, altitude; per folder: count, cameras, first and last time, positions, unreadable photos, photos without position |
| [`files.py`](../../data_acquisition/readers/files.py) | file names only | `companions`, `is_companion`, `inside_container` | which files belong to another: raster sidecars (`.aux.xml`, `.tfw`, `.ovr`, ...), shapefile parts, the inside of a `.gdb` folder |

A raster is recognised by its extension (`.tif`, `.tiff`) or, for other raster-like extensions (`.asc`, `.img`,
...), only if GDAL opens it as a raster: a `README.txt` is not one. The readers use
[rasterio](https://rasterio.readthedocs.io/en/stable/) and [pyogrio](https://pyogrio.readthedocs.io/en/stable/),
both built on [GDAL](https://gdal.org/); EXIF is read with [Pillow](https://pillow.readthedocs.io/en/stable/reference/ExifTags.html).

Each reads **headers only**, or a bounded sample: a raster's centre window, a few attribute rows, the photos'
EXIF but not their pixels. A 30 GB orthomosaic is described in a second.

## 2. By metadata standard

One reader per record format, registered in `RECORDS`
([`readers/__init__.py`](../../data_acquisition/readers/__init__.py)) with the file name its source client saves the
record under:

| Format | Reader | Saved as | Standard |
|---|---|---|---|
| `eml` | [`eml.py`](../../data_acquisition/readers/eml.py) | `metadata.xml` | [EML](https://eml.ecoinformatics.org/), DataONE repositories |
| `pangaea_tab` | [`pangaea.py`](../../data_acquisition/readers/pangaea.py) | `metadata.tab` | [PANGAEA](https://www.pangaea.de/) tab-delimited text (`?format=textfile`) |
| `zenodo_json` | [`zenodo.py`](../../data_acquisition/readers/zenodo.py) | `metadata.json` | [Zenodo REST API](https://developers.zenodo.org/) record |
| `hydroshare_json` | [`hydroshare.py`](../../data_acquisition/readers/hydroshare.py) | `resource.json` | [HydroShare](https://www.hydroshare.org/hsapi/) science metadata and file list |
| `ckan_json` | [`ckan.py`](../../data_acquisition/readers/ckan.py) | `package.json` | [CKAN](https://docs.ckan.org/en/latest/api/index.html) `package_show` |

Every record reader returns **the same shape**, so the builder and the evidence gatherer never ask which standard a
record came from: `{package_id, title, licence, rights, creators, dates, bounds, methods, entities}`, where
`entities` maps each file name to its `{url, pid, size, checksum, attributes}`. `licence` is an
[SPDX](https://spdx.org/licenses/) identifier, or None when the record's licence is not one the reader knows;
`rights` keeps the record's own text. A new standard is one module and one line in `RECORDS`
([chapter 19](19_extending.md)).

## 3. ArcGIS adjustments

ArcGIS can georeference a raster without changing it: it writes the adjustment (a `GeodataXform`, fitted to control
points) into the raster's `.aux.xml` sidecar, where GDAL does not apply it ([chapter 3](03_drone_surveys.md)).
`geotiff.arcgis_adjustment` reads it from the sidecar's text: its type (`PolynomialXform`, or a `CompositeXform`
that chains steps), its order, the CRS it maps into, and the control points in the file's own coordinates
(`source`) and in that CRS (`target`). A chained step given by coefficients alone is listed in `not_applied`.
`unapplied_georeference` summarises it for `curate`'s flag of the same name ([chapter 10](10_building_and_curating.md));
the field step uses the full result to write the fit as the file's georeferencing ([chapter 11](11_field_data.md)).

## 4. What a reader must not do

- **Know about sites, sources or datasets.** A reader is called with a path or a text, and returns facts about it.
  No reader contains a site name or a repository's quirk (a quirk of a *standard* belongs in its reader).
- **Guess.** Free text (a record's methods, abstract, notes) is returned as text, for a person or Claude to read;
  a licence the reader does not recognise is None, not the nearest match; a value that is absent stays absent.
- **Change anything.** Readers open files read-only.
- **Read everything.** Headers and bounded samples only; anything heavier is a step, not a reader.

## Exercises

Notebook: [`notebooks/13_readers.ipynb`](notebooks/13_readers.ipynb) (work in a copy); solutions in
[`solutions/notebooks/13_readers.ipynb`](solutions/notebooks/13_readers.ipynb).

<!-- This list is generated by tools/build_notebooks.py, from the notebooks' prompts: edit it there. -->

1. **Rasters.** Read the header of the sample's orthomosaic and of `dem_2022.asc` with `geotiff.info`. Which bands
   does each declare, and what does the grid lack? Is `README.txt` a raster?
2. **Vectors.** Read the extract's `dams.gpkg` (26 July) with `vector.info`. Where did its vertical CRS go, and
   which geometry type is reported?
3. **Records.** Read the sample's `metadata.xml` with the reader `RECORDS` gives for it. What does it say about
   each file's checksum?
4. **ArcGIS sidecars.** Read the four `original_*.arcgis.aux.xml` of the extract with `geotiff.arcgis_adjustment`;
   fit a first-order polynomial through each one's control points and compute the residuals. How do the chunks and
   the full tiles compare, and what does that say about [chapter 11](11_field_data.md)'s alignment results?
5. **Companions.** Which files does `files.companions` give for `ortho.tif` and for `dams.shp`?
6. **Test an edge case.** EXIF stores the altitude as a positive number with a separate flag (`GPSAltitudeRef`: 1 =
   below sea level). Write a pytest test that makes a photo 400 m below sea level and checks that `photos.exif`
   reads -400 m. Run it in a scratch folder. What happens?
7. **One shape from five standards.** `RECORD_TEXTS`, in the notebook, holds small records in the Zenodo,
   HydroShare, CKAN and PANGAEA formats. Read each with its reader: which keys do all share, and which entity did
   CKAN skip? Which size is only approximate? Then try `ckan.file_name`, `hydroshare.resource_id` and
   `readers.entity_bands`.
8. **Tables.** Write a CSV with a title line, coordinates and a row without coordinates, and one without
   coordinates at all. What do `table.read`, `table.info` and `table.rows_info` say? What happens if the spec names
   a column that does not exist?
9. **The small helpers.** `geotiff.sample` on the DSM, with two sizes. `geotiff.unapplied_georeference` on a copy
   of the extract's chunk, before and after putting its original ArcGIS sidecar next to it; is that sidecar a
   companion (`files.is_companion`)? `vector.is_vector` and `photos.is_photo_folder` on a few paths; `photos.info`
   on the sample's photos; `vector.one_layer` on a two-layer GeoPackage.

## Where this lives

- [`data_acquisition/readers/`](../../data_acquisition/readers/): one module per data type and per metadata standard;
  `__init__.py` holds `RECORDS`.
- [`tests/dataset/test_readers.py`](../../tests/dataset/test_readers.py): the readers' tests.

## Sources

- GDAL, [raster drivers](https://gdal.org/en/stable/drivers/raster/index.html),
  [vector drivers](https://gdal.org/en/stable/drivers/vector/index.html), [PAM `.aux.xml`](https://gdal.org/en/stable/user/raster_data_model.html)
- Esri, [overview of georeferencing](https://doc.esri.com/en/arcgis-pro/latest/help/data/imagery/overview-of-georeferencing.html)
- CIPA, [Exif 3.0 specification](https://www.cipa.jp/std/documents/download_e.html?CIPA_DC-008-2023-E) (GPS tags,
  `GPSAltitudeRef`)
- SPDX, [licence list](https://spdx.org/licenses/)
