# 1. Geospatial data: rasters, vectors, formats

Remote-sensing data come in two shapes: **rasters**, grids of pixels such as an orthomosaic, and
**vectors**, geometries such as the outline of a dam. This chapter explains both, how a file says what it
contains, and the file formats you will meet in our datasets, including the small companion files that
travel with them and are easy to lose.

## You will learn

- What rasters and vectors are, and what each is used for
- How to read a raster's header: size, bands, data type, resolution, transform, nodata, alpha
- How vector data are organised: geometries, attributes, layers, Z and M values
- The common file formats and their companion files

## 1. Rasters

A **raster** is a grid of cells (pixels), each holding one number per **band**. An RGB photo has three bands
(red, green, blue); an elevation model has one (height). Every band of a file has the same **data type**:
`uint8` (0 to 255, for colours), `float32` (heights in metres), and so on
([GDAL raster data model](https://gdal.org/en/stable/user/raster_data_model.html)).

What turns a picture into a map is its **georeferencing**: the CRS ([chapter 2](02_coordinates.md)) and a
**geotransform**, six numbers that say where the top-left corner of the grid is and how large each pixel is
(the **resolution**, in the units of the CRS). With them, every pixel has a position on the ground.

The raster products in our datasets:

| Product | What each pixel holds | Typical source |
|---|---|---|
| **orthomosaic** | colour (RGB, sometimes with alpha) of the ground, corrected for perspective | drone photos, by photogrammetry ([chapter 3](03_drone_surveys.md)) |
| **multispectral** | reflectance in several bands, e.g. red edge and near infrared | multispectral drone camera, satellites |
| **DSM** (digital surface model) | height of the top surface: ground, vegetation, dams | photogrammetry, lidar |
| **DTM** (digital terrain model) | height of the bare ground | derived from a DSM or lidar |
| **CHM** (canopy height model) | DSM minus DTM: height of vegetation | derived |
| **DoD** (DEM of difference) | change in height between two dates | derived from two DSMs |

([OpenDroneMap: outputs](https://docs.opendronemap.org/outputs/) describes the first ones as a drone
processing tool produces them.)

## 2. "Nothing here": nodata and alpha

A raster is a rectangle, but a survey rarely is. Pixels outside the surveyed area must be marked, or a
black pixel will be read as a real dark surface. There are two ways:

- **nodata**: one value of the band (often 0, -9999 or -32768) declared in the file to mean "no data"
  ([GDAL: nodata](https://gdal.org/en/stable/user/raster_data_model.html#nodata-value)). Common for DSMs.
- **alpha**: an extra band whose value is 0 where there is nothing and 255 where there is image. Common
  for orthomosaics (RGBA).

A raster with neither has no way to tell its edges from black ground. **In the pipeline**, `curate` flags
such a raster `nodata_undeclared`; a raster with an alpha band is not flagged
([`curate.check_raster`](../../data_acquisition/steps/curate.py)).

## 3. Vectors

A **vector** dataset is a list of **features**, each with a **geometry** and **attributes** (a row of a table).
The geometry types are defined by the [OGC Simple Features](https://www.ogc.org/standard/sfa/) standard:
points, lines (LineString), polygons, and their "multi" versions for features made of several parts. A dam
can be a polygon (its outline) or a point (its position); a canal or a beaver trail is a line.

Coordinates can carry two extra values: **Z**, a height, and **M**, a "measure" that ArcGIS uses for
distances along a line. The Rumney annotations have both (`MultiPolygonZM`), although Z and M are not
always meaningful. **Not every tool keeps M**: GDAL's command-line tools do, but pyogrio and GeoPandas drop it
when they read (with a warning) and when they write. That is why the field step copies layers with `ogr2ogr`
([chapter 11](11_field_data.md)): an early version of the course's Montana extract, written with GeoPandas, had
silently lost the M values.

A file can hold several **layers**, each a separate table of features: the original Rumney geodatabases have
one layer per date and colony. **In the pipeline**, a vector file is one catalogue item, unless the summary
says that its layers are separate epochs (`layers: {pattern, ...}`), in which case each layer becomes its own
item ([`vector.info`](../../data_acquisition/readers/vector.py), [chapter 6](06_what_the_pipeline_needs.md)).

## 4. File formats

| Format | Shape | What to know |
|---|---|---|
| **GeoTIFF** (`.tif`) | raster | A TIFF image plus georeferencing tags ([OGC GeoTIFF](https://www.ogc.org/standard/geotiff/); [GDAL GTiff](https://gdal.org/en/stable/drivers/raster/gtiff.html)). The usual format for orthomosaics and DSMs. |
| **ESRI ASCII grid** (`.asc`) | raster | A text grid with a short header ([GDAL AAIGrid](https://gdal.org/en/stable/drivers/raster/aaigrid.html)); no CRS of its own. |
| **GeoPackage** (`.gpkg`) | vector (and raster) | One SQLite file holding layers and their CRS ([geopackage.org](https://www.geopackage.org/); [GDAL GPKG](https://gdal.org/en/stable/drivers/vector/gpkg.html)). The pipeline's format for exported annotations. |
| **Shapefile** (`.shp` + parts) | vector | One layer spread over several files: `.shp` (geometry), `.shx` (index), `.dbf` (attributes, field names of 10 characters at most), `.prj` (CRS) and others ([Esri white paper](https://www.esri.com/content/dam/esrisites/sitecore-archive/Files/Pdfs/library/whitepapers/pdfs/shapefile.pdf); [GDAL Shapefile](https://gdal.org/en/stable/drivers/vector/shapefile.html)). Lose a part, lose the data. |
| **File Geodatabase** (`.gdb`) | vector | An ArcGIS format that is a **folder** of internal files, holding many layers ([GDAL OpenFileGDB](https://gdal.org/en/stable/drivers/vector/openfilegdb.html)). Used for the Montana annotations. |
| **KML / KMZ** | vector | Google Earth's format ([OGC KML](https://www.ogc.org/standard/kml/); [GDAL KML](https://gdal.org/en/stable/drivers/vector/kml.html)); always longitude/latitude on WGS 84. |
| **CSV** | table | Rows of values; points if two columns are coordinates. The CRS must be given ([chapter 6](06_what_the_pipeline_needs.md)). |
| **JPEG** (`.JPG`) | photo | Drone photos; their position and time are in the EXIF metadata ([chapter 3](03_drone_surveys.md)). |

## 5. Companion files (sidecars)

Many rasters travel with small files that share their name:

| Sidecar | Holds |
|---|---|
| `x.tif.ovr` | **overviews**: smaller copies of the image for fast display ([gdaladdo](https://gdal.org/en/stable/programs/gdaladdo.html)) |
| `x.tif.aux.xml` | extra metadata written by GDAL or ArcGIS: statistics, and sometimes a CRS, a geotransform or an ArcGIS georeferencing adjustment |
| `x.tfw`, `x.tfwx`, `x.wld` | a **world file**: six numbers giving pixel size, rotation and the position of the centre of the top-left pixel ([GDAL world file](https://gdal.org/en/stable/drivers/raster/wld.html); [Esri world files](https://doc.esri.com/en/arcgis-pro/latest/help/data/imagery/world-files-for-raster-datasets.html)). ArcGIS writes `.tfwx` when it saves its own georeferencing. |
| `x.prj` | the CRS, for formats that cannot store it |

A sidecar can change **where** a raster appears: the Montana chunks are placed only by their `.aux.xml`
([chapter 11](11_field_data.md)). Copy a raster without its sidecars and it may land somewhere else, or nowhere.

**In the pipeline**, companions are never described on their own: a summary lists `x.tif`, and the pipeline
knows that `x.tif.aux.xml`, `x.tfwx` and the parts of a shapefile belong to it
([`readers/files.py`](../../data_acquisition/readers/files.py): `RASTER_SIDECARS`, `SHAPEFILE_PARTS`,
`companions`).

## Case: a Rumney Ranch dam and the image it was drawn on

The Montana extract ([`docs/manual/data/montana_extract/`](data/montana_extract/README.md)) holds, for
26 July 2018, a 60 m × 60 m piece of an orthomosaic and the dams mapped on it. The orthomosaic is a raster of
three `uint8` bands at 5 cm; the dams are a GeoPackage layer of `MultiPolygonZM` features with a `NAME`
attribute (the dam's code, e.g. `R6`). Opened together, the dam outline sits on the pile of branches across the creek: two shapes of data,
one place. The exercises open both.

## Exercises

Notebook: [`notebooks/01_geospatial_data.ipynb`](notebooks/01_geospatial_data.ipynb) (work in a copy);
solutions in [`solutions/notebooks/01_geospatial_data.ipynb`](solutions/notebooks/01_geospatial_data.ipynb).

1. **A raster's header.** Open the sample's `ortho_2023-07-12.tif` with rasterio and print its width, height,
   band count, data types, resolution, geotransform, colour interpretation and nodata. Explain each.
2. **Nodata and alpha.** How many pixels of the sample orthomosaic are transparent (alpha 0)? How many pixels
   of the sample DSM are nodata? Read the DSM with `masked=True` and compare the minimum with and without the
   mask.
3. **Vectors.** List the layers of the sample's `dams_2023-07-12.gpkg` and of the extract's
   `2018-07-26/annotations/dams.gpkg`: geometry type, number of features, attribute names. Compare the geometry
   type pyogrio reports with the one `ogrinfo` reports for the extract's layer: what is lost?
4. **Companions.** Which companion files does the pipeline expect for `orthomosaic_part-3.tif`, and for
   `dams.shp`? Use `data_acquisition.readers.files.companions`.
5. **Draw both.** Plot the extract's 26 July orthomosaic chunk and draw the dam outlines on it.
6. **Find it in the code.** Which function decides whether a file is a raster, and which file extensions does it
   try before opening a file?

## Where this lives

- [`data_acquisition/readers/geotiff.py`](../../data_acquisition/readers/geotiff.py): `info`, `is_raster`,
  `declared_bands`, `sample`.
- [`data_acquisition/readers/vector.py`](../../data_acquisition/readers/vector.py): `info`, `one_layer`.
- [`data_acquisition/readers/table.py`](../../data_acquisition/readers/table.py): CSV tables as points or rows.
- [`data_acquisition/readers/files.py`](../../data_acquisition/readers/files.py): companions and folders read as one file.
- [`data_acquisition/catalog/summary.py`](../../data_acquisition/catalog/summary.py): the list of products (`PRODUCTS`).
- [`data_acquisition/steps/curate.py`](../../data_acquisition/steps/curate.py): `check_raster` (nodata, alpha).

## Sources

- GDAL, [raster data model](https://gdal.org/en/stable/user/raster_data_model.html), drivers
  [GTiff](https://gdal.org/en/stable/drivers/raster/gtiff.html), [AAIGrid](https://gdal.org/en/stable/drivers/raster/aaigrid.html),
  [GPKG](https://gdal.org/en/stable/drivers/vector/gpkg.html), [Shapefile](https://gdal.org/en/stable/drivers/vector/shapefile.html),
  [OpenFileGDB](https://gdal.org/en/stable/drivers/vector/openfilegdb.html), [KML](https://gdal.org/en/stable/drivers/vector/kml.html),
  [world files](https://gdal.org/en/stable/drivers/raster/wld.html), [gdaladdo](https://gdal.org/en/stable/programs/gdaladdo.html)
- OGC, [GeoTIFF](https://www.ogc.org/standard/geotiff/), [Simple Features](https://www.ogc.org/standard/sfa/),
  [KML](https://www.ogc.org/standard/kml/); [GeoPackage](https://www.geopackage.org/)
- Esri, [Shapefile technical description](https://www.esri.com/content/dam/esrisites/sitecore-archive/Files/Pdfs/library/whitepapers/pdfs/shapefile.pdf),
  [world files for raster datasets](https://doc.esri.com/en/arcgis-pro/latest/help/data/imagery/world-files-for-raster-datasets.html)
- OpenDroneMap, [outputs](https://docs.opendronemap.org/outputs/)
- [rasterio quickstart](https://rasterio.readthedocs.io/en/stable/quickstart.html), [pyogrio](https://pyogrio.readthedocs.io/en/stable/),
  [GeoPandas](https://geopandas.org/en/stable/)
