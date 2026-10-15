#!/usr/bin/env python3
"""PANGAEA download client: verified, read-only files, with the record saved as ``metadata.tab``.

PANGAEA keeps many files on tape: the first request answers 503 ("loading from tape") and the
file becomes available a minute or more later. This client requests every wanted file once to
stage it, then tries again in rounds with a growing wait. Files are verified against the MD5s of the
record (see :mod:`data_acquisition.sources.downloads`) and logged to ``<root>/downloads.csv``.

    python -m data_acquisition.sources.pangaea --root "<drive>/open_datasets" \\
        --id doi:10.1594/PANGAEA.939231 --filter '^(?!.*\\.(jpg|JPG|laz)$)'
"""
import argparse
import re
import time
import urllib.error
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional

from data_acquisition.readers import pangaea
from data_acquisition.sources import dataset_folder, downloads, http

RECORD = "https://doi.pangaea.de/{doi}?format=textfile"
FILES = "https://download.pangaea.de/dataset/{id}/files/{name}"
STAGING = (60, 120, 240, 480, 900)        # seconds between rounds while files are staged from tape


def _staged(url: str, dest: Path) -> bool:
    """Download ``url`` to ``dest``; False while PANGAEA is still staging it from tape (HTTP 503)."""
    try:
        http.fetch(url, dest, retries=False)
    except urllib.error.HTTPError as e:
        if e.code == 503:
            return False
        raise
    return True


def record_of(doi: str) -> (str, Dict[str, Any]):
    text = http.get(RECORD.format(doi=doi.removeprefix("doi:"))).decode("utf-8")
    return text, pangaea.read(text)


def download(root: Path, doi: str, name_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """Download the files of ``doi`` (waiting for tape staging); returns their log rows."""
    text, record = record_of(doi)
    folder = dataset_folder(root, "pangaea", doi)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "metadata.tab").write_text(text)
    dataset_id = doi.removeprefix("doi:").rsplit(".", 1)[-1]
    url = {n: FILES.format(id=dataset_id, name=urllib.parse.quote(n)) for n in record["entities"]
           if not name_filter or re.search(name_filter, n)}
    print(f"  {len(url)} of {len(record['entities'])} files, "
          f"{sum(record['entities'][n]['size'] or 0 for n in url) / 1e9:.2f} GB")
    pending = [n for n in url if not (folder / n).exists()]
    for wait in (0, *STAGING):
        if not pending:
            break
        if wait:
            print(f"  {len(pending)} files staging from tape; trying again in {wait} s")
            time.sleep(wait)
        pending = [n for n in pending if not _staged(url[n], folder / n)]
    if pending:
        raise IOError(f"still staging after {sum(STAGING)} s: {pending[:3]}… run again later")
    return [downloads.finish(folder / n, root, url[n], record["entities"][n]["checksum"], source="pangaea",
                             identifier=doi, record=record) for n in url]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", required=True, type=Path, help="data root (e.g. the open_datasets folder)")
    parser.add_argument("--id", "--doi", dest="ids", required=True, action="append", help="dataset DOI")
    parser.add_argument("--filter", default=None, help="regex on file names")
    parser.add_argument("--list", action="store_true", help="only print the files and licence")
    args = parser.parse_args()
    for doi in args.ids:
        print(doi)
        if args.list:
            downloads.listing(record_of(doi)[1], args.filter)
        else:
            downloads.log(args.root / "downloads.csv", download(args.root, doi, args.filter))


if __name__ == "__main__":
    main()
