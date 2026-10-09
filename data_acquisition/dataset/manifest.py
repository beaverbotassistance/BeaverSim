#!/usr/bin/env python3
"""Build the manifest of the field-season drive: every file the beaver dataset needs, and why.

The manifest is a single CSV with one row per source file (or per annotation layer) and a
``role`` column:

- ``raw_photo``:       drone photos, identified by camera model in EXIF (not by folder name)
- ``video_frame``:     frames extracted from drone video (May 2018 surveys): no EXIF, no GPS
- ``reference_ortho``: orthomosaics exported from the original processing (annotations were drawn on them)
- ``annotation``:      one row per layer of an ArcGIS File Geodatabase or shapefile

Common columns: ``role, site, survey_date, include, note, source_path, bytes``.
For photos ``survey_date`` is the EXIF capture date; ``folder_date`` is the date in the folder name
(they differ when a flight was filed in another survey's folder).
Role-specific columns are left empty for the other roles.

The drive is only read. Usage:

    python -m data_acquisition.dataset.manifest --root "/media/<user>/Seagate Portable Drive" \\
        --out output/dataset/manifest.csv
"""
import argparse
import csv
import datetime
import math
import os
import re
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from PIL import Image
from PIL.ExifTags import GPSTAGS, TAGS

# Constants
# Drone camera of the field seasons (DJI Phantom 4 Pro)
CAMERA_MODELS = {"FC6310"}
# Season folders scanned on the drive
SEASON_FOLDERS = ["2018 Field Season/Drone Flights", "2019 Field Season"]
# Folder name on the drive -> site slug
SITES = {
    "Rumney Ranch": "rumney_ranch", "Rumney": "rumney_ranch",
    "Pilling Ranch": "pilling_ranch", "Pilling": "pilling_ranch",
    "Willow Creek": "willow_creek", "Willow": "willow_creek",
    "Cut Bank Creek": "cut_bank_creek",
    "BBC Drone Mimicry Site": "bbc_mimicry",
    "Yard": "yard",
}
# Sites that are not study sites (kept in the manifest, excluded from the dataset)
NON_STUDY_SITES = {"bbc_mimicry": "filming set-up, not a study site", "yard": "test flight"}
MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
          "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12}
DATE_PATTERN = re.compile(r"(\d{1,2})\s*(jan|feb|mar|apr|may|june?|july?|aug|sept?|oct|nov|dec)[a-z]*\s*(20\d\d)", re.I)
# Annotation feature kinds, matched against geodatabase + layer name (first match wins)
# Month-before-day without year, e.g. 'Jul04', 'June06', 'July4' (not followed by more digits)
MONTH_DAY_PATTERN = re.compile(r"(jan|feb|mar|apr|may|june?|july?|aug|sept?|oct|nov|dec)[a-z]*_?(\d{1,2})(?!\d)", re.I)
FEATURE_KINDS = [
    ("dam", r"^(export_output_)?d\d"), ("canal", r"^c\d"), ("pond", r"^p\d{1,2}[a-z]"),
    ("elevation", r"^pg\d"),
    ("colony_boundary", r"colonyboundar"), ("dam_dimension", r"damwidth|damthick|damdimension"),
    ("dam", r"dam"), ("canal", r"canal"), ("trail", r"trail"), ("lodge", r"lodge"), ("pond", r"pond"),
    ("river_reach", r"riverreach|river|stream"), ("vegetation", r"vegetation"), ("elevation", r"elevation|profile"),
    ("fairy_ring", r"fairy"),
]
COLUMNS = ["role", "site", "survey_date", "folder_date", "include", "note", "source_path", "bytes",
           # raw_photo
           "camera", "taken_at", "lat", "lon", "alt_m", "width", "height",
           # reference_ortho
           "crs", "gsd_m", "bands",
           # annotation
           "layer", "geometry", "n_features", "feature_kind", "colony"]


# ============================================================
# PARSING HELPERS
# ============================================================

def parse_date(text: str, default_year: Optional[int] = None) -> Optional[str]:
    """
    First date in ``text`` as ISO 'YYYY-MM-DD'. Accepts '06May2018', '05 June 2018', '02Sept2019' and,
    when ``default_year`` is given, year-less forms such as 'Jul04', 'June06', 'July4', 'May05'.
    """
    m = DATE_PATTERN.search(text)
    if m:
        day, month, year = int(m.group(1)), MONTHS[m.group(2).lower()], int(m.group(3))
    else:
        m = MONTH_DAY_PATTERN.search(text) if default_year else None
        if not m:
            return None
        month, day, year = MONTHS[m.group(1).lower()], int(m.group(2)), default_year
    try:
        return datetime.date(year, month, day).isoformat()
    except ValueError:
        return None


