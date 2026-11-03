# 14. The builder

[Chapter 10](10_building_and_curating.md) used `build` as a command. This chapter opens it: how one entry of a
summary becomes one STAC item, where each value of the item comes from, and where every cross-check and flag is
made. It all happens in one file, [`catalog/build.py`](../../data_acquisition/catalog/build.py), on top of the
readers ([chapter 13](13_readers.md)) and of [`catalog/stac.py`](../../data_acquisition/catalog/stac.py), which
writes the STAC structures.

## You will learn

- Follow a summary entry to its STAC item, function by function
- Where each value of an item comes from: the file, the record, or the summary
- How dates, bands and attachments are decided
- How items are grouped into collections, and what the report collects

## 1. `build`, step by step

`build(root, summary)` returns a catalogue and a report. For each **group** of the summary:

1. it reads the group's metadata record, if it has one, with the reader `RECORDS` names for its format;
2. for each **file** entry, it fills in the group's defaults (`summary.resolve`: the file's own fields win;
   `notes` add up, the group's first);
3. it decides what the entry is:

| The entry | Becomes |
|---|---|
| a path not on disk | a `missing` line in the report |
| the group's own record | nothing more: the record is attached to every item of the group |
| a `role` (report, metadata, archive) | an attachment, placed at the end (§4) |
| a vector file with `layers:` | one item per layer whose name matches the pattern (`unmatched_layers` otherwise) |
| a table, raster, vector file or folder of photos | one item (`data_item`); `unsupported` if that fails, with the reason |
| anything else | `unsupported` |

4. it lists the folder's files that no entry covers (`_undescribed`): companions of a described file, files inside a
   described geodatabase or photo folder, and files outside the group's `download_filter` do not count.

Then the attachments are placed, and the items are grouped into one **collection per site**.

## 2. `data_item`: one item

**Its id** is `<site>_<time label>_<product>[_<variant>]`: `training_pond_2023-07-12_orthomosaic`. Two entries that
give the same id stop the build: two files cannot be the same item.

**Its kind** is decided in this order: a folder with product `photos`; an entry with a `table` spec; a file the
vector reader recognises; otherwise a raster. Each kind has its function (`_photos_item`, `_table_item`,
`_vector_item`, `_raster_item`), which calls the reader and `stac.*_item` to make the item with its asset.

**Its values** come from three places, and the item says which:

| From | Values | Labelled |
|---|---|---|
| the file (reader) | footprint, CRS, shape, transform, bands as declared, layers, fields, photo times | not labelled: facts, in the STAC fields |
| the record | licence, checksum, link, package id, title, creators | `beaver:licence` and `beaver:provenance` with source `repository` |
| the summary | product, date, site, positioning, platform, instruments, bands, CRS when the file has none, notes, `inspect` | `beaver:site`, `beaver:positioning` (and the provenance when there is no record) with source `claude` until reviewed, then `manual`, with who and when (`summary.author`); notes and `inspect` as flags with that source; the others (product, date, platform, instruments, bands) are not labelled |

Not every value says where it came from: a reader of the item must know that the product and the date are
always the summary's.

**Its flags** are made where the three meet: the file and the summary (`_bands`, `_fields_flags`, a raster without
CRS, photo dates outside the item's), the file and the record (`_record_flags`: not listed, size, date), and the
summary alone (`note`, `needs_inspection`, `date_unknown`). [Chapter 10](10_building_and_curating.md) lists them all.

**Its provenance** (`_provenance`) records where the file came from: the source, DOI, package id, path, link, the
download date and the checksum it was verified against (from `downloads.csv`), the archive it was extracted from,
and the summary file used.

## 3. Time and bands

**Time** (`summary.epoch`): a `date` with its `date_precision` (day, month, year), or a `start_date` and `end_date`.
A month or a year becomes its first and last day; the label in the id is the date, the month (`2022-08`), the year
or the range. `unknown` precision needs both limits, and raises `date_unknown`. A record's dates (`_period`) may be
whole years or months too: a file dated to the day must lie within the record's period, one dated to a month or a
year only overlap it, before `date_outside_record` is raised.

**Bands** (`_bands`): the summary's `bands` if given (flagged if their number or order differs from what the file
declares), else a metric product's single band name (`elevation` for a DSM or DTM), else the file's own colour
interpretation, else `b1`, `b2`, ... When the record describes the file's attributes, its band names are compared too.

## 4. Attachments, collections and the report

**Attachments** (`_attach`): a report or metadata file is attached to every item of the products in its `attach_to`,
in the same group (or in any group when its own has none of that product), on the same date when the file has one,
and of the same site when it names one. A file that finds no item is reported `unattached`.

**Collections**: one per site, with the site's name from the registry, the items' extent, the source as host, and a
licence: the items' licence when they all share one, else `various` (see finding 6 in
[`course_findings.md`](../dataset/course_findings.md)).

**The report** has five lists: `missing`, `undescribed`, `unsupported`, `unattached`, `unmatched_layers`. `main`
writes it as `build_report.json` next to the catalogue.

