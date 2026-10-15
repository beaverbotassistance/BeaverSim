"""Evidence for drafting a dataset summary: what code can read for sure from the files of a dataset.

For each file of each folder: its size, and by type the raster header (driver, CRS, resolution, bands,
nodata, lon/lat box), the vector layers (CRS, geometry types, fields, a few sample rows), the metadata
record (title, licence, creators, dates, methods text, entities), or the text of small text files and of
the first pages of PDF reports. Companions of a file (raster sidecars, shapefile parts) are left out; a
File Geodatabase folder is one entry, and so is a folder of photos (count, size, camera and capture time
of its first and last photo). A file that cannot be read is listed with its error.
"""
import datetime
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import ExifTags, Image
from pypdf import PdfReader
from pyproj import CRS

from data_acquisition.catalog import stac
from data_acquisition.readers import RECORD_FILES, RECORDS, files, geotiff, vector

METHODS_CHARS = 6000        # methods text kept per record (the rest is boilerplate)
TEXT_EXTENSIONS = (".txt", ".md", ".csv", ".r", ".py", ".json", ".yaml", ".yml")
TEXT_BYTES = 8000           # small text files (READMEs, settings, GCP lists) are included up to this size
PDF_PAGES, PDF_CHARS = 8, 15000   # processing reports: the first pages hold the summary (camera, dates, GCP errors)
VECTOR_SAMPLE_ROWS = 3
PHOTOS = (".jpg", ".jpeg")
PHOTO_FOLDER = 10           # a folder with at least this many photos is one evidence entry


def _lonlat(bbox: Optional[List[float]]) -> Optional[List[float]]:
    return [round(v, 5) for v in bbox] if bbox else None


def _raster(path: Path) -> Dict[str, Any]:
    h = geotiff.info(path)
    bbox = stac.footprint(h)[1] if h["has_crs"] else None     # no footprint without a CRS
    return {"driver": h["driver"], "has_crs": h["has_crs"], "epsg": h["epsg"],
            "crs_name": CRS.from_user_input(h["crs"]).name if h["crs"] else None,
            "resolution_m": [round(r, 4) for r in h["resolution"]], "bands": h["count"],
            "dtypes": sorted(set(h["dtypes"])), "colorinterp": h["colorinterp"], "nodata": h["nodata"],
            "lonlat_bbox": _lonlat(bbox), "overviews": bool(h["overviews"])}


def _vector(path: Path) -> Dict[str, Any]:
    v = vector.info(path, sample_rows=VECTOR_SAMPLE_ROWS)
    bbox = stac.lonlat_box(v["bounds"], v["crs"])[1] if v["bounds"] and v["crs"] else None
    return {"epsg": v["epsg"], "crs_name": CRS.from_user_input(v["crs"]).name if v["crs"] else None,
            "vertical_crs": v["vertical_crs"], "lonlat_bbox": _lonlat(bbox), "features": v["features"],
            "layers": [{k: l.get(k) for k in ("name", "geometry_type", "features", "fields", "sample")}
                       for l in v["layers"]]}


def _record(path: Path, fmt: str) -> Dict[str, Any]:
    """The record's fields; of its entities, only the downloaded ones are described (the rest are counted)."""
    r = RECORDS[fmt]["read"](path.read_text())
    here = {name: e for name, e in r["entities"].items() if (path.parent / name).exists()}
    return {"format": fmt, "package_id": r["package_id"], "title": r["title"], "licence": r["licence"],
            "creators": r["creators"], "dates": r["dates"], "bounds": r["bounds"],
            "methods": r["methods"][:METHODS_CHARS],
            "entities": {name: {"size": e["size"], "attributes": e["attributes"], "media_type": e.get("media_type")}
                         for name, e in here.items()},
            "entities_not_downloaded": len(r["entities"]) - len(here)}


def _pdf_text(path: Path) -> Tuple[str, bool]:
    """Text of the first pages of a PDF (whitespace collapsed); True if pages or characters were cut."""
    reader = PdfReader(path)
    text = "\n".join(re.sub(r"[ \t]+", " ", page.extract_text() or "") for page in reader.pages[:PDF_PAGES])
    return text[:PDF_CHARS], len(reader.pages) > PDF_PAGES or len(text) > PDF_CHARS


