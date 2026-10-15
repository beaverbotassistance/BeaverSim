"""Vector reader: layers of a vector dataset (GeoPackage, shapefile, GeoJSON, KML/KMZ, File
Geodatabase, FlatGeobuf, GPX) with their CRS, geometry type, feature count, fields and bounds.

Header-only (plus a few attribute rows for evidence); geometries are not loaded. A File Geodatabase
is a folder (``*.gdb``); every other format is a file.
"""
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pyogrio
from pyproj import CRS

EXTENSIONS = (".gpkg", ".shp", ".geojson", ".json", ".kml", ".kmz", ".gdb", ".fgb", ".gpx")


def is_vector(path: Path) -> bool:
    return path.suffix.lower() in EXTENSIONS and (path.suffix.lower() != ".json" or _opens(path))


def _opens(path: Path) -> bool:
    try:
        pyogrio.list_layers(path)
        return True
    except Exception:
        return False


def _epsg(crs: Optional[str]) -> Optional[int]:
    if not crs:
        return None
    return CRS.from_user_input(crs).to_epsg()


def _split(crs: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """(horizontal WKT, vertical CRS name) of a CRS; a compound CRS (e.g. UTM + NAVD88 feet) is split."""
    if not crs:
        return None, None
    c = CRS.from_user_input(crs)
    if c.is_compound:
        parts = c.sub_crs_list
        vertical = next((s for s in parts if s.is_vertical), None)
        horizontal = next((s for s in parts if not s.is_vertical), parts[0])
        return horizontal.to_wkt(), (f"{vertical.name} ({vertical.axis_info[0].unit_name})" if vertical else None)
    return c.to_wkt(), None


def _sampled_type(path: Path, layer: str, n: int = 50) -> str:
    """Geometry type(s) of the first ``n`` features of a layer that declares none, e.g. ``LineString``."""
    frame = pyogrio.read_dataframe(path, layer=layer, columns=[], max_features=n)
    types = sorted(set(frame.geom_type.dropna()))
    return "/".join(types) if types else "Unknown"


def info(path: Path, sample_rows: int = 0) -> Dict[str, Any]:
    """Layers of ``path`` (name, geometry type, features, fields, CRS, bounds); optional attribute rows.

    ``crs`` (horizontal WKT), ``epsg`` and ``bounds`` at the top level are those of the layers together,
    when they share a horizontal CRS (all None if they disagree; ``epsg`` alone is None for a CRS without
    an EPSG code). A compound CRS is split: its vertical part goes to ``vertical_crs`` (name and unit).
    GDAL's notice that measured (M) geometries are read without M is silenced: the geometry type
    reported is the one read.
    """
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Measured \\(M\\) geometry types")
        return _info(path, sample_rows)


def _info(path: Path, sample_rows: int) -> Dict[str, Any]:
    # GDAL opens the file again for every call below. That is cheap except for KML, which is parsed whole on
    # each open: a KML of ~1,450 layers (EEAGER) takes ~100 s per pass, twice (header and sampled type).
    layers: List[Dict[str, Any]] = []
    for name, geom_type in pyogrio.list_layers(path):
        meta = pyogrio.read_info(path, layer=name, force_feature_count=True, force_total_bounds=True)
        if geom_type in (None, "Unknown") and meta["features"]:     # e.g. KML: the layer does not declare it
            geom_type = _sampled_type(path, name)
        horizontal, vertical = _split(meta["crs"])
        layer = {"name": name, "geometry_type": geom_type, "features": int(meta["features"]),
                 "fields": list(meta["fields"]), "crs": horizontal, "vertical_crs": vertical,
                 "epsg": _epsg(horizontal),
                 "bounds": [float(v) for v in meta["total_bounds"]] if meta.get("total_bounds") is not None
                 and meta["features"] else None}
        if sample_rows and meta["features"] and layer["fields"]:
            table = pyogrio.read_dataframe(path, layer=name, read_geometry=False, max_features=sample_rows)
            layer["sample"] = table.astype(str).to_dict(orient="records")
        layers.append(layer)
    # layers share a CRS when their EPSG codes match (GDAL may write the same CRS as different WKT), else the WKT
    keys = {f"EPSG:{l['epsg']}" if l["epsg"] else l["crs"] for l in layers if l["bounds"]}
    bounded = [l["bounds"] for l in layers if l["bounds"]]
    same = bounded and len(keys) == 1
    crs = next(l["crs"] for l in layers if l["bounds"]) if same else None
    bounds = ([min(b[0] for b in bounded), min(b[1] for b in bounded), max(b[2] for b in bounded),
               max(b[3] for b in bounded)] if same else None)
    verticals = sorted({l["vertical_crs"] for l in layers if l["vertical_crs"]})
    return {"layers": layers, "crs": crs, "epsg": _epsg(crs) if crs else None, "bounds": bounds,
            "vertical_crs": verticals, "features": sum(l["features"] for l in layers)}


def one_layer(info: Dict[str, Any], name: str) -> Dict[str, Any]:
    """``info`` (from :func:`info`) restricted to the layer ``name``, in the same shape."""
    layer = next(l for l in info["layers"] if l["name"] == name)
    return {"layers": [layer], "crs": layer["crs"], "epsg": layer["epsg"], "bounds": layer["bounds"],
            "vertical_crs": [layer["vertical_crs"]] if layer["vertical_crs"] else [],
            "features": layer["features"]}