def season_of(rel_path: str) -> int:
    """Field-season year of a path: 2019 if the path names 2019, else 2018."""
    return 2019 if "2019" in rel_path else 2018


def site_of(rel_path: str) -> Optional[str]:
    """Site slug from a path relative to the drive root."""
    parts = rel_path.split("/")
    folder = parts[2] if parts[1] == "Drone Flights" else parts[1]
    return SITES.get(folder)


def survey_date_of(rel_path: str) -> Optional[str]:
    """Survey date from the flight folder (the first folder below the site), if it names one."""
    parts = rel_path.split("/")
    flight = parts[3] if parts[1] == "Drone Flights" and len(parts) > 4 else None
    return parse_date(flight) if flight else None


def colony_of(name: str) -> Optional[str]:
    """Colony label from a layer name: 'Colony4', 'Colony_A', 'Rumney_A', 'Willow3_', '_C3'."""
    for pattern in [r"[Cc]olony[ _]?([A-H1-9])\b", r"[Cc]olony_?([A-H1-9])(?=_|$)", r"Rumney_?([A-H])(?=_|$)",
                    r"Willow([1-9])(?=_|$)", r"_C([1-9])(?=_|$)"]:
        m = re.search(pattern, name)
        if m:
            return m.group(1)
    return None


def feature_kind_of(name: str) -> Optional[str]:
    low = name.lower()
    return next((kind for kind, pattern in FEATURE_KINDS if re.search(pattern, low)), None)


# ============================================================
# DRIVE SCAN
# ============================================================

def walk(root: Path) -> Iterable[os.DirEntry]:
    """All files below the season folders, skipping Metashape caches (``*.files``) and geodatabase internals."""
    stack = [root / folder for folder in SEASON_FOLDERS]
    while stack:
        with os.scandir(stack.pop()) as entries:
            for e in entries:
                if e.is_dir(follow_symlinks=False):
                    if not e.name.endswith((".files", ".gdb")):
                        stack.append(Path(e.path))
                else:
                    yield e


def find_geodatabases(root: Path) -> List[Path]:
    found = []
    for folder in SEASON_FOLDERS:
        for dirpath, dirnames, _ in os.walk(root / folder):
            dirnames[:] = [d for d in dirnames if not d.endswith(".files")]
            found += [Path(dirpath) / d for d in dirnames if d.endswith(".gdb")]
            dirnames[:] = [d for d in dirnames if not d.endswith(".gdb")]
    return sorted(found)


# ============================================================
# RAW PHOTOS
# ============================================================

def _dms(value, ref) -> float:
    deg = float(value[0]) + float(value[1]) / 60 + float(value[2]) / 3600
    return -deg if ref in ("S", "W") else deg


def read_photo(path: str) -> Dict[str, object]:
    """Camera model, capture time, GPS and size from EXIF (reads only the file header)."""
    try:
        with Image.open(path) as im:
            exif = im._getexif() or {}
            width, height = im.size
    except Exception as e:  # unreadable or not a JPEG
        return {"error": f"unreadable: {type(e).__name__}"}
    tags = {TAGS.get(k, k): v for k, v in exif.items()}
    gps = {GPSTAGS.get(k, k): v for k, v in (tags.get("GPSInfo") or {}).items()}
    out = {"camera": str(tags.get("Model", "")).strip("\x00 "), "width": width, "height": height}
    taken = tags.get("DateTimeOriginal")
    if taken:
        out["taken_at"] = str(taken).replace(":", "-", 2).replace(" ", "T")
    if "GPSLatitude" in gps and "GPSLongitude" in gps:
        out["lat"] = round(_dms(gps["GPSLatitude"], gps.get("GPSLatitudeRef", "N")), 7)
        out["lon"] = round(_dms(gps["GPSLongitude"], gps.get("GPSLongitudeRef", "E")), 7)
        if "GPSAltitude" in gps:
            out["alt_m"] = round(float(gps["GPSAltitude"]), 2)
    return out


