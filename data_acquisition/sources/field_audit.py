#!/usr/bin/env python3
"""Find drone photos that the original Metashape projects used but that are no longer on the drive.

Each Metashape project (``<name>.files/<chunk>/<frame>/frame.zip``) lists the photos it was built
from. Paths are resolved relative to the project; Windows absolute paths and moved folders are
matched by file name + EXIF capture time (stored by Metashape) against the inventory's EXIF cache;
photos without capture time (video frames) are matched by '<parent folder>/<file name>' within the same
survey folder. The drive is only read.

Usage:
    python -m data_acquisition.sources.field_audit --root "/media/<user>/Seagate Portable Drive" \\
        --out output/dataset/missing_photos.csv
"""
import argparse
import collections
import csv
import os
import re
import zipfile
from pathlib import Path, PureWindowsPath
from typing import Dict, List, Set, Tuple

from data_acquisition.sources.field_inventory import SEASON_FOLDERS, site_of, survey_date_of


def _key(path: str) -> Tuple[str, str]:
    """'<parent folder>/<file name>' in lower case, independent of OS and absolute prefixes."""
    p = PureWindowsPath(path.replace("/", "\\"))
    return p.parent.name.lower(), p.name.lower()


def project_photos(root: Path) -> List[Dict[str, str]]:
    """One row per (project, photo) listed in any Metashape frame.zip on the drive."""
    rows = []
    for folder in SEASON_FOLDERS:
        for dirpath, dirnames, filenames in os.walk(root / folder):
            if "frame.zip" in filenames and ".files" in dirpath:
                z = Path(dirpath) / "frame.zip"
                project = dirpath.split(".files")[0] + ".files"
                try:
                    with zipfile.ZipFile(z) as f:
                        xml = f.read("doc.xml").decode("utf-8", "replace")
                except Exception as e:
                    rows.append({"project": project, "listed_path": "",
                                 "error": f"unreadable frame.zip: {type(e).__name__}"})
                    continue
                for block in xml.split("<camera ")[1:]:
                    path = re.search(r'<photo path="([^"]+)"', block)
                    if not path:
                        continue
                    taken = re.search(r'name="Exif/DateTimeOriginal" value="([^"]+)"', block)
                    rows.append({"project": project, "frame_dir": dirpath, "listed_path": path.group(1),
                                 "taken_at": taken.group(1).replace(":", "-", 2).replace(" ", "T") if taken else ""})
            if dirpath.endswith(".files"):
                dirnames[:] = [d for d in dirnames if d.isdigit() or d in ("0",)] or dirnames
    return rows


def find_missing(root: Path, exif_cache: Path) -> List[Dict[str, object]]:
    root = Path(root)
    # Photos on the drive: (file name, capture time) -> path, from the inventory's EXIF cache
    by_name_time: Dict[Tuple[str, str], str] = {}
    with open(exif_cache, newline="") as f:
        for r in csv.DictReader(f):
            if r["taken_at"]:
                by_name_time[(Path(r["source_path"]).name.lower(), r["taken_at"])] = r["source_path"]
    # Photos without capture time (video frames): unique names like 'Willow_05May2018_Leg1 001.jpg', per site
    by_site_name: Dict[str, Set[str]] = collections.defaultdict(set)
    with open(exif_cache, newline="") as f:
        for r in csv.DictReader(f):
            by_site_name[site_of(r["source_path"])].add(Path(r["source_path"]).name.lower())

    out, seen = [], set()
    for row in project_photos(root):
        rel_project = os.path.relpath(row["project"], root).replace(os.sep, "/")
        site, survey = site_of(rel_project), survey_date_of(rel_project + "/x")
        if row.get("error"):
            out.append({"site": site, "survey_folder_date": survey, "project": rel_project, "photo": "",
                        "status": "project unreadable", "detail": row["error"]})
            continue
        listed = row["listed_path"]
        if (rel_project, listed) in seen:
            continue                                   # same photo listed by several frames/chunks
        seen.add((rel_project, listed))
        resolved = (Path(row["frame_dir"]) / listed).resolve() if not re.match(r"^[A-Za-z]:|^\\\\", listed) else None
        name = _key(listed)[1]
        if row["taken_at"]:
            found = by_name_time.get((name, row["taken_at"]))
            status = "present" if found and resolved is not None and str(resolved).endswith(found) else (
                "present (moved)" if found else "missing")
        elif resolved is not None and resolved.exists():
            status = "present"
        else:
            # Plain camera names (DJI_0123.JPG) repeat in every survey, so they can't be matched by name alone
            unique_name = not re.fullmatch(r"dji_\d{4}\.jpe?g", name)
            status = "present (moved)" if unique_name and name in by_site_name[site] else "missing"
        out.append({"site": site, "survey_folder_date": survey, "project": rel_project,
                    "photo": "/".join(_key(listed)), "taken_at": row["taken_at"], "status": status, "detail": listed})
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", required=True)
    parser.add_argument("--out", default="output/dataset/missing_photos.csv")
    parser.add_argument("--exif-cache", default="output/dataset/exif_cache.csv", help="written by field_inventory")
    args = parser.parse_args()
    rows = find_missing(Path(args.root), Path(args.exif_cache))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, ["site", "survey_folder_date", "project", "photo", "taken_at", "status", "detail"])
        w.writeheader()
        w.writerows(rows)
    counts = collections.Counter((r["site"], r["survey_folder_date"], r["status"]) for r in rows)
    for k in sorted(counts, key=lambda k: tuple(str(x) for x in k)):
        print(f"{str(k[0]):16s} {str(k[1]):11s} {k[2]:20s} {counts[k]:6d}")
    print(f"written: {args.out}")
