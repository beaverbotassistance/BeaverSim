#!/usr/bin/env python3
"""CKAN download client (Open Government portals: open.canada.ca, data.ontario.ca, …): verified, resumable,
read-only files, with the record saved as ``package.json``.

A CKAN package has no DOI and no versions: it is named by its own id (the folder is ``id_<id>``) and the
version downloaded is the record's ``metadata_modified``, which is logged. Resources that are web pages
or services are skipped (see :mod:`data_acquisition.readers.ckan`); the files may be served by the
publisher's own servers, which the record links to. Checksums: the record's ``hash`` when it gives one,
else the MD5 the server states when serving the file (``Content-MD5``, ``x-goog-hash`` or a plain ETag).
A file with neither is refused, unless ``--no-md5-ok`` is given: then it is accepted only if its size is
the one the server states and, for a zip, every member matches its CRC-32; the download log says which.
Zip archives are extracted next to themselves (:mod:`data_acquisition.sources.archives`). Temporary
errors are retried with a growing wait, and a partial ``.part`` file is resumed.

    python -m data_acquisition.sources.ckan --root "<drive>/open_datasets" \\
        --doi b44984f7-9ba6-45aa-b25b-a6dc596afea5 --list
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
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from data_acquisition.readers import ckan
from data_acquisition.sources import archives, checksums, dataset_folder
from data_acquisition.sources.dataone import log
from data_acquisition.sources.hydroshare import storage_md5

API = "https://open.canada.ca/data/api/3/action"
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


def package_id(text: str) -> str:
    """The package id or name in a CKAN dataset link (``…/dataset/<id>``), or the text itself."""
    m = re.search(r"/dataset/([^/?#]+)", text)
    return m.group(1) if m else text.strip()


def _served(url: str) -> Tuple[Optional[str], Optional[int]]:
    """The MD5 and size the server states for a file, from a HEAD request (Azure blob storage states the
    MD5 only for whole-file requests, not for byte ranges)."""
    with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=120) as r:
        azure = r.headers.get("x-ms-blob-content-md5")
        md5 = base64.b64decode(azure).hex() if azure else storage_md5(r.headers)
        return md5, int(r.headers["Content-Length"]) if r.headers.get("Content-Length") else None


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


def record_of(api: str, package: str) -> (str, Dict[str, Any]):
    """The record (the ``package_show`` response, as served, labelled with its URL) and its parsed form."""
    url = f"{api}/package_show?id={urllib.parse.quote(package_id(package))}"
    text = json.dumps({"package_url": url, "package": json.loads(_retry(lambda: _get(url)))}, indent=1)
    return text, ckan.read(text)


def list_files(api: str, package: str, name_filter: Optional[str] = None) -> None:
    _, record = record_of(api, package)
    print(f"  {record['package_id']}: {record['title']} (modified {record['version']})\n"
          f"  licence: {record['licence'] or record['rights']}")
    total = 0
    for name, e in record["entities"].items():
        if not name_filter or re.search(name_filter, name):
            md5, size = _retry(lambda: _served(e["url"]))
            size = e["size"] or size or 0
            total += size
            checksum = "record " + e["checksum"][0] if e["checksum"] else "served md5" if md5 else "no md5"
            print(f"  {size / 1e9:9.3f} GB  {name}  ({checksum}; {e['url']})")
    print(f"  {total / 1e9:9.3f} GB  total")


def download(api: str, root: Path, repository: str, package: str, name_filter: Optional[str] = None,
             no_md5_ok: bool = False) -> List[Dict[str, Any]]:
    """Download the files of ``package`` into ``root/repository/id_<id>``; returns log rows."""
    text, record = record_of(api, package)
    folder = dataset_folder(root, repository, record["package_id"])
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "package.json").write_text(text)
    print(f"  {record['package_id']}, version (metadata_modified) {record['version']}")
    rows = []
    for name, e in record["entities"].items():
        if name_filter and not re.search(name_filter, name):
            continue
        path = folder / name
        served_md5, served_size = _retry(lambda: _served(e["url"]))
        if not path.exists():
            print(f"  downloading {name} ({(e['size'] or served_size or 0) / 1e9:.2f} GB)")
            _retry(lambda: _fetch(e["url"], path, e["size"] or served_size))
        algorithm, expected = e["checksum"] or ("", "")
        if expected:
            if not checksums.check(path, algorithm, expected):
                raise IOError(f"{name}: {algorithm} {expected} mismatch")
            verified_by = f"record {algorithm}"
        elif served_md5:
            if checksums.digest(path, "md5") != served_md5:
                raise IOError(f"{name}: differs from the MD5 the server states")
            verified_by = "served md5"
        elif no_md5_ok and served_size is not None and path.stat().st_size == served_size:
            verified_by = "served size (no md5 published)"
            if path.suffix.lower() == ".zip":
                with zipfile.ZipFile(path) as z:
                    bad = z.testzip()
                if bad:
                    raise IOError(f"{name}: member {bad} fails its CRC-32")
                verified_by = "served size + zip CRC-32 (no md5 published)"
        else:
            raise IOError(f"{name}: no checksum in the record and the server states no MD5"
                          + ("; size differs from the served one" if no_md5_ok else " (see --no-md5-ok)"))
        actual = checksums.digest(path, "md5")
        path.chmod(path.stat().st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
        print(f"  ok {name} ({verified_by})")
        rows.append({"source": "ckan", "doi": f"id:{record['package_id']}", "file": name,
                     "path": os.path.relpath(path, root).replace(os.sep, "/"), "bytes": path.stat().st_size,
                     "checksum_algorithm": "MD5", "checksum": actual, "verified_by": verified_by,
                     "licence": record["licence"] or record["rights"],
                     "dataset_title": record["title"], "downloaded": datetime.date.today().isoformat(),
                     "url": e["url"]})
        if path.suffix.lower() == ".zip":      # not .docx, .xlsx, .kmz, … (zip containers read as files)
            print(f"  extracted or checked {len(archives.extract(path))} files of {name} (CRC-32 verified)")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", required=True, type=Path, help="data root (e.g. the open_datasets folder)")
    parser.add_argument("--doi", required=True, action="append",
                        help="CKAN package id or dataset link (CKAN packages have no DOI)")
    parser.add_argument("--filter", default=None, help="regex on file names")
    parser.add_argument("--list", action="store_true", help="only print the files and licence")
    parser.add_argument("--repository", default="open_canada", help="folder name of the portal")
    parser.add_argument("--api", default=API, help="CKAN action API base of the portal")
    parser.add_argument("--no-md5-ok", action="store_true",
                        help="accept a file with no published or served MD5 if its size (and, for a zip, "
                             "its members' CRC-32) match")
    args = parser.parse_args()
    for package in args.doi:
        print(package)
        if args.list:
            list_files(args.api, package, args.filter)
        else:
            log(args.root / "downloads.csv",
                download(args.api, args.root, args.repository, package, args.filter, args.no_md5_ok))


if __name__ == "__main__":
    main()
