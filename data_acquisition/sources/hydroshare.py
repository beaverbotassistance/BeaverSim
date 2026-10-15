#!/usr/bin/env python3
"""HydroShare download client: verified, resumable, read-only files, with the record saved as ``resource.json``.

HydroShare serves a resource's science metadata and its file list from two endpoints; both responses
are saved as served, each labelled with its URL, in ``resource.json`` (see
:mod:`data_acquisition.readers.hydroshare`). A collection resource has no files of its own: its record
is saved in its folder and each member resource is downloaded into its own folder. A resource id names
one version (a new version is a new resource). An unpublished resource has no DOI and is named
``hs:<id>``. Checksums: the record's when they can be checked (plain MD5s, or S3 multipart ETags of a
common part size), else the MD5 the cloud storage states (see :mod:`data_acquisition.sources.downloads`).

    python -m data_acquisition.sources.hydroshare --root "<drive>/open_datasets" \\
        --id 10.4211/hs.7c4ae80863174acfb571ccf8bdac8968 --list
"""
import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from data_acquisition.readers import hydroshare
from data_acquisition.sources import dataset_folder, downloads, http

API = "https://www.hydroshare.org"
METADATA = API + "/hsapi2/resource/{id}/json/"
FILES = API + "/hsapi/resource/{id}/files/"


def record_of(resource: str) -> (str, Dict[str, Any]):
    """The record (metadata and every page of the file list, as served) and its parsed form."""
    metadata_url = METADATA.format(id=resource)
    metadata = json.loads(http.get(metadata_url))
    files, page = [], FILES.format(id=resource)
    while page:
        d = json.loads(http.get(page))
        files += d["results"]
        page = d["next"]
    text = json.dumps({"metadata_url": metadata_url, "metadata": metadata,
                       "files_url": FILES.format(id=resource), "files": files}, indent=1)
    return text, hydroshare.read(text)


def list_files(identifier: str, name_filter: Optional[str] = None) -> None:
    """Print the files of a resource and, for a collection, of each member."""
    _, record = record_of(hydroshare.resource_id(identifier))
    for part in record["parts"]:
        downloads.listing(record_of(part)[1], name_filter)
    if record["entities"] or not record["parts"]:
        downloads.listing(record, name_filter)


def download(root: Path, identifier: str, name_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """Download the files of a resource (and, for a collection, of every member); returns their log rows."""
    resource = hydroshare.resource_id(identifier)
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
        path, url = folder / name, http.https(e["url"])
        if not path.exists():
            print(f"  downloading {name} ({(e['size'] or 0) / 1e9:.2f} GB)")
            http.fetch(url, path, e["size"])
        rows.append(downloads.finish(path, root, url, e["checksum"], source="hydroshare",
                                     identifier=record["package_id"], record=record))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", required=True, type=Path, help="data root (e.g. the open_datasets folder)")
    parser.add_argument("--id", "--doi", dest="ids", required=True, action="append",
                        help="resource DOI, link, or hs:<resource id>")
    parser.add_argument("--filter", default=None, help="regex on file names")
    parser.add_argument("--list", action="store_true", help="only print the files and licence")
    args = parser.parse_args()
    for identifier in args.ids:
        print(identifier)
        if args.list:
            list_files(identifier, args.filter)
        else:
            downloads.log(args.root / "downloads.csv", download(args.root, identifier, args.filter))


if __name__ == "__main__":
    main()
