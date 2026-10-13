#!/usr/bin/env python3
"""Build a STAC catalog from a data root and a dataset summary. Generic: no source or site logic.

For each file the summary describes, the reader for its type gives the header facts, the group's
standard metadata record (if any) gives licence, checksum and repository descriptions, and the
summary gives everything else. Disagreements between the three are flagged on the item, never
resolved silently. Files on disk that the summary doesn't describe are reported.

    python -m data_acquisition.catalog.build --root "<drive>/open_datasets" --summary arcticdata_seward
"""
import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import pystac

from data_acquisition.catalog import descriptors, stac
from data_acquisition.catalog import summary as summaries
from data_acquisition.catalog.descriptors import add_quality, set_field
from data_acquisition.readers import RECORDS, eml, geotiff
from data_acquisition.sources import dataone

COMMON_NAMES = {"blue": "blue", "green": "green", "red": "red", "red edge": "rededge", "rededge": "rededge",
                "near infrared": "nir", "near-infrared": "nir", "nir": "nir"}
# products measured in metres, and the default name of their bands when the summary gives none
METRIC_BANDS = {"dsm": "elevation", "dtm": "elevation", "chm": "canopy_height", "dod": "elevation_change",
                "uncertainty": "uncertainty"}


def _bands(product: str, wanted: Optional[List[str]], header: Dict[str, Any],
           entity: Optional[Dict[str, Any]]) -> (List[str], List[tuple]):
    """Band names (summary, else declared by the file), and (flag, detail, source) where summary, file
    and record disagree."""
    flags = []
    declared = geotiff.declared_bands(header)
    if wanted:
        names = wanted
        if len(wanted) != header["count"]:
            flags.append(("band_count_conflict", f"summary gives {len(wanted)} bands, the file has {header['count']}",
                          "auto"))
        elif declared and declared != wanted:
            flags.append(("band_order_conflict", f"summary gives {wanted}, the file declares {declared}", "auto"))
    elif product in METRIC_BANDS:
        names = [METRIC_BANDS[product]] * header["count"]
    else:
        names = declared or [f"b{i + 1}" for i in range(header["count"])]
    if entity is not None and entity["attributes"]:     # only records that describe the file's contents
        repo = [COMMON_NAMES.get(n, n) for n in eml.bands(entity)]
        expected = [] if product in METRIC_BANDS else [n for n in names if n != "alpha"]
        if repo != expected:
            flag = "band_order_conflict" if sorted(repo) == sorted(expected) else "repository_band_conflict"
            flags.append((flag, f"repository describes {repo or 'no'} bands; using {expected or 'none'} "
                                f"({'summary' if wanted else 'file'})", "repository"))
    return names, flags


def raster_item(s: Dict[str, Any], f: Dict[str, Any], path: Path, rel: str, group: Dict[str, Any],
                record: Optional[Dict[str, Any]], log: Dict[str, Dict[str, str]]) -> pystac.Item:
    source, who = summaries.author(s)
    product, site = f["product"], f["site"]
    start, end, label = summaries.epoch(f)
    item_id = f"{site}_{label}_{product}" + (f"_{f['variant']}" if f.get("variant") else "")
    header = geotiff.info(path)
    entity = record["entities"].get(path.name) if record else None
    algorithm, digest = (entity or {}).get("checksum") or (None, None)

    names, flags = _bands(product, f.get("bands"), header, entity)
    bands = [{"name": n, "common_name": n if n in COMMON_NAMES.values() else None} for n in names]
    item = stac.raster_item(item_id, path, header, start, end, product, ["data"], bands, title=path.name,
                            unit=f.get("unit") or ("m" if product in METRIC_BANDS else None),
                            checksum=stac.multihash(algorithm, digest) if algorithm in stac.MULTIHASH else None)
    for flag, detail, flag_source in flags:
        add_quality(item, flag, detail, source=flag_source)

    if record is not None:
        if entity is None:
            add_quality(item, "not_in_record", "the metadata record does not list this file", source="repository")
        elif entity["size"] is not None and entity.get("size_exact", True) and entity["size"] != path.stat().st_size:
            add_quality(item, "size_mismatch", f"record {entity['size']} bytes, file {path.stat().st_size}",
                        source="repository")
        if record["dates"] and not record["dates"][0] <= start.isoformat() <= end.isoformat() <= record["dates"][-1]:
            add_quality(item, "date_outside_record", f"{label} not within {record['dates'][0]}..{record['dates'][-1]}",
                        source="repository")
    for note in f.get("notes") or []:
        add_quality(item, "note", note, source=source)

    item.common_metadata.platform = f.get("platform")
    item.common_metadata.instruments = f.get("instruments")
    if (f.get("date_precision") or "day") != "day":
        item.properties["beaver:date_precision"] = f["date_precision"]
    if f.get("vertical_datum"):
        item.properties["beaver:vertical_datum"] = f["vertical_datum"]
    set_field(item, "site", site, source, **who)
    set_field(item, "positioning", f.get("positioning"), source, **who)
    if record is not None:
        set_field(item, "licence", record["licence"], "repository")
    else:
        item.properties.setdefault("beaver:licence", None)
    dl = log.get(rel, {})
    set_field(item, "provenance", {
        "source": s["source"]["provider"], "doi": group.get("doi"),
        "package_id": record["package_id"] if record else None,
        "dataset_title": record["title"] if record else s["title"],
        "creators": record["creators"] if record else None, "path": rel,
        "url": (entity or {}).get("url") or dl.get("url"), "downloaded": dl.get("downloaded"),
        "checksum": f"{algorithm}:{digest}" if algorithm else None, "summary": Path(s["_path"]).name},
        "repository" if record else source, **({} if record else who))
    return item