def _text(path: Path) -> Tuple[str, bool]:
    """The first ``TEXT_BYTES`` of a text file; True if it was cut."""
    with open(path, "rb") as f:
        head = f.read(TEXT_BYTES)
    return head.decode("utf-8", "replace"), path.stat().st_size > TEXT_BYTES


def entries(folder: Path) -> List[Path]:
    """Files under ``folder`` (recursively), each File Geodatabase folder as one entry, companions left out."""
    out = []
    for p in sorted(folder.rglob("*")):
        if files.inside_container(p.relative_to(folder).as_posix()):
            continue
        if p.is_dir() and p.suffix.lower() in files.CONTAINERS:
            out.append(p)
        elif p.is_file() and not p.name.endswith(".part") and not files.is_companion(p):
            out.append(p)
    return out


def _exif(path: Path) -> Dict[str, Any]:
    """Camera model and capture time of a photo, from its EXIF."""
    with Image.open(path) as im:
        exif = im.getexif()
        taken = exif.get_ifd(ExifTags.IFD.Exif).get(ExifTags.Base.DateTimeOriginal)
        return {"camera": exif.get(ExifTags.Base.Model), "taken": taken}


def _photo_folder(folder: Path, photos: List[Path]) -> Dict[str, Any]:
    """One evidence entry for a folder of photos: count, size, and the first and last photo's EXIF."""
    entry: Dict[str, Any] = {"photos": len(photos), "bytes": sum(p.stat().st_size for p in photos)}
    try:
        entry["first"] = {"name": photos[0].name, **_exif(photos[0])}
        entry["last"] = {"name": photos[-1].name, **_exif(photos[-1])}
    except Exception as e:      # PIL raises many error types; an unreadable photo is evidence too
        entry["error"] = f"{type(e).__name__}: {e}"
    return entry


def _folder_files(folder: Path) -> List[Dict[str, Any]]:
    """The evidence entries of one folder: each file, except folders of photos, which are one entry each."""
    found = entries(folder)
    by_dir: Dict[Path, List[Path]] = {}
    for p in found:
        if p.suffix.lower() in PHOTOS:
            by_dir.setdefault(p.parent, []).append(p)
    grouped = {d for d, photos in by_dir.items() if len(photos) >= PHOTO_FOLDER}
    out = [{"name": p.relative_to(folder).as_posix(), "bytes": stac.size_of(p), **describe_file(p)}
           for p in found if not (p.suffix.lower() in PHOTOS and p.parent in grouped)]
    out += [{"name": d.relative_to(folder).as_posix() + "/", **_photo_folder(d, by_dir[d])} for d in sorted(grouped)]
    return sorted(out, key=lambda e: e["name"])


def describe_file(path: Path) -> Dict[str, Any]:
    """What can be read of one file (keys ``raster``, ``vector``, ``record`` or ``text``), or its ``error``."""
    entry: Dict[str, Any] = {}
    try:
        if geotiff.is_raster(path):
            entry["raster"] = _raster(path)
        elif vector.is_vector(path):
            entry["vector"] = _vector(path)
        elif path.name in RECORD_FILES:
            entry["record"] = _record(path, RECORD_FILES[path.name])
        elif path.suffix.lower() == ".pdf":
            entry["text"], entry["text_truncated"] = _pdf_text(path)
        elif path.suffix.lower() in TEXT_EXTENSIONS:
            entry["text"], entry["text_truncated"] = _text(path)
    except Exception as e:  # readers raise many error types; an unreadable file is evidence too
        entry["error"] = f"{type(e).__name__}: {e}"
    return entry


def gather(root: Path, patterns: List[str]) -> Dict[str, Any]:
    """Evidence for every folder matching ``patterns`` (globs relative to ``root``), subfolders included."""
    folders = sorted({p for pattern in patterns for p in root.glob(pattern) if p.is_dir()})
    return {"root": str(root), "gathered": datetime.date.today().isoformat(),
            "folders": [{"folder": os.path.relpath(folder, root).replace(os.sep, "/"), "files": _folder_files(folder)}
                        for folder in folders]}
