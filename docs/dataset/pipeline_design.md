# Dataset pipeline: design

Status: draft for review, revision 2, 13 October 2026. Branch: `dev_dataset`.

## 1. Purpose and scope

A pipeline that takes **any beaver-site dataset** we receive or download, lets us **inspect it in
full detail**, and processes it into products for **validation** and **visualisation**.
Producing simulator inputs (including resampling to simulation resolution) comes later and is out
of scope for this document.

Principles:
- **Inspection first.** Before processing anything, show what a dataset contains: types, coverage,
  dates, quality, licence.
- **Dataset-agnostic.** The notebooks and steps know *data types*, never dataset names.
  Everything specific to one source lives in its dataset summary file (§4).
- **SI units everywhere.** Metres, square metres, seconds, ISO 8601 dates in UTC. Other units
  (feet, US survey feet, degrees for distances) are converted at ingest; the original unit is recorded.
- **Physical values are kept.** Stored products are never min–max normalised (see §8).
- **Reproducible.** Every product records the configuration and code version that made it, like
  the simulator's `run.json`.
- **Originals are never modified.** Sources are read-only; everything generated goes to `products/`.

## 2. What data we expect

| Type | Examples so far | Before use it needs |
|---|---|---|
| Raw photos | Montana 2018–2019 (DJI JPG with GPS) | photogrammetry → orthomosaic + DSM |
| Orthomosaic, RGB | Montana originals, Alaska 2021–2024, NAIP, national orthophotos | reproject, co-register, clip |
| Orthomosaic, multispectral | Alaska (green, red, red edge, NIR; reflectance-calibrated) | same, plus band handling |
| Elevation | Alaska DSMs (10 cm), national lidar DEMs | same, plus vertical datum and water/vegetation caveats |
| Satellite time series | Sentinel-2 (10–20 m, optical), Sentinel-1 (10 m, radar) | query by AOI and date, cloud filtering; complementary only |
| Vector annotations | Montana dams/canals/trails per date, Kotzebue dam points, EEAGER traces | normalise fields, reproject, assign to colony |

**Not handled:** video frames (Montana May 2018). They exist only in that dataset, carry no
positioning, and are not a robust input. They stay listed in the catalog as excluded.

## 3. Catalog: STAC

Every dataset is described as a **STAC** (SpatioTemporal Asset Catalog): JSON files that list
items with geometry, time and assets. Remote sources (Sentinel, NAIP) are already published as
STAC; our own data is converted to it by the builder (§4).

Layout, one catalog per source:

```
<catalog root>/catalog.json
  collection: <site>                      e.g. rumney_ranch, swan_lake_dlb
    item: <site>_<YYYY-MM-DD>_<product>   one acquisition of one product
      assets: data files (orthomosaic, dsm, multispectral, photos list, annotations.gpkg, report)
```

- **Items are per epoch and product**: `rumney_ranch_2018-07-06_photos`,
  `swan_lake_dlb_2022-08-12_orthomosaic`.
- **Raw photos** are one item per survey, with one asset: a photo list (CSV) pointing at the files.
- **Annotations** use the STAC *label* extension: one item per site and date, one GeoPackage asset.
- **Extensions:** `proj` (CRS, bounds), `eo` and `raster` (bands, resolution), `file` (checksums),
  `label` (annotations), and our own `beaver:` fields (§3.1).
- **Remote catalogs are queried, not copied** (§7, `sentinel_series`).

Python tooling: `pystac`, `pystac-client`, `rasterio`/`rioxarray`.

### 3.1 The `beaver:` descriptors and how they are collected

Collecting these fields is a pipeline step of its own (`curate`, §7), run once per dataset and
revisited when new information arrives. Every field records **where its value came from**:
`auto` (derived from the data), `repository` (from the source's metadata), `claude` (from a
summary drafted by Claude and not yet reviewed), or `manual` (entered or checked by a person,
with name and date).

| Field | Meaning | Collected by |
|---|---|---|
| `beaver:site` | site slug | summary file, confirmed manually |
| `beaver:colonies` | colonies present in the item | annotations or AOI intersection (§5) |
| `beaver:positioning` | `rtk`, `gnss`, `gcp`, `none` | auto (EXIF, processing report) or repository |
| `beaver:season` | winter / spring / summer / autumn | auto (date and latitude) |
| `beaver:quality` | flags: partial coverage, water elevation unreliable, misfiled, corrupt… | auto checks + manual notes |
| `beaver:licence` | SPDX id (CC0-1.0, CC-BY-4.0, …) | repository; manual for private data |
| `beaver:land_status` | ownership / jurisdiction of the site | **manual** |
| `beaver:governance` | data-use terms, Indigenous data-governance notes, publication approval needed | **manual** |
| `beaver:provenance` | source, DOI, original path, downloaded date, checksum | builder (metadata record, download log) |

