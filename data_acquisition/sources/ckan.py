#!/usr/bin/env python3
"""CKAN download client (Open Government portals: open.canada.ca, data.ontario.ca, …): verified, resumable,
read-only files, with the record saved as ``package.json``.

A CKAN package has no DOI and no versions: it is named by its own id (the folder is ``id_<id>``) and the
version downloaded is the record's ``metadata_modified``. Resources that are web pages or services are
skipped (see :mod:`data_acquisition.readers.ckan`); the files may be served by the publisher's own
servers, which the record links to. Checksums: the record's ``hash`` when it gives one, else the MD5 the
server states; a file with neither is refused unless ``--no-md5-ok`` allows the size and zip CRC-32
checks (see :mod:`data_acquisition.sources.downloads`). Zip archives are extracted next to themselves
(:mod:`data_acquisition.sources.archives`).

    python -m data_acquisition.sources.ckan --root "<drive>/open_datasets" \\
        --id b44984f7-9ba6-45aa-b25b-a6dc596afea5 --list
"""
import argparse
import json
import re
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional

from data_acquisition.readers import ckan
from data_acquisition.sources import archives, dataset_folder, downloads, http

API = "https://open.canada.ca/data/api/3/action"


def package_id(text: str) -> str:
    """The package id or name in a CKAN dataset link (``…/dataset/<id>``), or the text itself."""
    m = re.search(r"/dataset/([^/?#]+)", text)
    return m.group(1) if m else text.strip()


def record_of(api: str, package: str) -> (str, Dict[str, Any]):
    """The record (the ``package_show`` response, as served, labelled with its URL) and its parsed form."""
    url = f"{api}/package_show?id={urllib.parse.quote(package_id(package))}"
    text = json.dumps({"package_url": url, "package": json.loads(http.get(url))}, indent=1)
    return text, ckan.read(text)


def download(api: str, root: Path, repository: str, package: str, name_filter: Optional[str] = None,
             no_md5_ok: bool = False) -> List[Dict[str, Any]]:
    """Download the files of ``package`` into ``root/repository/id_<id>``; returns their log rows."""
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
        if not path.exists():
            print(f"  downloading {name}")
            http.fetch(e["url"], path, e["size"] or http.served(e["url"])[1])
        rows.append(downloads.finish(path, root, e["url"], e["checksum"], source="ckan",
                                     identifier=f"id:{record['package_id']}", record=record, size_only=no_md5_ok))
        if path.suffix.lower() == ".zip":      # not .docx, .xlsx, .kmz, … (zip containers read as files)
            print(f"  extracted or checked {len(archives.extract(path))} files of {name} (CRC-32 verified)")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", required=True, type=Path, help="data root (e.g. the open_datasets folder)")
    parser.add_argument("--id", "--doi", dest="ids", required=True, action="append",
                        help="CKAN package id or dataset link (CKAN packages have no DOI)")
    parser.add_argument("--filter", default=None, help="regex on file names")
    parser.add_argument("--list", action="store_true", help="only print the files, licence and checks")
    parser.add_argument("--repository", default="open_canada", help="folder name of the portal")
    parser.add_argument("--api", default=API, help="CKAN action API base of the portal")
    parser.add_argument("--no-md5-ok", action="store_true",
                        help="accept a file with no published or served MD5 if its size (and, for a zip, "
                             "its members' CRC-32) match")
    args = parser.parse_args()
    for package in args.ids:
        print(package)
        if args.list:
            downloads.listing(record_of(args.api, package)[1], args.filter, checks=True)
        else:
            downloads.log(args.root / "downloads.csv",
                          download(args.api, args.root, args.repository, package, args.filter, args.no_md5_ok))


if __name__ == "__main__":
    main()
