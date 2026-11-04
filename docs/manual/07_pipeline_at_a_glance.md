# 7. The pipeline at a glance

Part 1 gave the ideas; Part 2 uses the pipeline. This chapter is the map: what the pipeline does today and
what it does not, its stages and the command for each, and where every output goes. The next chapters take
the stages one by one.

## You will learn

- What the pipeline does today, and what is left to later milestones
- The stages, the command of each, and the file each writes
- Where the code of each stage lives

## 1. What it does, and what it does not

The pipeline's goal for now is to **see everything in a dataset and trust what you see**: find datasets,
bring them in, describe them, turn them into checked catalogues. Today it can:

- **download** open datasets from five kinds of repository (DataONE, PANGAEA, Zenodo, HydroShare, CKAN), with
  checksums verified on the way;
- **reorganise** the field-season drive into `beaver_dataset/`, site by site, from reviewed layout files;
- **describe** each dataset in a summary file, drafted by Claude and reviewed by a person;
- **build** a STAC catalogue of every dataset: rasters, vectors, tables and photo folders, with cross-checks;
- **curate** the catalogues: automatic checks, the decisions from the site registry, checksum verification;
- **measure** how well field annotations sit on their imagery.

It does **not** yet, and these are the next milestones ([design, §12](../dataset/pipeline_design.md#12-implementation-order)):

- **display** the data: coverage maps, timelines, side-by-side views (milestone 2, [chapter 12](12_inspecting.md));
- fetch **satellite imagery** (Sentinel-2) for the same places;
- **process** imagery: reproject, clip to colonies, compute vegetation and water indices, detect change;
- **reprocess** drone photos (photogrammetry) and **co-register** surveys;
- let a person **inspect and correct** annotations (milestone 8).

Everything it does today **describes the data as they are**: no file is converted, reprojected or edited, and
the originals are never written to. What it writes are catalogues, reports, and (for field data) links,
exported layers and sidecars, all recorded.

## 2. The stages

```
 open dataset                                     field-season drive
     |                                                  |
 source client (download, checksums)       field_inventory -> layout file (reviewed) -> field
     |                                                  |
     +------------------> data root <-------------------+
                              |
              describe prompt -> summary (Claude) -> review -> describe check
                              |
                            build  -> stac/<dataset>/catalog.json + build_report.json
                              |
                           curate  -> descriptors, flags, curate_report.csv  (--verify: checksums)
                              |
                            root   -> stac/catalog.json + sites.json
```

| Stage | Command | Writes | Chapter |
|---|---|---|---|
| download | `python -m data_acquisition.sources.<repository> --root <root> --id <doi or id> [--list] [--filter <regex>]` | the files, the metadata record, a row per file in `downloads.csv` | [8](08_open_datasets.md) |
| a new repository | `python -m data_acquisition.intake --url <link> --root <root> --dataset <slug>` | a prompt for a Claude Code session | [8](08_open_datasets.md) |
| field drive | `python -m data_acquisition.sources.field_inventory --root <drive>`, then `python -m data_acquisition.sources.field --drive <drive> --site <site> [--dry-run]` | `beaver_dataset/sites/<site>/` and its records | [11](11_field_data.md) |
| describe | `python -m data_acquisition.catalog.describe prompt ...`, then `... describe check --root <root> --summary <file>` | the evidence and a prompt; then a summary in `data_acquisition/summaries/` | [9](09_describing_a_dataset.md) |
| build | `python -m data_acquisition.catalog.build --root <root> --summary <name>` | `<root>/stac/<dataset>/`: the catalogue and `build_report.json` | [10](10_building_and_curating.md) |
| curate | `python -m data_acquisition.steps.curate --catalog <catalog.json> --summary <name> [--verify]` | the catalogue, updated; `curate_report.csv` | [10](10_building_and_curating.md) |
| root | `python -m data_acquisition.catalog.root --root <root>` | `<root>/stac/catalog.json`, `<root>/stac/sites.json` | [10](10_building_and_curating.md) |
| alignment | `python -m data_acquisition.sources.field_alignment --site-dir <site folder> [--sheet <png>]` | `alignment.csv` in the site folder | [11](11_field_data.md) |

Every command prints its options with `--help`. Three ways to look before writing: a repository client's
`--list` shows the files and licence without downloading; `describe check` builds the catalogue in memory and
reports, without writing it; and the field step's `--dry-run` writes only its plan, to `output/`. `build`,
`curate` and `root` write into the data root's `stac/` folder directly.

## 3. Where things are

**On a data root** (the drive, or the course's sample root):

```
<root>/
  <repository>/<dataset folder>/     downloaded files and their metadata record (never changed afterwards)
  downloads.csv                      one row per downloaded file
  stac/                              the catalogues (chapter 4)
```

**In the repository**:

```
data_acquisition/
  sources/          getting data: repository clients, HTTP and download helpers, checksums, archives;
                    the field-drive steps (field_inventory, field_audit, field, field_alignment)
  readers/          reading data, by type (geotiff, vector, table, photos, files) and by metadata standard
                    (eml, pangaea, zenodo, hydroshare, ckan)
  catalog/          describing and cataloguing: summary schema, evidence, describe, build, stac, descriptors, root
  steps/            steps run on catalogues: curate
  summaries/        one YAML summary per dataset (data, not code)
  field_layouts/    one YAML layout per field site (data, not code)
  sites.yaml        the site registry
  intake.py         the prompt for a dataset from a new repository
tests/dataset/      unit tests, the regression snapshot, the course's tests
output/             everything generated locally, never committed (evidence, prompts, plans, the sample root)
```

A rule runs through the layout: **code is organised by data type and metadata standard, never by site or
source**. Everything specific to one dataset or site is data: a summary, a layout file, a registry entry. Claude
may draft those files, and a person reviews them; Claude never writes site-specific code.

## Exercises

Notebook: [`notebooks/07_pipeline_at_a_glance.ipynb`](notebooks/07_pipeline_at_a_glance.ipynb) (work in a copy);
solutions in [`solutions/notebooks/07_pipeline_at_a_glance.ipynb`](solutions/notebooks/07_pipeline_at_a_glance.ipynb).

<!-- This list is generated by tools/build_notebooks.py, from the notebooks' prompts: edit it there. -->

1. **Run the stages.** On the sample root, run, as shell commands: `describe check` with the reference summary,
   then `build`, `curate` and `root`. After each, list what appeared under the sample root's `stac/`.
2. **Read the outputs.** Open `build_report.json`, `curate_report.csv` and `sites.json`. What does each tell you?
3. **Options.** Print the `--help` of every command in the table of section 2 of the chapter. Which ones write into
   the data root, and which option or command lets you see what would happen without writing anything?
4. **Find the stages.** For each stage, name the module and its main function.

## Where this lives

- [`data_acquisition/sources/`](../../data_acquisition/sources/), [`data_acquisition/intake.py`](../../data_acquisition/intake.py)
- [`data_acquisition/catalog/`](../../data_acquisition/catalog/): `describe.py`, `build.py`, `root.py`
- [`data_acquisition/steps/curate.py`](../../data_acquisition/steps/curate.py)
- [`docs/dataset/pipeline_design.md`](../dataset/pipeline_design.md): the design and the milestones

## Sources

- The pipeline's design: [`docs/dataset/pipeline_design.md`](../dataset/pipeline_design.md)
- STAC, [stacspec.org](https://stacspec.org/en)