def build(root: Path, s: Dict[str, Any]) -> (pystac.Catalog, Dict[str, List[str]]):
    """Catalog of the files ``s`` describes under ``root``, and a report of problems."""
    log = dataone.read_log(root / s["source"]["log"]) if s["source"].get("log") else {}
    report = {"missing": [], "undescribed": [], "unsupported": [], "unattached": []}
    items: Dict[str, pystac.Item] = {}
    placed: Dict[str, tuple] = {}          # item id -> (group index, product, epoch label)
    attachments = []
    for gi, g in enumerate(s["groups"]):
        folder = root / g["folder"]
        record, described = None, set()
        if g.get("record"):
            described.add(g["record"]["path"])
            record = RECORDS[g["record"]["format"]]["read"]((folder / g["record"]["path"]).read_text())
        for file in g["files"]:
            f = summaries.resolve(g, file)
            path, described = folder / f["path"], described | {f["path"]}
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            if not path.exists():
                report["missing"].append(rel)
            elif f.get("role"):
                attachments.append((gi, f, path))
            elif path.suffix.lower() in geotiff.EXTENSIONS:
                item = raster_item(s, f, path, rel, g, record, log)
                if item.id in items:
                    raise ValueError(f"two files for {item.id}: {rel}")
                if record is not None:
                    stac.add_file_asset(item, "metadata", folder / g["record"]["path"], ["metadata"],
                                        f"{g['record']['format']} record", RECORDS[g["record"]["format"]]["media"])
                items[item.id] = item
                placed[item.id] = (gi, f["product"], summaries.epoch(f)[2])
            else:
                report["unsupported"].append(rel)
        if folder.exists():
            report["undescribed"] += [os.path.relpath(p, root) for p in sorted(folder.iterdir())
                                      if p.is_file() and p.name not in described and not p.name.endswith(".part")]

    for gi, f, path in attachments:
        dated = any(f.get(k) is not None for k in ("date", "start_date"))
        label = summaries.epoch(f)[2] if dated else None
        for product in f["attach_to"]:
            targets = [items[i] for i, (g2, p2, l2) in placed.items()
                       if g2 == gi and p2 == product and (label is None or l2 == label)]
            if not targets:
                report["unattached"].append(f"{path.name} -> {product}{f' {label}' if label else ''}")
            for item in targets:
                key = f["role"] if f["role"] not in item.assets else f"{f['role']}:{path.stem}"
                stac.add_file_asset(item, key, path, [f["role"]], path.name,
                                    "application/pdf" if path.suffix.lower() == ".pdf" else None)

    catalog = pystac.Catalog(s["dataset"], f"{s['title']}. Built from {Path(s['_path']).name}.")
    for slug in sorted({descriptors.get_field(i, "site") for i in items.values()}):
        site_items = sorted((i for i in items.values() if descriptors.get_field(i, "site") == slug),
                            key=lambda i: (i.datetime or i.common_metadata.start_datetime, i.id))
        licences = {descriptors.get_field(i, "licence") for i in site_items}
        collection = pystac.Collection(
            slug, s["sites"][slug]["name"], pystac.Extent.from_items(site_items),
            license=licences.pop() if len(licences) == 1 and None not in licences else "various",
            providers=[pystac.Provider(s["source"]["provider"], roles=["host"], url=s["source"].get("url"))])
        collection.add_items(site_items)
        catalog.add_child(collection)
    return catalog, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", required=True, type=Path, help="data root the summary's paths are relative to")
    parser.add_argument("--summary", required=True, help="summary name or YAML path")
    parser.add_argument("--out", type=Path, default=None, help="catalog folder (default <root>/stac/<dataset>)")
    args = parser.parse_args()
    s = summaries.load(args.summary)
    catalog, report = build(args.root, s)
    out = stac.save(catalog, args.out or args.root / "stac" / s["dataset"])
    (out.parent / "build_report.json").write_text(json.dumps(report, indent=1))
    print(f"{len(list(catalog.get_items(recursive=True)))} items -> {out}")
    for kind, entries in report.items():
        for e in entries:
            print(f"  {kind}: {e}")


if __name__ == "__main__":
    main()
