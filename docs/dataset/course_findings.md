# Findings from writing the course

Flaws, gaps and open questions about the pipeline found while writing the course (`docs/manual/`). The
course is written around the code as it is; these are **not fixed** there, to be reviewed and iterated on
together. Each entry: what was found, the evidence, and a suggestion. Newest last.

## Changed in the pipeline while writing the course (before the "no pipeline changes" rule)

- **`requirements.txt` was missing `geopandas`, `pyogrio`, `shapely` (and `affine`, imported directly).**
  A fresh environment from the requirement files could not import the pipeline. Added with the versions in use
  (commit 9ced3b5); a fresh venv then passed all 75 tests.
- **`BEAVER_SITES`** environment variable added to `summary.load_sites`, so the course's sample root has its own
  site registry (commit e6651e2).

## Open

1. **Group dates are inherited by reports and metadata files.** A README listed in a group with a `date`
   gets that date and attaches only to items of that date; items of other dates are left without it
   (`unattached`). Found with the course's reference summary (README vs a 2022 grid in a 2023 group).
   Suggestion: don't let `role` files inherit the group's date (only an explicit `date` on the file), or warn.
   `summary.resolve`, `build._attach`.
2. **Catalogue drops M from geometry types.** `vector.info` reads layer types through pyogrio, which converts
   measured types (`MultiPolygonZM` → `MultiPolygon Z`); the Rumney items' `beaver:layers` say
   `MultiPolygon Z` although the files hold Z and M (checked with `ogrinfo`). Suggestion: take the geometry type
   from `ogrinfo -json` or GDAL directly, or record M separately.
3. **ArcGIS adjustments in open datasets are only flagged.** Red Canyon (`zenodo_red_canyon`, `rgb2017.tif`,
   `rgb2019.tif`) carries `GeodataXform` sidecars like the Montana tiles; the open-dataset path flags
   `unapplied_georeference` but never applies them, so their footprints are the unadjusted positions. The
   field step's `georeference` could serve open datasets too (written next to the catalogue, never into the
   download folder). To decide with the Red Canyon annotations, if any were drawn on them.
4. **The ARC-zone ambiguity is handled for Montana only.** The correction lives in the Rumney layout file. No
   `.prj` in `open_datasets/` uses an ESRI Equidistant Cylindrical zone (checked), but layers inside
   geodatabases or GeoPackages were not checked, and any future ESRI data in such a zone would land about 30 km off
   under PROJ ≥ 9.8 (rasterio, QGIS). Suggestion: a curate check that flags CRSs whose method is spherical in
   ESRI's definition but ellipsoidal when read.
5. **A folder of photos has `media_type: image/jpeg`** on its STAC asset, although the asset is a folder, not a
   JPEG (`stac.photos_item`). Suggestion: no media type, or a role/extra field saying it is a folder.
