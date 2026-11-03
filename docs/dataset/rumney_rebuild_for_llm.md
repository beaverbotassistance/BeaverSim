# Rumney Ranch rebuild: procedure for an AI assistant

Machine-oriented companion of [`rumney_rebuild_guide.md`](rumney_rebuild_guide.md) (the human guide; read it for
the reasons). You are helping a user rebuild `beaver_dataset/sites/rumney_ranch/` on **macOS** from their exact
copy of the 2018-2019 Montana field drive, with the BeaverSim repository, and verify that the result is
identical to the reference build. Follow the steps in order. Verify every expected output before continuing.
On any STOP condition, stop and report to the user; do not improvise a workaround.

## Rules (MUST / MUST NOT)

- MUST NOT write, rename, delete, chmod or `dot_clean` anything inside `$DRIVE/2018 Field Season/` or
  `$DRIVE/2019 Field Season/`. Only the pipeline's own commands below may create `$DRIVE/beaver_dataset/`.
- MUST NOT edit any file of the repository (code, `data_acquisition/field_layouts/rumney_ranch.yaml`,
  `data_acquisition/summaries/`, `data_acquisition/sites.yaml`). The layout file is reviewed data; a rebuild that
  needs a change to it is a STOP.
- MUST NOT pass `--force`-style options, delete `beaver_dataset/` contents by hand, or run the field step for any
  site other than `rumney_ranch` (no other layout file exists).
- MUST NOT copy, upload or share the data outside the user's machine: it is internal, unpublished field data.
- MUST run every command from the repository root with the virtual environment active and `BEAVER_SITES` unset.
- MUST quote `$DRIVE` in every command (the path usually contains spaces).

## Variables

| Name | Value |
|---|---|
| `REPO` | the clone of `git@github.com:beaverbotassistance/BeaverSim.git`, branch `dev_dataset` |
| `DRIVE` | the folder that directly contains `2018 Field Season/` and `2019 Field Season/` (e.g. `/Volumes/<disk>`) |
| `SITE_DIR` | `$DRIVE/beaver_dataset/sites/rumney_ranch` |

## Preconditions (check all; any failure is a STOP unless a fix is given)

| # | Check | Command | Expected | If not |
|---|---|---|---|---|
| P1 | macOS version | `sw_vers -productVersion`; `uname -m` | `arm64` with ≥ 14.0, or `x86_64` with ≥ 15.0 | STOP: pinned `rasterio==1.5.1` has no wheel |
| P2 | drive layout | `ls "$DRIVE"` | lists `2018 Field Season` and `2019 Field Season` | STOP: ask the user for the right folder |
| P3 | file system | `diskutil info "$DRIVE" \| grep "File System Personality"` | `APFS` (or `HFS+`/Mac OS Extended) | STOP: exFAT cannot hold hard links; NTFS is read-only on macOS. The user must copy the data to an APFS disk |
| P4 | writable | `touch "$DRIVE/.beaver_write_test" && rm "$DRIVE/.beaver_write_test"` | no error | STOP |
| P5 | no previous build | `ls "$DRIVE/beaver_dataset/sites/rumney_ranch" 2>/dev/null` | nothing, or a folder containing `manifest.csv` (a previous build by this procedure) | STOP if it exists without `manifest.csv` |
| P6 | Python | `python3.12 --version` | `Python 3.12.x` | fix: `brew install python@3.12` |
| P7 | GDAL tools | `ogr2ogr --version`; `ogrinfo --version` | GDAL ≥ 3.7 (needed for `ogrinfo -json`) | fix: `brew install gdal`, new shell |
| P8 | repository | `git -C "$REPO" rev-parse --abbrev-ref HEAD`; `git -C "$REPO" status --porcelain` | `dev_dataset`; empty | STOP if modified files |
| P9 | real site registry in use | `echo "${BEAVER_SITES:-unset}"` | `unset` | fix: `unset BEAVER_SITES` (it would select another registry, and the catalogue steps would fail or use the wrong sites) |

## Setup (once)

```bash
cd "$REPO"
python3.12 -m venv beaversim_venv
source beaversim_venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q tests/dataset
```

Expected: install completes; the tests end with `76 passed`. Any failure: STOP.

## Steps

