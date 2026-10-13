"""Table reader: a CSV of points read as a point layer, as the summary's ``table`` spec says.

``spec = {skip, x, y[, z, delimiter]}``: lines to skip above the column names, and the coordinate
columns. The CRS comes from the summary (tables rarely state one). Returns the same shape as
:func:`data_acquisition.readers.vector.info`, so tables become vector items like any point layer.
"""
from pathlib import Path
from typing import Any, Dict

import pandas as pd

EXTENSIONS = (".csv", ".tsv", ".txt")


def read(path: Path, spec: Dict[str, Any]) -> pd.DataFrame:
    sep = spec.get("delimiter") or ("\t" if path.suffix.lower() == ".tsv" else ",")
    table = pd.read_csv(path, skiprows=int(spec.get("skip") or 0), sep=sep)
    table.columns = [str(c).strip() for c in table.columns]
    missing = [spec[k] for k in ("x", "y", "z") if spec.get(k) and spec[k] not in table.columns]
    if missing:
        raise KeyError(f"{path.name}: no column {missing}; columns are {list(table.columns)}")
    return table


def info(path: Path, spec: Dict[str, Any], crs: str) -> Dict[str, Any]:
    """One point layer: features (rows with numeric coordinates), fields, bounds in ``crs``."""
    from data_acquisition.readers.vector import _epsg
    from pyproj import CRS
    table = read(path, spec)
    x = pd.to_numeric(table[spec["x"]], errors="coerce")
    y = pd.to_numeric(table[spec["y"]], errors="coerce")
    ok = x.notna() & y.notna()
    wkt = CRS.from_user_input(crs).to_wkt()
    bounds = [float(x[ok].min()), float(y[ok].min()), float(x[ok].max()), float(y[ok].max())] if ok.any() else None
    layer = {"name": path.stem, "geometry_type": "Point Z" if spec.get("z") else "Point", "features": int(ok.sum()),
             "fields": list(table.columns), "crs": wkt, "vertical_crs": None, "epsg": _epsg(wkt), "bounds": bounds,
             "rows_without_coordinates": int((~ok).sum())}
    return {"layers": [layer], "crs": wkt, "epsg": layer["epsg"], "bounds": bounds, "vertical_crs": [],
            "features": layer["features"]}
