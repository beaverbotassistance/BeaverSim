"""Table reader: a CSV read as the summary's ``table`` spec says, either as a point layer or, without
coordinate columns, as a non-spatial table (e.g. model results per stream reach).

``spec = {skip[, x, y, z, delimiter]}``: lines to skip above the column names, and the coordinate
columns (both ``x`` and ``y``, or neither). The CRS comes from the summary (tables rarely state one).
Returns the same shape as :func:`data_acquisition.readers.vector.info`, so tables become vector items
like any point layer.
"""
from pathlib import Path
from typing import Any, Dict

import pandas as pd
from pyproj import CRS

EXTENSIONS = (".csv", ".tsv", ".txt")


def read(path: Path, spec: Dict[str, Any]) -> pd.DataFrame:
    sep = spec.get("delimiter") or ("\t" if path.suffix.lower() == ".tsv" else ",")
    table = pd.read_csv(path, skiprows=int(spec.get("skip") or 0), sep=sep)
    table.columns = [str(c).strip() for c in table.columns]
    missing = [spec[k] for k in ("x", "y", "z") if spec.get(k) and spec[k] not in table.columns]
    if missing:
        raise KeyError(f"{path.name}: no column {missing}; columns are {list(table.columns)}")
    return table


def rows_info(path: Path, spec: Dict[str, Any]) -> Dict[str, Any]:
    """A table without coordinates (``spec`` has no ``x``/``y``): its columns and row count, no geometry.

    Rows are counted as lines, without loading the table (some are hundreds of MB)."""
    sep = spec.get("delimiter") or ("\t" if path.suffix.lower() == ".tsv" else ",")
    columns = [str(c).strip() for c in pd.read_csv(path, skiprows=int(spec.get("skip") or 0), sep=sep, nrows=0).columns]
    with open(path, "rb") as f:
        lines = sum(1 for _ in f)
    rows = max(lines - int(spec.get("skip") or 0) - 1, 0)
    layer = {"name": path.stem, "geometry_type": None, "features": rows, "fields": columns, "crs": None,
             "vertical_crs": None, "epsg": None, "bounds": None}
    return {"layers": [layer], "crs": None, "epsg": None, "bounds": None, "vertical_crs": [], "features": rows,
            "spatial": False}


def info(path: Path, spec: Dict[str, Any], crs: str) -> Dict[str, Any]:
    """One point layer: features (rows with numeric coordinates), fields, bounds in ``crs``; a table spec
    without ``x``/``y`` gives :func:`rows_info` instead."""
    if not (spec.get("x") and spec.get("y")):
        return rows_info(path, spec)
    table = read(path, spec)
    x = pd.to_numeric(table[spec["x"]], errors="coerce")
    y = pd.to_numeric(table[spec["y"]], errors="coerce")
    ok = x.notna() & y.notna()
    crs_ = CRS.from_user_input(crs)
    wkt = crs_.to_wkt()
    bounds = [float(x[ok].min()), float(y[ok].min()), float(x[ok].max()), float(y[ok].max())] if ok.any() else None
    layer = {"name": path.stem, "geometry_type": "Point Z" if spec.get("z") else "Point",
             "features": int(ok.sum()), "fields": list(table.columns), "crs": wkt, "vertical_crs": None,
             "epsg": crs_.to_epsg(), "bounds": bounds, "rows_without_coordinates": int((~ok).sum())}
    return {"layers": [layer], "crs": wkt, "epsg": layer["epsg"], "bounds": bounds, "vertical_crs": [],
            "features": layer["features"]}
