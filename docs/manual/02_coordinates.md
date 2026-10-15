# 2. Coordinates: CRS, projections, units, heights

Every pixel of an orthomosaic and every vertex of a dam outline is a pair of numbers. Those numbers mean
nothing until you know **what system they are in**. Getting this wrong does not produce an error: it
produces data that sits in the wrong place, sometimes by centimetres, sometimes by kilometres. This
chapter explains the systems, how files describe them, and how the pipeline checks them, ending with a
real case from our own data where the same numbers land 25 km apart depending on the software.

## You will learn

- What a coordinate reference system (CRS) is, and why there are thousands of them
- How to read an EPSG code and a WKT description, and tell a geographic CRS from a projected one
- Why the same coordinates can end up in different places, and how to check that they don't
- How heights are described (vertical datums, compound CRSs, US survey feet)
- Where the pipeline reads, records, checks and corrects CRSs

## 1. Positions on the Earth: geographic coordinates

The simplest way to give a position is **latitude and longitude**, angles in degrees measured on a model of
the Earth. The model matters: the Earth is not a sphere but closer to a flattened sphere, an
**ellipsoid**, and a **datum** fixes such an ellipsoid to the real Earth. The datum almost everyone uses
today is **WGS 84**, the one GPS reports in
([NGA, WGS 84](https://earth-info.nga.mil/index.php?dir=wgs84&action=wgs84)).

A CRS made of a datum and angles is a **geographic CRS**. The most common one has the code
[EPSG:4326](https://epsg.io/4326): WGS 84, latitude and longitude in degrees. Our drone photos record their
position in it (chapter 3), and some of the Montana orthomosaic tiles are stored in it.

Degrees are awkward for measuring: one degree of longitude is about 111 km at the equator but only about
73 km at Rumney Ranch (49° N), and a pixel "0.0000002 degrees wide" says nothing useful about its size on
the ground. That is why maps are usually drawn in projected coordinates.

## 2. Projected coordinates: flattening the Earth

A **projection** is a formula that turns latitude and longitude into flat x and y coordinates, usually in
metres ([PROJ: projections](https://proj.org/en/stable/usage/projections.html)). A **projected CRS** is a
geographic CRS plus a projection. No projection keeps every distance, angle and area true at once, so each
is a compromise chosen for a region and a purpose
([QGIS, a gentle introduction to CRSs](https://docs.qgis.org/latest/en/docs/gentle_gis_introduction/coordinate_reference_systems.html)).

For small areas like our sites, the usual choice is **UTM** (Universal Transverse Mercator): the world is
cut into 60 zones 6° wide, each with its own projection, accurate to well under a metre per kilometre
inside the zone ([PROJ: utm](https://proj.org/en/stable/operations/projections/utm.html)). Rumney Ranch is
in zone 12 north, [EPSG:32612](https://epsg.io/32612); Swan Lake in Alaska is in zone 3 north
(EPSG:32603). Coordinates in UTM are metres: an easting of about 300,000–700,000 and a northing that is the
distance from the equator (5,420,000 m at Rumney).

**In the pipeline:** every site has one working CRS, its local UTM zone, written in the site registry
[`data_acquisition/sites.yaml`](../../data_acquisition/sites.yaml) (`crs: EPSG:32612`). Data in another CRS
are not converted in milestone 1; they are flagged (`crs_mismatch` for rasters, `crs_differs` for vectors) so
that a later step knows what to reproject.

## 3. How a file says which CRS it uses

A file can describe its CRS in several ways, and the same CRS can be written in many of them:

| Form | Example | Notes |
|---|---|---|
| **EPSG code** | `EPSG:32612` | A number in the [EPSG registry](https://epsg.org/home.html), kept by the oil and gas industry's geodesy committee (IOGP). Short and unambiguous when it exists. |
| **PROJ string** | `+proj=utm +zone=12 +datum=WGS84 +units=m` | The parameters of the formula ([PROJ](https://proj.org/en/stable/)). Compact, but loses details (names, areas of use). |
| **WKT** (Well-Known Text) | `PROJCRS["WGS 84 / UTM zone 12N", BASEGEOGCRS[...], CONVERSION[...], CS[...]]` | The full description. WKT1 is the older dialect, WKT2 the current standard ([OGC 18-010r11](https://docs.ogc.org/is/18-010r11/18-010r11.pdf)). ESRI software writes its own WKT1 variant. |

A CRS **without** an EPSG code is still a valid CRS, as long as its WKT says everything. ESRI defines many
CRSs of its own (codes like `ESRI:102432`), and software that does not know them sees only their WKT.

Some files have **no CRS at all**: an ESRI ASCII grid, a CSV of points, a picture with a world file. Then the
CRS must come from somewhere else, usually the dataset's documentation.

**In the pipeline:** the raster reader returns the EPSG code when there is one and the WKT otherwise
([`geotiff.info`](../../data_acquisition/readers/geotiff.py)); the catalogue writes the EPSG code, or the WKT2
when there is no code, into the item's [projection extension](https://github.com/stac-extensions/projection)
([`stac.raster_item`](../../data_acquisition/catalog/stac.py)). A raster with no CRS is a **required**
gap: the summary must give one (`crs: EPSG:<code>`, taken from the record or its text), or the file is
skipped and reported as unsupported ([chapter 6](06_what_the_pipeline_needs.md)).

## 4. Units: metres, degrees, and the size of a pixel

The CRS also fixes the **units**. In a projected CRS they are usually metres; in a geographic CRS, degrees.
A raster stores its pixel size in those units, so a 1.3 cm pixel of an EPSG:4326 orthomosaic is stored as
about 0.00000018 degrees.

The STAC standard says the ground sample distance (`gsd`) of an item is in metres
([STAC common metadata](https://github.com/radiantearth/stac-spec/blob/master/commons/common-metadata.md)),
so the pipeline converts degrees to metres at the raster's latitude before writing it
([`stac.resolution_m`](../../data_acquisition/catalog/stac.py)). An earlier version did not, wrote
`gsd: 0.0` for 21 Rumney tiles, and failed STAC validation: a typical units bug.

## 5. Heights: vertical datums and compound CRSs

Heights need a reference too. A height above the WGS 84 ellipsoid differs from a height above sea level by
tens of metres, depending on where you are. A **vertical datum** fixes the zero; in the United States the
usual one is NAVD 88 ([NOAA NGS, NAVD 88](https://geodesy.noaa.gov/datums/vertical/north-american-vertical-datum-1988.shtml);
[NOAA NGS, datums](https://geodesy.noaa.gov/datums/index.shtml)).

A CRS that gives both horizontal and vertical positions is a **compound CRS**: a horizontal CRS plus a
vertical one. The Rumney Ranch annotation layers use one: the ARC System zone (below) plus
"NAVD88 height (ftUS)", heights in **US survey feet**. The US survey foot is 1200/3937 m, about
0.3048006 m, slightly longer than the international foot of 0.3048 m; it became obsolete at the end of 2022
but survives in older data ([NIST, the U.S. survey foot](https://www.nist.gov/pml/us-surveyfoot)).

**In the pipeline:** the vector reader splits a compound CRS into its two parts and records the vertical
one with its unit ([`vector._split`](../../data_acquisition/readers/vector.py)); `curate` flags heights in
feet (`vertical_unit_feet`) so that nobody mixes them with metres
([`curate.check_vector`](../../data_acquisition/steps/curate.py)).

## 6. When the same numbers land in different places

Coordinates are only as good as the CRS that comes with them. Three things move data without changing a
single number:

1. **A wrong or missing CRS.** Some Montana tiles store degrees but declare a CRS in metres; read as
   declared, they land near latitude 0, longitude 0, off the coast of Africa.
2. **Georeferencing kept outside the file.** ArcGIS can store a correction in a sidecar file that other
   software ignores (chapter 3 and [chapter 11](11_field_data.md)).
3. **The same CRS read differently by two programs.** The case below.

The defence is to check positions by **effect**, not by text: transform a few points with each description
and compare where they land. Two WKT texts can differ and mean the same place; the field step's check does
exactly this ([`field._same_place`](../../data_acquisition/sources/field.py)).

## Case: the ARC System zone, 25 km apart

The Rumney Ranch annotations were drawn in ArcGIS in the CRS "WGS_1984_ARC_System_Zone_12"
(`ESRI:102432`), an Equidistant Cylindrical projection. That projection has two forms: one on a **sphere**
(EPSG method 1029) and one on the **ellipsoid** (EPSG method 1028)
([PROJ: eqc](https://proj.org/en/stable/operations/projections/eqc.html);
[ArcGIS: Equidistant Cylindrical](https://pro.arcgis.com/en/pro-app/latest/help/mapping/properties/equidistant-cylindrical.htm)).
ArcGIS evaluates this CRS on a sphere. The file's description, once converted to plain WKT, just says
"Equidistant Cylindrical on WGS 84".

For years PROJ, the library almost every open-source GIS tool uses, had only the spherical formula, so the
ambiguity did not matter. **PROJ 9.8.0 (2 March 2026) added the ellipsoidal form**
([PROJ news, 9.8.0](https://proj.org/en/stable/news.html): "Add support for Equidistant Cylindrical
ellipsoidal method (EPSG:1028)"). Since then the same description is evaluated on the ellipsoid, and every
Rumney layer moves about **25 km north-east**.

In our own environment both behaviours coexist: pyproj ships PROJ 9.5.1 and puts a Rumney dam at
48.9245° N, 113.1391° W; rasterio and GDAL ship PROJ 9.8.1 and put the same coordinates at 49.1495° N,
112.9018° W. Which is right? ArcGIS itself wrote latitude and longitude columns into some layers: with the
sphere they agree to 0.19 m, with the ellipsoid they are 25 km off.

**How the pipeline handles it:** the correction is data, not code. The layout file of the site declares it,
with its evidence
([`field_layouts/rumney_ranch.yaml`](../../data_acquisition/field_layouts/rumney_ranch.yaml),
`crs_corrections`), and the field step writes every exported layer with the sphere spelled out
(`+R=6378137`), so that every version of PROJ reads it the same way. The check after each export compares
positions under **both** PROJ versions ([`field.corrected_crs`](../../data_acquisition/sources/field.py),
[`field._same_place`](../../data_acquisition/sources/field.py)). The coordinates in the files are not changed.

## 7. Reprojecting, and why milestone 1 does not

**Reprojecting** converts coordinates from one CRS to another, for example from the ARC zone to UTM 12N,
with a library such as PROJ (through [pyproj](https://pyproj4.github.io/pyproj/stable/) or
[rasterio](https://rasterio.readthedocs.io/en/stable/topics/georeferencing.html)). For vectors it only moves
vertices; for rasters it resamples pixels, which changes them a little. Milestone 1 never reprojects: it
records each file's CRS as found, flags where it differs from the site's, and leaves the conversion to the
processing milestones, so that the catalogue always describes the data as they are.

## Exercises

Use the sample data root ([00 Setup](00_setup.md)) and the Montana extract
([`docs/manual/data/montana_extract/`](data/montana_extract/README.md)).

1. **Read a CRS.** Open `ortho_2023-07-12.tif` of the sample root with rasterio. Print `crs`, `crs.to_epsg()`
   and `crs.to_wkt()`. Is it geographic or projected? What are the units of `res`?
2. **Degrees and metres.** Transform the four corners of the sample orthomosaic to EPSG:4326 with
   `pyproj.Transformer`. How wide is the image in degrees of longitude, and in metres? Explain the ratio.
3. **No CRS.** Open `dem_2022.asc`. What does rasterio report as its CRS? Where in the sample's
   `metadata.xml` would you find the CRS to put in the summary?
4. **Heights in feet.** Open `2018-07-26/annotations/dams.gpkg` of the Montana extract with `pyogrio.read_info`.
   Split its CRS into horizontal and vertical parts (`pyproj.CRS.from_user_input(...).sub_crs_list`). What is
   the vertical datum, and its unit? How many metres is 5 US survey feet?
5. **Two PROJ versions.** Take the first vertex of a dam in the extract (the dams are MultiPolygons:
   `geometry.iloc[0].geoms[0].exterior.coords[0]`). Transform it to EPSG:4326 with
   `pyproj` (PROJ 9.5) and with `rasterio.warp.transform` (PROJ 9.8), first using the CRS written in the file,
   then using `+proj=eqc +lat_ts=-52.28859923 +datum=WGS84 +units=m`. Which pairs agree and which are 25 km
   apart? Why does the file in the extract not show the problem?
6. **Find it in the code.** Which function writes the WKT2 of a raster into its STAC item when there is no
   EPSG code? Which flag does `curate` raise for a raster whose CRS differs from the site's, and in which
   function?

## Where this lives

- [`data_acquisition/sites.yaml`](../../data_acquisition/sites.yaml): each site's working CRS.
- [`data_acquisition/readers/geotiff.py`](../../data_acquisition/readers/geotiff.py) (`info`) and
  [`data_acquisition/readers/vector.py`](../../data_acquisition/readers/vector.py) (`_split`, `_epsg`): reading CRSs.
- [`data_acquisition/catalog/stac.py`](../../data_acquisition/catalog/stac.py) (`raster_crs`, `footprint`,
  `resolution_m`, `raster_item`): footprints, `gsd` and the projection extension.
- [`data_acquisition/steps/curate.py`](../../data_acquisition/steps/curate.py) (`check_raster`, `check_vector`):
  `crs_mismatch`, `crs_differs`, `vertical_unit_feet`.
- [`data_acquisition/sources/field.py`](../../data_acquisition/sources/field.py) (`corrected_crs`, `_lonlat`,
  `_same_place`) and [`data_acquisition/field_layouts/rumney_ranch.yaml`](../../data_acquisition/field_layouts/rumney_ranch.yaml)
  (`crs_corrections`): the ARC-zone correction.
- [`tests/dataset/test_field.py`](../../tests/dataset/test_field.py) (`test_same_place_catches_a_different_earth_model`).

## Sources

- NGA, [World Geodetic System 1984](https://earth-info.nga.mil/index.php?dir=wgs84&action=wgs84)
- IOGP, [EPSG Geodetic Parameter Dataset](https://epsg.org/home.html); [EPSG:4326](https://epsg.io/4326), [EPSG:32612](https://epsg.io/32612)
- PROJ, [documentation](https://proj.org/en/stable/), [projections](https://proj.org/en/stable/usage/projections.html),
  [UTM](https://proj.org/en/stable/operations/projections/utm.html),
  [Equidistant Cylindrical](https://proj.org/en/stable/operations/projections/eqc.html), [news](https://proj.org/en/stable/news.html)
- OGC, [Well-known text representation of coordinate reference systems (18-010r11)](https://docs.ogc.org/is/18-010r11/18-010r11.pdf)
- QGIS, [Coordinate Reference Systems](https://docs.qgis.org/latest/en/docs/gentle_gis_introduction/coordinate_reference_systems.html)
- Esri, [Equidistant Cylindrical](https://pro.arcgis.com/en/pro-app/latest/help/mapping/properties/equidistant-cylindrical.htm)
- NOAA NGS, [NAVD 88](https://geodesy.noaa.gov/datums/vertical/north-american-vertical-datum-1988.shtml), [datums](https://geodesy.noaa.gov/datums/index.shtml)
- NIST, [The U.S. survey foot](https://www.nist.gov/pml/us-surveyfoot)
- STAC, [common metadata](https://github.com/radiantearth/stac-spec/blob/master/commons/common-metadata.md),
  [projection extension](https://github.com/stac-extensions/projection)
- [pyproj](https://pyproj4.github.io/pyproj/stable/), [rasterio: georeferencing](https://rasterio.readthedocs.io/en/stable/topics/georeferencing.html)
