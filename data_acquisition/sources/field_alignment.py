#!/usr/bin/env python3
"""How well the annotations of one ``beaver_dataset`` site sit on the imagery of their date.

For every polygon annotation (dams, ponds, lodges, colony boundaries: their outlines follow visible
edges), on the first chunk and the first full orthomosaic tile that hold it: the shift that makes
its outline follow the image edges best (mean gradient of the smoothed image along the outline,
searched on a grid up to ``MAX_SHIFT`` m, coarse then fine). A best shift near zero means the outline
was drawn on that image as it is placed. Nothing is changed: this is a measurement, written to
``alignment.csv`` in the site folder.

Single values are noisy (an outline can lock onto another edge, and a shift at the search limit means
no fit was found), so read medians per date and image kind, as ``main`` prints them.

    python -m data_acquisition.sources.field_alignment --site-dir "<drive>/beaver_dataset/sites/rumney_ranch"
"""
import argparse
import csv
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.windows import Window
from scipy import ndimage

POLYGON_FEATURES = ("dams", "ponds", "lodges", "colony_boundaries")
MAX_SHIFT = 3.0                 # metres searched in each direction
COARSE, FINE = 0.2, 0.05        # grid steps, metres
MAX_WINDOW_PX = 9_000_000       # skip outlines whose window would be larger than this (pixels)
FIELDS = ["date", "layer", "fid", "kind", "image", "east_m", "north_m", "shift_m", "fit_found"]


def _outline_points(geom, to_px, res: float) -> np.ndarray:
    """Points along the outline(s) of a polygon, every ~2 pixels, as (column, row)."""
    pts = []
    for part in (geom.geoms if hasattr(geom, "geoms") else [geom]):
        ring = part.exterior
        n = max(int(ring.length / (res * 2)), 20)
        pts += [to_px * ring.interpolate(t, normalized=True).coords[0][:2]
                for t in np.linspace(0, 1, n, endpoint=False)]
    return np.array(pts)


def best_shift(tif: Path, geom) -> Optional[Tuple[float, float]]:
    """(east, north) shift in metres that best aligns ``geom`` (in the image's CRS) with the image edges, or
    None when the outline is not wholly on the image or the image there is mostly empty."""
    with rasterio.open(tif) as r:
        res = abs(r.transform.a)
        pad = int(MAX_SHIFT / res) + 20
        minx, miny, maxx, maxy = geom.bounds
        r0, c0 = r.index(minx, maxy)
        r1, c1 = r.index(maxx, miny)
        r0, c0, r1, c1 = min(r0, r1) - pad, min(c0, c1) - pad, max(r0, r1) + pad, max(c0, c1) + pad
        if r0 < 0 or c0 < 0 or r1 > r.height or c1 > r.width or (r1 - r0) * (c1 - c0) > MAX_WINDOW_PX:
            return None
        window = Window(c0, r0, c1 - c0, r1 - r0)
        img = r.read([1, 2, 3], window=window).astype(float).mean(0)
        to_px = ~r.window_transform(window)
    if (img == 0).mean() > 0.2:
        return None
    smooth = ndimage.gaussian_filter(img, 2)
    grad = np.hypot(ndimage.sobel(smooth, 0), ndimage.sobel(smooth, 1))
    pts = _outline_points(geom, to_px, res)

    def score(dx: float, dy: float) -> float:          # dx, dy in pixels
        x, y = pts[:, 0] + dx, pts[:, 1] + dy
        ok = (x >= 0) & (y >= 0) & (x < grad.shape[1] - 1) & (y < grad.shape[0] - 1)
        return float(ndimage.map_coordinates(grad, [y[ok], x[ok]], order=1).mean())

    def search(cx: float, cy: float, half: float, step: float) -> Tuple[float, float]:
        steps = np.arange(-half, half + 1e-9, step) / res
        return max(((cx + dx, cy + dy) for dy in steps for dx in steps), key=lambda s: score(*s))

    dx, dy = search(0.0, 0.0, MAX_SHIFT, COARSE)
    dx, dy = search(dx, dy, COARSE, FINE)
    return dx * res, -dy * res                       # rows grow southwards


def _images(survey: Path) -> Dict[str, List[Path]]:
    tifs = sorted(survey.glob("orthomosaic_part-*.tif"))
    return {"chunk": [t for t in tifs if "_chunk-" in t.name],
            "full tile": [t for t in tifs if "_chunk-" not in t.name]}


def check(site_dir: Path) -> List[Dict[str, Any]]:
    """One row per polygon annotation and image kind: the image used and the best-fit shift."""
    rows = []
    for adir in sorted((site_dir / "annotations").iterdir()):
        survey = site_dir / "surveys" / adir.name
        if not survey.is_dir():
            continue                                  # a season-wide folder (e.g. 2018): no imagery of its own
        images = _images(survey)
        for layer in sorted(adir.glob("*.gpkg")):
            if layer.stem.split("_colony-")[0].split("_points")[0].split("_pass")[0] not in POLYGON_FEATURES:
                continue
            frame = gpd.read_file(layer)
            for fid, geom in zip(frame.index, frame.geometry, strict=True):
                if geom is None or geom.is_empty or "Polygon" not in geom.geom_type:
                    continue
                for kind, tifs in images.items():
                    for tif in tifs:
                        try:
                            with rasterio.open(tif) as r:
                                local = gpd.GeoSeries([geom], crs=frame.crs).to_crs(r.crs.to_wkt()).iloc[0]
                        except Exception:     # an image whose CRS cannot be placed (e.g. a nameless LOCAL_CS)
                            continue
                        shift = best_shift(tif, local)
                        if shift is None:
                            continue
                        east, north = shift
                        rows.append({"date": adir.name, "layer": layer.stem, "fid": fid, "kind": kind,
                                     "image": tif.name,
                                     "east_m": round(east, 3), "north_m": round(north, 3),
                                     "shift_m": round(float(np.hypot(east, north)), 3),
                                     "fit_found": bool(max(abs(east), abs(north)) < MAX_SHIFT - FINE)})
                        break
    return rows


def summary(rows: List[Dict[str, Any]]) -> List[str]:
    """Median best-fit shift per date and image kind (shifts at the search limit left out)."""
    out = []
    for day in sorted({r["date"] for r in rows}):
        for kind in ("chunk", "full tile"):
            found = [r["shift_m"] for r in rows if r["date"] == day and r["kind"] == kind and r["fit_found"]]
            total = sum(1 for r in rows if r["date"] == day and r["kind"] == kind)
            if total:
                out.append(f"{day} {kind:9s}: median {np.median(found) if found else float('nan'):.2f} m over "
                           f"{len(found)} of {total} outlines")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--site-dir", required=True, type=Path, help="beaver_dataset/sites/<site>")
    args = parser.parse_args()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        rows = check(args.site_dir)
    with open(args.site_dir / "alignment.csv", "w", newline="") as f:
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        w.writerows(rows)
    print("\n".join(summary(rows)))
    print(f"-> {args.site_dir / 'alignment.csv'}")


if __name__ == "__main__":
    main()
