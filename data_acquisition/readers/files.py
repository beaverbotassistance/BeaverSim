"""Files that belong to another file: raster sidecars, shapefile parts, and folders read as one file.

A summary lists a dataset's main files (``x.tif``, ``x.shp``, ``x.gdb``); their companions are never
listed on their own. The builder uses :func:`companions` to know which files a described file covers,
and the evidence gatherer uses :func:`is_companion` to leave them out of the evidence.
"""
from pathlib import Path, PurePosixPath
from typing import Set

# GDAL and ArcGIS sidecars of a raster x.tif: x.tif.ovr, x.tif.aux.xml, x.tfw, x.tfwx, ...
RASTER_SIDECARS = (".ovr", ".aux.xml", ".tfw", ".tfwx", ".msk", ".prj")
RASTERS = (".tif", ".tiff")
# the parts of a shapefile x.shp
SHAPEFILE_PARTS = (".shx", ".dbf", ".prj", ".cpg", ".sbn", ".sbx", ".qix", ".shp.xml", ".fix")
# folders read as one file (a File Geodatabase)
CONTAINERS = (".gdb",)


def companions(main: str) -> Set[str]:
    """The companion files of ``main`` (a path relative to its dataset folder, ``/``-separated)."""
    lower = main.lower()
    stem = main.rsplit(".", 1)[0]
    if lower.endswith(RASTERS):
        return {main + ext for ext in RASTER_SIDECARS} | {stem + ext for ext in RASTER_SIDECARS}
    if lower.endswith(".shp"):
        return {stem + ext for ext in SHAPEFILE_PARTS}
    return set()


def is_companion(path: Path) -> bool:
    """True if ``path`` is a sidecar or shapefile part whose main file exists next to it."""
    name = path.name.lower()
    stem = path.name.split(".")[0]
    for ext in RASTER_SIDECARS:
        if name.endswith(ext):
            main = path.name[:-len(ext)]
            if (path.with_name(main).exists() and main.lower().endswith(RASTERS)) or \
                    any(path.with_name(stem + r).exists() for r in RASTERS):
                return True
    return any(name.endswith(ext) for ext in SHAPEFILE_PARTS) and path.with_name(stem + ".shp").exists()


def inside_container(relative: str) -> bool:
    """True if ``relative`` (a ``/``-separated path) lies inside a folder read as one file."""
    return any(p.suffix.lower() in CONTAINERS for p in PurePosixPath(relative).parents)
