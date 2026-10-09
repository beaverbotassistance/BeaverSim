# Drone surveys and remote sensing: a primer

A practical introduction for people who work on the beaver dataset but have not done
remote sensing before. It explains what kinds of data exist, how a drone survey turns
into maps, what was done in our 2018–2019 field seasons, and which other methods and
tools could be used. Terms in **bold** are defined in the glossary at the end.

---

## 1. Remote sensing in one paragraph

Remote sensing means measuring the landscape without touching it: from a satellite,
an aircraft, or a drone. The sensor records either **light reflected by the surface**
(cameras: what colour is this spot?) or **distance to the surface** (LiDAR: how far away
is this spot?). Everything we use downstream (orthomosaics, elevation models,
vegetation indices, maps of dams and canals) is derived from those two kinds of
measurement plus the position of the sensor when it took them.

---

## 2. Two kinds of geographic data

### Raster: a grid of cells
An image where every pixel covers a known patch of ground.
- Examples: an **orthomosaic** (colour per pixel), a **DEM** (elevation per pixel),
  a vegetation index map.
- Key property: **resolution**, the ground size of one pixel, called **GSD**
  (ground sampling distance). Our drone orthomosaics are about **1.8 cm/pixel**; the
  simulator works at about **0.5–1 m/pixel**.
- Common formats: **GeoTIFF** (`.tif` with location embedded), Cloud-Optimised GeoTIFF.

### Vector: shapes with attributes
Points, lines and polygons with a table of properties.
- Examples: a lodge (point), a canal (line), a pond or a colony boundary (polygon),
  each with fields such as name, length, area, date.
- Common formats: **Shapefile** (`.shp` + `.shx` + `.dbf` + `.prj`, several files per
  layer), **File Geodatabase** (`.gdb` folder, ArcGIS's format, many layers in one
  folder), **GeoPackage** (`.gpkg`, a single open file, the modern default).

### Point clouds: millions of 3D points
Each point has x, y, z (and often colour). Produced by photogrammetry or LiDAR.
- Formats: **LAS / LAZ** (open standard), plus proprietary formats such as
  Metashape's `.oc3`.

---

## 3. Where a pixel is: coordinate reference systems

A coordinate means nothing without its **CRS** (coordinate reference system).

- **Geographic CRS**: latitude/longitude in degrees, e.g. **EPSG:4326** (WGS 84,
  what GPS reports). Degrees are not metres, and a degree of longitude shrinks
  towards the poles, so measuring distances or areas in it is awkward.
- **Projected CRS**: the Earth flattened onto a plane, coordinates in metres. For our
  sites (longitude about −113°) the natural choice is **UTM zone 12N, EPSG:32612**.
- **Vertical datum**: what "height zero" means. GPS heights are above the
  **ellipsoid** (a mathematical shape); map heights are usually above a **geoid**
  model (approximately mean sea level), e.g. NAVD88 in the US. They differ by tens of
  metres, so heights from different sources can't be compared without converting.

**Rule for our pipeline:** reproject everything (rasters and vectors) into one
projected CRS in metres before doing anything else.

---

## 4. How a drone photo survey works

### 4.1 Flying
The drone flies a **lawn-mower pattern** at constant height, taking photos so that
consecutive images overlap (typically 70–80 % forward, 60–70 % sideways). Every point
on the ground then appears in many photos from slightly different angles, which is
what makes 3D reconstruction possible.

Flight height sets the resolution: lower flights give smaller pixels but more photos
and less area per battery. Large areas are flown in several **legs** (one per
battery or per block).

### 4.2 Positioning: how accurately do we know where each photo was taken?

| Setup | How it works | Typical accuracy |
|---|---|---|
| **Consumer GPS** (our case) | The drone's own GNSS receiver tags each photo | about 1–5 m horizontally, worse vertically |
| **RTK** (real-time kinematic) | A base station on a known point sends corrections to the drone in flight | 1–3 cm |
| **PPK** (post-processed kinematic) | Same corrections, applied after the flight from logged data | 1–3 cm |
| **GCPs** (ground control points) | Visible targets on the ground surveyed with a survey-grade GNSS rover; used to pin the model during processing | 1–5 cm |

