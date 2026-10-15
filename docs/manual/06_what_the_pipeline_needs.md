# 6. What the pipeline needs from you

The pipeline reads what it can from the files themselves: sizes, headers, CRSs, layers, EXIF, the
repository's metadata record. Everything else comes from **you**, through a dataset summary, the site
registry or a layout file. This chapter lists every piece of information the pipeline asks for, who
provides it, whether it is required, and **exactly what happens when it is missing**: where the pipeline
stops, where it skips a file, and where it only leaves a flag. Read it before describing your first dataset
([chapter 9](09_describing_a_dataset.md)), and come back to it whenever the pipeline refuses something.

## You will learn

- The four levels of "missing": blocks, blocks one step, skips one file, flags only
- What a summary must contain, and what is optional
- The time information every data file needs, and what is checked against it
- What only a person may fill in, and why it never blocks the catalogue
- What a field site's layout file needs before the field step will run

## 1. Four levels of "missing"

| Level | What happens | Where you see it |
|---|---|---|
| **Blocks** | Nothing is built. The summary (or site registry) is refused with a list of problems. | `describe check` prints them; `build` stops with the same list |
| **Blocks one step** | That step refuses to run; the others work. | The step's message, e.g. the field step on an unreviewed layout file |
| **Skips one file** | The catalogue is built without that file, which is listed in the build report. | `build_report.json` next to the catalogue: `missing`, `unsupported`, `unmatched_layers`, `undescribed`, `unattached` |
| **Flags only** | The item is built; the gap is recorded on it. | The item's `beaver:quality` flags; `curate_report.csv`; `sites.json` (missing site fields) |

The rule behind the levels: the pipeline **blocks** only when it cannot know what a file is, where or when
it belongs; it **skips** a file it cannot read or place; and it only **flags** what a person must decide but
that does not stop the data from being catalogued.

The checks are in [`data_acquisition/catalog/summary.py`](../../data_acquisition/catalog/summary.py)
(`check`, `check_sites`, `epoch`); the skips and the report in
[`data_acquisition/catalog/build.py`](../../data_acquisition/catalog/build.py) (`build`); the flags in the
builder and in [`data_acquisition/steps/curate.py`](../../data_acquisition/steps/curate.py).

## 2. The dataset summary

A summary is a YAML file in [`data_acquisition/summaries/`](../../data_acquisition/summaries/); its full
layout is the docstring of [`summary.py`](../../data_acquisition/catalog/summary.py) and the how-to is
[`describing_a_dataset.md`](../dataset/describing_a_dataset.md). What it must and may contain:

