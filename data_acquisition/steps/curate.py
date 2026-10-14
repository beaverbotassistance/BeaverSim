#!/usr/bin/env python3
"""Step ``curate``: fill the ``beaver:`` descriptors of a catalog and report what is still unknown.

- **auto:** season, and quality checks on each raster (opens, CRS is the site CRS, nodata declared,
  values plausible for the product, snow likely, unapplied ArcGIS georeferencing) and each vector
  (opens, empty layers, CRS, heights in feet); optionally the checksum (``--verify``).
- **manual** (or **claude**, when Claude entered it): site confirmation, colonies, land status,
  governance and licence overrides, from the dataset summary. An entry is ``{value, by, date[, note]}``.
- **repository** values set by the builder are kept unless the summary overrides them.

Auto quality flags are recomputed on every run; repository and manual flags are kept.
The catalog is rewritten in place and ``curate_report.csv`` is written next to it.

    python -m data_acquisition.steps.curate --catalog "<drive>/open_datasets/stac/arcticdata_seward/catalog.json" \\
        --summary arcticdata_seward [--verify]
"""
import argparse
import csv
import datetime
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pystac
import rasterio

from data_acquisition.catalog import descriptors, stac
from data_acquisition.catalog import summary as summaries
from data_acquisition.readers import geotiff, table, vector
from data_acquisition.sources.archives import verify_member
from data_acquisition.sources.dataone import file_hash
from data_acquisition.catalog.descriptors import add_quality, get_field, set_field

SAMPLE = 1024           # side of the central window read for value checks, pixels
SNOW_LATITUDE = 55.0    # above this latitude, Nov–Apr surveys are flagged as likely snow-covered
ELEVATION_RANGE = (-500.0, 9000.0)
REFLECTANCE_RANGE = (0.0, 1.5)   # reflectance slightly above 1 is possible over specular surfaces


def _set_entered(item: pystac.Item, field: str, entry: Dict[str, Any], value: Any) -> None:
    """Set a field entered in the summary, as ``claude`` or ``manual`` depending on who entered it."""
    by = str(entry["by"])
    set_field(item, field, value, "claude" if by.startswith("claude") else "manual", by=by,
              date=str(entry.get("date")), note=entry.get("note"))


def check_raster(item: pystac.Item, key: str, site: Dict[str, Any], verify: bool) -> None:
    """Auto quality flags for the raster asset ``key`` of ``item``."""
    asset = item.assets[key]
    path = stac.asset_path(asset)
    if not path.exists():
        add_quality(item, "missing_file", str(path))
        return
    try:
        info = geotiff.info(path)
        data = geotiff.sample(path, SAMPLE)
    except rasterio.errors.RasterioError as e:
        add_quality(item, "unreadable", str(e))
        return
    expected = int(site["crs"].split(":")[1])
    epsg = info["epsg"] if info["has_crs"] else int(str(item.properties.get("beaver:crs_from_summary", ":0")).split(":")[1])
    if epsg != expected:
        add_quality(item, "crs_mismatch", f"EPSG:{epsg}, site CRS is {site['crs']}")
    xform = geotiff.unapplied_georeference(path)
    if xform:
        add_quality(item, "unapplied_georeference",
                    f"ArcGIS {xform['type']} (order {xform['order']}, {xform['gcps']} control points, shifts "
                    f"{xform['shift_min']}..{xform['shift_max']} m) in {path.name}.aux.xml is not applied when the "
                    "file is read; the footprint is the unadjusted position")
    if info["nodata"] is None:
        add_quality(item, "nodata_undeclared", "no nodata value; zero/black pixels may be outside the survey")
    names = [b.get("name") for b in asset.extra_fields.get("eo:bands", [])]
    if key in ("dsm", "dtm") and "elevation" in names:      # check only the elevation bands
        data = data[[i for i, n in enumerate(names) if n == "elevation"]]
    valid = data.compressed()
    if valid.size == 0:
        add_quality(item, "sample_empty", f"central {SAMPLE}px window has no valid pixels; values not checked")
    elif key in ("dsm", "dtm") and (valid.min() < ELEVATION_RANGE[0] or valid.max() > ELEVATION_RANGE[1]):
        add_quality(item, "elevation_range", f"sample {valid.min():.1f}..{valid.max():.1f} m")
    elif key == "multispectral":
        outside = np.mean((valid < REFLECTANCE_RANGE[0]) | (valid > REFLECTANCE_RANGE[1]))
        if outside > 0.01:
            add_quality(item, "not_reflectance",
                        f"{outside:.0%} of sampled values outside {REFLECTANCE_RANGE}; range "
                        f"{valid.min():.3g}..{valid.max():.3g}")
    if verify:
        _verify(item, asset, path)


