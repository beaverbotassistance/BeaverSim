#!/usr/bin/env python3
"""HydroShare download client: verified, resumable, read-only files, with the record saved as ``resource.json``.

HydroShare serves a resource's science metadata and its file list (with MD5s) from two endpoints;
both responses are saved, unchanged, in ``resource.json`` (see :mod:`data_acquisition.readers.hydroshare`).
A collection resource has no files of its own: its record is saved in its folder and each member
resource (its own DOI) is downloaded into its own folder. A HydroShare resource id names one
version (a new version is a new resource), so the DOI given is the version downloaded. Checksums: the record's when it can be
checked (plain MD5, or an S3 multipart ETag of known part size), else the MD5 the cloud storage states
when serving the file; the download log says which. Files are
served from cloud storage through redirects; temporary errors are retried with a growing wait, and
a partial ``.part`` file is resumed.

    python -m data_acquisition.sources.hydroshare --root "<drive>/open_datasets" \\
        --doi 10.4211/hs.7c4ae80863174acfb571ccf8bdac8968 --list
"""
import argparse
import base64
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
from data_acquisition.sources import checksums, dataset_folder
from data_acquisition.sources.dataone import log

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


def storage_md5(headers) -> Optional[str]:
    """The whole file's MD5 as the storage serving it states it (``x-goog-hash: md5=``, ``Content-MD5``, or a
    plain ETag), or None. These describe the stored object even when a byte range was requested."""
    for value in headers.get_all("x-goog-hash") or []:
        if value.strip().lower().startswith("md5="):
            return base64.b64decode(value.split("=", 1)[1].strip()).hex()
    if headers.get("Content-MD5"):
        return base64.b64decode(headers["Content-MD5"]).hex()
    etag = (headers.get("ETag") or "").strip('"').lower()
    return etag if re.fullmatch(r"[0-9a-f]{32}", etag) else None


def _stored_md5(url: str) -> Optional[str]:
    """Ask the storage for a file's MD5 with a one-byte request (headers only matter)."""
    req = urllib.request.Request(url, headers={"Range": "bytes=0-0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return storage_md5(r.headers)


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
        verdict = checksums.check(path, algorithm, expected) if expected else None
        if verdict is False:
            raise IOError(f"{name}: {algorithm} {expected} mismatch")
        if verdict:
            verified_by = f"record {checksums.parse(algorithm, expected)[0]}"
        else:
            # no record checksum, or a multipart ETag whose part size is unknown: check the storage's own MD5
            stored = _retry(lambda: _stored_md5(_https(e["url"])))
            if not stored:
                raise IOError(f"{name}: the record checksum cannot be checked and the storage states no MD5")
            if checksums.digest(path, "md5") != stored:
                raise IOError(f"{name}: differs from the MD5 the storage states")
            verified_by = "storage md5" + (f" (record {expected} not checkable)" if expected else "")
        actual = checksums.digest(path, "md5")
        path.chmod(path.stat().st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
        print(f"  ok {name} ({verified_by})")
        rows.append({"source": "hydroshare", "doi": record["package_id"], "file": name,
                     "path": os.path.relpath(path, root).replace(os.sep, "/"), "bytes": path.stat().st_size,
                     "checksum_algorithm": "MD5", "checksum": actual, "verified_by": verified_by,
                     "licence": record["licence"],
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
