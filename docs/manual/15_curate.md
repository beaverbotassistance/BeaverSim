# 15. `curate` and the descriptors

The builder makes an item from what the file, the record and the summary say. `curate` adds what code can check
by looking at the data itself, and what people have decided about the site. This chapter opens
[`steps/curate.py`](../../data_acquisition/steps/curate.py) and
[`catalog/descriptors.py`](../../data_acquisition/catalog/descriptors.py): the descriptors and their sources, each
automatic check and its thresholds, how files are verified, and how to add a check.

## You will learn

- What the `beaver:` descriptors are, and why each records its source
- What `curate` does to an item, in order
- Every automatic check, with its threshold
- How a file is verified, and against what
- How to add a new check

## 1. Descriptors and their sources

A **descriptor** is one of nine fields every item should have, stored as `beaver:<field>`
(`descriptors.FIELDS`): `site`, `colonies`, `positioning`, `season`, `quality`, `licence`, `land_status`,
`governance`, `provenance`. They are what the design calls "knowing a dataset"
([`pipeline_design.md` §3.1](../dataset/pipeline_design.md#31-the-beaver-descriptors-and-how-they-are-collected)).

Each value records where it came from, in `beaver:origin` (`descriptors.set_field`):

| Source | Meaning | Carries |
|---|---|---|
| `auto` | computed from the data by code | an optional note |
| `repository` | read from the source's metadata record | |
| `claude` | written by Claude, in a summary or the registry, not yet reviewed | who (`claude (<model>)`) and when |
| `manual` | entered or checked by a person | who and when |

`set_field` refuses an unknown field, an unknown source, and a `claude` or `manual` value without who entered it.
A field whose value is None is **missing** (`descriptors.missing`), and `curate_report.csv` lists it.

Quality flags (`beaver:quality`) have the same sources plus `build` (the builder's cross-checks,
[chapter 14](14_builder.md)).

Why record the source? Because the same value means different things: "summer" computed from a date, a licence
copied from a record, colonies a person has checked, and colonies Claude proposed are not equally trustworthy. Only a
`manual` value is confirmed.

## 2. What `curate_item` does

For one item, in this order:

1. **site**: if the registry has no such site, flag `unknown_site` and stop;
2. **clear** the previous `auto` flags (every other source is kept): checks are recomputed on every run;
3. **site confirmation** from the registry (`confirmed: {by, date}`), as `manual` or `claude` by who entered it;
4. **season** (`auto`), and `snow_likely`;
5. **colonies, land status, governance** from the registry, or None (missing);
6. for each **data asset**: `missing_file`; then `check_raster` or `check_vector` (photo folders were checked when
   built); and with `verify_files`, `verify`.

`curate` runs it on every item of a catalogue, saves the catalogue, writes `curate_report.csv`, and `main` then
validates the catalogue against the STAC schemas.

## 3. The automatic checks

**Season** (`descriptors.season`): meteorological seasons, whole months (December to February is winter in the
north; [NOAA](https://www.ncei.noaa.gov/news/meteorological-versus-astronomical-seasons)), flipped south of the
equator, from the latitude of the footprint's centre. An item with a period gets one season only if the period
stays within one and lasts at most 92 days; otherwise `multiple` (a range of exact dates) or `unknown` (a month or
year, or an unknown date).

| Flag | Kind | Raised when | Constant |
|---|---|---|---|
| `snow_likely` | any | a single-date item at 55° latitude or more, dated November to April (May to October in the south) | `SNOW_LATITUDE` |
| `unreadable` | raster, vector | the reader fails | |
| `crs_mismatch` | raster | the CRS is not the site's (also for a CRS without EPSG code) | |
| `unapplied_georeference` | raster | an ArcGIS adjustment in the `.aux.xml` ([chapter 13](13_readers.md)) | |
| `nodata_undeclared` | raster | no nodata value and no alpha band | |
| `sample_empty` | raster | the central 1024 × 1024 window has no valid pixel | `SAMPLE` |
| `elevation_range` | DSM, DTM | a sampled height below -500 m or above 9000 m | `ELEVATION_RANGE` |
| `not_reflectance` | multispectral | more than 1 % of sampled values outside 0 to 1.5 | `REFLECTANCE_RANGE` |
| `empty_layers` | vector | layers without features | |
| `crs_mixed` | vector | layers with different CRSs, or none | |
| `crs_differs` | vector | a common CRS that is not the site's | |
| `vertical_unit_feet` | vector | a vertical CRS in feet | |

Value checks read only the central window ([`geotiff.sample`](../../data_acquisition/readers/geotiff.py)): fast on
any file, but blind to problems elsewhere in it.

## 4. Verification

`verify` checks a file against the first of these it finds (`_checksum_verdict`):

1. the record's checksum written on the asset (`file:checksum`, a [multihash](https://multiformats.io/multihash/));
2. for a file extracted from an archive, the CRC-32 the archive stores ([chapter 8](08_open_datasets.md));
3. the record's checksum in another form (an S3 multipart ETag, [chapter 4](04_catalogs_and_metadata.md)), when it
   can be decided;
4. the checksum computed on download (`downloads.csv`).

A match writes `verified: <date> (<against what>)` into the provenance; a mismatch flags `checksum_mismatch`;
nothing to check against flags `checksum_unknown`. A mismatch does not remove an earlier `verified` (finding 20 in
[`course_findings.md`](../dataset/course_findings.md)): read the flags, not only the date.

## 5. Adding a check

A check is a few lines in `check_raster` or `check_vector` that call `add_quality(item, "<flag>", "<detail>")`
(source `auto`, so it is recomputed on every run). What makes it part of the pipeline:

- a **flag name** that says what was found, not what to do, and a detail with the numbers;
- a **threshold** as a named constant at the top of `curate.py`, with a comment on why that value;
- a **test** in [`tests/dataset/`](../../tests/dataset/) with a file that raises it and one that does not
  ([chapter 18](18_testing.md));
- a line in the flag table of [chapter 10](10_building_and_curating.md) and of this chapter.

## Exercises

Notebook: [`notebooks/15_curate.ipynb`](notebooks/15_curate.ipynb) (work in a copy); solutions in
[`solutions/notebooks/15_curate.ipynb`](solutions/notebooks/15_curate.ipynb).

1. **Descriptors.** On a copy of one sample item, set `colonies` as `manual` without `by`, as `claude` with `by`, and
   an unknown field. Which calls fail? What does `descriptors.missing` return before and after?
2. **Seasons.** Compute the season of 15 January, 15 April, 15 July and 15 October at 48° N and at 45° S. Then run
   `curate._season` on the sample's items: why is the DTM's season `summer`?
3. **Make checks fire.** In a scratch copy of the sample, add a five-band multispectral raster with values 0-255
   (digital numbers, not reflectance) and a DSM whose empty cells are -32767 without a declared nodata, describe
   them, build and curate. Which flags appear?
4. **Verification.** For each sample item, which source would `_checksum_verdict` use? Then reproduce finding 20 in a
   scratch copy: verify, change the DTM, verify again.
5. **Add a check.** Write, outside the pipeline, a check `no_overviews` for rasters wider or taller than a limit that
   have no overviews (slow to display; milestone 2 will need quick-looks), apply it after `curate_item`, and test it
   with a small limit.

6. **One check at a time.** `check_raster` and `check_vector` on their own, with the right site and with one in another UTM
   zone; `check_vector` on the extract's dams; `verify` on the orthomosaic and the photos.
7. **Reading the result.** `descriptors.get_field` and `descriptors.summary` after curating every item.

## Where this lives

- [`data_acquisition/steps/curate.py`](../../data_acquisition/steps/curate.py): `curate`, `curate_item`, `check_raster`,
  `check_vector`, `verify`, `_checksum_verdict`, `_season`, and the constants at the top.
- [`data_acquisition/catalog/descriptors.py`](../../data_acquisition/catalog/descriptors.py): `FIELDS`, `SOURCES`,
  `set_field`, `add_quality`, `missing`, `season`.
- [`data_acquisition/sites.yaml`](../../data_acquisition/sites.yaml): the decisions `curate` copies
  ([chapter 5](05_data_governance.md)).

## Sources

- NOAA NCEI, [meteorological versus astronomical seasons](https://www.ncei.noaa.gov/news/meteorological-versus-astronomical-seasons)
- Multiformats, [multihash](https://multiformats.io/multihash/); STAC [file extension](https://github.com/stac-extensions/file)
- GDAL, [overviews (`gdaladdo`)](https://gdal.org/en/stable/programs/gdaladdo.html)
- STAC, [validation with pystac](https://pystac.readthedocs.io/en/stable/concepts.html#validation)