Manual fields live in the dataset's **summary** file (§4), so they are versioned and reviewable. The
inspect notebook shows fields still missing and blocks nothing: it reports what is unknown.

## 4. From files to a catalog: readers, summaries, one builder

There are no per-source adapters with their own logic. Code is organised by **data type** and by
**metadata standard**. Everything specific to a source or site is written as **data**, in a
dataset summary file:

| Part | What it knows | Where |
|---|---|---|
| **Readers** | one data type (GeoTIFF, vector, drone photos) or one metadata standard (EML) | `readers/` |
| **Dataset summary** | per dataset: sites (CRS, manual fields), and per group of files (one DOI, one survey): site, date, product, sensor, positioning, bands, notes; which report belongs to which product | `summaries/<dataset>.yaml` |
| **Builder** | data root + summary → STAC catalog; cross-checks summary, file header and metadata record | `catalog/build.py` |
| **Access clients** | one protocol each (DataONE download, STAC API query) | `sources/` |

Rules:
- **Structured facts come from readers**, never from the summary: CRS, bounds, band count,
  checksums, licence, repository dates.
- **Disagreements are flagged, not resolved**: summary vs file header vs metadata record
  (band order and count, file not in the record, size, date outside the record). Files on disk
  that the summary doesn't describe, and described files that are missing, are reported.
- **Workarounds are written in the summary as data** (e.g. "the repository's band descriptions are
  shifted; bands follow the methods text"), with a note that travels to the item's quality flags.
- **Lessons from the earlier scripts** (`dataset/`, reference only; the first downloader `open_data/arcticdata.py` was replaced by `sources/dataone.py` and `readers/eml.py`) become rules of
  the readers they belong to. For drone photos: capture date from EXIF, not folder names; site from
  GPS when a photo is far from its folder's site; duplicates by capture time and size. For any
  file: detect split copies, non-georeferenced exports, corrupt files and empty layers. For
  downloads: verify against repository checksums.

**Who writes the summary.** A person, or Claude. `catalog/describe.py` gathers the evidence (file
list, headers, metadata records) and writes a prompt with the drafting rules. A **Claude Code
session** drafts the summary from it, which is covered by a Claude Pro/Max subscription and is the
default path. The same rules can run through the **Claude API** (`describe draft`), which is billed
separately per token, for unattended use. Either way the draft is schema-checked and reviewed.
Summary values are recorded with source `claude` (model and date) until the file has a `reviewed`
entry, then as `manual`. Land status and governance are always entered by a person. How-to:
[describing_a_dataset.md](describing_a_dataset.md).

## 5. Space

### 5.1 Levels

| Level | Extent | Used for |
|---|---|---|
| Region | 10–500 km² | dam inventories, network analysis, Sentinel context |
| Site | 1–10 km² | photogrammetry, co-registration (needs stable features outside colonies) |
| Colony | 1–25 ha | the unit for validation and figures; matches the simulator |

### 5.2 Coordinate reference systems

- **Horizontal: one projected CRS per site, its local UTM zone, in metres** (Montana EPSG:32612,
  Swan Lake EPSG:32603). UTM is used because a global CRS can't be in metres without large
  distortion.
- **Vertical: metres.** All heights are converted to metres at ingest. Reference: ellipsoidal
  height (WGS 84), the datum GNSS measures and the Alaska DSMs already use. Heights given in another
  datum or unit (e.g. Rumney annotations: NAVD88, US survey feet) are transformed with `pyproj` and
  the original datum is recorded.
- Lat/lon is used only for the STAC footprint (required by the standard), never for measurements.

### 5.3 Areas of interest (colonies)

`colonies.gpkg` per site, one polygon per colony, with `source` = `annotated`, `estimated` or `manual`.

- **Where colony polygons exist** (Rumney Ranch, from the original annotations): taken as
  `annotated` and used as given, still shown for review.
- **Where they don't** (Pilling, Willow, Alaska): an **automatic first estimate**, then review:
  1. **Seed features:** the colony's annotated features where colony tags exist (lodges, dams,
     canals, trails). Otherwise dams, lodges and ponds are grouped into candidate colonies with
     **DBSCAN** on distances between geometries (nearest edges, not centroids):
     - DBSCAN, not k-means: the number of colonies is unknown, colonies are elongated along
       streams, and isolated structures should be allowed to stay out (noise). k-means needs the
       count, assumes compact clusters of similar size and assigns every point.
     - Parameters: `eps` (joining distance) and `min_samples`. Colonies are kilometres apart
       (Jordan), structures within a colony tens to hundreds of metres apart, so `eps` has a wide
       gap to sit in.
     - Known risk: chaining, i.e. continuous dams along a stream linking two colonies. Checked
       during calibration.
  2. **Activity zone:** the union of buffers around those features: the colony extends beyond its
     structures because beavers forage and dig canals and trails away from them. Default **50 m**.
  3. **Review:** the notebook shows the estimate over the imagery; the user edits (redraws, merges,
     splits) and approves. The approved polygon is saved as `manual`, with name and date.

