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
   geodatabases or GeoPackages were not checked, and any future ESRI data in such a zone would land 25 km off
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