def check_vector(item: pystac.Item, key: str, site: Dict[str, Any], verify: bool) -> None:
    """Auto quality flags for the vector asset ``key`` of ``item``."""
    asset = item.assets[key]
    path = stac.asset_path(asset)
    if not path.exists():
        add_quality(item, "missing_file", str(path))
        return
    try:
        spec = item.properties.get("beaver:table")
        info = table.info(path, spec, item.properties["beaver:crs_from_summary"]) if spec else vector.info(path)
        if item.properties.get("beaver:layer"):        # an item for one layer of the file: check that layer
            from data_acquisition.catalog.build import one_layer
            info = one_layer(info, item.properties["beaver:layer"])
    except Exception as e:      # GDAL raises several error types for broken vector files
        add_quality(item, "unreadable", f"{type(e).__name__}: {e}")
        return
    empty = [l["name"] for l in info["layers"] if not l["features"]]
    if empty:
        add_quality(item, "empty_layers", f"{len(empty)} of {len(info['layers'])} layers have no features: "
                                          f"{', '.join(empty[:10])}{'…' if len(empty) > 10 else ''}")
    expected = int(site["crs"].split(":")[1])
    if not info["crs"]:
        add_quality(item, "crs_mixed", "layers have different CRSs (or none); each is reprojected on its own")
    elif info["epsg"] != expected:
        add_quality(item, "crs_differs", f"{'EPSG:' + str(info['epsg']) if info['epsg'] else 'a CRS without EPSG code'}"
                                         f"; site CRS is {site['crs']} (reprojected when processed)")
    feet = [v for v in info["vertical_crs"] if "foot" in v.lower() or "feet" in v.lower()]
    if feet:
        add_quality(item, "vertical_unit_feet", f"heights in {', '.join(feet)}; convert to metres before use")
    if verify:
        _verify(item, asset, path)


def _verify(item: pystac.Item, asset: pystac.Asset, path: Path) -> None:
    """Check ``path`` against the repository checksum, or against its archive when it was extracted from one."""
    checksum = asset.extra_fields.get("file:checksum")
    archive = (get_field(item, "provenance") or {}).get("archive")
    if archive and not checksum:      # extracted from an archive: check against the archive's CRC-32
        zip_path = next((p / Path(archive).name for p in path.parents if (p / Path(archive).name).exists()), None)
        files = [f for f in path.rglob("*") if f.is_file()] if path.is_dir() else [path]
        if zip_path and all(verify_member(zip_path, f) for f in files):
            prov = dict(get_field(item, "provenance") or {})
            prov["verified"] = f"{datetime.date.today().isoformat()} (CRC-32 against {Path(archive).name})"
            item.properties["beaver:provenance"] = prov
        else:
            add_quality(item, "checksum_mismatch", f"differs from its member in {Path(archive).name}")
    elif not checksum:
        add_quality(item, "checksum_unknown", "no repository checksum to verify against")
    else:
        algorithm = {v: k for k, v in stac.MULTIHASH.items()}[checksum[:4]]
        if file_hash(path, algorithm) != checksum[4:]:
            add_quality(item, "checksum_mismatch", f"{algorithm} differs from the repository")
        else:
            prov = dict(get_field(item, "provenance") or {})
            prov["verified"] = datetime.date.today().isoformat()
            item.properties["beaver:provenance"] = prov


def curate_item(item: pystac.Item, summary: Dict[str, Any], verify: bool = False) -> None:
    slug = get_field(item, "site")
    site = summary["sites"].get(slug)
    if site is None:
        add_quality(item, "unknown_site", f"site {slug!r} is not in the summary")
        return
    # reset auto flags, keep repository and manual ones
    item.properties["beaver:quality"] = [q for q in get_field(item, "quality") or [] if q["source"] != "auto"]

    if site.get("confirmed"):
        _set_entered(item, "site", site["confirmed"], slug)
    lat = (item.bbox[1] + item.bbox[3]) / 2
    if item.datetime is not None:
        date = item.datetime.date()
        set_field(item, "season", descriptors.season(date, lat), "auto")
        if abs(lat) >= SNOW_LATITUDE and date.month in ((11, 12, 1, 2, 3, 4) if lat > 0 else (5, 6, 7, 8, 9, 10)):
            add_quality(item, "snow_likely", f"{date.isoformat()} at {lat:.1f}° latitude")
    else:   # a time span: one season only if it stays within one; else several epochs, or not known
        start, end = (item.common_metadata.start_datetime.date(), item.common_metadata.end_datetime.date())
        seasons = {descriptors.season(start, lat), descriptors.season(end, lat)}
        if len(seasons) == 1 and (end - start).days <= 92:
            value = seasons.pop()
        else:
            value = "unknown" if item.properties.get("beaver:date_precision") else "multiple"
        set_field(item, "season", value, "auto", note=f"{start}..{end}")

    for field in ("colonies", "land_status", "governance", "licence"):
        entry = site.get(field)
        if entry is not None:
            _set_entered(item, field, entry, entry["value"])
        else:
            item.properties.setdefault(f"beaver:{field}", None)   # listed as missing

    for key, asset in item.assets.items():
        if "data" in (asset.roles or []):
            raster = not item.properties.get("beaver:table") and geotiff.is_raster(stac.asset_path(asset))
            (check_raster if raster else check_vector)(item, key, site, verify)


def curate(catalog_path: Path, summary: Dict[str, Any], verify: bool = False) -> List[Dict[str, Any]]:
    catalog = stac.load(catalog_path)
    items = list(catalog.get_items(recursive=True))
    for item in items:
        print(f"  {item.id}")
        curate_item(item, summary, verify)
    catalog.save(pystac.CatalogType.SELF_CONTAINED)
    rows = descriptors.summary(items)
    with open(catalog_path.parent / "curate_report.csv", "w", newline="") as f:
        w = csv.DictWriter(f, ["item", "missing", "quality"])
        w.writeheader()
        w.writerows(rows)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--summary", required=True, help="summary name or YAML path")
    parser.add_argument("--verify", action="store_true", help="hash every file against its repository checksum")
    args = parser.parse_args()
    rows = curate(args.catalog, summaries.load(args.summary), args.verify)
    for r in rows:
        print(f"{r['item']:45s} missing: {r['missing'] or '-':35s} quality: {r['quality'] or '-'}")
    errors = stac.validate(stac.load(args.catalog))
    print("STAC valid" if not errors else "\n".join(["STAC errors:"] + errors))


if __name__ == "__main__":
    main()
