#!/usr/bin/env python3
"""Make the course's Montana extract: a 60 m × 60 m piece of Rumney Ranch at two survey dates, from
``beaver_dataset/`` (needs the field-season drive).

For each date: the orthomosaic chunk the annotations were drawn on and the full tile, both cut to the box
and resampled to 5 cm (JPEG-compressed GeoTIFF); the features of every annotation layer of that date that
touch the box (unchanged: Z, M, attributes and feature ids); three photos taken over the box, downscaled
with their EXIF kept. The box is centred on the largest dam that lies on a chunk at both dates. A README
records the sources and what was done to them. A few MB, committed under ``docs/manual/data/montana_extract/``.

    python docs/manual/tools/make_montana_extract.py --site-dir "<drive>/beaver_dataset/sites/rumney_ranch"
"""
import argparse
import csv
import json
import subprocess
import warnings
from pathlib import Path
from typing import List, Optional, Tuple

import geopandas as gpd
import numpy as np
import rasterio
from PIL import Image
from rasterio.enums import Resampling
from rasterio.windows import from_bounds
from shapely.geometry import box

DATES = ("2018-07-26", "2018-08-06")      # chunks fit the annotations well on both (alignment.csv medians ~0.1-0.2 m)
HALF = 30.0                               # metres from the box centre to its edge
RES = 0.05                                # metres per pixel of the extract
PHOTO_PX = 800                            # longest side of the extract photos
OUT = Path("docs/manual/data/montana_extract")


def _holds(tif: Path, bounds: Tuple[float, float, float, float]) -> bool:
    with rasterio.open(tif) as r:
        b = r.bounds
    return b.left <= bounds[0] and b.bottom <= bounds[1] and b.right >= bounds[2] and b.top >= bounds[3]


def _image(survey: Path, bounds, chunk: bool) -> Optional[Path]:
    """The first chunk (or full tile) of a survey that holds the whole box."""
    tifs = sorted(survey.glob("orthomosaic_part-*.tif"))
    for tif in tifs:
        if ("_chunk-" in tif.name) == chunk and _holds(tif, bounds):
            return tif
    return None


def pick_box(site: Path) -> Tuple[float, float, float, float]:
    """Bounds (in the annotations' CRS) of a box around the largest dam on a chunk at every date of ``DATES``."""
    dams = gpd.read_file(site / "annotations" / DATES[0] / "dams.gpkg")
    for geom in dams.geometry.iloc[np.argsort(-dams.geometry.area.values)]:
        c = geom.centroid
        bounds = (c.x - HALF, c.y - HALF, c.x + HALF, c.y + HALF)
        if all(_image(site / "surveys" / d, bounds, chunk=True) and _image(site / "surveys" / d, bounds, chunk=False)
               for d in DATES):
            return bounds
    raise SystemExit("no dam lies on a chunk and a full tile at every date")


def cut_raster(tif: Path, bounds, out: Path) -> None:
    """The box of ``tif`` resampled to ``RES`` (average), RGB only, written as a JPEG-compressed GeoTIFF."""
    with rasterio.open(tif) as r:
        window = from_bounds(*bounds, transform=r.transform)
        size = int(round(2 * HALF / RES))
        data = r.read([1, 2, 3], window=window, out_shape=(3, size, size), resampling=Resampling.average)
        transform = rasterio.transform.from_bounds(*bounds, size, size)
        profile = {"driver": "GTiff", "width": size, "height": size, "count": 3, "dtype": "uint8",
                   "crs": r.crs, "transform": transform, "compress": "jpeg", "jpeg_quality": 85,
                   "photometric": "ycbcr", "tiled": True}
    with rasterio.open(out, "w", **profile) as d:
        d.write(data)


def cut_annotations(adir: Path, bounds, out_dir: Path) -> List[str]:
    """Every layer of an annotations folder, reduced to the features that touch the box: copied with ``ogr2ogr``
    (as the field step exports them), so geometries keep Z and M, attributes are unchanged and the feature ids
    are those of ``beaver_dataset``, which corrections refer to. Returns the files written."""
    written = []
    area = box(*bounds)
    for layer in sorted(adir.glob("*.gpkg")):
        if not gpd.read_file(layer).intersects(area).any():
            continue
        subprocess.run(["ogr2ogr", "-f", "GPKG", str(out_dir / layer.name), str(layer), layer.stem,
                        "-spat", *map(str, bounds), "-preserve_fid"], check=True, capture_output=True)
        written.append(layer.name)
    return written


def cut_photos(photo_dir: Path, lonlat_box, out_dir: Path, n: int = 3) -> List[str]:
    """``n`` photos taken over the box, downscaled, EXIF kept."""
    from data_acquisition.readers import photos
    chosen = []
    for p in sorted(photo_dir.rglob("*.JPG")):
        e = photos.exif(p)
        inside = e["lon"] is not None and lonlat_box[0] <= e["lon"] <= lonlat_box[2] \
            and lonlat_box[1] <= e["lat"] <= lonlat_box[3]
        if inside:
            chosen.append(p)
        if len(chosen) == n:
            break
    out_dir.mkdir(parents=True, exist_ok=True)
    for p in chosen:
        with Image.open(p) as im:
            exif = im.info.get("exif", b"")
            im.thumbnail((PHOTO_PX, PHOTO_PX))
            im.save(out_dir / p.name, exif=exif, quality=80)
    return [p.name for p in chosen]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--site-dir", required=True, type=Path, help="beaver_dataset/sites/rumney_ranch")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    warnings.simplefilter("ignore")
    site = args.site_dir
    bounds = pick_box(site)
    any_layer = next((site / "annotations" / DATES[0]).glob("*.gpkg"))
    crs = gpd.read_file(any_layer, rows=1).crs
    lonlat = gpd.GeoSeries([box(*bounds)], crs=crs).to_crs("EPSG:4326").total_bounds
    alignment = list(csv.DictReader(open(site / "alignment.csv"))) if (site / "alignment.csv").exists() else []
    record = {"site": "rumney_ranch", "box": {"bounds": [round(v, 3) for v in bounds], "crs": crs.to_wkt(),
                                              "lonlat": [round(v, 6) for v in lonlat]},
              "resolution_m": RES, "dates": {}}
    for day in DATES:
        out = args.out / day
        (out / "annotations").mkdir(parents=True, exist_ok=True)
        entry = {}
        for kind, chunk in (("chunk", True), ("full_tile", False)):
            tif = _image(site / "surveys" / day, bounds, chunk)
            cut_raster(tif, bounds, out / f"orthomosaic_{kind}.tif")
            entry[kind] = f"surveys/{day}/{tif.name}"
        entry["annotations"] = cut_annotations(site / "annotations" / day, bounds, out / "annotations")
        entry["photos"] = cut_photos(site / "surveys" / day / "photos", lonlat, out / "photos")
        names = {Path(a).stem for a in entry["annotations"]}
        entry["alignment"] = [r for r in alignment if r["date"] == day and r["layer"] in names
                              and r["kind"] == "chunk" and r["image"] == Path(entry["chunk"]).name]
        record["dates"][day] = entry
    (args.out / "extract.json").write_text(json.dumps(record, indent=1))
    size = sum(p.stat().st_size for p in args.out.rglob("*") if p.is_file())
    print(f"-> {args.out} ({size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
