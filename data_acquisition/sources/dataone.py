#!/usr/bin/env python3
"""DataONE download client (Arctic Data Center, KNB, …): verified, resumable, read-only files.

The record of a dataset is its EML document, saved as ``<folder>/metadata.xml``. Files are verified
against the checksums the EML gives (see :mod:`data_acquisition.sources.downloads`) and logged to
``<root>/downloads.csv``. Two ways to name what to download: DOIs (``--id``, into
``<root>/<repository>/doi_<doi>/``), or a summary (``--summary``: every group with a ``doi``, into its
folder, with its ``download_filter``).

    python -m data_acquisition.sources.dataone --root "<drive>/open_datasets" --id doi:10.18739/A22R3NZ98 --list
    python -m data_acquisition.sources.dataone --root "<drive>/open_datasets" --summary arcticdata_seward
"""
import argparse
import os
import re
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional

from data_acquisition.catalog import summary as summaries
from data_acquisition.readers import eml
from data_acquisition.sources import dataset_folder, downloads, http

# DataONE coordinating node: serves objects of every member repository; used when a summary names no
# member-node API (a member node is closer to the data and supports resumed downloads)
COORDINATING_NODE = "https://cn.dataone.org/cn/v2"


def _object(api: str, pid: str) -> str:
    return f"{api}/object/{urllib.parse.quote(pid, safe='')}"


def record_of(api: str, doi: str) -> (str, Dict[str, Any]):
    """The EML record of ``doi`` (as served) and its parsed form."""
    text = http.get(_object(api, doi)).decode("utf-8", "replace")
    return text, eml.read(text)


def download(api: str, root: Path, folder: str, doi: str, name_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """Download the files of ``doi`` into ``root/folder``; returns their log rows."""
    text, record = record_of(api, doi)
    target = root / folder
    target.mkdir(parents=True, exist_ok=True)
    (target / "metadata.xml").write_text(text)
    rows = []
    for name, e in record["entities"].items():
        if name_filter and not re.search(name_filter, name):
            continue
        # the record's own download link (a /resolve/ address that redirects to the node holding the file):
        # the coordinating node's /object/ serves records but not always data files
        path, url = target / name, http.https(e["url"]) if e["url"] else _object(api, e["pid"])
        if not path.exists():
            print(f"  downloading {name} ({(e['size'] or 0) / 1e9:.2f} GB)")
            http.fetch(url, path, e["size"])
        rows.append(downloads.finish(path, root, url, e["checksum"], source="dataone", identifier=doi, record=record))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", required=True, type=Path, help="data root (e.g. the open_datasets folder)")
    parser.add_argument("--summary", help="download every group of this summary (name or YAML path)")
    parser.add_argument("--id", "--doi", dest="ids", action="append",
                        help="or: these DOIs, into <root>/<repository>/doi_<doi>/")
    parser.add_argument("--filter", default=None, help="regex on file names (with --id)")
    parser.add_argument("--list", action="store_true", help="only print the files and licence (with --id)")
    parser.add_argument("--repository", default="arcticdata", help="folder name of the member repository")
    parser.add_argument("--api", default=COORDINATING_NODE, help="DataONE API base (member or coordinating node)")
    args = parser.parse_args()
    if args.ids:
        for doi in args.ids:
            print(doi)
            if args.list:
                downloads.listing(record_of(args.api, doi)[1], args.filter)
            else:
                folder = os.path.relpath(dataset_folder(args.root, args.repository, doi), args.root)
                downloads.log(args.root / "downloads.csv", download(args.api, args.root, folder, doi, args.filter))
        return
    if not args.summary:
        parser.error("give --summary or --id")
    s = summaries.load(args.summary)
    if s["source"]["kind"] != "dataone":
        raise SystemExit(f"source kind is {s['source']['kind']!r}, not dataone")
    for g in s["groups"]:
        if g.get("doi"):
            print(g["doi"])
            downloads.log(args.root / s["source"]["log"],
                          download(s["source"].get("api", COORDINATING_NODE), args.root, g["folder"], g["doi"],
                                   g.get("download_filter")))


if __name__ == "__main__":
    main()
