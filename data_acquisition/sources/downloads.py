"""Finishing a downloaded file, and the download log, shared by every source client.

:func:`finish` verifies a file, makes it read-only and returns its log row. The checks, in order:

1. the repository's checksum, when it gives one that can be decided (a plain digest, or an S3 multipart
   ETag of a common part size; see :mod:`data_acquisition.sources.checksums`);
2. else the MD5 the server states when serving the file;
3. else, only when the caller allows it (``size_only=True``), the size the server states and, for a zip,
   the CRC-32 of every member.

A file that passes none is refused. The log row's ``verified_by`` says which check it passed.

The download log (``<root>/downloads.csv``) has one row per file, keyed by its path under the data root.
"""
import csv
import datetime
import os
import re
import stat
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from data_acquisition.sources import checksums, http

LOG_FIELDS = ["source", "doi", "file", "path", "bytes", "checksum_algorithm", "checksum", "licence",
              "dataset_title", "downloaded", "url", "verified_by"]


def read_only(path: Path) -> None:
    path.chmod(path.stat().st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def verify(path: Path, url: str, checksum: Optional[Tuple[str, str]], size_only: bool = False) -> str:
    """Check a downloaded file (see the module docstring); returns what it was checked against, or raises."""
    if checksum:
        verdict = checksums.check(path, *checksum)
        if verdict is False:
            raise IOError(f"{path.name}: differs from the repository's {checksum[0]} {checksum[1]}")
        if verdict:
            return f"record {checksums.parse(*checksum)[0]}"
    md5, size = http.served(url)
    unchecked = f" (record {checksum[1]} not checkable)" if checksum else ""
    if md5:
        if checksums.digest(path, "md5") != md5:
            raise IOError(f"{path.name}: differs from the MD5 the server states")
        return "served md5" + unchecked
    if size_only and size is not None and path.stat().st_size == size:
        if path.suffix.lower() == ".zip":
            with zipfile.ZipFile(path) as z:
                bad = z.testzip()
            if bad:
                raise IOError(f"{path.name}: member {bad} fails its CRC-32")
            return "served size + zip CRC-32 (no md5 published)"
        return "served size (no md5 published)"
    raise IOError(f"{path.name}: no checksum to verify against" + ("" if size_only else " (size-only not allowed)"))


def finish(path: Path, root: Path, url: str, checksum: Optional[Tuple[str, str]], *, source: str,
           identifier: Optional[str], record: Dict[str, Any], size_only: bool = False) -> Dict[str, Any]:
    """Verify ``path``, make it read-only, and return its download-log row."""
    verified_by = verify(path, url, checksum, size_only)
    read_only(path)
    print(f"  ok {path.name} ({verified_by})")
    return {"source": source, "doi": identifier or "", "file": path.name,
            "path": os.path.relpath(path, root).replace(os.sep, "/"), "bytes": path.stat().st_size,
            "checksum_algorithm": "MD5", "checksum": checksums.digest(path, "md5"), "verified_by": verified_by,
            "licence": record.get("licence") or record.get("rights") or "", "dataset_title": record["title"],
            "downloaded": datetime.date.today().isoformat(), "url": url}


def listing(record: Dict[str, Any], name_filter: Optional[str] = None, checks: bool = False) -> None:
    """Print a record's files (size, name), licence and total, for a client's ``--list``. With ``checks``,
    also ask the server for each file and say how it could be verified (record checksum, served MD5, or
    neither), and use the served size when the record gives none."""
    print(f"  {record.get('package_id')}: {record['title']}\n  licence: {record['licence'] or record['rights']}")
    total = 0
    for name, e in record["entities"].items():
        if name_filter and not re.search(name_filter, name):
            continue
        size, how = e["size"], ""
        if checks:
            md5, served_size = http.served(http.https(e["url"]))
            size = size or served_size
            how = "  (record checksum)" if e["checksum"] else "  (served md5)" if md5 else "  (no md5: size only)"
        total += size or 0
        print(f"  {(size or 0) / 1e9:9.3f} GB  {name}{how}")
    print(f"  {total / 1e9:9.3f} GB  total")


def log(path: Path, rows: List[Dict[str, Any]]) -> None:
    """Merge ``rows`` into the download log at ``path`` (one row per file path)."""
    old = list(read_log(path).values())
    keep = [r for r in old if r["path"] not in {x["path"] for x in rows}]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, LOG_FIELDS, restval="")       # older rows have no verified_by
        w.writeheader()
        w.writerows(keep + rows)


def read_log(path: Path) -> Dict[str, Dict[str, str]]:
    """The download log's rows, keyed by file path relative to the data root."""
    if not path.exists():
        return {}
    with open(path, newline="") as f:
        return {r["path"]: r for r in csv.DictReader(f)}