def read_photos(jpgs: List[os.DirEntry], root: Path, cache: Optional[Path], workers: int) -> List[Dict[str, object]]:
    """EXIF of every JPEG, reusing ``cache`` (CSV keyed by path, size and mtime) for unchanged files."""
    cached = {}
    if cache and cache.exists():
        with open(cache, newline="") as f:
            for r in csv.DictReader(f):
                cached[(r.pop("source_path"), r.pop("bytes"), r.pop("mtime"))] = {k: v for k, v in r.items() if v != ""}
    keys = [(os.path.relpath(e.path, root).replace(os.sep, "/"), str(e.stat().st_size), str(int(e.stat().st_mtime))) for e in jpgs]
    todo = [i for i, k in enumerate(keys) if k not in cached]
    with ThreadPoolExecutor(workers) as pool:
        for i, info in zip(todo, pool.map(lambda i: read_photo(jpgs[i].path), todo)):
            cached[keys[i]] = info
    if cache:
        fields = ["camera", "taken_at", "lat", "lon", "alt_m", "width", "height", "error"]
        cache.parent.mkdir(parents=True, exist_ok=True)
        with open(cache, "w", newline="") as f:
            w = csv.DictWriter(f, ["source_path", "bytes", "mtime"] + fields)
            w.writeheader()
            for k in keys:
                w.writerow({"source_path": k[0], "bytes": k[1], "mtime": k[2], **cached[k]})
    return [cached[k] for k in keys]


def photo_rows(root: Path, files: List[os.DirEntry], workers: int = 4, cache: Optional[Path] = None) -> List[Dict[str, object]]:
    jpgs = [e for e in files if e.name.lower().endswith((".jpg", ".jpeg"))]
    infos = read_photos(jpgs, root, cache, workers)

    rows, seen = [], {}
    for e, info in zip(jpgs, infos):
        rel = os.path.relpath(e.path, root).replace(os.sep, "/")
        site = site_of(rel)
        folder_date = survey_date_of(rel)
        if info.get("camera") not in CAMERA_MODELS:
            # Frames extracted from 4K drone video (May 2018 surveys): no EXIF at all
            if not info.get("camera") and str(info.get("width")) == "3840" and str(info.get("height")) == "2160" and folder_date:
                rows.append({"role": "video_frame", "site": site, "survey_date": folder_date, "folder_date": folder_date,
                             "source_path": rel, "bytes": e.stat().st_size, "width": 3840, "height": 2160,
                             "include": False, "note": "video frame: no EXIF, no GPS"})
            continue  # screenshots, other cameras, thumbnails
        taken_date = (info.get("taken_at") or "")[:10] or None
        row = {"role": "raw_photo", "site": site, "survey_date": taken_date or folder_date, "folder_date": folder_date,
               "source_path": rel, "bytes": e.stat().st_size, **info}
        notes = []
        key = (info.get("taken_at"), row["bytes"])
        if key in seen:
            notes.append(f"duplicate of {seen[key]}")
        else:
            seen[key] = rel
        if site in NON_STUDY_SITES:
            notes.append(NON_STUDY_SITES[site])
        if taken_date and folder_date and taken_date != folder_date:
            notes.append(f"filed under folder date {folder_date}")
        if "lat" not in info:
            notes.append("no GPS")
        row["include"] = not any(n.startswith(("duplicate", "filming", "test", "no GPS")) for n in notes)
        row["note"] = "; ".join(notes)
        rows.append(row)
    return rows


# ============================================================
# REFERENCE ORTHOMOSAICS
# ============================================================

