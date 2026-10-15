"""Photo reader: a folder of drone photos (JPEG with EXIF), read as one survey.

Reads only the EXIF of each photo: camera model, capture time and GPS position. Returns the count,
the cameras, the capture time span and the positions, from which the builder makes the footprint.
Photos in subfolders (one per camera folder, e.g. ``100MEDIA``) are included.
"""
import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import ExifTags, Image

EXTENSIONS = (".jpg", ".jpeg")


def is_photo_folder(path: Path) -> bool:
    return path.is_dir() and any(p.suffix.lower() in EXTENSIONS for p in path.rglob("*"))


def _degrees(dms: Tuple[float, float, float], ref: str) -> float:
    value = float(dms[0]) + float(dms[1]) / 60 + float(dms[2]) / 3600
    return -value if ref in ("S", "W") else value


def exif(path: Path) -> Dict[str, Any]:
    """Camera model, capture time (``datetime``, naive: the camera's clock) and lon/lat/altitude of a photo."""
    with Image.open(path) as im:
        tags = im.getexif()
        taken = tags.get_ifd(ExifTags.IFD.Exif).get(ExifTags.Base.DateTimeOriginal)
        gps = tags.get_ifd(ExifTags.IFD.GPSInfo)
    model = tags.get(ExifTags.Base.Model)
    out: Dict[str, Any] = {"camera": model.strip("\x00 ") if model else None,     # DJI pads it with NULs
                           "taken": datetime.datetime.strptime(taken, "%Y:%m:%d %H:%M:%S") if taken else None,
                           "lon": None, "lat": None, "alt": None}
    if gps.get(ExifTags.GPS.GPSLatitude) and gps.get(ExifTags.GPS.GPSLongitude):
        out["lat"] = _degrees(gps[ExifTags.GPS.GPSLatitude], gps.get(ExifTags.GPS.GPSLatitudeRef, "N"))
        out["lon"] = _degrees(gps[ExifTags.GPS.GPSLongitude], gps.get(ExifTags.GPS.GPSLongitudeRef, "E"))
        if gps.get(ExifTags.GPS.GPSAltitude) is not None:
            out["alt"] = float(gps[ExifTags.GPS.GPSAltitude])
    return out


def info(folder: Path) -> Dict[str, Any]:
    """Photos under ``folder``: count, bytes, cameras, first and last capture time, positions (lon, lat), and
    the photos whose EXIF could not be read or has no position."""
    photos = sorted(p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in EXTENSIONS)
    cameras: Dict[str, int] = {}
    times: List[datetime.datetime] = []
    positions: List[Tuple[float, float]] = []
    unreadable, no_position = [], []
    for p in photos:
        try:
            e = exif(p)
        except Exception:       # PIL raises many error types for broken JPEGs
            unreadable.append(p.relative_to(folder).as_posix())
            continue
        if e["camera"]:
            cameras[e["camera"]] = cameras.get(e["camera"], 0) + 1
        if e["taken"]:
            times.append(e["taken"])
        if e["lon"] is None:
            no_position.append(p.relative_to(folder).as_posix())
        else:
            positions.append((e["lon"], e["lat"]))
    first: Optional[datetime.datetime] = min(times) if times else None
    last: Optional[datetime.datetime] = max(times) if times else None
    return {"count": len(photos), "bytes": sum(p.stat().st_size for p in photos), "cameras": cameras,
            "first": first, "last": last, "positions": positions, "unreadable": unreadable,
            "no_position": no_position}
