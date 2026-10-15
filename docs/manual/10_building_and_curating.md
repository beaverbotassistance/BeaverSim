# 10. Building and curating catalogues

With a reviewed summary, two commands turn a dataset into a checked catalogue: `build` makes one STAC item per
file and cross-checks the summary against the files and the record; `curate` runs the automatic checks, copies in
the decisions of the site registry and, on request, verifies every file's checksum. This chapter explains what
each writes, every quality flag either can raise, and how to read the reports.

## You will learn

- What `build` makes from a summary, and what its report means
- Every quality flag, who raises it, and what to do about it
- What `curate` adds, and what `--verify` checks
- How to rebuild after a change, and what the root catalogue collects

## 1. `build`

```
python -m data_acquisition.catalog.build --root <root> --summary <name or path>
```

reads the summary and, for each data file, makes an item ([`catalog/build.py`](../../data_acquisition/catalog/build.py),
`data_item`): one per raster, vector file, table or folder of photos, and one per **layer** for a vector file whose
layers are separate dates (`layers:` in the summary). Reports and metadata files are attached to the items they
describe; the group's metadata record is attached to every item of its group. The catalogue is written to
`<root>/stac/<dataset>/` ([chapter 4](04_catalogs_and_metadata.md)), next to `build_report.json`:

| Report entry | Means | What to do |
|---|---|---|
| `missing` | a file in the summary is not on disk | download it, or fix the path |
| `undescribed` | a file on disk is not in the summary (sidecars and parts of described files excepted) | describe it, or leave it out on purpose |
| `unsupported` | a described file could not be made into an item, with the reason | e.g. give `crs` for a raster without one |
| `unattached` | a report or metadata file found no item to attach to | check its `attach_to` and its date |
| `unmatched_layers` | layers whose names do not match the summary's `layers.pattern` | fix the pattern, or accept the gap |

## 2. Quality flags

Every item has a list `beaver:quality` of flags, each `{flag, detail, source}`. The source says who raised it
([`descriptors.add_quality`](../../data_acquisition/catalog/descriptors.py)):

| Raised by | Flags |
|---|---|
| **build**, comparing summary and file | `crs_from_summary` (the file has no CRS; the summary's was used), `non_spatial` (a table without coordinates), `band_count_conflict`, `band_order_conflict` (the summary's bands differ from the file's), `fields_missing` (declared attribute columns not in the file), `date_unknown` (only date limits are known), `photo_dates`, `photos_without_position`, `photos_unreadable` |
| **repository**, comparing record and file | `not_in_record`, `size_mismatch`, `date_outside_record`, `repository_band_conflict` (the record's band description differs), `band_order_conflict` (same bands, another order) |
| **the summary** (source `claude` or `manual`) | `note` (each of the summary's notes), `needs_inspection` (the summary's `inspect`) |
| **auto**, by `curate` | `unreadable`, `missing_file`, `unknown_site`; rasters: `crs_mismatch`, `nodata_undeclared`, `unapplied_georeference`, `sample_empty`, `elevation_range`, `not_reflectance`, `snow_likely`; vectors and tables: `empty_layers`, `crs_mixed`, `crs_differs`, `vertical_unit_feet`; with `--verify`: `checksum_mismatch`, `checksum_unknown` |

A flag is information, not an error: the item is in the catalogue either way. `crs_mismatch` on every Rumney
orthomosaic says "not in the site's UTM zone yet", a fact a later reprojection needs; `checksum_mismatch` says
"this file is not the one published", which needs action now.

## 3. `curate`

```
python -m data_acquisition.steps.curate --catalog <root>/stac/<dataset>/catalog.json --summary <name> [--verify]
```

for every item ([`steps/curate.py`](../../data_acquisition/steps/curate.py), `curate_item`): clears the previous
`auto` flags (the others are kept), sets the season, copies the site registry's decisions with who entered them,
and runs the checks of the item's kind. Rasters are checked on a 1024 × 1024 window at their centre (values,
nodata), not read whole. It rewrites the catalogue and writes `curate_report.csv` (per item, the missing
descriptors and the flags), then validates the catalogue against the STAC schemas.

`--verify` also checks every file against its checksum ([chapter 4](04_catalogs_and_metadata.md)), which reads every
byte: about 1-2 minutes per 10 GB from a USB drive.

## 4. Rebuilding, and the root catalogue

Run `build` and then `curate` again after any change to a summary or the registry: `build` rewrites the dataset's
catalogue from scratch. One caution: an item that no longer exists disappears from the catalogue's links, but its
folder stays on disk; follow links (as pystac does), do not scan the folder.

```
python -m data_acquisition.catalog.root --root <root>
```

then links every dataset's catalogue under `<root>/stac/catalog.json` and writes `<root>/stac/sites.json`: for each
site, its datasets, products and dates, the sites it lies within, and its decisions still missing
([`catalog/root.py`](../../data_acquisition/catalog/root.py)).

## Case: the open datasets

Rebuilt with the current code, the twelve open datasets give 152 items, every one verified against its checksum,
with these flags beyond the summaries' notes: `nodata_undeclared` (rasters without nodata or alpha),
`repository_band_conflict` and `band_order_conflict` (records that describe bands differently from the files),
`date_unknown` (datasets whose acquisition dates are only bounded), `non_spatial` (the Wyoming BRAT tables),
`crs_differs`, `snow_likely` (surveys above 55° N dated between November and April), `crs_from_summary`, `date_outside_record`, and
`unapplied_georeference` (the two Red Canyon orthomosaics). Each points to something a person may want to know
before using the data.

## Exercises

Notebook: [`notebooks/10_building_and_curating.ipynb`](notebooks/10_building_and_curating.ipynb) (work in a copy);
solutions in [`solutions/notebooks/10_building_and_curating.ipynb`](solutions/notebooks/10_building_and_curating.ipynb).

1. **Build.** Build the sample with the reference summary. Then copy any small file into the dataset folder and build
   again: what does the report say? Remove the copy.
2. **Flags.** Curate the items and list every flag with its source. Which ones need action?
3. **Make flags appear.** In copies of the reference summary, give the orthomosaic the wrong band order, the grid a
   CRS of the wrong UTM zone (`EPSG:32611`), and the DSM a date outside the record's period. Which flag does each
   produce, and who raises it?
4. **Verify.** Curate with `verify_files=True`. What was each file checked against, and why do the photos get
   `checksum_unknown`?
5. **Rebuild.** Remove the DSM from a copy of the summary, rebuild into a scratch root, and compare the collection's
   links with the item folders on disk.
6. **Find it in the code.** Where does `curate` clear the previous automatic flags, and where does `build` write the
   report?

## Where this lives

- [`data_acquisition/catalog/build.py`](../../data_acquisition/catalog/build.py): `build`, `data_item`, `_raster_item`,
  `_vector_item`, `_table_item`, `_photos_item`, `_record_flags`, `_attach`, `_undescribed`.
- [`data_acquisition/steps/curate.py`](../../data_acquisition/steps/curate.py): `curate`, `curate_item`, `check_raster`,
  `check_vector`, `verify`.
- [`data_acquisition/catalog/descriptors.py`](../../data_acquisition/catalog/descriptors.py): flags and descriptors.
- [`data_acquisition/catalog/root.py`](../../data_acquisition/catalog/root.py): the root catalogue and `sites.json`.

## Sources

- STAC, [item specification](https://github.com/radiantearth/stac-spec/blob/master/item-spec/item-spec.md);
  [pystac](https://pystac.readthedocs.io/en/stable/)
