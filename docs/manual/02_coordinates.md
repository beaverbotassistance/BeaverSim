# Coordinates: CRS, projections, units, heights

> Status: outline. Learning goals, sections and exercises; the text is still to be written.

## You will learn

- Explain what a coordinate reference system is and why there are many
- Read EPSG codes and WKT; tell geographic from projected CRSs
- Know why the same numbers can land in different places
- Handle vertical datums and units (feet vs metres)

## Sections

1. Geographic coordinates: latitude, longitude, datums (WGS 84)
2. Projections and projected CRSs: UTM and others; EPSG codes
3. Describing a CRS: EPSG, PROJ strings, WKT1 and WKT2
4. Units and resolution: metres vs degrees (why `gsd` must be in metres)
5. Heights: vertical datums (NAVD88), compound CRSs, US survey feet
6. Reprojecting, and why the pipeline does not do it in milestone 1
7. Case: the ARC System zone read on a sphere by ArcGIS and on an ellipsoid by newer PROJ (25 km apart)

## Exercises

1. Transform a point between EPSG:4326 and the site's UTM zone.
2. Reproduce the 25 km ARC-zone difference with two PROJ definitions.
3. Find where the field step corrects a CRS and where the correction is declared.

## Where this lives

- [`data_acquisition/sources/field.py`](../../data_acquisition/sources/field.py)
- [`data_acquisition/field_layouts/rumney_ranch.yaml`](../../data_acquisition/field_layouts/rumney_ranch.yaml)
- [`data_acquisition/catalog/stac.py`](../../data_acquisition/catalog/stac.py)
- [`data_acquisition/sites.yaml`](../../data_acquisition/sites.yaml)

## Sources

- (links to the sources of each concept, checked when the chapter is written)