**Can PPK be applied after the fact?** Only if the drone logged its *raw* satellite
observations during the flight. PPK compares those with a base station's recordings
from the same time. Free base-station data exists (in the US, NOAA's **CORS** network,
with multi-year archives), but our Phantom 4 Pro (camera FC6310) stores only the
final metre-level position in each photo; the RTK variant (FC6310R) is the one that
logs raw observations. No GNSS logs exist on the field-season drive, so PPK is not
possible for the 2018–2019 surveys.

"**Survey-grade**" means the centimetre-level options above. With consumer GPS a map
is internally consistent (distances and shapes inside one survey are right), but the
whole map can be shifted by metres relative to another survey of the same area.
For week-to-week change detection, surveys must be **co-registered**: aligned to each
other using features that did not move (rocks, fences, roads, buildings).

### 4.3 Processing: from photos to maps (photogrammetry)
The standard method is **Structure from Motion + Multi-View Stereo (SfM-MVS)**:

1. **Feature matching**: find the same distinctive points in overlapping photos.
2. **Camera alignment** (**bundle adjustment**): solve for where each photo was taken
   and how the camera lens distorts. Output: camera positions and a **sparse cloud**.
3. **Dense matching**: compute depth for (almost) every pixel. Output: the
   **dense point cloud**.
4. **Surface**: turn the cloud into a mesh and/or an elevation raster (**DSM**).
5. **Orthorectification**: project every photo onto that surface, removing perspective
   and terrain distortion, and blend them. Output: the **orthomosaic**, a map-accurate
   image.

Typical products of one survey:

| Product | What it is | Used for |
|---|---|---|
| Orthomosaic | Map-accurate colour image | Vegetation, water, manual annotation |
| **DSM** (digital surface model) | Elevation of the top surface, including vegetation and structures | Dams, lodges, canopy height |
| **DTM** (digital terrain model) | Bare-ground elevation, vegetation removed | Terrain, flow routing |
| Dense point cloud | 3D points | Deriving DSM/DTM, measuring volumes |
| Mesh / 3D model | Textured surface | Visualisation |

**Known weaknesses of photogrammetry** that matter for beaver sites:
- **Water**: reflections and moving, featureless surfaces don't match between
  photos, so elevation over water is noisy or missing. Water depth can't be measured.
- **Vegetation**: the DSM follows the top of the canopy, not the ground. Getting a DTM
  under dense willow requires filtering, and is never perfect.
- **Repeated texture** (uniform grass, snow) can produce holes or bumps.

---

## 5. Our dataset: what was done in 2018–2019

| | |
|---|---|
| **Sites** | Rumney Ranch, Pilling Ranch, Willow Creek, Cut Bank Creek (northern Montana, about 48.5–49°N, 113°W) |
| **Season** | Weekly surveys May → August 2018; one survey per site in early September 2019 |
| **Drone / camera** | DJI Phantom 4 Pro, camera model FC6310: 20 MP, 1-inch sensor, mechanical shutter (5472 × 3648 px in 2018, 4864 × 3648 in 2019) |
| **Positioning** | Built-in consumer GPS, coordinates in each photo's metadata (EXIF). No RTK; GCPs not yet checked |
| **Resolution** | About 1.7–1.9 cm/pixel, which for this camera means flights roughly 60–70 m above ground |
| **Processing** | Agisoft Metashape: one project per survey, split into **chunks**; orthomosaics exported per chunk as GeoTIFF |
| **Annotation** | ArcGIS: dams, canals, trails, lodges, ponds and colony boundaries digitised by hand on the orthomosaics, often per survey date and per colony |
| **Colonies** | Rumney Ranch 8 (A–H), Pilling Ranch 5 (1–5), Willow Creek 3 (1–3); Cut Bank Creek not annotated |

What this means in practice:
- The **orthomosaics** exist and are high resolution, but come in several CRSs.
- **Elevation models were almost never exported**; dense point clouds exist only
  inside the Metashape projects.
- The **annotations were drawn on those orthomosaics**, so they share the
  orthomosaics' georeferencing, including its metre-level GPS error. Any new product
  (for example a reprocessed orthomosaic) has to be aligned to the original ones
  before the annotations can be overlaid on it.
