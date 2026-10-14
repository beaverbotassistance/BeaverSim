#!/usr/bin/env python3
"""HydroShare download client: verified, resumable, read-only files, with the record saved as ``resource.json``.

HydroShare serves a resource's science metadata and its file list (with MD5s) from two endpoints;
both responses are saved, unchanged, in ``resource.json`` (see :mod:`data_acquisition.readers.hydroshare`).
A collection resource has no files of its own: its record is saved in its folder and each member
resource (its own DOI) is downloaded into its own folder. A HydroShare resource id names one
version (a new version is a new resource), so the DOI given is the version downloaded. Files are
served from cloud storage through redirects; temporary errors are retried with a growing wait, and
a partial ``.part`` file is resumed.

    python -m data_acquisition.sources.hydroshare --root "<drive>/open_datasets" \\
        --doi 10.4211/hs.7c4ae80863174acfb571ccf8bdac8968 --list
"""
import argparse
import datetime
import json
import os
import re
import stat
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from data_acquisition.readers import hydroshare
from data_acquisition.sources import dataset_folder
from data_acquisition.sources.dataone import file_hash, log

API = "https://www.hydroshare.org"
METADATA = API + "/hsapi2/resource/{id}/json/"
FILES = API + "/hsapi/resource/{id}/files/"
CHUNK = 8 * 1024 * 1024
WAITS = [10, 30, 60, 120, 300]            # seconds before each retry of a temporary error
TEMPORARY = (429, 500, 502, 503, 504)


def _retry(action: Callable[[], Any]) -> Any:
    """``action()``, retried after a growing wait on rate limits, server errors and dropped connections."""
    for wait in WAITS + [None]:
        try:
            return action()
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if wait is None or (isinstance(e, urllib.error.HTTPError) and e.code not in TEMPORARY):
                raise
            print(f"  {e}; retrying in {wait} s")
            time.sleep(wait)


def _get(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=120) as r:
        return r.read()


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
        raise ConnectionError(f"{dest.name}: got {part.stat().st_size} bytes, expected {size}")
    part.rename(dest)


def record_of(resource: str) -> (str, Dict[str, Any]):
    """The record (metadata and every page of the file list, as served) and its parsed form."""
    metadata_url = METADATA.format(id=resource)
    metadata = json.loads(_retry(lambda: _get(metadata_url)))
    files, page = [], FILES.format(id=resource)
    while page:
        d = json.loads(_retry(lambda: _get(page)))
        files += d["results"]
        page = d["next"]
    text = json.dumps({"metadata_url": metadata_url, "metadata": metadata,
                       "files_url": FILES.format(id=resource), "files": files}, indent=1)
    return text, hydroshare.read(text)


def _https(url: str) -> str:
    return re.sub(r"^http://", "https://", url)


def list_files(doi: str, name_filter: Optional[str] = None) -> None:
    _, record = record_of(hydroshare.resource_id(doi))
    print(f"  {record['package_id']}: {record['title']}\n  licence: {record['licence'] or record['rights']}")
    total = 0
    for part in record["parts"]:
        _, member = record_of(part)
        print(f"  member {member['package_id']}: {member['title']}\n  licence: {member['licence'] or member['rights']}")
        for name, e in member["entities"].items():
            if not name_filter or re.search(name_filter, name):
                total += e["size"] or 0
                print(f"  {(e['size'] or 0) / 1e9:9.3f} GB  {name}")
    for name, e in record["entities"].items():
        if not name_filter or re.search(name_filter, name):
            total += e["size"] or 0
            print(f"  {(e['size'] or 0) / 1e9:9.3f} GB  {name}")
    print(f"  {total / 1e9:9.3f} GB  total")


def download(root: Path, doi: str, name_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """Download the files of ``doi`` (and, for a collection, of every member); returns log rows."""
    resource = hydroshare.resource_id(doi)
    text, record = record_of(resource)
    # a published resource has a DOI; an unpublished one only its resource id (no DOI is made up for it)
    folder = dataset_folder(root, "hydroshare", record["package_id"] or f"hs:{resource}")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "resource.json").write_text(text)
    rows = []
    for part in record["parts"]:
        print(f"  member {part}")
        rows += download(root, f"hs:{part}", name_filter)
    for name, e in record["entities"].items():
        if name_filter and not re.search(name_filter, name):
            continue
        path = folder / name
        if not path.exists():
            print(f"  downloading {name} ({(e['size'] or 0) / 1e9:.2f} GB)")
            path.parent.mkdir(parents=True, exist_ok=True)
            _retry(lambda: _fetch(_https(e["url"]), path, e["size"]))
        algorithm, expected = e["checksum"] or ("", "")
        actual = file_hash(path, algorithm) if algorithm else ""
        if expected and actual != expected:
            raise IOError(f"{name}: {algorithm} mismatch")
        path.chmod(path.stat().st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
        print(f"  ok {name}")
        rows.append({"source": "hydroshare", "doi": record["package_id"], "file": name,
                     "path": os.path.relpath(path, root).replace(os.sep, "/"), "bytes": path.stat().st_size,
                     "checksum_algorithm": algorithm.upper(), "checksum": actual, "licence": record["licence"],
                     "dataset_title": record["title"], "downloaded": datetime.date.today().isoformat(),
                     "url": e["url"]})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", required=True, type=Path, help="data root (e.g. the open_datasets folder)")
    parser.add_argument("--doi", required=True, action="append")
    parser.add_argument("--filter", default=None, help="regex on file names")
    parser.add_argument("--list", action="store_true", help="only print the files and licence")
    args = parser.parse_args()
    for doi in args.doi:
        print(doi)
        if args.list:
            list_files(doi, args.filter)
        else:
            log(args.root / "downloads.csv", download(args.root, doi, args.filter))


if __name__ == "__main__":
    main()
