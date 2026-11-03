# Rebuilding Rumney Ranch from your copy of the field drive (macOS)

You have an exact copy of the 2018-2019 Montana field drive (Jordan's dataset). This guide explains how we
reorganised its Rumney Ranch data into `beaver_dataset/`, and how to rebuild the same thing on your Mac, from
your copy, with our code. At the end you can check, file by file, that your result is identical to ours.

Your copy is never changed: the rebuild only reads it and adds a new folder, `beaver_dataset/`, next to the
original folders.

> **Internal data.** These are unpublished field data whose land status and data-use terms are still being
> settled. Keep them, and anything made from them, inside the project.

A companion file, [`rumney_rebuild_for_llm.md`](rumney_rebuild_for_llm.md), gives the same procedure as a
checklist for an AI assistant (Claude Code or similar) to follow and verify for you.

## 1. What we did, and why

The drive holds about 97,000 files in folders named by hand: drone photos, orthomosaics exported several times,
test flights, video frames, and annotations (dams, ponds, canals, ...) drawn in ArcGIS. To use them in our
pipeline, every file needs a clear date and type. Rather than change the originals, we built a second,
organised view of them:

```
beaver_dataset/sites/rumney_ranch/
  surveys/2018-07-26/                         one folder per survey date (the day the photos were taken)
    photos/100MEDIA/DJI_0139.JPG              the drone photos of that day
    orthomosaic_part-4.tif                    tile 4 of that day's orthomosaic
    orthomosaic_part-4_chunk-3.tif            a piece of tile 4, as georeferenced in ArcGIS
    survey.json                               the survey: photos, time span, original folders
  annotations/2018-07-26/dams.gpkg            one annotation layer per file
  manifest.csv    every file and the original it comes from
  excluded.csv    every original left out, and why
  georeference.csv, alignment.csv             two checks, explained below
```

What happens to each kind of file:

- **Photos and orthomosaics are hard links.** A hard link is a second name for the same file on disk: no copy, no
  extra space. They are made read-only, which also protects the original. Photos go to the folder of the day
  they were taken (from their EXIF), not the folder they were filed in.
- **Annotations are exported.** Each ArcGIS layer becomes its own GeoPackage (`.gpkg`), with the same features,
  attributes and feature ids.
- **ArcGIS's georeferencing is applied.** Many orthomosaics were placed on the map in ArcGIS, which stores the
  adjustment in a sidecar file (`.aux.xml`) that other software ignores. We write the adjustment as the file's
  own georeferencing, so every program places the image as ArcGIS did. No pixel changes.
- **One coordinate system is corrected.** The annotations use ESRI's "WGS_1984_ARC_System_Zone_12". ArcGIS
  computes it on a sphere, but recent versions of the PROJ library (used by QGIS and Python) compute it on an
  ellipsoid and put everything about 30 km away. We write the sphere explicitly into every exported layer.
- **Some files are left out**, each with its reason in `excluded.csv`: copies of photos, video frames, test
  flights, unreadable or ungeoreferenced exports, empty layers.

What goes where was decided once, in a reviewed **layout file**,
[`data_acquisition/field_layouts/rumney_ranch.yaml`](../../data_acquisition/field_layouts/rumney_ranch.yaml).
The names follow [`field_naming.md`](field_naming.md).

Two findings matter when you use the data:

- **The annotations were drawn on the chunks**, not on the full tiles. On the chunks the outlines fit their image
  to about 0.1-0.4 m (median per survey date); on the full tiles they are typically 0.5-2 m off.
- **Every annotation still needs a person's check** (`needs_inspection`). `alignment.csv` measures how well each
  outline follows the edges of its image.

Only Rumney Ranch is rebuilt so far. The other sites (Pilling Ranch, Willow Creek, Cut Bank Creek) have no layout
file yet.

For the full story, read chapters 11 and 17 of the course in [`docs/manual/`](../manual/README.md).

## 2. What you need

| | Requirement | How to check |
|---|---|---|
| Mac | Apple silicon with macOS 14 or newer, or Intel with macOS 15 or newer (the pinned `rasterio` has no wheels for older versions) | Apple menu → About This Mac |
| Disk | your copy on an **APFS** (or Mac OS Extended) disk, which you can write to | `diskutil info "/Volumes/<disk>" \| grep Personality` |
| Space | about 40 MB free on that disk (links take no space; the exported layers and written files are 33 MB) | Finder |
| Python | Python 3.12 | `python3.12 --version` |
| GDAL | the GDAL command-line tools, 3.7 or newer | `ogr2ogr --version` |
| Code | access to the BeaverSim repository, branch `dev_dataset` | |

**Why APFS.** The rebuild makes hard links next to your copy, on the same disk. A disk formatted **exFAT** cannot
hold hard links, and macOS cannot write to **NTFS** (the format of the original drive) without extra software. If
your copy is on one of those, copy it to an APFS disk first (Disk Utility can format an external disk as APFS).
An APFS disk also avoids the `._` files macOS creates on other disks, which would add rows to `excluded.csv`.

## 3. Set up (once)

In Terminal:

```bash
# Homebrew (https://brew.sh), if you do not have it, then Python 3.12 and GDAL
brew install python@3.12 gdal

# the code
git clone git@github.com:beaverbotassistance/BeaverSim.git
cd BeaverSim
git checkout dev_dataset

# a Python environment with the exact library versions we use
python3.12 -m venv beaversim_venv
source beaversim_venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q tests/dataset          # should end with "78 passed"
```

Run every command below from the `BeaverSim` folder, with the environment active (`source
beaversim_venv/bin/activate` in each new Terminal window). If `echo $BEAVER_SITES` prints anything, run
`unset BEAVER_SITES` first: that variable selects the course's sample registry instead of the real sites.

Set the path of your copy once per Terminal window: the folder that contains `2018 Field Season` and
`2019 Field Season`.

```bash
export DRIVE="/Volumes/<your disk>"            # adjust; quotes matter if the name has spaces
ls "$DRIVE"                                   # must list "2018 Field Season" and "2019 Field Season"
```

## 4. Rebuild

**Step 1: the inventory.** Reads every file of the two seasons once (photo headers, orthomosaic headers,
annotation layers) and writes `output/dataset/field_inventory.csv`. It only reads your copy. It reads about
70,000 photos, so it takes a long time; you only run it once.

```bash
python -m data_acquisition.sources.field_inventory --root "$DRIVE"
```

It ends with `inventory written: output/dataset/field_inventory.csv (73763 rows)`.

**Step 2: a dry run.** Plans every action and writes the plan to `output/dataset/field/rumney_ranch/`, without
touching the disk.

```bash
python -m data_acquisition.sources.field --drive "$DRIVE" --site rumney_ranch --dry-run
```

It prints `plan: {'link': 29087, 'georef': 283, 'export': 104}, excluded: 1783`.

**Step 3: the build.** Same command without `--dry-run`. It creates `$DRIVE/beaver_dataset/sites/rumney_ranch/`.

```bash
python -m data_acquisition.sources.field --drive "$DRIVE" --site rumney_ranch
```

Do not put files of your own inside `beaver_dataset/sites/`: a later build removes anything it did not make there.

**Step 4 (optional): the alignment check.** Measures how well each annotation outline fits its image and writes
`alignment.csv`. It reads a window of an orthomosaic around each of the 488 polygon outlines.

```bash
python -m data_acquisition.sources.field_alignment --site-dir "$DRIVE/beaver_dataset/sites/rumney_ranch"
```

**Step 5: the catalogue.** Describes the rebuilt data as a STAC catalogue, using the reviewed summary
[`montana_rumney_ranch.yaml`](../../data_acquisition/summaries/montana_rumney_ranch.yaml).

```bash
python -m data_acquisition.catalog.build --root "$DRIVE/beaver_dataset" --summary montana_rumney_ranch
python -m data_acquisition.steps.curate --catalog "$DRIVE/beaver_dataset/stac/montana_rumney_ranch/catalog.json" \
    --summary montana_rumney_ranch
```

The first prints `420 items -> ...`; the second ends with `STAC valid`.

## 5. Check that your result is ours

Compute the fingerprints (SHA-256) of your files and compare them with ours:

```bash
shasum -a 256 output/dataset/field_inventory.csv output/dataset/field/rumney_ranch/plan.csv \
    "$DRIVE"/beaver_dataset/sites/rumney_ranch/{manifest,excluded,georeference,alignment}.csv
```

| File | Rows | SHA-256 |
|---|---|---|
| `output/dataset/field_inventory.csv` | 73,763 | `48890b099cfb637faf2c4e3e331f102dc7b2415182273af6ad5400e8bbd53ddb` |
| `output/dataset/field/rumney_ranch/plan.csv` | 29,474 | `7ff905e1d50081917e0807a3dd558eec9fa95e1b407a6b2b0f2a26aa814655a6` |
| `manifest.csv` | 29,474 | `f7c526f335d53a64faff07c1a3725c87919b1d1f87696408948579f0b584cc8f` |
| `excluded.csv` | 1,783 | `23260420bf0be683ed47cab8bc46f19a7b7031ec83d96183b2cdca6a1515adcb` |
| `georeference.csv` | 283 | `035344866f6c8dec917e0790a960a6e88b2d4fd20eba025db5779e5234346e6c` |
| `alignment.csv` | 786 | `f03348646c7280eeaf2cd70289ff6cc35810b091d056b9b191a5da6641277e21` |

(Rows exclude the header line. The values are from the code of `dev_dataset` as of 19 October 2026.)

**If a fingerprint differs**, the first file that differs tells you where:

- **`field_inventory.csv`**: this does **not** by itself mean your copy differs. About 700 Rumney photos exist twice,
  and which copy is kept depends on the order your disk lists files, which may differ on a Mac (this has not been
  tried yet). The rows that change then say `duplicate of ...`, and `plan.csv`, `manifest.csv` and `excluded.csv` differ
  too. Check the row and action counts first: if they match, the data are the same, with some photos under another
  camera folder (e.g. `100MEDIA` instead of `106MEDIA`). If the counts differ, ask us for our inventory and compare
  them; `._` files from a copy to a non-APFS disk show up here.
- **`plan.csv` or `manifest.csv`** with an identical inventory: the code differs; check `git status` and that you
  are on `dev_dataset`.
- **`georeference.csv` or `alignment.csv`** alone: these hold computed numbers; a different processor can change
  the last digit of a few values. Compare the values: differences of 0.001 m (`georeference.csv`) or one 0.05 m
  step (`alignment.csv`) are rounding; anything larger is a real difference.

## 6. If something goes wrong

| Problem | Cause and fix |
|---|---|
| `Operation not permitted` or `Read-only file system` | your copy is on NTFS (macOS cannot write to it) or not writable: use an APFS disk |
| an error when linking (e.g. `Operation not supported`) | the disk is exFAT (no hard links): use an APFS disk |
| `ogr2ogr: command not found` | `brew install gdal`, then open a new Terminal |
| `pip install` fails for `rasterio` | macOS too old for the pinned version (section 2), or not Python 3.12 |
| the build stops with "exists but was not built from a layout file" | a `beaver_dataset/sites/rumney_ranch/` from elsewhere is in the way: move it aside |

More in the course's troubleshooting appendix, [`docs/manual/B_troubleshooting.md`](../manual/B_troubleshooting.md).
