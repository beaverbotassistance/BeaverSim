# Geospatial data: rasters, vectors, formats

> Status: outline. Learning goals, sections and exercises; the text is still to be written.

## You will learn

- Tell rasters from vectors and know what each is for
- Read a raster's header: size, bands, data type, resolution, nodata, alpha
- Know the common file formats and their quirks

## Sections

1. Rasters: pixels, bands, data types, resolution; orthomosaics, DSMs, DTMs
2. Nodata and alpha: how a raster says 'nothing here'
3. Vectors: points, lines, polygons, attributes, layers
4. Formats: GeoTIFF, GeoPackage, shapefile (and its parts), File Geodatabase, KML, CSV of points
5. Sidecar files: `.aux.xml`, `.ovr`, `.tfw`/`.tfwx`, `.prj`
6. Case: a Rumney Ranch orthomosaic chunk and its dam layer

## Exercises

1. Open a sample raster with rasterio; print its header and explain each field.
2. List the layers of a GeoPackage and the files of a shapefile.
3. Find the function that decides whether a file is a raster.

## Where this lives

- [`data_acquisition/readers/geotiff.py`](../../data_acquisition/readers/geotiff.py)
- [`data_acquisition/readers/vector.py`](../../data_acquisition/readers/vector.py)
- [`data_acquisition/readers/files.py`](../../data_acquisition/readers/files.py)

## Sources

- (links to the sources of each concept, checked when the chapter is written)