| Field | Required? | If missing or wrong |
|---|---|---|
| `schema: 1`, `dataset`, `title`, `authored`, `source`, `groups` | **required** | **blocks** ("missing title", "schema must be 1") |
| `authored: {by, date}`; `reviewed: {by, date}` or `null` | `authored` required; `reviewed` optional | **blocks** if either is not `{by, date}` (`reviewed: true` is refused) |
| each group: `folder`, `files` | **required** | **blocks** ("needs folder and files") |
| each file: exactly one of `product` (data) or `role` + `attach_to` (reports, metadata) | **required** | **blocks** |
| `product` from the list (orthomosaic, dsm, dtm, annotations, photos, …) | **required** for data files | **blocks** ("product must be one of …") |
| `site` (on the file or its group), a slug of the site registry | **required** for data files | **blocks** ("site … is not in data_acquisition/sites.yaml") |
| a time for each data file (section 3) | **required** for data files | **blocks** ("date must be YYYY-MM-DD …") |
| `variant`, when two data files share site, time and product | **required** in that case | **blocks** ("same site, time and product … give each a variant") |
| `crs: EPSG:<code>` for a raster without a CRS of its own | **required** for such a raster | **skips the file** ("the raster declares no CRS; give `crs` in the summary"); a `crs` not written `EPSG:<code>` **blocks** |
| `record: {path, format}` (the repository's metadata record) | optional | without it: no licence, checksums or repository cross-checks (flags only) |
| `platform`, `instruments`, `positioning`, `bands`, `unit`, `vertical_datum` | optional | the descriptor is left empty and listed as missing; `positioning` outside rtk/ppk/gcp/gnss/none **blocks** |
| `notes`, `evidence`, `open_questions`, `doi` | optional | nothing; notes become `note` flags on the items |
| `inspect` (a sentence) | optional | the item gets `needs_inspection` when given; anything but a sentence **blocks** |
| `layers`, `fields`, `table` | optional (by file type) | malformed **blocks**; layers whose names do not match the pattern are **skipped** (`unmatched_layers`) |
| site entries in a summary: `hints` only | optional | any other key **blocks** ("only hints belong in a summary") |
| YAML anchors and aliases (`&name`, `*name`) | not allowed | **blocks** |

Files the summary does not describe are not an error: they are listed as `undescribed` in the build
report so you can decide. A described file that is not on disk is listed as `missing`.

## 3. Time: what every data file needs

Every **data file** (every entry with a `product`) needs a time; reports and metadata may have none. The
pipeline accepts exactly these forms ([`summary.epoch`](../../data_acquisition/catalog/summary.py)):

| You know | Write | The item gets | Example |
|---|---|---|---|
| the day | `date: 2023-07-12` | that day | a drone survey |
| only the month | `date: 2022-08-01` + `date_precision: month` | the whole month | the sample's `dem_2022.asc` |
| only the year | `date: 2017` + `date_precision: year` | the whole year | a lidar composite |
| a period (two epochs) | `start_date` + `end_date` | the range | a DEM of difference |
| nothing for sure | `date_precision: unknown` + `start_date` + `end_date` (the limits the evidence supports) | the range, and the flag `date_unknown` | "no later than the record's creation" |
| one date per layer (in the layer names) | `layers: {pattern, date_precision}` | one item per matching layer | EEAGER dam traces |

**No time at all blocks the summary.** The pipeline never guesses one, and never uses an upload or
publication date as an acquisition date: those are when the data were shared, not when they were taken.

Ranges follow STAC: an item with one day has `datetime`; an item with a range has `start_datetime` and
`end_datetime` and no `datetime` ([STAC item spec](https://github.com/radiantearth/stac-spec/blob/master/item-spec/item-spec.md)).

**A group's date is inherited by its files**, reports included, and a report with a date attaches only to
items of the same date. A README that describes the whole dataset must therefore have **no** date: put
the dates on the data files, not on the group. The course's reference summary does exactly this
([`solutions/training_pond.yaml`](solutions/training_pond.yaml)); with the date on the group, the README
does not reach the 2022 grid and the build report says `unattached`.

**What is checked against the dates (flags only):**

- the repository record's dates: a day must fall inside the record's period, a month or year must overlap
  it (`date_outside_record`)
- the photos' EXIF capture times, for a folder of photos (`photo_dates`)
- the season, computed from the day and the hemisphere; a month or a range spanning seasons gives
  `unknown` or `multiple` ([`curate._season`](../../data_acquisition/steps/curate.py))
- snow: a day in November–April above 55° N (May–October in the south) gives `snow_likely`

## 4. Space: where each file is

- **The site.** Every data file belongs to one site of the registry
  [`data_acquisition/sites.yaml`](../../data_acquisition/sites.yaml). A new site must be added there first,
  with a name and a working CRS (`EPSG:<code>`, the local UTM zone); a registry entry without them
  **blocks** every summary.
- **The file's CRS.** Read from the file. A raster without one needs `crs` in the summary (otherwise
  **skipped**); a raster whose CRS cannot be placed on the Earth at all (an engineering CRS with no link to
  it) is **skipped** as unsupported ([chapter 2](02_coordinates.md)).
- **CRS different from the site's:** flagged only (`crs_mismatch`, `crs_differs`), for a later
  reprojection.

## 5. Review marks: who wrote what

- `authored` says who wrote the summary: a person, or `claude` with the model.
- Until `reviewed: {by, date}` is set, every value taken from the summary is labelled `claude` in the
  catalogue (in `beaver:origin`). The catalogue **is built** either way: review is a label, not a gate.
- Only a person sets `reviewed`. A draft written by Claude has `reviewed: null`.

## 6. Fields only a person fills in

Some descriptors are decisions, not facts in the files. The pipeline **never** fills them and **never** blocks
on them; they are reported as missing until someone enters them in the site registry as
`{value, by, date[, note]}`:

| Descriptor | Where | Why only a person |
|---|---|---|
| `colonies` | site registry | which beaver colonies are at the site, and their extent |
| `land_status` | site registry | who owns or manages the land |
| `governance` | site registry | who may use the data and how; for Indigenous lands, the community's say ([CARE principles](https://doi.org/10.5334/dsj-2020-043); [GIDA](https://www.gida-global.org/)) |
| `licence` | from the repository record | an open dataset's licence; field data have none until one is decided |

Summaries may only suggest values, as `hints` with their source. Chapter 5 explains why.

## 7. Field data: the layout file

Field sites go through one more step before a summary: a **layout file**
([`data_acquisition/field_layouts/`](../../data_acquisition/field_layouts/)) says where each original file
goes in `beaver_dataset/` ([chapter 11](11_field_data.md)). The field step
([`sources/field.py`](../../data_acquisition/sources/field.py)) is stricter than the builder, because it
writes to the drive:

| Situation | Level |
|---|---|
| a layout entry with both or neither of `to` and `exclude`; a name outside the naming policy; two sources for one target | **blocks** (`load_layout`) |
| the layout file not reviewed | **blocks the step** (`--dry-run` still works) |
| the site folder exists but was not built from a layout file | **blocks the step** (move it aside first) |
| an exported layer that differs from its source (features, geometry type, extent, position) | **blocks the step** (nothing is half-written silently) |
| an orthomosaic whose ArcGIS adjustment is not a first-order fit to control points | **blocks the step** (exclude it in the layout, with the reason) |
| an ArcGIS fit whose control points miss it by more than 3 m | reported, not blocking (`georeference.csv`) |

## Case: the legacy example datasets

The folder [`data_acquisition/example_datasets/`](../../data_acquisition/example_datasets/) holds the inputs of
the simulator's current setup. They are a good test of this chapter: none of them could enter the pipeline
as they are.

| Dataset | What it is | What is missing, and the level |
|---|---|---|
| `ACADIA_DEM/Acadia.csv` | elevation points (x, y, elevation, label) | **date** (blocks); the **CRS** of x and y (a table of points needs `crs`); the source, so no record and no licence (flags) |
| `RUMNEY_MARSH_DEM/RumneyMarsh.csv` | elevation points near Boston | the same as Acadia; and a site in the registry (blocks) |
| `RUMNEY_RANCH_RGB/A2/*.PNG` | screenshots of part of Rumney Ranch, one per week | the dates are in the file names, but the images are **not georeferenced**: no CRS, no position, and PNG is not a format the raster checks place; they could only be described as unplaceable (skipped) |

They will probably be removed when the simulator is joined to the later milestones; the catalogued data
replace them.

## Exercises

Notebook: [`notebooks/06_what_the_pipeline_needs.ipynb`](notebooks/06_what_the_pipeline_needs.ipynb) (work in a copy); solutions in
[`solutions/notebooks/06_what_the_pipeline_needs.ipynb`](solutions/notebooks/06_what_the_pipeline_needs.ipynb).

Use the sample data root and its reference summary
([`docs/manual/solutions/training_pond.yaml`](solutions/training_pond.yaml)). Copy the summary, change one
thing at a time, and run `describe check` on your copy:

```
export BEAVER_SITES=output/manual/sample_root/sites.yaml
python -m data_acquisition.catalog.describe check --root output/manual/sample_root --summary my_copy.yaml
```

1. Remove the `date` of `ortho_2023-07-12.tif`. Before running, write down which level you expect.
2. Remove the `crs` of `dem_2022.asc`. What does the check say, and what does the build report say?
3. Move `date: 2023-07-12` from the files to the group. Which file is now reported, and under what?
4. Add a second orthomosaic entry for the same file name with `variant: copy`. What changes if you remove the
   variant?
5. Set `reviewed: true`. Then set `reviewed: {by: <you>, date: <today>}` and build: which descriptor sources
   change in the items' `beaver:origin`?
6. In the code, find the line that refuses a data file without a time, and the line that skips a raster
   without a CRS.

## Where this lives

- [`data_acquisition/catalog/summary.py`](../../data_acquisition/catalog/summary.py): `check`,
  `_file_problems`, `check_sites`, `epoch`, `author`; the schema in the module docstring.
- [`data_acquisition/catalog/build.py`](../../data_acquisition/catalog/build.py): `build` (the report),
  `_raster_item` (no CRS), `_record_flags` (dates against the record), `_attach` (attachments).
- [`data_acquisition/steps/curate.py`](../../data_acquisition/steps/curate.py): `curate_item`, `_season`;
  the missing descriptors in `descriptors.summary`.
- [`data_acquisition/sites.yaml`](../../data_acquisition/sites.yaml): the site registry.
- [`data_acquisition/sources/field.py`](../../data_acquisition/sources/field.py): `check_layout`, `main`,
  `execute`.

## Sources

- STAC, [item specification](https://github.com/radiantearth/stac-spec/blob/master/item-spec/item-spec.md)
  (`datetime`, `start_datetime`, `end_datetime`)
- S. R. Carroll et al., [The CARE Principles for Indigenous Data Governance](https://doi.org/10.5334/dsj-2020-043),
  Data Science Journal, 2020; [Global Indigenous Data Alliance](https://www.gida-global.org/)
