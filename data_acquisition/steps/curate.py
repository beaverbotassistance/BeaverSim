#!/usr/bin/env python3
"""Step ``curate``: fill the ``beaver:`` descriptors of a catalog and report what is still unknown.

- **auto:** season, and quality checks on each raster (opens, CRS is the site CRS, nodata declared,
  values plausible for the product, snow likely, unapplied ArcGIS georeferencing) and each vector or
  table (opens, empty layers, CRS, heights in feet); optionally the checksum (``--verify``).
- **manual** (or **claude**, when Claude entered it): site confirmation, colonies, land status and
  governance, from the site registry. An entry is ``{value, by, date[, note]}``.
- **repository** and **build** values set by the builder are kept.

Auto quality flags are recomputed on every run; the builder's, the repository's and the summary's are kept.
The catalog is rewritten in place and ``curate_report.csv`` is written next to it.

    python -m data_acquisition.steps.curate --catalog "<drive>/open_datasets/stac/arcticdata_seward/catalog.json" \\
        --summary arcticdata_seward [--verify]
"""
import argparse
import csv
import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pystac
import rasterio
from pystac.extensions.projection import ProjectionExtension

from data_acquisition.catalog import descriptors, stac
from data_acquisition.catalog import summary as summaries
from data_acquisition.catalog.descriptors import add_quality, get_field, set_field
from data_acquisition.readers import geotiff, table, vector
from data_acquisition.sources import checksums
from data_acquisition.sources.archives import verify_member

SAMPLE = 1024           # side of the central window read for value checks, pixels
SNOW_LATITUDE = 55.0    # above this latitude, Nov–Apr surveys are flagged as likely snow-covered
ELEVATION_PRODUCTS = ("dsm", "dtm")              # products whose values are heights, checked for plausibility
ELEVATION_RANGE = (-500.0, 9000.0)
REFLECTANCE_RANGE = (0.0, 1.5)   # reflectance slightly above 1 is possible over specular surfaces
MANUAL_FIELDS = ("colonies", "land_status", "governance")


def _set_entered(item: pystac.Item, field: str, entry: Dict[str, Any], value: Any) -> None:
    """Set a field entered in the registry, as ``claude`` or ``manual`` depending on who entered it."""
    by = str(entry["by"])
    set_field(item, field, value, "claude" if by.startswith("claude") else "manual", by=by,
              date=str(entry.get("date")), note=entry.get("note"))


def check_raster(item: pystac.Item, key: str, site: Dict[str, Any]) -> None:
    """Auto quality flags for the raster asset ``key`` of ``item``."""
    path = stac.asset_path(item.assets[key])
    try:
        info = geotiff.info(path)
        data = geotiff.sample(path, SAMPLE)
    except rasterio.errors.RasterioError as e:
        add_quality(item, "unreadable", str(e))
        return
    epsg = info["epsg"] if info["has_crs"] else ProjectionExtension.ext(item).epsg   # else: the summary's CRS
    if epsg != int(site["crs"].split(":")[1]):
        add_quality(item, "crs_mismatch", f"EPSG:{epsg}, site CRS is {site['crs']}")
    xform = geotiff.unapplied_georeference(path)
    if xform:
        add_quality(item, "unapplied_georeference",
                    f"ArcGIS {xform['type']} (order {xform['order']}, {xform['gcps']} control points, shifts "
                    f"{xform['shift_min']}..{xform['shift_max']} m) in {path.name}.aux.xml is not applied when the "
                    "file is read; the footprint is the unadjusted position")
    if info["nodata"] is None:
        add_quality(item, "nodata_undeclared", "no nodata value; zero/black pixels may be outside the survey")
    names = [b.get("name") for b in item.assets[key].extra_fields.get("eo:bands", [])]
    if key in ELEVATION_PRODUCTS and "elevation" in names:      # check only the elevation bands
        data = data[[i for i, n in enumerate(names) if n == "elevation"]]
    valid = data.compressed()
    if valid.size == 0:
        add_quality(item, "sample_empty", f"central {SAMPLE}px window has no valid pixels; values not checked")
    elif key in ELEVATION_PRODUCTS and (valid.min() < ELEVATION_RANGE[0] or valid.max() > ELEVATION_RANGE[1]):
        add_quality(item, "elevation_range", f"sample {valid.min():.1f}..{valid.max():.1f} m")
    elif key == "multispectral":
        outside = np.mean((valid < REFLECTANCE_RANGE[0]) | (valid > REFLECTANCE_RANGE[1]))
        if outside > 0.01:
            add_quality(item, "not_reflectance",
                        f"{outside:.0%} of sampled values outside {REFLECTANCE_RANGE}; range "
                        f"{valid.min():.3g}..{valid.max():.3g}")


