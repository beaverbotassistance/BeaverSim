#!/usr/bin/env python3
"""PANGAEA download client: verified, read-only files, with the record saved as ``metadata.tab``.

PANGAEA keeps many files on tape: the first request answers 503 ("loading from tape") and the
file becomes available a minute or more later. This client requests every wanted file once to
stage it, then retries with a growing wait.

    python -m data_acquisition.sources.pangaea --root "<drive>/open_datasets" \\
        --doi doi:10.1594/PANGAEA.939231 --filter '^(?!.*\\.(jpg|JPG|laz)$)'
"""
import argparse
import datetime
import os
import re
import stat
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from data_acquisition.readers import pangaea
from data_acquisition.sources import dataset_folder
from data_acquisition.sources.dataone import file_hash, log

RECORD = "https://doi.pangaea.de/{doi}?format=textfile"
FILES = "https://download.pangaea.de/dataset/{id}/files/{name}"
CHUNK = 8 * 1024 * 1024
WAITS = [60, 120, 240, 480, 900]          # seconds between rounds while files are staged from tape


def _fetch(url: str, dest: Path) -> bool:
    """Download ``url`` to ``dest``; False while PANGAEA is still staging it (HTTP 503)."""
    part = dest.with_name(dest.name + ".part")
    try:
        with urllib.request.urlopen(url, timeout=300) as r, open(part, "wb") as f:
            for block in iter(lambda: r.read(CHUNK), b""):
                f.write(block)
    except urllib.error.HTTPError as e:
        if e.code == 503:
            return False
        raise
    part.rename(dest)
    return True


def download(root: Path, doi: str, name_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    bare = doi.removeprefix("doi:")
    text = urllib.request.urlopen(RECORD.format(doi=bare), timeout=120).read().decode("utf-8")
    record = pangaea.read(text)
    folder = dataset_folder(root, "pangaea", doi)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "metadata.tab").write_text(text)
    dataset_id = bare.rsplit(".", 1)[-1]
    wanted = {n: e for n, e in record["entities"].items() if not name_filter or re.search(name_filter, n)}
    print(f"  {len(wanted)} of {len(record['entities'])} files, "
          f"{sum(e['size'] or 0 for e in wanted.values()) / 1e9:.2f} GB")
    pending = [n for n in wanted if not (folder / n).exists()]
    for wait in [0] + WAITS:
        if not pending:
            break
        if wait:
            print(f"  {len(pending)} files staging from tape; retrying in {wait} s")
            time.sleep(wait)
        pending = [n for n in pending
                   if not _fetch(FILES.format(id=dataset_id, name=urllib.parse.quote(n)), folder / n)]
    if pending:
        raise IOError(f"still staging after {sum(WAITS)} s: {pending[:3]}… run again later")
    rows = []
    for name, e in wanted.items():
        path = folder / name
        algorithm, expected = e["checksum"] or ("", "")
        actual = file_hash(path, algorithm) if algorithm else ""
        if expected and actual != expected:
            raise IOError(f"{name}: {algorithm} mismatch")
        path.chmod(path.stat().st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
        rows.append({"source": "pangaea", "doi": doi, "file": name,
                     "path": os.path.relpath(path, root).replace(os.sep, "/"), "bytes": path.stat().st_size,
                     "checksum_algorithm": algorithm.upper(), "checksum": actual, "licence": record["licence"],
                     "dataset_title": record["title"], "downloaded": datetime.date.today().isoformat(),
                     "url": FILES.format(id=dataset_id, name=urllib.parse.quote(name))})
    print(f"  ok, {len(rows)} files verified")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", required=True, type=Path, help="data root (e.g. the open_datasets folder)")
    parser.add_argument("--doi", required=True, action="append")
    parser.add_argument("--filter", default=None, help="regex on file names")
    args = parser.parse_args()
    for doi in args.doi:
        print(doi)
        log(args.root / "downloads.csv", download(args.root, doi, args.filter))


if __name__ == "__main__":
    main()