6. **Collection licence `various`, also for data with no licence.** `build` sets a site collection's `license` to
   `various` whenever its items do not share one licence, including when none has a licence (all Rumney items:
   the collection says `various`). STAC deprecates `various` and `proprietary`; it asks for an SPDX expression for
   several licences (e.g. `CC0-1.0 AND CC-BY-4.0`) and `other` when the licence is not on the SPDX list, which with
   no licence link means "private, no rights granted"
   ([collection spec](https://github.com/radiantearth/stac-spec/blob/master/collection-spec/collection-spec.md)).
   Suggestion: an SPDX `AND` expression for mixed licences, `other` for none. `build.build`.
7. **The milestone table of `pipeline_design.md` (§12) is out of date.** Milestone 4 lists "photo and vector readers
   + Montana summary", which exist now (the inspect notebook does not); the `describe` row still mentions the paid
   API path, removed in the code review; the field step, the field layout files and the alignment check are not in
   the table at all. The course therefore says "what exists today" rather than "milestone 1". Suggestion: update §12
   (and §11, done) when milestone 2 is planned.
8. **`--list` prints sizes in GB with three decimals,** so small datasets show `0.000 GB` (Baldwin dams: a 55 KB zip,
   listed as `0.000 GB`, total `0.000 GB`). Suggestion: human-readable units (KB/MB/GB) in the clients' listing.
9. **A file that fails verification stays in place.** `http.fetch` renames the `.part` file to its final name
   before `downloads.verify` runs; when verification fails, the client stops with an error but the bad file stays
   where the good one belongs (writable, not logged). A second run sees it exists, skips the download, and fails
   again, until someone deletes it by hand (`sources/dataone.py`, the same pattern in the other clients).
   Suggestion: verify the `.part` file before renaming it, or move a failed file aside (e.g. `<name>.failed`).
10. **Photos in small folders get no evidence.** The evidence gatherer groups a folder of photos into one entry
    only from 10 photos up (`evidence.PHOTO_FOLDER`); below that each photo is listed on its own, and for a single
    photo it reads nothing (no camera, time or position). The course's sample, 6 photos, shows six empty entries.
    Suggestion: group any folder of photos, or read the EXIF of single photos too.
11. **The drafting prompt hard-codes the repository's paths.** `describe prompt` tells Claude to write the draft
    into `data_acquisition/summaries/` and to add new sites to `data_acquisition/sites.yaml`, even when
    `BEAVER_SITES` points to another registry (the registry it *lists* does follow `BEAVER_SITES`). Drafting the
    course's sample with Claude would write into the real summaries folder and registry. Suggestion: take the
    registry path from `load_sites`' resolution and allow an output folder for the draft.
12. **`describing_a_dataset.md` is partly out of date.** Step 5 says "Fill the manual fields you can" in the draft,
    but manual fields now live only in `data_acquisition/sites.yaml` (a summary may only give `hints`, anything else
    blocks); step 2 describes the evidence as "file lists, GeoTIFF headers, metadata records", leaving out vector
    layers, photo folders and report text. Suggestion: update the how-to (the course's chapter 9 has the current
    picture).
13. **A rebuild leaves the folders of items that no longer exist.** Removing a file from a summary and rebuilding
    gives a catalogue whose links are right (the item is gone from the collection), but the item's folder and JSON
    stay on disk under `stac/<dataset>/<site>/` (tested on the course's sample: the DSM's folder remained). Tools
    that follow links are fine; anything that scans the folder (`rglob("*.json")`, as several checks in this
    project's history did) still sees the old item. Suggestion: `stac.save` clears the dataset's catalogue folder
    (only `stac/<dataset>/`) before writing, or `build` removes item folders it did not write.
14. **`alignment.csv`'s `fid` is a row position, not the feature id.** `field_alignment.check` reads each layer with
    `gpd.read_file`, whose index is the row position (0-based), and writes it as `fid`; the exported GeoPackages keep
    the FileGDB's feature ids (`-preserve_fid`, 1-based, with gaps). On Rumney the two differ for every feature: the
    extract's dam is feature 45 on both 26 July and 6 August 2018, but row 44 and row 42 in `alignment.csv`. Anyone
    (or milestone 8's correction tool) joining alignment rows to features by `fid` gets the wrong feature.
    Suggestion: read with `pyogrio.read_dataframe(..., fid_as_index=True)` (or `gpd.read_file(..., fid_as_index=True)`)
    and rewrite `alignment.csv`. The course's extract tool now records both (`fid` as written, and `feature_id`).
15. **The ARC-zone offset is 30 km, not 25 km.** The Rumney layout file (`crs_corrections`, "about 25 km
    north-east") and `field_naming.md` ("newer PROJ: 25 km off") give the northward part only. Measured on a
    dam (chapter 2: 48.9245° N, 113.1391° W under the sphere; 49.1495° N, 112.9018° W under the ellipsoid) and on
    the extract's box centre, the shift is 30.4 km at a bearing of 35°: 25.0 km north, 17.4 km east. Suggestion:
    "about 30 km north-east" in both, and in the comment of `test_same_place_catches_a_different_earth_model`
    (`tests/dataset/test_field.py`). The course now says 30 km.
16. **`field.plan`'s docstring omits `georef` actions.** It says "``link`` and ``export`` actions", but `plan`
    also makes a `georef` action for each orthomosaic with an ArcGIS adjustment. Suggestion: name all three.
17. **A photo folder's footprint is where the camera was, not what it saw.** `stac.photos_item` uses the convex hull
    of the photos' GPS positions. For photos taken along one line (the course's sample: six photos, one line) that
    hull is a sliver polygon of almost no area (0.0003 m²), invisible on a map; the envelope fallback only catches
    exactly collinear points. Even for a full survey it understates the ground covered by about half a photo's
    footprint on every side (at 60 m, a Phantom 4 Pro photo covers about 90 m × 60 m). This matters for
    milestone 2's coverage map. Suggestion: buffer the hull by half the ground footprint, computed from the
    height above take-off and the camera (chapter 3), or at least by a fixed distance, and record which in the item.
18. **An item's product is not a property.** The product (orthomosaic, dsm, dams, ...) is recorded only as the key
    of the item's `data` asset and inside the item id; a reader must find the asset with role `data` to get it
    (the course's chapter 12 does). Milestone 2's timeline ("one row per product") will need it on every item.
    Suggestion: also write it as `beaver:product`.
19. **Photo altitude ignores `GPSAltitudeRef`, and EXIF is read by two separate functions.** EXIF stores the
    altitude as a positive number and a flag (`GPSAltitudeRef`, 1 = below sea level); `readers.photos.exif` and
    `field_inventory.read_photo` both read the number alone, so a photo 400 m below sea level reads +400 m (tested
    with a synthetic JPEG; harmless for our sites, all well above sea level). The two functions duplicate one job
    (the inventory's uses PIL's private `_getexif`), against the rule that code is organised by data type; the
    reader's test (`test_photo_reader` in `tests/dataset/test_evidence.py`) does not check the altitude, and the
    inventory's reader has no test. Suggestion: one EXIF reader in
    `readers/photos.py`, honouring the altitude flag, used by both, with a test.
20. **A failed verification keeps the last success.** `curate.verify` writes `verified: <date> (<against>)` into the
    provenance on success, but on a mismatch only adds `checksum_mismatch`, leaving the earlier `verified`. Tested on
    a scratch copy of the course's sample: verify, change one value in `dem_2022.asc`, verify again; the DTM item
    then says `verified: 2026-10-19 (repository md5)` and `checksum_mismatch` at once. Suggestion: remove `verified`
    (or record the failure in it) when the check fails or cannot be made.
21. **`snow_likely` is checked only for items with one date.** `curate_item` tests the month only when
    `item.datetime` is set; an item dated to a month or with a start and end (e.g. "March 2019" at 66° N) is never
    flagged, though its whole period may lie in the snow months. Suggestion: flag when every month of the item's
    period is a snow month (and say "possibly" when only some are).
22. **`http.stated_md5` misses Google's combined hash header.** It accepts an `x-goog-hash` value only if it starts
    with `md5=`; Google documents three response forms, `crc32c=…`, `md5=…` and `crc32c=…,md5=…` in one header
    ([XML API headers](https://cloud.google.com/storage/docs/xml-api/reference-headers)). For the combined form
    the MD5 is not read (tested with a hand-built header). Often harmless, as a GCS object's plain ETag is its MD5
    and is read next, but not for composite objects, whose ETag is not. Suggestion: split the header's values on
    commas before matching `md5=`.
23. **`prune` deletes any file it did not plan, not only its own.** Its docstring says it removes "links … and
    files the field step wrote", but it removes every file in the site folder that the new plan does not make,
    except the record names. Tested on a scratch drive (course chapter 17): a person's `my_notes.txt` in
    `beaver_dataset/sites/<site>/` was deleted by the next build, with no copy (it was not a link). Anything later
    stored there by hand, or by milestone 8's inspection tool, would be lost the same way. Suggestion: prune only
    what the previous `manifest.csv` lists (links and written files), and report anything else as unknown.
24. **Importing `field_alignment` switches off inline plots.** The module calls `matplotlib.use("Agg")` at import
    (for `--sheet`), which changes the backend for the whole process: in a notebook that imports it, `plt.show()`
    then draws nothing (found in the course's chapter 17, whose plots disappeared). Milestone 2's notebooks will
    import pipeline modules. Suggestion: choose the backend in `main` (or draw with `matplotlib.figure.Figure`,
    which needs no backend), not at import.
25. **No lint configuration.** `requirements-dev.txt` pins ruff 0.17.0, but the repository has no ruff settings
    (no `ruff.toml`, no `[tool.ruff]`), so `ruff check` uses its defaults: on the pipeline (`catalog`, `sources`,
    `readers`, `steps`, `intake.py`, `tests/dataset`) 503 findings at 120 columns, 447 of them `UP` (`typing.List`
    instead of `list`), a style the code deliberately does not follow. With the rules the code does follow
    (`--select E,F,W --line-length 120`), 22 remain: 13 ambiguous names `l` (E741), 8 lines of 121-123 characters
    (E501), a lambda assigned to a name (E731). Each person's own ruff settings change the result again. Suggestion: a `ruff.toml` with
    `line-length = 120` and the selected rules (excluding the legacy `data_acquisition/modules/`), and fix the 22.
26. **The tests fail when `BEAVER_SITES` is set.** `summary.load_sites` prefers the `BEAVER_SITES` environment
    variable to `summary.SITES`, but the tests' `registry` fixture (`tests/dataset/conftest.py`) only patches
    `SITES`. In a terminal where `BEAVER_SITES` is set (the course's chapters 0 and 6 tell students to export it),
    `python -m pytest tests/dataset` gives 1 failure and 22 errors ("site 'test_site' is not in
    data_acquisition/sites.yaml"). Introduced with `BEAVER_SITES` itself (commit `e6651e2`, before the course's
    no-pipeline-changes rule). Suggestion: `monkeypatch.delenv("BEAVER_SITES", raising=False)` in the fixture.
27. **`beaver_dataset/` still holds the output of the removed build tool, and `field_naming.md` is partly out of
    date.** On the drive, `beaver_dataset/README.md`, `manifest.csv` and `excluded.csv` (9 October) describe the
    old layout of `data_acquisition/dataset/build.py` (`raw/`, `reference/`, `products/`), removed in the code
    review; `sites/cut_bank_creek/` (2,235 files), `sites/pilling_ranch/` (21,355) and `sites/willow_creek/`
    (16,646, Montana's Willow Creek under the Alaska site's slug) are that tool's links. Only
    `sites/rumney_ranch/` comes from the current field step. `field_naming.md` says photo copies are found by
    being "byte-identical" (the inventory compares capture time and size) and lists ungeoreferenced `SmallChunks/`
    exports among the rules (the layout file decides those), besides the 25 km of finding 15. Found while writing
    the Mac rebuild guide (`rumney_rebuild_guide.md`), which reproduced the Rumney build read-only with the current
    code: inventory, plan, manifest, georeference fits and alignment identical; only one `excluded.csv` reason
    reworded since the build (commit f655273). Suggestion: move the legacy files and folders aside (e.g.
    `beaver_dataset_legacy/`, which exists) until the other sites get layout files; update `field_naming.md`.
28. **The root catalogue stores its own location as an absolute path.** `catalog/root.py` (`build_root`) sets the
    root catalogue's self href to the resolved path, so the `root` link of `<root>/stac/catalog.json` is absolute
    (`/media/fedeoli/Seagate Portable Drive/open_datasets/stac/catalog.json`), unlike its `child` links and the
    dataset catalogues, which are relative. On a copy of the drive mounted elsewhere, or under another user, that
    link points to the old location until `python -m data_acquisition.catalog.root --root <root>` is run again.
    Suggestion: save the root catalogue as self-contained, like `stac.save` does for the dataset catalogues, so
    the whole `stac/` folder can move.
