# 12. Looking ahead: inspecting a dataset (milestone 2)

Everything so far ends in a catalogue: checked, flagged, but read as JSON. Milestone 2 is where a person
**sees** a dataset: where it lies, when it was taken, what each item looks like, and what is wrong with it. It is
not built yet, and its plan is still to be discussed. This chapter says what the design proposes, what it will
read from the catalogues of milestone 1, and what those catalogues do not give it yet. It ends with a small
preview you build yourself from the sample.

## You will learn

- What milestone 2 is meant to show, and the rules it inherits
- Which fields of the catalogue each view needs, and which are there today
- What is missing for it, and which later milestone brings it

## 1. What milestone 2 adds

The design ([`pipeline_design.md`, §9](../dataset/pipeline_design.md#9-notebooks)) proposes one notebook,
`inspect.ipynb`, that goes from a catalogue to an understanding of it:

1. a summary: items by type, site and date; licences; governance notes; decisions still missing;
2. a coverage map: the footprint of every item, and the colonies' areas when defined;
3. a timeline: one row per product, one mark per date (Sentinel-2 dates alongside, from milestone 3);
4. an item browser: a quick-look of any item, with its descriptors and quality flags;
5. side by side: two items over the same area at the same scale;
6. annotations: features per colony and date, conflicts, features in no colony.

Milestone 2 is "done" when the coverage map, timeline, item browser and side-by-side work on a real dataset
([§12](../dataset/pipeline_design.md#12-implementation-order); the design names a Swan Lake dataset).

It inherits three rules from milestone 1:

- **it reads the catalogues and changes nothing**: no file, no catalogue entry;
- **it is dataset-agnostic**: its sections depend on the kinds of item in the catalogue (raster, vector, table,
  photos), never on a dataset's name;
- **it starts with reminders**: check governance and land status before sharing a figure
  ([chapter 5](05_data_governance.md)), and the terms of any basemap before publishing a map.

## 2. What it reads

Each view needs fields that milestone 1 already writes ([chapter 4](04_catalogs_and_metadata.md),
[chapter 10](10_building_and_curating.md)):

| View | Reads | There today? |
|---|---|---|
| summary | `beaver:kind`, `beaver:site`, `beaver:licence`, `beaver:governance`; `<root>/stac/sites.json` | yes |
| coverage map | the item's `geometry` (longitude/latitude footprint) | yes, but for photos only the camera positions; colony areas: no (`beaver:colonies` is null everywhere) |
| timeline | `datetime`, or `start_datetime`/`end_datetime`, with `beaver:date_precision`; the product | yes; the product only as the key of the `data` asset |
| item browser | the `data` asset's file, `beaver:quality`, every `beaver:` descriptor | descriptors and flags yes; quick-looks: no |
| side by side | the assets' files and `proj:*` (CRS, transform, shape) | yes |
| annotations | vector items, `beaver:colonies` | items yes; colonies no |

Two points from the table deserve attention. Dates are not all exact: of the 152 items of the open datasets, 96
have one date, 21 only a year, 2 only a month, 24 only date limits (`date_unknown`,
[chapter 10](10_building_and_curating.md)), and 9 cover a period (a dam history from 2001 to 2024, a
difference of two surveys a year apart); a timeline must draw intervals, not points. And no item stores a quick-look: the catalogues on the drive have
`data`, `metadata`, `report` and `archive` assets, no `thumbnail`. The browser will have to make one from the file
(a reduced read, as in the exercises), or a step must add them.

## 3. What it will not have yet

| Missing | Needed for | Comes with |
|---|---|---|
| colonies (areas of interest) | colony areas on the map; annotations per colony | the registry's decisions ([chapter 5](05_data_governance.md)); `define_aoi` (milestone 5) |
| Sentinel-2 imagery | Sentinel dates on the timeline, satellite quick-looks | milestone 3 |
| a common grid | comparing surveys pixel by pixel | `reproject`, `coregister` (milestones 5 and 7) |
| corrected annotations | trusting the Montana annotations | milestone 8 ([chapter 11](11_field_data.md)) |

None of these blocks milestone 2: it shows what the catalogue holds, and says so where something is missing.
What milestone 2 needs from you is the same as everything before it: datasets described, built and curated.

## Exercises

A preview, made only from what the catalogue holds. Nothing here is the milestone 2 notebook; it shows that the
catalogue is enough to start from.

Notebook: [`notebooks/12_inspecting.ipynb`](notebooks/12_inspecting.ipynb) (work in a copy); solutions in
[`solutions/notebooks/12_inspecting.ipynb`](solutions/notebooks/12_inspecting.ipynb).

1. **A table of items.** Build, curate and root the sample (as in [chapter 7](07_pipeline_at_a_glance.md)), open
   `<sample root>/stac/catalog.json` with pystac, and make one table row per item: id, product, kind, site, start
   and end of its time, date precision, number of flags.
2. **Coverage.** Turn the table into a GeoDataFrame and plot the footprints in the site's UTM zone, coloured by
   product. What does each footprint cover, and why is the photos' one invisible?
3. **Timeline.** One row per product, a mark per item from its start to its end. Which item is an interval, and why?
4. **Quick-look.** Without a stored quick-look, read the orthomosaic at about 200 pixels wide (`out_shape`) and
   show it next to the item's flags.
5. **What is missing.** By code: which items have a `thumbnail` asset, which have colonies, and what does
   `sites.json` say is still to decide?

## Where this lives

- [`docs/dataset/pipeline_design.md`](../dataset/pipeline_design.md): §9 (notebooks), §12 (milestones).
- [`data_acquisition/catalog/root.py`](../../data_acquisition/catalog/root.py): the root catalogue and `sites.json`, the
  natural entry point of an inspection.
- [`data_acquisition/catalog/stac.py`](../../data_acquisition/catalog/stac.py): how items, assets and their roles
  are written.

## Sources

- STAC, [item specification](https://github.com/radiantearth/stac-spec/blob/master/item-spec/item-spec.md)
  (`datetime`, `start_datetime`, `end_datetime`) and [asset roles](https://github.com/radiantearth/stac-spec/blob/master/best-practices.md#list-of-asset-roles)
  (`thumbnail`, `overview`, `data`, `metadata`)
- pystac, [reading a catalogue](https://pystac.readthedocs.io/en/stable/concepts.html)
- rasterio, [reading at a reduced resolution](https://rasterio.readthedocs.io/en/stable/topics/resampling.html)
- GeoPandas, [mapping](https://geopandas.org/en/stable/docs/user_guide/mapping.html)
