# The beaver dataset pipeline: a course

This course teaches how the BeaverSim dataset pipeline finds, describes, catalogues and checks the
remote-sensing data of beaver sites, and the geospatial ideas it rests on. It is written for people who
can read and run Python but are new to GIS and remote sensing.

The pipeline is being built in milestones ([the plan](../dataset/pipeline_design.md#12-implementation-order)).
**This course covers milestone 1**, which is complete: getting datasets in, describing them, and turning
them into checked catalogues. It does not process imagery, reproject, co-register or display the data:
those are later milestones, and the chapters that will cover them are marked as such.

## How to use it

- Read the chapters in order the first time. Part 1 is background, Part 2 is how to use the pipeline,
  Part 3 is how it works inside, for those who will change it.
- Each chapter has exercises, in a notebook under [`notebooks/`](notebooks/) (work in a copy; the solutions
  are in [`solutions/notebooks/`](solutions/notebooks/), try first). Most run on a small **sample data root** that a script generates
  ([00 Setup](00_setup.md)); a few use a real extract of the Montana field data that is committed with the
  course (`docs/manual/data/`), and one downloads a small open dataset.
- Every concept links to a source you can check. Every chapter ends with **Where this lives**: the files and
  functions of the codebase to open next. Paths are relative to the repository root, e.g.
  [`data_acquisition/catalog/build.py`](../../data_acquisition/catalog/build.py).
- When the pipeline asks you for information, the course says whether it is **required** (the pipeline
  stops without it), **checked** (the file is skipped and reported) or **optional** (the catalogue is built
  and the gap is flagged). [Chapter 6](06_what_the_pipeline_needs.md) collects all of them in one place.

## Contents

| # | Chapter | Status |
|---|---|---|
| 00 | [Setup: environment, drives, sample data](00_setup.md) | draft, for review |
| | **Part 1 – Background** | |
| 01 | [Geospatial data: rasters, vectors, formats](01_geospatial_data.md) | draft, for review |
| 02 | [Coordinates: CRS, projections, units, heights](02_coordinates.md) | draft, for review |
| 03 | [Drone surveys: from photos to maps](03_drone_surveys.md) | draft, for review |
| 04 | [Catalogues and metadata: STAC, records, checksums](04_catalogs_and_metadata.md) | draft, for review |
| 05 | [Data governance: licences, land, Indigenous data](05_data_governance.md) | draft, for review |
| 06 | [What the pipeline needs from you](06_what_the_pipeline_needs.md) | draft, for review |
| | **Part 2 – Using the pipeline (milestone 1)** | |
| 07 | [The pipeline at a glance](07_pipeline_at_a_glance.md) | draft, for review |
| 08 | [Bringing in an open dataset](08_open_datasets.md) | draft, for review |
| 09 | [Describing a dataset: summaries and Claude](09_describing_a_dataset.md) | draft, for review |
| 10 | [Building and curating catalogues](10_building_and_curating.md) | outline |
| 11 | [Field data: from a field drive to `beaver_dataset/`](11_field_data.md) | outline |
| 12 | [Inspecting a dataset (milestone 2)](12_inspecting.md) | waits for milestone 2 |
| | **Part 3 – Inside the pipeline** | |
| 13 | [Readers](13_readers.md) | outline |
| 14 | [The builder](14_builder.md) | outline |
| 15 | [`curate` and the descriptors](15_curate.md) | outline |
| 16 | [Sources: downloads and checksums](16_sources.md) | outline |
| 17 | [The field step, inside](17_field_step_internals.md) | outline |
| 18 | [Testing a change](18_testing.md) | outline |
| 19 | [Extending the pipeline](19_extending.md) | outline |
| | **Appendices** | |
| A | [Glossary](A_glossary.md) | outline |
| B | [Troubleshooting](B_troubleshooting.md) | outline |
| C | [Conventions](C_conventions.md) | outline |

## Related documents

These are the pipeline's design and reference documents; the course links to them rather than repeating
them.

- [`docs/dataset/pipeline_design.md`](../dataset/pipeline_design.md): the design, milestones and decisions.
- [`docs/dataset/describing_a_dataset.md`](../dataset/describing_a_dataset.md): the how-to for summaries.
- [`docs/dataset/field_naming.md`](../dataset/field_naming.md): the layout and names of `beaver_dataset/`.
- [`docs/dataset/beaver_open_datasets.md`](../dataset/beaver_open_datasets.md): the open datasets surveyed.
- [`docs/dataset/hdd_inventory.md`](../dataset/hdd_inventory.md): what is on the field-season drive.