def ortho_rows(root: Path, files: List[os.DirEntry]) -> List[Dict[str, object]]:
    import rasterio  # imported here: only this step needs GDAL
    rows = []
    for e in files:
        if not e.name.lower().endswith((".tif", ".tiff")):
            continue
        rel = os.path.relpath(e.path, root).replace(os.sep, "/")
        row = {"role": "reference_ortho", "site": site_of(rel), "survey_date": survey_date_of(rel),
               "source_path": rel, "bytes": e.stat().st_size}
        notes = []
        try:
            with warnings.catch_warnings(), rasterio.open(e.path) as ds:
                warnings.simplefilter("ignore")
                row["bands"] = ds.count
                crs = ds.crs
                if crs is None:
                    notes.append("not georeferenced (world file only)")
                else:
                    row["crs"] = f"EPSG:{crs.to_epsg()}" if crs.to_epsg() else ("ESRI:102432 ARC zone 12" if "ARC_System" in crs.to_wkt() else crs.to_wkt()[:40])
                    if crs.is_geographic:
                        lat = (ds.bounds.top + ds.bounds.bottom) / 2
                        row["gsd_m"] = round(ds.res[0] * 111320 * math.cos(math.radians(lat)), 4)
                    else:
                        row["gsd_m"] = round(ds.res[0], 4)
                if ds.dtypes[0] != "uint8" or ds.count < 3:
                    notes.append(f"not an RGB orthomosaic ({ds.count} band {ds.dtypes[0]})")
        except Exception as ex:
            notes.append(f"unreadable: {str(ex)[:60]}")
        if "/SmallChunks/" in rel:
            notes.append("SmallChunks split copy")
        if row["site"] in NON_STUDY_SITES:
            notes.append(NON_STUDY_SITES[row["site"]])
        if row["survey_date"] is None:
            notes.append("no survey date in path")
        row["include"] = not notes
        row["note"] = "; ".join(notes)
        rows.append(row)
    return rows


# ============================================================
# ANNOTATIONS
# ============================================================

def annotation_rows(root: Path, files: List[os.DirEntry]) -> List[Dict[str, object]]:
    import pyogrio
    sources = [(g, None) for g in find_geodatabases(root)]
    sources += [(Path(e.path), None) for e in files if e.name.lower().endswith(".shp")]
    rows = []
    for src, _ in sources:
        rel = os.path.relpath(src, root).replace(os.sep, "/")
        base = {"role": "annotation", "site": site_of(rel), "source_path": rel,
                "bytes": sum(f.stat().st_size for f in os.scandir(src)) if src.is_dir() else src.stat().st_size}
        try:
            layers = pyogrio.list_layers(src)
        except Exception as ex:
            rows.append({**base, "include": False, "note": f"unreadable: {str(ex)[:60]}"})
            continue
        for name, geometry in layers:
            row = {**base, "layer": name, "geometry": geometry}
            notes = []
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    info = pyogrio.read_info(src, layer=name)
                row["n_features"] = info["features"]
                row["crs"] = str(info["crs"])[:60] if info["crs"] else ""
            except Exception as ex:
                notes.append(f"unreadable layer: {str(ex)[:60]}")
            label = f"{src.stem}/{name}"
            row["feature_kind"] = feature_kind_of(name) or feature_kind_of(label)   # layer-name prefixes first
            row["colony"] = colony_of(name)
            row["survey_date"] = parse_date(name, default_year=season_of(rel)) or survey_date_of(rel)
            if row.get("n_features") == 0:
                notes.append("empty layer")
            if row["feature_kind"] is None:
                notes.append("unknown feature kind")
            if row["site"] in NON_STUDY_SITES:
                notes.append(NON_STUDY_SITES[row["site"]])
            if row["survey_date"] is None and row["feature_kind"] != "colony_boundary":
                notes.append("no date in layer name")
            row["include"] = not any(n.startswith(("unreadable", "empty", "filming", "test")) for n in notes)
            row["note"] = "; ".join(notes)
            rows.append(row)
    return rows


# ============================================================
# MAIN
# ============================================================

def build_manifest(root: Path, out: Path, workers: int = 4) -> List[Dict[str, object]]:
    root = Path(root)
    files = list(walk(root))
    print(f"files scanned: {len(files)}")
    rows = annotation_rows(root, files)
    print(f"annotation layers: {len(rows)}")
    rows += ortho_rows(root, files)
    print(f"+ orthomosaics: {len(rows)}")
    rows += photo_rows(root, files, workers, cache=Path(out).with_name("exif_cache.csv"))
    print(f"+ photos and video frames: {len(rows)}")
    rows.sort(key=lambda r: (r["role"], r.get("site") or "", r.get("survey_date") or "", r["source_path"], r.get("layer") or ""))
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="") as f:
        writer = csv.DictWriter(f, COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"manifest written: {out} ({len(rows)} rows)")
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", required=True, help="drive root (folder containing '2018 Field Season')")
    parser.add_argument("--out", default="output/dataset/manifest.csv")
    parser.add_argument("--workers", type=int, default=4, help="threads reading photo EXIF")
    args = parser.parse_args()
    build_manifest(Path(args.root), Path(args.out), args.workers)
