# A. Glossary

Each term with a short definition, the chapter that explains it, and a source. Terms specific to this project link
to its own documents.

## Geospatial data

| Term | Meaning | Chapter | Source |
|---|---|---|---|
| **raster** | a grid of cells (pixels), each with one value per band | [1](01_geospatial_data.md) | [GDAL raster data model](https://gdal.org/en/stable/user/raster_data_model.html) |
| **vector** | features (points, lines, polygons) with attributes | [1](01_geospatial_data.md) | [OGC Simple Features](https://www.ogc.org/standard/sfa/) |
| **band** | one layer of values of a raster (red, green, elevation, ...) | [1](01_geospatial_data.md) | [GDAL raster data model](https://gdal.org/en/stable/user/raster_data_model.html) |
| **nodata** | the value marking cells with no data | [1](01_geospatial_data.md) | [GDAL: nodata](https://gdal.org/en/stable/user/raster_data_model.html#nodata-value) |
| **geotransform** | the six numbers placing a raster's pixels in its CRS | [1](01_geospatial_data.md) | [rasterio: georeferencing](https://rasterio.readthedocs.io/en/stable/topics/georeferencing.html) |
| **overview** | a reduced copy of a raster stored with it, for fast display | [15](15_curate.md) | [gdaladdo](https://gdal.org/en/stable/programs/gdaladdo.html) |
| **GeoTIFF** | a TIFF image with georeferencing tags | [1](01_geospatial_data.md) | [OGC GeoTIFF](https://www.ogc.org/standard/geotiff/) |
| **ESRI ASCII grid** | a raster as plain text, without a CRS | [1](01_geospatial_data.md) | [GDAL AAIGrid](https://gdal.org/en/stable/drivers/raster/aaigrid.html) |
| **GeoPackage** | a vector (and raster) format in one SQLite file | [1](01_geospatial_data.md) | [geopackage.org](https://www.geopackage.org/) |
| **shapefile** | an older vector format made of several files (`.shp`, `.shx`, `.dbf`, `.prj`, ...) | [1](01_geospatial_data.md) | [Esri white paper](https://www.esri.com/content/dam/esrisites/sitecore-archive/Files/Pdfs/library/whitepapers/pdfs/shapefile.pdf) |
| **File Geodatabase** | ArcGIS's vector format, a folder ending in `.gdb` | [1](01_geospatial_data.md) | [GDAL OpenFileGDB](https://gdal.org/en/stable/drivers/vector/openfilegdb.html) |
| **KML** | Google Earth's vector format | [1](01_geospatial_data.md) | [OGC KML](https://www.ogc.org/standard/kml/) |
| **Z, M** | a geometry's third coordinate (height) and a "measure" value per vertex | [1](01_geospatial_data.md) | [OGC Simple Features](https://www.ogc.org/standard/sfa/) |
| **sidecar** | a file that belongs to another: `.aux.xml`, `.tfw`, `.ovr`, ... | [13](13_readers.md) | [GDAL raster data model](https://gdal.org/en/stable/user/raster_data_model.html) |
| **world file** | a sidecar with a raster's geotransform (`.tfw`, `.tfwx`) | [3](03_drone_surveys.md) | [GDAL world file](https://gdal.org/en/stable/drivers/raster/wld.html) |

## Coordinates

| Term | Meaning | Chapter | Source |
|---|---|---|---|
| **CRS** | coordinate reference system: what the numbers of a position mean | [2](02_coordinates.md) | [QGIS, a gentle introduction to CRSs](https://docs.qgis.org/latest/en/docs/gentle_gis_introduction/coordinate_reference_systems.html) |
| **datum, ellipsoid** | the model of the Earth's shape a CRS is tied to | [2](02_coordinates.md) | [NOAA NGS, datums](https://geodesy.noaa.gov/datums/index.shtml) |
| **WGS 84** | the global datum of GPS | [2](02_coordinates.md) | [NGA, WGS 84](https://earth-info.nga.mil/index.php?dir=wgs84&action=wgs84) |
| **EPSG code** | a registry number for a CRS (`EPSG:32612`) | [2](02_coordinates.md) | [EPSG registry](https://epsg.org/home.html) |
| **UTM** | Universal Transverse Mercator: 60 zones of 6° with metre coordinates | [2](02_coordinates.md) | [PROJ: utm](https://proj.org/en/stable/operations/projections/utm.html) |
| **WKT** | Well-Known Text, the full text description of a CRS (WKT1, WKT2) | [2](02_coordinates.md) | [OGC 18-010r11](https://docs.ogc.org/is/18-010r11/18-010r11.pdf) |
| **PROJ** | the library that transforms coordinates, used by nearly all open GIS tools | [2](02_coordinates.md) | [PROJ](https://proj.org/en/stable/) |
| **ARC System zone** | an ESRI Equidistant Cylindrical CRS, read on a sphere by ArcGIS | [2](02_coordinates.md) | [PROJ: eqc](https://proj.org/en/stable/operations/projections/eqc.html) |
| **vertical datum, NAVD 88** | the reference for heights; North America's | [2](02_coordinates.md) | [NOAA NGS, NAVD 88](https://geodesy.noaa.gov/datums/vertical/north-american-vertical-datum-1988.shtml) |
| **US survey foot** | 1200/3937 m, slightly longer than the international foot | [2](02_coordinates.md) | [NIST](https://www.nist.gov/pml/us-surveyfoot) |
| **georeferencing** | placing an image in a CRS, often with control points | [3](03_drone_surveys.md) | [Esri, overview of georeferencing](https://doc.esri.com/en/arcgis-pro/latest/help/data/imagery/overview-of-georeferencing.html) |
| **first-order polynomial (affine)** | a georeferencing that shifts, scales, rotates and shears | [17](17_field_step_internals.md) | [Esri, overview of georeferencing](https://pro.arcgis.com/en/pro-app/latest/help/data/imagery/overview-of-georeferencing.htm) |

## Drone surveys

| Term | Meaning | Chapter | Source |
|---|---|---|---|
| **orthomosaic** | an image stitched from many photos and corrected to a map | [3](03_drone_surveys.md) | [OpenDroneMap, outputs](https://docs.opendronemap.org/outputs/) |
| **DSM, DTM** | digital surface model (tops of everything), digital terrain model (bare ground) | [3](03_drone_surveys.md) | [OpenDroneMap, outputs](https://docs.opendronemap.org/outputs/) |
| **structure from motion** | reconstructing 3D shape and camera positions from overlapping photos | [3](03_drone_surveys.md) | [Structure from motion](https://en.wikipedia.org/wiki/Structure_from_motion) |
| **GSD** | ground sampling distance: the ground size of one pixel | [3](03_drone_surveys.md) | [Pix4D, GSD](https://support.pix4d.com/hc/en-us/articles/202559809) |
| **GCP** | ground control point: a marked point with surveyed coordinates | [3](03_drone_surveys.md) | [OpenDroneMap, GCPs](https://docs.opendronemap.org/gcp/) |
| **RTK** | real-time kinematic positioning: centimetre GNSS from a base station's corrections | [3](03_drone_surveys.md) | [DJI, Phantom 4 RTK specs](https://www.dji.com/phantom-4-rtk/info) |
| **EXIF, XMP** | metadata inside a photo: camera, time, GPS; DJI adds flight data in XMP | [3](03_drone_surveys.md) | [CIPA DC-008, the Exif standard](https://www.cipa.jp/std/documents/e/DC-X008-Translation-2019-E.pdf) |
| **chunk** | a piece of an orthomosaic, georeferenced on its own in ArcGIS (Montana) | [11](11_field_data.md) | [`field_naming.md`](../dataset/field_naming.md) |

## Catalogues and metadata

| Term | Meaning | Chapter | Source |
|---|---|---|---|
| **STAC** | SpatioTemporal Asset Catalog, the JSON standard the catalogues follow | [4](04_catalogs_and_metadata.md) | [stacspec.org](https://stacspec.org/en) |
| **catalog, collection, item, asset** | a tree of links; a group with an extent and licence; one dataset file in space and time; a file of an item | [4](04_catalogs_and_metadata.md) | [STAC item spec](https://github.com/radiantearth/stac-spec/blob/master/item-spec/item-spec.md) |
| **STAC extension** | a set of extra fields (projection, raster, eo, file) | [4](04_catalogs_and_metadata.md) | [projection](https://github.com/stac-extensions/projection) |
| **metadata record** | the repository's description of a dataset (EML, PANGAEA, Zenodo, HydroShare, CKAN) | [4](04_catalogs_and_metadata.md) | [EML](https://eml.ecoinformatics.org/) |
| **DOI** | a persistent identifier for a dataset version | [4](04_catalogs_and_metadata.md) | [doi.org](https://www.doi.org/) |
| **checksum (MD5, SHA-256)** | a fingerprint of a file's bytes | [4](04_catalogs_and_metadata.md) | [RFC 1321](https://www.rfc-editor.org/rfc/rfc1321), [FIPS 180-4](https://csrc.nist.gov/pubs/fips/180-4/upd1/final) |
| **multihash** | a checksum prefixed with its algorithm's code | [4](04_catalogs_and_metadata.md) | [Multihash](https://multiformats.io/multihash/) |
| **multipart ETag** | an object store's `<md5 of md5s>-<parts>` for files uploaded in parts | [16](16_sources.md) | [AWS, checking object integrity](https://docs.aws.amazon.com/AmazonS3/latest/userguide/checking-object-integrity.html) |
| **SPDX identifier** | a standard short name for a licence (`CC-BY-4.0`) | [5](05_data_governance.md) | [SPDX licence list](https://spdx.org/licenses/) |
| **FAIR** | findable, accessible, interoperable, reusable | [5](05_data_governance.md) | [Wilkinson et al. 2016](https://doi.org/10.1038/sdata.2016.18) |
| **CARE** | collective benefit, authority to control, responsibility, ethics: Indigenous data governance | [5](05_data_governance.md) | [Carroll et al. 2020](https://doi.org/10.5334/dsj-2020-043) |

## The pipeline

| Term | Meaning | Chapter | Source |
|---|---|---|---|
| **data root** | a folder holding datasets and their catalogues (`open_datasets/`, `beaver_dataset/`, the sample) | [0](00_setup.md) | [`pipeline_design.md`](../dataset/pipeline_design.md) |
| **source client** | the code that downloads from one kind of repository | [8](08_open_datasets.md), [16](16_sources.md) | [`sources/`](../../data_acquisition/sources/) |
| **reader** | the code that turns a file or record into facts | [13](13_readers.md) | [`readers/`](../../data_acquisition/readers/) |
| **evidence** | what code reads about a dataset's files, given to Claude | [9](09_describing_a_dataset.md) | [`catalog/evidence.py`](../../data_acquisition/catalog/evidence.py) |
| **summary** | a dataset's YAML description: product, time and site of each file | [6](06_what_the_pipeline_needs.md), [9](09_describing_a_dataset.md) | [`catalog/summary.py`](../../data_acquisition/catalog/summary.py) |
| **site registry** | the list of sites and the decisions about them (`sites.yaml`) | [5](05_data_governance.md) | [`sites.yaml`](../../data_acquisition/sites.yaml) |
| **layout file** | where each file of a field drive goes in `beaver_dataset/` | [11](11_field_data.md) | [`field_layouts/`](../../data_acquisition/field_layouts/) |
| **product** | what a data file is: orthomosaic, dsm, dtm, annotations, ... | [6](06_what_the_pipeline_needs.md) | [`catalog/summary.py`](../../data_acquisition/catalog/summary.py) (`PRODUCTS`) |
| **descriptor** | one of the nine `beaver:` fields every item should have | [15](15_curate.md) | [`catalog/descriptors.py`](../../data_acquisition/catalog/descriptors.py) |
| **quality flag** | a fact about an item worth knowing before use, with its source | [10](10_building_and_curating.md) | [`catalog/descriptors.py`](../../data_acquisition/catalog/descriptors.py) |
| **origin, source** | where a value came from: auto, build, repository, claude, manual | [15](15_curate.md) | [`catalog/descriptors.py`](../../data_acquisition/catalog/descriptors.py) |
| **review** | a person checking a draft and setting `reviewed: {by, date}` | [9](09_describing_a_dataset.md) | [appendix C](C_conventions.md) |
| **field step** | the code that builds `beaver_dataset/` from a drive and a layout file | [11](11_field_data.md), [17](17_field_step_internals.md) | [`sources/field.py`](../../data_acquisition/sources/field.py) |
| **alignment check** | how well annotation outlines follow the edges of their image | [11](11_field_data.md), [17](17_field_step_internals.md) | [`sources/field_alignment.py`](../../data_acquisition/sources/field_alignment.py) |
| **colony, AOI** | a beaver family's area; the polygon drawn for it (area of interest) | [5](05_data_governance.md), [12](12_inspecting.md) | [`pipeline_design.md` §5.3](../dataset/pipeline_design.md#53-areas-of-interest-colonies) |
| **milestone** | a stage of the pipeline's plan (1: catalogues; 2: inspection; ...) | [7](07_pipeline_at_a_glance.md) | [`pipeline_design.md` §12](../dataset/pipeline_design.md#12-implementation-order) |
| **regression snapshot** | every item of the real datasets, saved to compare before and after a change | [18](18_testing.md) | [`tests/dataset/regression.py`](../../tests/dataset/regression.py) |
