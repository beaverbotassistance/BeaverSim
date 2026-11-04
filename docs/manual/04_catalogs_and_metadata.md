# 4. Catalogues and metadata: STAC, records, checksums

A folder of files is not a dataset you can trust: you cannot see what is in it without opening everything,
nor where it came from, nor whether a file is still the one that was published. The pipeline turns each
dataset into a **catalogue** in a standard format, records where every value came from, and checks every
file against the checksum its repository published. This chapter explains the standard (STAC), the metadata
records repositories publish, and what checksums do and do not prove.

## You will learn

- What a STAC catalogue, collection, item and asset are, and how our catalogues are organised
- Which extensions and `beaver:` properties our items carry, and where each value came from
- What a repository's metadata record holds, and how DOIs identify datasets
- What a checksum proves, the forms repositories publish them in, and how the pipeline verifies files

## 1. STAC

The [SpatioTemporal Asset Catalog](https://stacspec.org/en) (STAC) is a standard for describing geospatial
data as JSON files, so that any tool can search them by place and time. Four objects:

| Object | What it is | In our catalogues |
|---|---|---|
| **Catalog** ([spec](https://github.com/radiantearth/stac-spec/blob/master/catalog-spec/catalog-spec.md)) | a folder-like list of links to other catalogues, collections or items | the root catalogue of a data root, and one catalogue per dataset |
| **Collection** ([spec](https://github.com/radiantearth/stac-spec/blob/master/collection-spec/collection-spec.md)) | a catalogue with an extent in space and time, a licence and providers | one per site, inside each dataset's catalogue |
| **Item** ([spec](https://github.com/radiantearth/stac-spec/blob/master/item-spec/item-spec.md)) | one thing at one place and time: a GeoJSON feature with a footprint, a time and properties | one per data file (or per layer, or per folder of photos) |
| **Asset** | a file the item points to, with its roles and type | the data file, plus attached reports and the metadata record |

The layout on disk (for `open_datasets/`; `beaver_dataset/` is the same):

```
stac/
  catalog.json                 root catalogue: links to every dataset's catalogue
  sites.json                   per site, the datasets, products and dates found there
  <dataset>/
    catalog.json               the dataset
    build_report.json          what the builder could not describe or attach
    curate_report.csv          per item, missing descriptors and quality flags
    <site>/collection.json     the site, with its extent and licence
    <site>/<item id>/<item id>.json
```

Item ids are `<site>_<time>_<product>[_<variant>]`, e.g. `rumney_ranch_2018-07-26_orthomosaic_part-4_chunk-3`.
The catalogues are **self-contained**: every link and every asset path is relative
([best practices](https://github.com/radiantearth/stac-spec/blob/master/best-practices.md)), so a catalogue on the
drive keeps working wherever the drive is mounted.

## 2. Extensions and `beaver:` properties

STAC's core is small; **extensions** add fields for specific kinds of data. Our items use:

| Extension | Fields | Example |
|---|---|---|
| [projection](https://github.com/stac-extensions/projection) | `proj:code` or `proj:wkt2`, `proj:bbox`, `proj:shape`, `proj:transform` | the file's own CRS and grid ([chapter 2](02_coordinates.md)) |
| [raster](https://github.com/stac-extensions/raster) | per band: data type, nodata, unit, resolution | `uint8`, `float32`, `m` |
| [eo](https://github.com/stac-extensions/eo) | per band: name, common name | `red`, `nir`, `elevation` |
| [file](https://github.com/stac-extensions/file) | `file:size`, `file:checksum` | the size and the repository's checksum of the file |

Everything specific to beaver sites is in properties named `beaver:…`
([`catalog/descriptors.py`](../../data_acquisition/catalog/descriptors.py)):

| Property | Holds |
|---|---|
| `beaver:site`, `beaver:colonies` | the site, and the colonies present |
| `beaver:positioning` | how the product was positioned: rtk, ppk, gcp, gnss, none ([chapter 3](03_drone_surveys.md)) |
| `beaver:season` | meteorological season, from the date and the hemisphere |
| `beaver:licence`, `beaver:land_status`, `beaver:governance` | the decisions of [chapter 5](05_data_governance.md) |
| `beaver:provenance` | source, DOI, original path, URL, download date, checksums, the summary used, when the file was verified |
| `beaver:quality` | flags, each `{flag, detail, source}` |
| `beaver:origin` | for each descriptor, where its value came from: `auto` (computed), `repository` (the metadata record), `claude` (an unreviewed summary) or `manual` (a person) |
| `beaver:kind` | raster, vector, table or photos |

Quality flags have one more source, `build`: cross-checks made by the builder between the summary, the
record and the file ([`descriptors.add_quality`](../../data_acquisition/catalog/descriptors.py)).

## 3. Metadata records and identifiers

Repositories describe each dataset in a **metadata record**: title, creators, licence, dates, extent, methods,
and a list of files with their sizes and checksums. Each repository has its own format, and the pipeline reads
each with its own reader ([`readers/__init__.py`](../../data_acquisition/readers/__init__.py), `RECORDS`):

| Repository | Record | Saved as |
|---|---|---|
| [DataONE](https://www.dataone.org/) (e.g. the [Arctic Data Center](https://arcticdata.io/)) | [EML](https://eml.ecoinformatics.org/), Ecological Metadata Language (XML) | `metadata.xml` |
| [PANGAEA](https://www.pangaea.de/) | its tab-separated format with a metadata header | `metadata.tab` |
| [Zenodo](https://developers.zenodo.org/) | JSON from its REST API | `metadata.json` |
| [HydroShare](https://www.hydroshare.org/) | JSON from its API | `resource.json` |
| [CKAN](https://docs.ckan.org/en/latest/api/index.html) portals (e.g. Ontario's) | JSON from its API | `package.json` |

The record is saved **unchanged** next to the data, and attached to every item of its dataset.

A **DOI** ([doi.org](https://www.doi.org/)) is a permanent identifier for a published dataset, usually registered
through [DataCite](https://datacite.org/); `doi:10.18739/A22R3NZ98` will point to the same dataset even if the
repository moves it. Versioned repositories (Zenodo) give each version its own DOI; the pipeline records the
version's.

## 4. Checksums: what a match proves

A **checksum** is a short fingerprint computed from a file's bytes: change one byte, and the checksum changes.
Repositories publish them so that you can check that the file you have is the file they published.

| Form | What it is |
|---|---|
| **MD5** ([RFC 1321](https://www.rfc-editor.org/rfc/rfc1321)) | 128 bits; still widely published, but not collision-resistant ([RFC 6151](https://www.rfc-editor.org/rfc/rfc6151)) |
| **SHA-256** ([FIPS 180-4](https://csrc.nist.gov/pubs/fips/180-4/upd1/final)) | 256 bits; the current standard |
| **S3 multipart ETag** | `<hex>-<parts>`, published by object stores for large files. It is not an MD5 of the file: "If an object is created by either the Multipart Upload or Part Copy operation, the ETag is not an MD5 digest" ([Amazon S3 API](https://docs.aws.amazon.com/AmazonS3/latest/API/API_Object.html)). It is the MD5 of the parts' MD5s, so checking it needs the part size. |

A match proves that the bytes are the ones the repository's checksum describes: nothing was lost or corrupted
in the download or on the drive. It does not prove that the data are correct, and with MD5 it does not prove
that nobody altered them on purpose.

STAC's `file:checksum` stores a checksum as a [multihash](https://multiformats.io/multihash/): a code for the
algorithm, the length, then the digest. MD5 is `d5` + `10` (16 bytes), SHA-256 is `12` + `20` (32 bytes)
([multicodec table](https://github.com/multiformats/multicodec/blob/master/table.csv); MD5's code is still
marked "draft" there). So an MD5 digest `<32 hex digits>` is stored as `d510<32 hex digits>` ([`stac.multihash`](../../data_acquisition/catalog/stac.py)).

**How the pipeline verifies a file** (`curate --verify`, [`curate._checksum_verdict`](../../data_acquisition/steps/curate.py)),
in this order:

1. the repository's checksum written on the asset (`file:checksum`);
2. for a file extracted from a zip, the zip's own CRC-32 of that file;
3. the repository's checksum in another form, e.g. a multipart ETag, tried with the common part sizes
   ([`sources/checksums.py`](../../data_acquisition/sources/checksums.py)); if no part size fits, the answer is
   "undecided", never a guess;
4. the checksum recorded when the file was downloaded ([`downloads.csv`](16_sources.md)).

A match is recorded in `beaver:provenance` (`verified`, with the date and what it was checked against); a
mismatch becomes the flag `checksum_mismatch`, and "nothing to check against" becomes `checksum_unknown`.
Field data have no published checksums, so they can only be `checksum_unknown`.

## Case: one Rumney chunk, end to end

Open the item `rumney_ranch_2018-07-26_orthomosaic_part-4_chunk-3` in the Rumney catalogue on the drive
(`beaver_dataset/stac/montana_rumney_ranch/`): its footprint is the chunk's area in longitude and latitude;
`proj:code` is null and `proj:wkt2` holds the ARC zone on a sphere, as the projection extension prescribes for a
CRS without a code ([chapter 2](02_coordinates.md)); its `gsd` is 0.0129 m; its `beaver:quality` carries the
summary's notes, `crs_mismatch` (not UTM 12N) and `nodata_undeclared` (the chunks are RGB, without alpha); its
`beaver:origin` says the site came from a reviewed summary (`manual`, with the reviewer and date); its data asset
points, through a relative path, to the file in `beaver_dataset/sites/rumney_ranch/surveys/2018-07-26/`, and the
survey's `survey.json` and the site's records (manifest, exclusions, georeferencing, alignment) are attached as
metadata assets. Everything the catalogue says about the file can be
traced to the file, the summary or a check.

## Exercises

Notebook: [`notebooks/04_catalogs_and_metadata.ipynb`](notebooks/04_catalogs_and_metadata.ipynb) (work in a
copy); solutions in [`solutions/notebooks/04_catalogs_and_metadata.ipynb`](solutions/notebooks/04_catalogs_and_metadata.ipynb).

<!-- This list is generated by tools/build_notebooks.py, from the notebooks' prompts: edit it there. -->

1. **Build a catalogue.** Build the sample dataset with the reference summary, run `curate` on its items, and save
   it under `output/manual/stac/training_pond`. Walk the tree: catalogue, collections, items.
2. **Read an item.** Open the orthomosaic item's JSON. Find its footprint, time, `gsd`, projection fields, assets
   and their roles, and every `beaver:` property. Which descriptors are still missing?
3. **Validate.** Validate the catalogue against the STAC schemas with `stac.validate`.
4. **Verify a checksum.** Compute the MD5 of the sample orthomosaic; compare it with the record (`metadata.xml`)
   and with the item's `file:checksum`. Decode the multihash prefix.
5. **A multipart ETag.** Compute the S3 multipart ETag of the sample orthomosaic for a part size of 5 MiB and of 64
   KiB, by hand. Check both with `checksums.check(path, "s3etag", value)`. What does `check` return for an ETag of
   a part size it does not try?
6. **Find it in the code.** Where is the multihash prefix of each algorithm defined, and which function fills
   `beaver:provenance`?

## Where this lives

- [`data_acquisition/catalog/stac.py`](../../data_acquisition/catalog/stac.py): items, assets, extensions, `multihash`,
  `save`, `validate`.
- [`data_acquisition/catalog/descriptors.py`](../../data_acquisition/catalog/descriptors.py): the `beaver:` descriptors,
  their sources, quality flags.
- [`data_acquisition/catalog/build.py`](../../data_acquisition/catalog/build.py): `_provenance`, `_record_flags`, the
  layout of a dataset's catalogue.
- [`data_acquisition/catalog/root.py`](../../data_acquisition/catalog/root.py): the root catalogue and `sites.json`.
- [`data_acquisition/readers/`](../../data_acquisition/readers/): `eml`, `pangaea`, `zenodo`, `hydroshare`, `ckan`.
- [`data_acquisition/sources/checksums.py`](../../data_acquisition/sources/checksums.py) and
  [`data_acquisition/steps/curate.py`](../../data_acquisition/steps/curate.py) (`_checksum_verdict`, `verify`).

## Sources

- STAC, [stacspec.org](https://stacspec.org/en); specifications of
  [catalog](https://github.com/radiantearth/stac-spec/blob/master/catalog-spec/catalog-spec.md),
  [collection](https://github.com/radiantearth/stac-spec/blob/master/collection-spec/collection-spec.md),
  [item](https://github.com/radiantearth/stac-spec/blob/master/item-spec/item-spec.md),
  [best practices](https://github.com/radiantearth/stac-spec/blob/master/best-practices.md); extensions
  [projection](https://github.com/stac-extensions/projection), [raster](https://github.com/stac-extensions/raster),
  [eo](https://github.com/stac-extensions/eo), [file](https://github.com/stac-extensions/file); [pystac](https://pystac.readthedocs.io/en/stable/)
- [EML](https://eml.ecoinformatics.org/), [DataONE](https://www.dataone.org/), [Arctic Data Center](https://arcticdata.io/),
  [PANGAEA](https://www.pangaea.de/), [Zenodo API](https://developers.zenodo.org/), [HydroShare](https://www.hydroshare.org/),
  [CKAN API](https://docs.ckan.org/en/latest/api/index.html)
- [DOI](https://www.doi.org/), [DataCite](https://datacite.org/)
- IETF, [RFC 1321 (MD5)](https://www.rfc-editor.org/rfc/rfc1321), [RFC 6151](https://www.rfc-editor.org/rfc/rfc6151);
  NIST, [FIPS 180-4](https://csrc.nist.gov/pubs/fips/180-4/upd1/final); Amazon,
  [S3 Object (ETag)](https://docs.aws.amazon.com/AmazonS3/latest/API/API_Object.html)
- [Multihash](https://multiformats.io/multihash/), [multicodec table](https://github.com/multiformats/multicodec/blob/master/table.csv)