**Calibration of both distances** from the annotated Montana colonies (Rumney: 8 colonies with
polygons; Pilling: 5 colonies with tagged features), with literature as a check (foraging typically
within ~100 m of water, rarely beyond ~200 m):
- `eps`: distances between structures of the same colony versus between structures of different
  colonies; the threshold must separate them, and DBSCAN must recover the known colonies.
- buffer: how far annotated canals and trails reach beyond dams, lodges and water; a high
  percentile (e.g. 95th) is the candidate value, compared with the 50 m default.

### 5.4 Colony assignment of vector annotations

Every annotation feature gets `colony` and `colony_source`:

| Case | Rule | `colony_source` |
|---|---|---|
| Colony given in the data (layer name or attribute) | keep it | `annotated` |
| No colony given | the colony polygon it intersects (largest overlap for lines and polygons) | `spatial` |
| Given colony disagrees with the polygon it lies in | keep both, flag for review | `conflict` |
| Outside every colony polygon | no colony | `unassigned` |

Conflicts and unassigned features are listed in the inspect notebook.

## 6. Time

- **Epochs are the data's own dates.** No interpolation between epochs by default.
- **Each epoch carries a season tag**, because a March survey shows snow, not vegetation.
- **Combining sources:** epochs are matched by nearest date within a tolerance set in the config
  (e.g. a drone survey and the closest cloud-free Sentinel-2 scene within ±5 days).
- **Typical cadences:** weekly within one season (Montana 2018), yearly (Alaska 2021–2024),
  1–2 years (orthophoto programmes), every few days (Sentinel-2, cloud permitting).

## 7. Steps

Each step is a module under `data_acquisition/steps/` declaring its inputs (item types), outputs
and level. A step writes its outputs as new STAC items linked to their inputs (`derived_from`),
and produces a standard figure.

| Step | Needs | Produces | Level |
|---|---|---|---|
| `curate` | catalog + summary | filled `beaver:` descriptors, list of missing fields | dataset |
| `photogrammetry` | raw photos | orthomosaic, DSM (OpenDroneMap) | site |
| `reproject` | raster or vector | same data in the site CRS and SI units, **native resolution** | site |
| `coregister` | two rasters of the same site, different dates | aligned raster + shift estimate | site |
| `define_aoi` | colony tags, annotations, lodges/dams | estimated colony polygons → review → `colonies.gpkg` | site |
| `clip` | raster or vector + AOI | clipped product | colony |
| `annotations` | vector layers | normalised GeoPackage per date (kind, colony, colony_source, date, source) | site |
| `water_mask` | multispectral / Sentinel (water index), or RGB heuristic | water raster | site / colony |
| `vegetation_index` | RGB (ExG, VARI) or NIR (NDVI) | index raster | site / colony |
| `sentinel_series` | AOI + date range | **clipped** scenes and per-date water/vegetation statistics, AOI only | colony / region |
| `change` | two epochs of the same product | difference raster or vector diff + summary | colony |

**Resampling:** `reproject` keeps each product's native resolution. Reprojection still has to
interpolate pixels: bilinear for continuous values (RGB, elevation, indices), nearest neighbour for
classes (masks, labels). Choosing a common resolution is deferred to the simulator-input stage.
Figures may downsample for display only.

Later, not in this first version: `elevation_above_water`, `export_simulator`.

## 8. Normalisation

Stored products keep **physical or native values**; nothing is min–max normalised. Min and max
change between epochs (lighting, season, a new pond), so per-epoch min–max scaling would make epochs
incomparable. What we do instead, per type:

| Type | Handling |
|---|---|
| Elevation | never normalised; metres (§5.2) |
| Multispectral | already reflectance-calibrated (Alaska: calibration panel) → no normalisation |
| RGB | values stay as delivered. Comparisons across epochs use (a) **ratio-based indices** (ExG, VARI are computed from chromatic coordinates r/(r+g+b), …, so overall brightness cancels) and, where needed, (b) **relative radiometric normalisation** to a reference epoch, fitted only on stable areas (bare ground, roads, rock) and recorded as a transform, never baked into the stored data |
| Sentinel-2 | surface reflectance (L2A) → no normalisation |
| Display | a fixed stretch per dataset (e.g. percentiles of a reference epoch), the same for all epochs, applied only when drawing |

## 9. Notebooks

Two notebooks, both dataset-agnostic. Sections appear based on the item types in the catalog,
never on the dataset name. Both start with **reminders**: check governance notes and land status
before sharing figures; check basemap terms before using maps in publications.

