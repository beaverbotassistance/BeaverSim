"""GeoTIFF reader: header facts, band names declared by the file, and value samples."""
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import rasterio
from rasterio.windows import Window

EXTENSIONS = (".tif", ".tiff")


def info(path: Path) -> Dict[str, Any]:
    """Header-only facts: CRS, bounds, shape, transform, resolution, bands, nodata, overviews."""
    with rasterio.open(path) as d:
        return {"epsg": d.crs.to_epsg() if d.crs else None, "bounds": tuple(d.bounds),
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


def unapplied_georeference(path: Path) -> Optional[Dict[str, Any]]:
    """An ArcGIS georeferencing adjustment stored in ``<file>.aux.xml`` (``GeodataXform``), which GDAL
    does not apply, so the file's position as read here is the unadjusted one. Returns its type,
    order, number of control-point pairs and the range of their shifts (in CRS units), or None.
    """
    import math
    import re
    aux = path.with_name(path.name + ".aux.xml")
    if not aux.exists():
        return None
    text = aux.read_text(errors="replace")
    xform = re.search(r'<GeodataXform[^>]*xsi:type="typens:(\w+)"(.*?)</GeodataXform>', text, re.S)
    if not xform:
        return None
    body = xform.group(2)

    def points(tag: str) -> List[float]:
        block = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", body, re.S)
        return [float(v) for v in re.findall(r"<Double>([^<]+)</Double>", block.group(1))] if block else []

    src, dst = points("SourceGCPs"), points("TargetGCPs")
    pairs = list(zip(zip(src[0::2], src[1::2]), zip(dst[0::2], dst[1::2])))
    shifts = [math.dist(a, b) for a, b in pairs]
    order = re.search(r"<PolynomialOrder>(\d+)</PolynomialOrder>", body)
    return {"type": xform.group(1), "order": int(order.group(1)) if order else None, "gcps": len(pairs),
            "shift_min": round(min(shifts), 2) if shifts else None, "shift_max": round(max(shifts), 2) if shifts else None}
