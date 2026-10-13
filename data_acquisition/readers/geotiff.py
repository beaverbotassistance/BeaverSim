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
    """Band names the file itself declares (RGB photometric interpretation), else None."""
    names = [c for c in header["colorinterp"] if c in ("red", "green", "blue")]
    return names if len(names) == header["count"] else None


def sample(path: Path, size: int = 1024) -> np.ma.MaskedArray:
    """Central ``size``×``size`` window of every band, nodata masked."""
    with rasterio.open(path) as d:
        w = Window(max(0, d.width // 2 - size // 2), max(0, d.height // 2 - size // 2),
                   min(size, d.width), min(size, d.height))
        return d.read(window=w, masked=True)
