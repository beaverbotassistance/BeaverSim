#!/usr/bin/env python3
"""Zenodo download client: verified, resumable, read-only files, with the record saved as ``metadata.json``.

A concept DOI (all versions) resolves to the latest version; the version downloaded is the one the
saved record names: it names the folder and is the one logged (the concept DOI stays in the record).
Files are verified against the record's MD5s (see :mod:`data_acquisition.sources.downloads`) and logged
to ``<root>/downloads.csv``.

    python -m data_acquisition.sources.zenodo --root "<drive>/open_datasets" --id 10.5281/zenodo.7493152 --list
"""
import argparse
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from data_acquisition.readers import zenodo
from data_acquisition.sources import dataset_folder, downloads, http

RECORD = "https://zenodo.org/api/records/{id}"


def record_of(doi: str) -> (str, Dict[str, Any]):
    """The record JSON (as served) and its parsed form, for a version or concept DOI."""
    record_id = doi.removeprefix("doi:").rsplit("zenodo.", 1)[-1]
    text = http.get(RECORD.format(id=record_id)).decode("utf-8")
    return text, zenodo.read(text)


def download(root: Path, doi: str, name_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """Download the files of the version ``doi`` resolves to; returns their log rows."""
    text, record = record_of(doi)
    folder = dataset_folder(root, "zenodo", record["package_id"])     # the exact version
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "metadata.json").write_text(text)
    version = record["package_id"].removeprefix("doi:")
    if version != doi.removeprefix("doi:"):
        print(f"  {doi} resolves to version {version}")
    rows = []
    for name, e in record["entities"].items():
        if name_filter and not re.search(name_filter, name):
            continue
        path = folder / name
        if not path.exists():
            print(f"  downloading {name} ({(e['size'] or 0) / 1e9:.2f} GB)")
            http.fetch(e["url"], path, e["size"])
        rows.append(downloads.finish(path, root, e["url"], e["checksum"], source="zenodo",
                                     identifier=record["package_id"], record=record))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", required=True, type=Path, help="data root (e.g. the open_datasets folder)")
    parser.add_argument("--id", "--doi", dest="ids", required=True, action="append", help="version or concept DOI")
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