| # | Command | Writes | Expected (last lines) |
|---|---|---|---|
| S1 inventory | `python -m data_acquisition.sources.field_inventory --root "$DRIVE"` | `output/dataset/field_inventory.csv`, `output/dataset/exif_cache.csv` (repository only) | `+ photos and video frames: 73763` and `inventory written: output/dataset/field_inventory.csv (73763 rows)`. Long-running (reads ~70,000 photo headers); do not interrupt |
| S2 dry run | `python -m data_acquisition.sources.field --drive "$DRIVE" --site rumney_ranch --dry-run` | `output/dataset/field/rumney_ranch/plan.csv`, `.../excluded.csv` | `plan: {'link': 29087, 'georef': 283, 'export': 104}, excluded: 1783 -> output/dataset/field/rumney_ranch` |
| V1 | `shasum -a 256 output/dataset/field_inventory.csv output/dataset/field/rumney_ranch/plan.csv` | | both match the reference table; if not, STOP before S3 (see Diagnosis) |
| S3 build | `python -m data_acquisition.sources.field --drive "$DRIVE" --site rumney_ranch` | `$SITE_DIR` (links, exported GeoPackages, `.aux.xml` sidecars, records) | a `built: {...}` line with `'link': 29087` (or `'link (already there)'` on a rerun), `'georef': 283`, `'export': 104`; no `RuntimeError` |
| S4 alignment (optional) | `python -m data_acquisition.sources.field_alignment --site-dir "$SITE_DIR"` | `$SITE_DIR/alignment.csv` | per-date medians, e.g. `2018-07-26 chunk    : median 0.11 m over 40 of 53 outlines` |
| S5 catalogue | `python -m data_acquisition.catalog.build --root "$DRIVE/beaver_dataset" --summary montana_rumney_ranch` | `$DRIVE/beaver_dataset/stac/montana_rumney_ranch/` | `420 items -> ...`, and no `missing`/`undescribed`/`unsupported`/`unattached` lines |
| S6 curate | `python -m data_acquisition.steps.curate --catalog "$DRIVE/beaver_dataset/stac/montana_rumney_ranch/catalog.json" --summary montana_rumney_ranch` | the catalogue, `curate_report.csv` | ends with `STAC valid` |
| V2 | `shasum -a 256 "$SITE_DIR"/{manifest,excluded,georeference,alignment}.csv` | | all match the reference table |

S3 may be rerun: existing correct links are kept, exported layers and written sidecars are made again, and files
the plan no longer makes are removed from `$SITE_DIR`. Never place other files in `$SITE_DIR`: they would be
deleted (known issue).

## Reference values

Code: branch `dev_dataset` as of 2026-10-19 (`data_acquisition/` unchanged since commit `f655273`, except that `summary.load_sites` honours `BEAVER_SITES`). Rows exclude the header.

| File | Rows | SHA-256 |
|---|---|---|
| `output/dataset/field_inventory.csv` | 73763 | `48890b099cfb637faf2c4e3e331f102dc7b2415182273af6ad5400e8bbd53ddb` |
| `output/dataset/field/rumney_ranch/plan.csv` | 29474 | `7ff905e1d50081917e0807a3dd558eec9fa95e1b407a6b2b0f2a26aa814655a6` |
| `$SITE_DIR/manifest.csv` | 29474 | `f7c526f335d53a64faff07c1a3725c87919b1d1f87696408948579f0b584cc8f` |
| `$SITE_DIR/excluded.csv` | 1783 | `23260420bf0be683ed47cab8bc46f19a7b7031ec83d96183b2cdca6a1515adcb` |
| `$SITE_DIR/georeference.csv` | 283 | `035344866f6c8dec917e0790a960a6e88b2d4fd20eba025db5779e5234346e6c` |
| `$SITE_DIR/alignment.csv` | 786 | `f03348646c7280eeaf2cd70289ff6cc35810b091d056b9b191a5da6641277e21` |

Other expected facts: 12 survey folders under `$SITE_DIR/surveys/` (2018-06-05, 06-13, 06-21, 06-28, 07-06,
07-17, 07-26, 08-06, 08-14, 08-22; 2019-09-03, 09-05), each with a `survey.json`; 104 `.gpkg` files under
`$SITE_DIR/annotations/`; 27990 photo links; new data written to the disk ≈ 33 MB (everything else is hard links).

## Diagnosis when a hash differs

Find the first differing file in this order: inventory → plan → manifest → excluded → georeference → alignment.

| First difference | Meaning | Action |
|---|---|---|
| `field_inventory.csv` | the copy differs from the reference drive (missing, extra or changed files), or macOS created `._*` files (non-APFS copy) | count `find "$DRIVE/2018 Field Season" "$DRIVE/2019 Field Season" -name '._*' \| wc -l` (reference: 408 `._*.JPG` files, which are harmless). Report the difference to the user; ask them to obtain the reference inventory for a line diff. STOP |
| `plan.csv` with identical inventory | code differs | check P8; STOP |
| `manifest.csv` only | an unexpected action ordering or path; STOP | report |
| `excluded.csv` only | reasons differ: compare the `reason` column with the reference; report | STOP |
| `georeference.csv` only | floating-point differences in the least-squares fits | compare numerically: `rms_m` and `max_m` within 0.001 is acceptable; report |
| `alignment.csv` only | floating-point differences in the edge search | compare per row: `east_m`/`north_m` within 0.05 (one grid step) is acceptable; compare the per-date medians S4 prints; report |

## Known issues (do not fix; report if met)

- `field_alignment` imports matplotlib with a file-only backend; plots in a notebook need `%matplotlib inline`.
- The field step deletes any file in `$SITE_DIR` that it did not plan (keep user files elsewhere).
- The full list is in [`course_findings.md`](course_findings.md).

## Further reading for context

- [`field_naming.md`](field_naming.md): naming policy of `beaver_dataset/`.
- [`data_acquisition/field_layouts/rumney_ranch.yaml`](../../data_acquisition/field_layouts/rumney_ranch.yaml):
  every decision (target or exclusion, with reason) per orthomosaic and annotation layer; `crs_corrections`.
- [`data_acquisition/sources/field.py`](../../data_acquisition/sources/field.py) (module docstring),
  [`field_inventory.py`](../../data_acquisition/sources/field_inventory.py),
  [`field_alignment.py`](../../data_acquisition/sources/field_alignment.py).
- Course chapters [11](../manual/11_field_data.md) and [17](../manual/17_field_step_internals.md).