- The raw photos carry GPS, so every survey **can be reprocessed from scratch** with
  any photogrammetry tool.

---

## 6. Other data sources and methods

### Other sensors
| Sensor | Measures | Strengths | Limits |
|---|---|---|---|
| **RGB camera** (ours) | Visible colour | Cheap, very high resolution | No near-infrared; elevation only through photogrammetry |
| **Multispectral camera** (e.g. MicaSense) | Several narrow bands incl. near-infrared (NIR) | True vegetation indices (NDVI) | Lower resolution, needs radiometric calibration |
| **Thermal camera** | Surface temperature | Water vs land, wet soil, animals | Low resolution |
| **LiDAR** | Distance by laser pulses | Penetrates gaps in vegetation (multiple returns), so better DTMs; direct elevation | Expensive; also unreliable over water |

### Other platforms
| Source | Resolution | Revisit | Notes |
|---|---|---|---|
| Drone (ours) | 1–5 cm | Whenever flown | Small areas (tens of hectares per flight) |
| **NAIP** aerial imagery (USA) | 0.6–1 m, RGB + NIR | Every 2–3 years | Free; good for vegetation context |
| **PlanetScope** satellite | 3 m | Daily | Commercial; academic access programmes exist |
| **Sentinel-2** satellite | 10–20 m | ~5 days | Free; too coarse for individual dams |
| **Landsat** satellite | 30 m | 16 days | Free; decades of history |
| **USGS 3DEP** airborne LiDAR (USA) | ~1 m DEMs | One-off | Free; coverage varies by area |

### Vegetation from colour
Without a near-infrared band, true **NDVI** isn't available. RGB-only indices such as
**ExG** (excess green) or **VARI** are the usual substitute; `data_acquisition/modules/rgb_to_matrix.py`
already implements some of them. They are sensitive to lighting, so values from
different dates must be normalised before being compared.

---

## 7. Tools

| Task | Commercial | Open source |
|---|---|---|
| Photogrammetry | Agisoft **Metashape** (Windows/macOS/Linux; Python API in the Professional edition), Pix4D | **OpenDroneMap** (ODM / WebODM; Docker, command line, Python client `pyodm`) |
| Desktop GIS | ArcGIS Pro | **QGIS** |
| Raster processing (Python) | — | **GDAL**, **rasterio**, rioxarray |
| Vector processing (Python) | — | **geopandas**, shapely, pyogrio |
| Point clouds | — | **PDAL**, CloudCompare, laspy |
| Reprojection | — | **pyproj** (inside all of the above) |

---

## 8. Glossary

- **Bundle adjustment**: the optimisation that solves camera positions and lens
  parameters from matched points across photos.
- **Chunk** (Metashape): an independent part of a project, e.g. one area or one flight leg.
- **Co-registration**: aligning two datasets of the same area so the same feature has
  the same coordinates in both.
- **CRS**: coordinate reference system; defines what the numbers in a coordinate mean.
- **DEM**: digital elevation model; generic name for DSM and DTM.
- **DSM / DTM**: surface (top of everything) vs terrain (bare ground) elevation models.
- **EPSG code**: a numeric ID for a CRS, e.g. 4326 (WGS 84 lat/lon), 32612 (UTM 12N).
- **EXIF**: metadata stored inside a photo (camera, time, GPS position).
- **GCP**: ground control point; a surveyed target used to pin a model to true coordinates.
- **GeoTIFF**: a TIFF image with embedded georeferencing.
- **GNSS**: global navigation satellite systems (GPS, GLONASS, Galileo, …).
- **GSD**: ground sampling distance, the ground size of one pixel.
- **NDVI**: normalised difference vegetation index, (NIR − Red)/(NIR + Red).
- **Orthomosaic**: a mosaic of photos corrected so that it has a uniform map scale.
- **RTK / PPK**: GNSS correction methods giving centimetre-level positions.
- **SfM-MVS**: Structure from Motion + Multi-View Stereo, the photogrammetry method.
- **UTM**: Universal Transverse Mercator, a family of projected CRSs in metres, one per 6° of longitude.
- **World file** (`.tfw`, `.tfwx`, `.jgw`): a small sidecar text file giving an image's
  position and pixel size, used when the georeferencing isn't embedded in the image.