**`inspect.ipynb`**: catalog → understanding.
1. Load or build the catalog (data root + summary file).
2. Summary: items by type, site, date; licences; governance notes; descriptors still missing.
3. Coverage map: footprints of all items, AOIs if present.
4. Timeline: one row per product type, one mark per epoch; Sentinel dates alongside.
5. Item browser: quick-look, descriptors and quality flags for any item.
6. Side by side: any two items over the same area at the same scale.
7. Annotations: features per colony and date, conflicts and unassigned features.

**`process.ipynb`**: config → products.
1. Load the catalog; the planner proposes a plan.
2. Config dictionary, pre-filled from the plan and the summary:
   ```python
   config = {
       "catalog": "...",
       "sites": ["swan_lake_dlb"],
       "colonies": "all",
       "epochs": {"from": "2021-01-01", "to": "2024-12-31", "season": ["summer"]},
       "steps": ["curate", "define_aoi", "reproject", "clip", "vegetation_index", "sentinel_series", "change"],
       "aoi": {"cluster_distance_m": 300, "buffer_m": 100},
       "sentinel": {"max_cloud": 20, "match_days": 5},
       "medium": "chapter",
   }
   ```
3. AOI review (when `define_aoi` runs): estimate shown, user edits and approves, then continue.
4. Run: each step's products and standard figure.
5. Report: per colony, epochs side by side and change over time.

## 10. Products and provenance

```
<dataset root>/products/<run id>/
  run.json          config, git commit, catalog used, step versions, date
  catalog.json      STAC catalog of the products (linked to the source items)
  <site>/<colony>/<epoch>/...
  figures/
```

The dataset roots are on the field-season drive (`beaver_dataset/`-like folder for the field data,
`open_datasets/` for downloads). Sentinel data is stored only as AOI-clipped windows. Large
intermediate files (photogrammetry working folders) go to the PC during processing and are deleted
afterwards.

## 11. Code layout

```
data_acquisition/
  catalog/      STAC helpers, descriptors, summary schema, build.py (summary → catalog)
  readers/      geotiff, eml; later vector, photos
  sources/      dataone (download); later stac_api (Sentinel, NAIP)
  summaries/    one YAML file per dataset
  steps/        one module per step
  planner.py
  dataset/      earlier scripts, reference only
  modules/      existing DEM/RGB conversion, reused where useful
notebooks/dataset/inspect.ipynb, process.ipynb
```

Figures use `beaversim.viz` (theme, palette, media presets) so they match the simulator's.

## 12. Implementation order

| # | Milestone | Done when |
|---|---|---|
| 1 | Catalog helpers, GeoTIFF/EML readers, builder, DataONE client, `curate` | Swan Lake downloads described as a valid STAC catalog with descriptors (**done**) |
| 2 | `inspect.ipynb` on Swan Lake | coverage map, timeline, item browser, side-by-side work |
| 3 | `stac_api` source + Sentinel-2 in the timeline and side-by-side | Sentinel dates and clipped quick-looks over Swan Lake |
| 4 | photo and vector readers + Montana summary | Montana in the same inspect notebook, no notebook changes |
| – | `describe`: Claude drafts a summary from the evidence (Claude Code or API) | **done** |
| 5 | Planner + `process.ipynb` with `reproject`, `define_aoi` (+ review), `clip`, `vegetation_index` | colony products for Swan Lake |
| 6 | `annotations` (colony assignment), `water_mask`, `sentinel_series`, `change` | multi-year colony report for Swan Lake; annotated epochs for Rumney |
| 7 | `photogrammetry` (OpenDroneMap) and `coregister` | Montana surveys processed into the same products |

Milestones 1–4 are inspection only and deliver the "see everything in a dataset" goal.

## 13. Open questions

1. **Reference epoch for RGB comparison** per site, and which stable areas to use.

Decided, OpenDroneMap (milestone 7): the development environment is itself a Docker container, so
OpenDroneMap runs **on the host**, as a **NodeODM server** (`docker run -p 3000:3000
opendronemap/nodeodm`). The pipeline submits surveys and collects results through `pyodm`.
OpenDroneMap needs one flat image folder per survey; the pipeline prepares it on the drive as
read-only hard links renamed with their camera subfolder (`100MEDIA_DJI_0001.JPG`), since file
names repeat across subfolders. To check when we get there: that this environment can reach the
host's port 3000. Fallback: the pipeline prepares the job folder and prints the `docker run` command
to run in a host terminal.

Decided, AOI distances: DBSCAN `eps` and buffer calibrated from the annotated Montana colonies,
literature as a check (§5.3).

Decided: Sentinel stored as AOI-clipped windows only; AOIs as automatic estimate + user review;
governance and basemap reminders at the top of both notebooks; resampling to a common resolution
deferred to the simulator-input stage; video frames not handled.