def check_vector(item: pystac.Item, key: str, site: Dict[str, Any]) -> None:
    """Auto quality flags for the vector or table asset ``key`` of ``item`` (for a layer item, its layer)."""
    path = stac.asset_path(item.assets[key])
    try:
        spec = item.properties.get("beaver:table")
        info = (table.info(path, spec, item.properties.get("beaver:crs_from_summary") or site["crs"]) if spec
                else vector.info(path))
        if item.properties.get("beaver:layer"):
            info = vector.one_layer(info, item.properties["beaver:layer"])
    except Exception as e:      # GDAL raises several error types for broken vector files
        add_quality(item, "unreadable", f"{type(e).__name__}: {e}")
        return
    empty = [l["name"] for l in info["layers"] if not l["features"]]
    if empty:
        add_quality(item, "empty_layers", f"{len(empty)} of {len(info['layers'])} layers have no features: "
                                          f"{', '.join(empty[:10])}{'…' if len(empty) > 10 else ''}")
    if info.get("spatial") is not False:       # a non-spatial table has no CRS to check
        if not info["crs"]:
            add_quality(item, "crs_mixed", "layers have different CRSs (or none); each is reprojected on its own")
        elif info["epsg"] != int(site["crs"].split(":")[1]):
            found = f"EPSG:{info['epsg']}" if info["epsg"] else "a CRS without EPSG code"
            add_quality(item, "crs_differs", f"{found}; site CRS is {site['crs']} (reprojected when processed)")
    feet = [v for v in info["vertical_crs"] if "foot" in v.lower() or "feet" in v.lower()]
    if feet:
        add_quality(item, "vertical_unit_feet", f"heights in {', '.join(feet)}; convert to metres before use")


def _checksum_verdict(asset: pystac.Asset, path: Path, provenance: Dict[str, Any]) -> Tuple[Optional[bool], str]:
    """(matches?, what it was checked against) for a file; matches is None when there is nothing to check.

    In order: the record's checksum written on the asset (``file:checksum``); the archive the file was
    extracted from (CRC-32 of each member); the record's checksum in another form (e.g. a multipart ETag),
    when it can be decided; the checksum recorded when the file was downloaded."""
    multihash = asset.extra_fields.get("file:checksum")
    if multihash:
        algorithm = {v: k for k, v in stac.MULTIHASH.items()}[multihash[:4]]
        return checksums.digest(path, algorithm) == multihash[4:], f"repository {algorithm}"
    if provenance.get("archive"):
        name = Path(provenance["archive"]).name
        archive = next((p / name for p in path.parents if (p / name).exists()), None)
        if archive is None:
            return None, f"archive {name} not found"
        members = [f for f in path.rglob("*") if f.is_file()] if path.is_dir() else [path]
        return all(verify_member(archive, m) for m in members), f"CRC-32 against {name}"
    record = provenance.get("checksum")
    if record:
        verdict = checksums.check(path, record["algorithm"], record["value"])
        if verdict is not None:
            return verdict, f"record {record['algorithm']}"
    download = provenance.get("download_checksum")
    if download:
        return (checksums.digest(path, download["algorithm"]) == download["value"],
                f"{download['algorithm']} recorded at download ({provenance.get('download_verified_by')})")
    return None, "no checksum"


def verify(item: pystac.Item, key: str) -> None:
    """Check the file of asset ``key`` against its checksum; record the date, or flag the problem."""
    asset = item.assets[key]
    provenance = get_field(item, "provenance") or {}
    verdict, against = _checksum_verdict(asset, stac.asset_path(asset), provenance)
    if verdict is None:
        add_quality(item, "checksum_unknown", f"nothing to verify against ({against})")
    elif not verdict:
        add_quality(item, "checksum_mismatch", f"differs from the {against}")
    else:
        item.properties["beaver:provenance"] = {**provenance,
                                                "verified": f"{datetime.date.today().isoformat()} ({against})"}


