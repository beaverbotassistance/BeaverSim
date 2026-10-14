#!/usr/bin/env python3
"""DataONE download client (Arctic Data Center, KNB, …): verified, resumable, read-only files.

For every group of a summary file with a ``doi``: saves the EML record as ``<folder>/metadata.xml``,
downloads the data files (optionally only those matching ``download_filter``), verifies them
against the checksum in the EML, makes them read-only, and logs one row per file to
``<root>/<source.log>``.

    python -m data_acquisition.sources.dataone --root "<drive>/open_datasets" --summary arcticdata_seward
    python -m data_acquisition.sources.dataone --root "<drive>/open_datasets" --doi doi:10.18739/A22R3NZ98 --list
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
from typing import Any, Dict, List, Optional

from data_acquisition.catalog import summary as summaries
from data_acquisition.readers import eml
from data_acquisition.sources import dataset_folder

CHUNK = 8 * 1024 * 1024
# DataONE coordinating node: serves objects of every member repository; used when a summary names no
# member-node API (a member node is closer to the data and supports resumed downloads)
COORDINATING_NODE = "https://cn.dataone.org/cn/v2"
LOG_FIELDS = ["source", "doi", "file", "path", "bytes", "checksum_algorithm", "checksum", "licence",
              "dataset_title", "downloaded", "url", "verified_by"]     # verified_by: which checksum the file matched


def _get(url: str, timeout: int = 120) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()


def file_hash(path: Path, algorithm: str) -> str:
    h = hashlib.new(algorithm)
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def _fetch(url: str, dest: Path, size: Optional[int]) -> None:
    """Stream ``url`` to ``dest``, resuming a partial ``.part`` file."""
    part = dest.with_name(dest.name + ".part")
    have = part.stat().st_size if part.exists() else 0
    req = urllib.request.Request(url)
    if have:
        req.add_header("Range", f"bytes={have}-")
    with urllib.request.urlopen(req, timeout=300) as r, open(part, "ab" if have and r.status == 206 else "wb") as f:
        for block in iter(lambda: r.read(CHUNK), b""):
            f.write(block)
    if size is not None and part.stat().st_size != size:
        raise IOError(f"{dest.name}: got {part.stat().st_size} bytes, expected {size}")
    part.rename(dest)


def download(api: str, root: Path, folder: str, doi: str, name_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """Download the files of ``doi`` into ``root/folder``; returns log rows."""
    xml = _get(f"{api}/object/{urllib.parse.quote(doi, safe='')}").decode("utf-8", "replace")
    record = eml.read(xml)
    target = root / folder
    target.mkdir(parents=True, exist_ok=True)
    (target / "metadata.xml").write_text(xml)
    rows = []
    for name, e in record["entities"].items():
        if name_filter and not re.search(name_filter, name):
            continue
        path = target / name
        if not path.exists():
            print(f"  downloading {name} ({(e['size'] or 0) / 1e9:.2f} GB)")
            _fetch(f"{api}/object/{urllib.parse.quote(e['pid'], safe='')}", path, e["size"])
        algorithm, expected = e["checksum"] or ("", "")
        actual = file_hash(path, algorithm) if algorithm else ""
        if expected and actual != expected:
            raise IOError(f"{name}: {algorithm} mismatch")
        path.chmod(path.stat().st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
        print(f"  ok {name}")
        rows.append({"source": "dataone", "doi": doi, "file": name,
                     "path": os.path.relpath(path, root).replace(os.sep, "/"), "bytes": path.stat().st_size,
                     "checksum_algorithm": algorithm.upper(), "checksum": actual, "licence": record["licence"],
                     "dataset_title": record["title"], "downloaded": datetime.date.today().isoformat(),
                     "url": e["url"]})
    return rows


def log(path: Path, rows: List[Dict[str, Any]]) -> None:
    """Merge rows into the download log (one row per file path)."""
    old = list(csv.DictReader(open(path, newline=""))) if path.exists() else []
    keep = [r for r in old if r["path"] not in {x["path"] for x in rows}]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, LOG_FIELDS, restval="")       # older rows have no verified_by
        w.writeheader()
        w.writerows(keep + rows)


def read_log(path: Path) -> Dict[str, Dict[str, str]]:
    """Download log rows keyed by file path relative to the data root."""
    return {r["path"]: r for r in csv.DictReader(open(path, newline=""))} if path.exists() else {}


def list_files(api: str, doi: str, name_filter: Optional[str] = None) -> None:
    record = eml.read(_get(f"{api}/object/{urllib.parse.quote(doi, safe='')}").decode("utf-8", "replace"))
    print(f"  {record['title']}\n  licence: {record['licence'] or record['rights'][:80]}")
    total = 0
    for name, e in record["entities"].items():
        if not name_filter or re.search(name_filter, name):
            total += e["size"] or 0
            print(f"  {(e['size'] or 0) / 1e9:9.3f} GB  {name}")
    print(f"  {total / 1e9:9.3f} GB  total")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", required=True, type=Path, help="data root (e.g. the open_datasets folder)")
    parser.add_argument("--summary", help="download every group of this summary (name or YAML path)")
    parser.add_argument("--doi", action="append", help="or: these DOIs, into <root>/<repository>/doi_<doi>/")
    parser.add_argument("--filter", default=None, help="regex on file names (with --doi)")
    parser.add_argument("--list", action="store_true", help="only print the files and licence (with --doi)")
    parser.add_argument("--repository", default="arcticdata", help="folder name of the member repository")
    parser.add_argument("--api", default=COORDINATING_NODE, help="DataONE API base (member or coordinating node)")
    args = parser.parse_args()
    if args.doi:
        for doi in args.doi:
            print(doi)
            if args.list:
                list_files(args.api, doi, args.filter)
            else:
                folder = dataset_folder(args.root, args.repository, doi)
                log(args.root / "downloads.csv",
                    download(args.api, args.root, os.path.relpath(folder, args.root), doi, args.filter))
        return
    if not args.summary:
        parser.error("give --summary or --doi")
    s = summaries.load(args.summary)
    if s["source"]["kind"] != "dataone":
        raise SystemExit(f"source kind is {s['source']['kind']!r}, not dataone")
    for g in s["groups"]:
        if g.get("doi"):
            print(g["doi"])
            log(args.root / s["source"]["log"],
                download(s["source"].get("api", COORDINATING_NODE), args.root, g["folder"], g["doi"],
                         g.get("download_filter")))


if __name__ == "__main__":
    main()
