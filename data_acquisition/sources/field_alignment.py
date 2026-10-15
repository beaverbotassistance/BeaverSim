#!/usr/bin/env python3
"""How well the annotations of one ``beaver_dataset`` site sit on the imagery of their date.

For every polygon annotation (dams, ponds, lodges, colony boundaries: their outlines follow visible
edges), on the first chunk and the first full orthomosaic tile that hold it: the shift that makes
its outline follow the image edges best (mean gradient of the smoothed image along the outline,
searched on a grid up to ``MAX_SHIFT`` m, coarse then fine). A best shift near zero means the outline
was drawn on that image as it is placed. Nothing is changed: this is a measurement, written to
``alignment.csv`` in the site folder.

Single values are noisy (an outline can lock onto another edge, and a shift at the search limit means
no fit was found), so read medians per date and image kind, as ``main`` prints them, and look at the
annotations themselves: ``--sheet`` draws, per date and annotation type, one feature on the chunk and on
the full tile that hold it.

    python -m data_acquisition.sources.field_alignment --site-dir "<drive>/beaver_dataset/sites/rumney_ranch" \\
        [--sheet output/dataset/field/rumney_ranch/alignment.png]
"""
import argparse
import csv
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import Window
from scipy import ndimage

matplotlib.use("Agg")                   # files only, no display
import matplotlib.pyplot as plt  # noqa: E402  (after choosing the backend)

POLYGON_FEATURES = ("dams", "ponds", "lodges", "colony_boundaries")
MAX_SHIFT = 3.0                 # metres searched in each direction
COARSE, FINE = 0.2, 0.05        # grid steps, metres
MAX_WINDOW_PX = 9_000_000       # skip outlines whose window would be larger than this (pixels)
SHEET_FEATURES = ("dams", "canals", "trails", "ponds")
SHEET_HALF = 450                # half-size of each sheet panel, pixels (about 6 m at 1.3 cm)
FIELDS = ["date", "layer", "fid", "kind", "image", "east_m", "north_m", "shift_m", "fit_found"]


def _outline_points(geom, to_px, res: float) -> np.ndarray:
    """Points along the outline(s) of a polygon, every ~2 pixels, as (column, row)."""
    pts = []
    for part in (geom.geoms if hasattr(geom, "geoms") else [geom]):
        ring = part.exterior
        n = max(int(ring.length / (res * 2)), 20)
        pts += [to_px @ ring.interpolate(t, normalized=True).coords[0][:2]
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


def _holder(tifs: List[Path], feature: gpd.GeoDataFrame) -> Optional[Path]:
    """The first image of ``tifs`` that holds ``feature`` with a margin of ``SHEET_HALF`` pixels."""
    for tif in tifs:
        try:
            with rasterio.open(tif) as r:
                c = feature.to_crs(r.crs.to_wkt()).geometry.iloc[0].centroid
                row, col = r.index(c.x, c.y)
                if SHEET_HALF < col < r.width - SHEET_HALF and SHEET_HALF < row < r.height - SHEET_HALF:
                    return tif
        except Exception:               # an image whose CRS cannot be placed
            continue
    return None


def contact_sheet(site_dir: Path, out: Path) -> int:
    """Draw, per date and annotation type, the largest feature that an image holds, with every annotation of
    that date around it, on the chunk (left) and the full tile (right); returns the number of rows."""
    rows = []
    for adir in sorted((site_dir / "annotations").iterdir()):
        survey = site_dir / "surveys" / adir.name
        if not survey.is_dir():
            continue
        images = _images(survey)
        layers = {p.stem: gpd.read_file(p) for p in sorted(adir.glob("*.gpkg"))}
        everything = pd.concat(layers.values(), ignore_index=True)
        for kind in SHEET_FEATURES:
            names = [n for n in layers if n.split("_")[0] == kind and "points" not in n and "pass-1" not in n]
            if not names:
                continue
            cand = pd.concat([layers[n] for n in names], ignore_index=True)
            size = cand.geometry.area if kind in ("dams", "ponds") else cand.geometry.length
            for i in np.argsort(-size.values)[:15]:
                feature = cand.iloc[[i]]
                chunk, tile = _holder(images["chunk"], feature), _holder(images["full tile"], feature)
                if chunk or tile:
                    rows.append((adir.name, kind, feature, everything, chunk, tile))
                    break
    fig, axes = plt.subplots(len(rows), 2, figsize=(8, 4 * len(rows)), squeeze=False)
    for i, (day, kind, feature, everything, *tifs) in enumerate(rows):
        for j, tif in enumerate(tifs):
            ax = axes[i, j]
            ax.axis("off")
            if tif is None:
                ax.set_title(f"{day} {kind}: no {'chunk' if j == 0 else 'full tile'} holds it", fontsize=7)
                continue
            with rasterio.open(tif) as r:
                f = feature.to_crs(r.crs.to_wkt()).geometry.iloc[0]
                row, col = r.index(f.centroid.x, f.centroid.y)
                win = Window(col - SHEET_HALF, row - SHEET_HALF, 2 * SHEET_HALF, 2 * SHEET_HALF)
                img = r.read([1, 2, 3], window=win, boundless=True)
                to_px = ~r.window_transform(win)
                near = everything.to_crs(r.crs.to_wkt())
                near = near[near.intersects(f.centroid.buffer(SHEET_HALF * abs(r.transform.a) * 1.5))]
            ax.imshow(np.moveaxis(img, 0, -1))
            ax.set_title(f"{day} {kind}: {tif.name}", fontsize=7)
            for g in near.geometry:
                for part in (g.geoms if hasattr(g, "geoms") else [g]):
                    line = part.exterior if part.geom_type == "Polygon" else part
                    if line.geom_type != "Point":
                        q = np.array([to_px @ tuple(p[:2]) for p in line.coords])
                        ax.plot(q[:, 0], q[:, 1], color="yellow", lw=1)
            ax.set_xlim(0, 2 * SHEET_HALF)
            ax.set_ylim(2 * SHEET_HALF, 0)
    plt.tight_layout()
    plt.savefig(out, dpi=55)
    plt.close(fig)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--site-dir", required=True, type=Path, help="beaver_dataset/sites/<site>")
    parser.add_argument("--sheet", type=Path, help="also draw the contact sheet to this PNG")
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
    if args.sheet:
        args.sheet.parent.mkdir(parents=True, exist_ok=True)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            print(f"{contact_sheet(args.site_dir, args.sheet)} rows -> {args.sheet}")


if __name__ == "__main__":
    main()