def _season(item: pystac.Item) -> Tuple[str, Optional[str]]:
    """(season, note) of an item: from its date and hemisphere; for a span, one season only if the span
    stays within one; ``unknown`` without a footprint or when the date is unknown or imprecise."""
    if not item.bbox:
        return "unknown", "no footprint"
    lat = (item.bbox[1] + item.bbox[3]) / 2
    if item.datetime is not None:
        return descriptors.season(item.datetime.date(), lat), None
    start, end = item.common_metadata.start_datetime.date(), item.common_metadata.end_datetime.date()
    seasons = {descriptors.season(start, lat), descriptors.season(end, lat)}
    if item.properties.get("beaver:date_precision") == "unknown":
        return "unknown", f"{start}..{end}"
    if len(seasons) == 1 and (end - start).days <= 92:
        return seasons.pop(), f"{start}..{end}"
    # a month or year spanning seasons is not known more precisely; two epochs compared span several
    return ("unknown" if item.properties.get("beaver:date_precision") else "multiple"), f"{start}..{end}"


def curate_item(item: pystac.Item, summary: Dict[str, Any], verify_files: bool = False) -> None:
    """Recompute the auto descriptors and quality flags of ``item``, and fill its manual fields from the
    site registry (through ``summary``, which has the registry's site entries)."""
    slug = get_field(item, "site")
    site = summary["sites"].get(slug)
    if site is None:
        add_quality(item, "unknown_site", f"site {slug!r} is not in the summary")
        return
    item.properties["beaver:quality"] = [q for q in get_field(item, "quality") or [] if q["source"] != "auto"]

    if site.get("confirmed"):
        _set_entered(item, "site", site["confirmed"], slug)
    season, note = _season(item)
    set_field(item, "season", season, "auto", note=note)
    if item.datetime is not None and item.bbox:
        lat, month = (item.bbox[1] + item.bbox[3]) / 2, item.datetime.month
        if abs(lat) >= SNOW_LATITUDE and month in ((11, 12, 1, 2, 3, 4) if lat > 0 else (5, 6, 7, 8, 9, 10)):
            add_quality(item, "snow_likely", f"{item.datetime.date().isoformat()} at {lat:.1f}° latitude")

    for field in MANUAL_FIELDS:
        entry = site.get(field)
        if entry is not None:
            _set_entered(item, field, entry, entry["value"])
        else:
            item.properties.setdefault(f"beaver:{field}", None)   # listed as missing

    for key, asset in item.assets.items():
        if "data" not in (asset.roles or []):
            continue
        if not stac.asset_path(asset).exists():
            add_quality(item, "missing_file", str(stac.asset_path(asset)))
            continue
        kind = item.properties.get("beaver:kind") or (    # catalogs built before items recorded their kind
            "table" if item.properties.get("beaver:table") else
            "raster" if geotiff.is_raster(stac.asset_path(asset)) else "vector")
        (check_raster if kind == "raster" else check_vector)(item, key, site)
        if verify_files:
            verify(item, key)


def curate(catalog_path: Path, summary: Dict[str, Any], verify_files: bool = False) -> List[Dict[str, Any]]:
    """Curate every item of the catalog at ``catalog_path`` in place; returns the report rows."""
    catalog = stac.load(catalog_path)
    items = list(catalog.get_items(recursive=True))
    for item in items:
        print(f"  {item.id}")
        curate_item(item, summary, verify_files)
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
    parser.add_argument("--verify", action="store_true", help="check every file against its checksum")
    args = parser.parse_args()
    rows = curate(args.catalog, summaries.load(args.summary), args.verify)
    for r in rows:
        print(f"{r['item']:45s} missing: {r['missing'] or '-':35s} quality: {r['quality'] or '-'}")
    errors = stac.validate(stac.load(args.catalog))
    print("STAC valid" if not errors else "\n".join(["STAC errors:"] + errors))


if __name__ == "__main__":
    main()