## 5. `stac.py`: writing the items

The per-type functions of `build.py` decide the values; [`catalog/stac.py`](../../data_acquisition/catalog/stac.py) writes
them as STAC. It knows nothing about summaries:

| Function | Takes | Does |
|---|---|---|
| `raster_crs(info)` | a raster's header | its EPSG code, or its WKT for a CRS without one |
| `lonlat_box(bounds, crs)` | a box in any CRS | the longitude/latitude polygon and bounding box, with edges densified |
| `footprint(info)` | a raster's header | `lonlat_box` of its bounds |
| `resolution_m(info, bbox)` | a header and its box | the pixel size in metres; for a CRS in degrees, measured on the ellipsoid at the raster's centre |
| `multihash(algorithm, hex)` | a checksum | the form STAC's `file:checksum` uses; only MD5 and SHA-256 are mapped |
| `size_of(path)` | a file or a folder | its bytes (a `.gdb` is a folder) |
| `raster_item`, `vector_item`, `photos_item` | a header, dates, a key, roles | an item with one asset. One day gives `datetime`; a span gives `start_datetime` and `end_datetime` |
| `add_file_asset(item, key, path, roles)` | an item and a file | a further asset, with its size: how reports and records are attached |
| `save(catalog, out_dir)`, `load(path)` | a catalogue | write it with relative links, read it back |
| `asset_path(asset)`, `validate(catalog)` | an asset; a catalogue | its local path; schema errors (the first run needs the network, for the schemas) |

A raster without an EPSG code gets `proj:code` null and `proj:wkt2`, as the Montana data does. A SHA-1 from a record
has no multihash, so `file:checksum` stays empty and the checksum is kept in the provenance.

## Exercises

Notebook: [`notebooks/14_builder.ipynb`](notebooks/14_builder.ipynb) (work in a copy); solutions in
[`solutions/notebooks/14_builder.ipynb`](solutions/notebooks/14_builder.ipynb).

1. **Trace one entry.** Take the DTM entry of the reference summary: resolve it with its group, compute its time and
   its item id, then build it with `build.data_item` and print where each value came from (the `beaver:` fields'
   sources, the provenance, the flags).
2. **Dates.** Compute `summary.epoch` for a day, a month, a year, a range and an `unknown` date; and `build._period`
   for a record whose dates are `["2001", "2024-06"]`.
3. **Bands.** Call `build._bands` for the sample's orthomosaic with no bands given, with the right ones, with three
   bands, and with the order reversed; then for a DSM.
4. **One item per layer.** In a scratch copy of the sample, write a GeoPackage with layers `dams_2021` and `dams_2023`
   (and one called `notes`), describe it (product `annotations`, variant `by_year`) with
   `layers: {pattern: '_(\d{4})$', date_precision: year}`, and build. First date each layer name with
   `summaries.layer_epoch` ([chapter 9](09_describing_a_dataset.md)): which gives None? Then: how many items, and
   what does the report say?
5. **Attachments.** Give README.txt a date (`2023-07-12`) in a copy of the summary, then `attach_to: [chm]`. Where
   does it attach each time?
6. **Find it in the code.** Where is the item id made, and where is a collection's licence set to `various`?

7. **Places and sizes.** `raster_crs`, `footprint` and `resolution_m` on the orthomosaic and the extract's chunk, and for a
   raster in degrees; `lonlat_box`; `size_of`; `multihash` for MD5, SHA-256 and SHA-1.
8. **Items by hand.** `raster_item` with one date, with a span and without an EPSG code; `vector_item`; `photos_item`;
   `add_file_asset`; `asset_path`.

## Where this lives

- [`data_acquisition/catalog/build.py`](../../data_acquisition/catalog/build.py): `build`, `data_item`, `_raster_item`,
  `_vector_item`, `_table_item`, `_photos_item`, `_bands`, `_period`, `_record_flags`, `_provenance`, `_attach`,
  `_undescribed`.
- [`data_acquisition/catalog/summary.py`](../../data_acquisition/catalog/summary.py): `resolve`, `epoch`, `layer_epoch`,
  `author`.
- [`data_acquisition/catalog/stac.py`](../../data_acquisition/catalog/stac.py): the functions of section 5.
- [`tests/dataset/test_build.py`](../../tests/dataset/test_build.py): the builder's tests.

## Sources

- STAC, [item](https://github.com/radiantearth/stac-spec/blob/master/item-spec/item-spec.md),
  [collection](https://github.com/radiantearth/stac-spec/blob/master/collection-spec/collection-spec.md) and
  [common metadata](https://github.com/radiantearth/stac-spec/blob/master/commons/common-metadata.md) (`platform`,
  `instruments`, `start_datetime`, `end_datetime`)
- STAC extensions: [projection](https://github.com/stac-extensions/projection),
  [raster](https://github.com/stac-extensions/raster), [eo](https://github.com/stac-extensions/eo) (band
  `common_name`), [file](https://github.com/stac-extensions/file) (checksums)
- pystac, [API reference](https://pystac.readthedocs.io/en/stable/api.html)
