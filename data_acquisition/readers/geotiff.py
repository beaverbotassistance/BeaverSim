"""Raster reader (GeoTIFF and any other raster GDAL opens, e.g. ESRI ASCII grids): header facts, band
names declared by the file, and value samples. The module keeps its name; GeoTIFF is the usual case."""
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import rasterio
from rasterio.windows import Window

EXTENSIONS = (".tif", ".tiff")
# other extensions that may hold a raster; a file is a raster only if GDAL opens it as one
PROBE = (".asc", ".txt", ".img", ".vrt", ".jp2", ".nc", ".bil", ".dem", ".grd", ".xyz", ".hgt", ".sid", ".ecw")


def is_raster(path: Path) -> bool:
    """True for a GeoTIFF, or a file with a raster-like extension that GDAL opens as a georeferenceable raster."""
    suffix = path.suffix.lower()
    if suffix in EXTENSIONS:
        return True
    if suffix not in PROBE or not path.is_file():
        return False
    try:
        with rasterio.open(path) as d:
            return d.width > 1 and d.height > 1
    except Exception:            # not a raster GDAL can read (e.g. a README .txt)
        return False


def info(path: Path) -> Dict[str, Any]:
    """Header-only facts: CRS (EPSG code, and WKT2 for a CRS without one), bounds, shape, transform, resolution,
    bands, nodata, overviews, driver."""
    with rasterio.open(path) as d:
        return {"epsg": d.crs.to_epsg() if d.crs else None, "has_crs": d.crs is not None, "driver": d.driver,
                "crs": d.crs.to_wkt(version="WKT2_2019") if d.crs else None,
                "bounds": tuple(d.bounds),
                "shape": [d.height, d.width], "transform": list(d.transform)[:6],
                "resolution": tuple(abs(r) for r in d.res), "count": d.count, "dtypes": list(d.dtypes),
                "nodata": d.nodata, "colorinterp": [c.name for c in d.colorinterp],
                "overviews": d.overviews(1)}


def declared_bands(header: Dict[str, Any]) -> Optional[List[str]]:
    """Band names the file itself declares (RGB or RGBA photometric interpretation), else None."""
    names = [c for c in header["colorinterp"] if c in ("red", "green", "blue", "alpha")]
    return names if len(names) == header["count"] else None


def sample(path: Path, size: int = 1024) -> np.ma.MaskedArray:
    """Central ``size``×``size`` window of every band, nodata masked."""
    with rasterio.open(path) as d:
        w = Window(max(0, d.width // 2 - size // 2), max(0, d.height // 2 - size // 2),
                   min(size, d.width), min(size, d.height))
        return d.read(window=w, masked=True)


def arcgis_adjustment(aux: str) -> Optional[Dict[str, Any]]:
    """The ArcGIS georeferencing adjustment (``GeodataXform``) in the text of an ``.aux.xml``, or None.

    Returns ``type`` (e.g. PolynomialXform, CompositeXform), and for the step fitted to control points:
    ``order``, ``wkt`` (the CRS it maps into), ``source`` and ``target`` (n×2 arrays: the control points in
    the file's own coordinates and in that CRS). A ``CompositeXform`` chains steps: the one fitted to control
    points is taken, the others (given by coefficients only, e.g. an extra scaling) are listed in
    ``not_applied``. ``source`` is None when no single step is fitted to control points."""
    xform = re.search(r'<GeodataXform[^>]*xsi:type="typens:(\w+)"(.*?)</GeodataXform>', aux, re.S)
    if not xform:
        return None
    if xform.group(1) == "CompositeXform":
        steps = re.findall(r'<(XF_\d+) xsi:type="typens:(\w+)">(.*?)</\1>', xform.group(2), re.S)
    else:
        steps = [("XF", xform.group(1), xform.group(2))]
    fitted = [(name, kind, body) for name, kind, body in steps if "<SourceGCPs" in body]
    out: Dict[str, Any] = {"type": xform.group(1), "order": None, "wkt": None, "source": None, "target": None,
                           "not_applied": [f"{n} ({k})" for n, k, _ in steps]}
    if len(fitted) != 1:
        return out
    name, kind, body = fitted[0]

    def points(tag: str) -> np.ndarray:
        block = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", body, re.S).group(1)
        return np.array([float(v) for v in re.findall(r"<Double>([^<]+)</Double>", block)]).reshape(-1, 2)

    order = re.search(r"<PolynomialOrder>(\d+)</PolynomialOrder>", body)
    wkt = re.search(r"<WKT>(.*?)</WKT>", body, re.S)
    out.update(order=int(order.group(1)) if order and kind == "PolynomialXform" else None,
               wkt=wkt.group(1) if wkt else None, source=points("SourceGCPs"), target=points("TargetGCPs"),
               not_applied=[f"{n} ({k})" for n, k, _ in steps if n != name])
    return out


def unapplied_georeference(path: Path) -> Optional[Dict[str, Any]]:
    """An ArcGIS georeferencing adjustment in ``<file>.aux.xml`` (see :func:`arcgis_adjustment`), which GDAL
    does not apply, so the file's position as read here is the unadjusted one: its type, order and number of
    control points, or None."""
    aux = path.with_name(path.name + ".aux.xml")
    xform = arcgis_adjustment(aux.read_text(errors="replace")) if aux.exists() else None
    if xform is None:
        return None
    return {"type": xform["type"], "order": xform["order"],
            "control_points": 0 if xform["source"] is None else len(xform["source"])}
