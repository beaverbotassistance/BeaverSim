#!/usr/bin/env python3
"""Download datasets from the NSF Arctic Data Center (DataONE API), verified and with provenance.

For each DOI the dataset metadata (EML) is saved as ``metadata.xml`` and every data file is
downloaded to ``<dest>/arcticdata/<doi>/``, resumed if interrupted, verified against the checksum
in DataONE's system metadata, and made read-only. One row per file is appended to
``<dest>/downloads.csv`` (source, DOI, licence, size, checksum, date).

    python -m data_acquisition.open_data.arcticdata --dest "/media/<user>/Seagate Portable Drive/open_datasets" \\
        --doi doi:10.18739/A2J09W600 --doi doi:10.18739/A22R3NZ98 --name "Swan_Lake_DLB"
"""
import argparse
import csv
import datetime
import hashlib
import os
import re
import stat
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

API = "https://arcticdata.io/metacat/d1/mn/v2"
CHUNK = 8 * 1024 * 1024
LOG_FIELDS = ["source", "doi", "file", "path", "bytes", "checksum_algorithm", "checksum", "licence",
              "dataset_title", "downloaded", "url"]


def _get(url: str, timeout: int = 120) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()


def _q(pid: str) -> str:
    return urllib.parse.quote(pid, safe="")


def dataset(doi: str) -> Dict[str, object]:
    """Title, licence, raw EML and data files (name, pid, size) of a dataset."""
    eml = _get(f"{API}/object/{_q(doi)}").decode("utf-8", "replace")
    title = re.search(r"<title>(.*?)</title>", eml, re.S)
    licence = ("CC0-1.0" if "publicdomain/zero" in eml else "CC-BY-4.0" if "licenses/by/4.0" in eml else "unknown")
    files = []
    for kind, body in re.findall(r"<(otherEntity|dataTable|spatialRaster|spatialVector)[ >](.*?)</\1>", eml, re.S):
        name = re.search(r"<entityName>(.*?)</entityName>", body)
        url = re.search(r"<url[^>]*>([^<]+)</url>", body)
        size = re.search(r"<size[^>]*>(\d+)</size>", body)
        if name and url:
            pid = urllib.parse.unquote(url.group(1).rsplit("/resolve/", 1)[-1].rsplit("/object/", 1)[-1])
            files.append({"name": name.group(1).strip(), "pid": pid, "size": int(size.group(1)) if size else None})
    return {"title": re.sub(r"\s+", " ", title.group(1)).strip() if title else "", "licence": licence,
            "eml": eml, "files": files}


def checksum(pid: str) -> (str, str):
    """Checksum algorithm and value from DataONE system metadata."""
    meta = _get(f"{API}/meta/{_q(pid)}").decode("utf-8", "replace")
    m = re.search(r'<checksum algorithm="([^"]+)">([^<]+)</checksum>', meta)
    return (m.group(1), m.group(2).strip()) if m else ("", "")


def _hash(path: Path, algorithm: str) -> str:
    h = hashlib.new(algorithm.replace("-", "").lower())
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def download(pid: str, dest: Path, size: Optional[int]) -> None:
    """Stream ``pid`` to ``dest``, resuming a partial ``.part`` file."""
    part = dest.with_name(dest.name + ".part")
    have = part.stat().st_size if part.exists() else 0
    req = urllib.request.Request(f"{API}/object/{_q(pid)}")
    if have:
        req.add_header("Range", f"bytes={have}-")
    with urllib.request.urlopen(req, timeout=300) as r:
        mode = "ab" if have and r.status == 206 else "wb"
        with open(part, mode) as f:
            for block in iter(lambda: r.read(CHUNK), b""):
                f.write(block)
    if size is not None and part.stat().st_size != size:
        raise IOError(f"{dest.name}: got {part.stat().st_size} bytes, expected {size}")
    part.rename(dest)


def fetch(doi: str, dest_root: Path, name_filter: Optional[str] = None) -> List[Dict[str, object]]:
    """Download (and verify) every file of ``doi`` whose name matches ``name_filter``."""
    ds = dataset(doi)
    folder = dest_root / "arcticdata" / re.sub(r"[^A-Za-z0-9._-]+", "_", doi)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "metadata.xml").write_text(ds["eml"])
    rows = []
    for f in ds["files"]:
        if name_filter and not re.search(name_filter, f["name"]):
            continue
        path = folder / f["name"]
        algorithm, expected = checksum(f["pid"])
        if not path.exists():
            print(f"  downloading {f['name']} ({(f['size'] or 0) / 1e9:.2f} GB)")
            download(f["pid"], path, f["size"])
        actual = _hash(path, algorithm) if algorithm else ""
        if expected and actual != expected:
            raise IOError(f"{f['name']}: {algorithm} mismatch")
        path.chmod(path.stat().st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
        print(f"  ok {f['name']} ({algorithm} verified)")
        rows.append({"source": "arcticdata", "doi": doi, "file": f["name"],
                     "path": os.path.relpath(path, dest_root).replace(os.sep, "/"), "bytes": path.stat().st_size,
                     "checksum_algorithm": algorithm, "checksum": actual, "licence": ds["licence"],
                     "dataset_title": ds["title"], "downloaded": datetime.date.today().isoformat(),
                     "url": f"{API}/object/{_q(f['pid'])}"})
    return rows


def log(dest_root: Path, rows: List[Dict[str, object]]) -> None:
    """Append rows to downloads.csv, replacing earlier rows for the same file."""
    path = dest_root / "downloads.csv"
    old = list(csv.DictReader(open(path, newline=""))) if path.exists() else []
    keep = [r for r in old if r["path"] not in {x["path"] for x in rows}]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, LOG_FIELDS)
        w.writeheader()
        w.writerows(keep + rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dest", required=True, help="open_datasets root folder")
    parser.add_argument("--doi", action="append", required=True)
    parser.add_argument("--name", default=None, help="regex on file names (e.g. one site of a multi-site dataset)")
    args = parser.parse_args()
    dest = Path(args.dest)
    for doi in args.doi:
        print(doi)
        log(dest, fetch(doi, dest, args.name))
