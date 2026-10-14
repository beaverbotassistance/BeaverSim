#!/usr/bin/env python3
"""Build a STAC catalog from a data root and a dataset summary. Generic: no source or site logic.

For each file the summary describes, the reader for its type gives the header facts, the group's
standard metadata record (if any) gives licence, checksum and repository descriptions, and the
summary gives everything else. Disagreements between the three are flagged on the item, never
resolved silently. Files on disk that the summary doesn't describe are reported.

    python -m data_acquisition.catalog.build --root "<drive>/open_datasets" --summary arcticdata_seward
"""
import argparse
import functools
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import pystac

from data_acquisition.catalog import descriptors, stac
from data_acquisition.catalog import summary as summaries
from data_acquisition.catalog.descriptors import add_quality, set_field
from data_acquisition.readers import RECORD_FILES, RECORDS, eml, geotiff, table, vector
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
                          "build"))
        elif declared and declared != wanted:
            flags.append(("band_order_conflict", f"summary gives {wanted}, the file declares {declared}", "build"))
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


def _period(dates: List[str]) -> (Optional[str], Optional[str]):
    """First and last day of a record's dates, which may be years (``2001``) or months (``2024-06``)."""
    if not dates:
        return None, None
    first, last = dates[0], dates[-1]
    first = first + "-01" * ((10 - len(first)) // 3)
    if len(last) == 4:
        last += "-12-31"
    elif len(last) == 7:
        import calendar
        last += f"-{calendar.monthrange(int(last[:4]), int(last[5:7]))[1]:02d}"
    return first[:10], last[:10]


@functools.lru_cache(maxsize=None)
def _vector_info(path: Path) -> Dict[str, Any]:
    return vector.info(path)        # read once per build, also when one file gives one item per layer


def one_layer(info: Dict[str, Any], name: str) -> Dict[str, Any]:
    """``info`` restricted to the layer ``name``."""
    layer = next(l for l in info["layers"] if l["name"] == name)
    return {"layers": [layer], "crs": layer["crs"], "epsg": layer["epsg"], "bounds": layer["bounds"],
            "vertical_crs": [layer["vertical_crs"]] if layer["vertical_crs"] else [], "features": layer["features"]}


def data_item(s: Dict[str, Any], f: Dict[str, Any], path: Path, rel: str, group: Dict[str, Any],
              record: Optional[Dict[str, Any]], log: Dict[str, Dict[str, str]],
              layer: Optional[str] = None) -> pystac.Item:
    """Item for a data file (raster or vector), or for one ``layer`` of a vector file: header facts from its
    reader, the rest from the summary and the record, with flags where they disagree."""
    source, who = summaries.author(s)
    product, site = f["product"], f["site"]
    start, end, label = summaries.epoch(f)
    item_id = f"{site}_{label}_{product}" + (f"_{f['variant']}" if f.get("variant") else "")
    archive = f.get("archive")
    entity = record["entities"].get(archive or path.name) if record else None   # an extracted file: the archive's
    algorithm, digest = (entity or {}).get("checksum") or (None, None)
    checksum = stac.multihash(algorithm, digest) if algorithm in stac.MULTIHASH and not archive else None

    flags = []
    if f.get("table"):          # a CSV: points (CRS from the summary or the site), or rows without geometry
        crs = f.get("crs") or s["sites"][site]["crs"]
        layers = table.info(path, f["table"], crs)
        item = stac.vector_item(item_id, path, layers, start, end, product, ["data"], checksum, title=path.name)
        item.assets[product].media_type = "text/csv"
        item.properties["beaver:table"] = f["table"]
        if layers.get("spatial", True):
            item.properties["beaver:crs_from_summary"] = crs
            flags.append(("crs_from_summary", f"the table states no CRS; {crs} from the "
                                              f"{'summary' if f.get('crs') else 'site'}", "build"))
        else:
            flags.append(("non_spatial", f"a table of {layers['features']} rows without coordinates; no footprint, "
                                         "site from the summary", "build"))
    elif vector.is_vector(path):
        layers = one_layer(_vector_info(path), layer) if layer else _vector_info(path)
        item = stac.vector_item(item_id, path, layers, start, end, product, ["data"], checksum,
                                title=f"{path.name}, layer {layer}" if layer else path.name)
        if layer:
            item.properties["beaver:layer"] = layer
        if layers["vertical_crs"]:
            item.properties["beaver:vertical_crs"] = layers["vertical_crs"]
    else:
        header = geotiff.info(path)
        if not header["has_crs"]:
            if not f.get("crs"):
                raise ValueError("the raster declares no CRS; give `crs` in the summary")
            header["epsg"] = int(f["crs"].split(":")[1])
            flags.append(("crs_from_summary", f"the raster declares no CRS; {f['crs']} from the summary", "build"))
        names, band_flags = _bands(product, f.get("bands"), header, entity)
        flags += band_flags
        bands = [{"name": n, "common_name": n if n in COMMON_NAMES.values() else None} for n in names]
        item = stac.raster_item(item_id, path, header, start, end, product, ["data"], bands, title=path.name,
                                unit=f.get("unit") or ("m" if product in METRIC_BANDS else None), checksum=checksum)
        if not header["has_crs"]:
            item.properties["beaver:crs_from_summary"] = f["crs"]
        if path.suffix.lower() not in geotiff.EXTENSIONS:
            item.assets[product].media_type = None      # not a GeoTIFF; the GDAL driver is recorded instead
            item.assets[product].extra_fields["beaver:driver"] = header["driver"]
    if f.get("fields") and (f.get("table") or vector.is_vector(path)):    # meaning of attribute columns
        item.properties["beaver:fields"] = f["fields"]
        columns = {c for l in layers["layers"] for c in l["fields"]}
        named = [c for v in f["fields"].values() for c in ([v] if isinstance(v, str) else v)]
        absent = [c for c in named if c not in columns]
        if absent:
            flags.append(("fields_missing", f"declared columns {absent} are not in the file "
                                            f"(columns: {sorted(columns)})", "build"))
    for flag, detail, flag_source in flags:
        add_quality(item, flag, detail, source=flag_source)

    if record is not None:
        if entity is None:
            add_quality(item, "not_in_record", "the metadata record does not list this file", source="repository")
        elif not archive and path.is_file() and entity["size"] is not None and entity.get("size_exact", True) \
                and entity["size"] != path.stat().st_size:
            add_quality(item, "size_mismatch", f"record {entity['size']} bytes, file {path.stat().st_size}",
                        source="repository")
        first, last = _period(record["dates"])
        precise = (f.get("date_precision") or "day") == "day"
        # a precise date (or span) must lie within the record's period; a month or year must only overlap it
        if first and (not first <= start.isoformat() <= end.isoformat() <= last if precise
                      else end.isoformat() < first or start.isoformat() > last):
            add_quality(item, "date_outside_record", f"{label} not within {first}..{last}",
                        source="repository")
    for note in f.get("notes") or []:
        add_quality(item, "note", note, source=source)

    item.common_metadata.platform = f.get("platform")
    item.common_metadata.instruments = f.get("instruments")
    if (f.get("date_precision") or "day") != "day":
        item.properties["beaver:date_precision"] = f["date_precision"]
    if f.get("date_precision") == "unknown":
        add_quality(item, "date_unknown", f"acquisition date not known; only its limits {start}..{end}", source="build")
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
        **({"concept_id": record["concept_id"]} if record and record.get("concept_id") else {}),
        "dataset_title": record["title"] if record else s["title"],
        **({"dataset_doi": s["doi"]} if s.get("doi") and s.get("doi") != group.get("doi") else {}),
        "creators": record["creators"] if record else None, "path": rel,
        "url": (entity or {}).get("url") or dl.get("url"), "downloaded": dl.get("downloaded"),
        "checksum": f"{algorithm}:{digest}" if algorithm and not archive else None,
        **({"download_checksum": f"{dl['checksum_algorithm'].lower()}:{dl['checksum']}",
            "download_verified_by": dl.get("verified_by") or "record checksum"}
           if dl.get("checksum") and not archive else {}),
        **({"archive": f"{group['folder']}/{archive}",
            "archive_checksum": f"{algorithm}:{digest}" if algorithm else None,
            "extracted": "CRC-32 verified against the archive (data_acquisition.sources.archives)"} if archive else {}),
        "summary": Path(s["_path"]).name},
        "repository" if record else source, **({} if record else who))
    return item


def build(root: Path, s: Dict[str, Any]) -> (pystac.Catalog, Dict[str, List[str]]):
    """Catalog of the files ``s`` describes under ``root``, and a report of problems."""
    log = dataone.read_log(root / s["source"]["log"]) if s["source"].get("log") else {}
    report = {"missing": [], "undescribed": [], "unsupported": [], "unattached": [], "unmatched_layers": []}
    _vector_info.cache_clear()
    items: Dict[str, pystac.Item] = {}
    placed: Dict[str, tuple] = {}          # item id -> (group index, product, epoch label, site)
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
            elif f.get("role") and g.get("record") and f["path"] == g["record"]["path"]:
                continue                    # the group's record is attached to every item already
            elif f.get("role"):
                attachments.append((gi, f, path))
            elif f.get("layers") and vector.is_vector(path):    # one item per layer, dated by the layer's name
                for layer in _vector_info(path)["layers"]:
                    time = summaries.layer_epoch(layer["name"], f["layers"])
                    if time is None:
                        report["unmatched_layers"].append(f"{rel}: {layer['name']}")
                        continue
                    lf = {k: v for k, v in f.items() if k not in ("start_date", "end_date")} | time
                    item = data_item(s, lf, path, rel, g, record, log, layer=layer["name"])
                    if item.id in items:
                        raise ValueError(f"two layers for {item.id}: {rel}")
                    if record is not None:
                        stac.add_file_asset(item, "metadata", folder / g["record"]["path"], ["metadata"],
                                            f"{g['record']['format']} record", RECORDS[g["record"]["format"]]["media"])
                    items[item.id] = item
                    placed[item.id] = (gi, f["product"], summaries.epoch(lf)[2], f["site"])
                continue
            elif f.get("table") or geotiff.is_raster(path) or vector.is_vector(path):
                try:
                    item = data_item(s, f, path, rel, g, record, log)
                except (ValueError, KeyError) as e:
                    report["unsupported"].append(f"{rel}: {e}")
                    continue
                if item.id in items:
                    raise ValueError(f"two files for {item.id}: {rel}")
                if record is not None:
                    stac.add_file_asset(item, "metadata", folder / g["record"]["path"], ["metadata"],
                                        f"{g['record']['format']} record", RECORDS[g["record"]["format"]]["media"])
                items[item.id] = item
                placed[item.id] = (gi, f["product"], summaries.epoch(f)[2], f["site"])
            else:
                report["unsupported"].append(rel)
        if folder.exists():
            rasters = [d for d in described if d.lower().endswith(geotiff.EXTENSIONS)]
            shapefiles = [d[:-4] for d in described if d.lower().endswith(".shp")]
            sidecars = ({r + ext for r in rasters for ext in summaries.SIDECARS}
                        | {r.rsplit(".", 1)[0] + ext for r in rasters for ext in summaries.SIDECARS}
                        | {s_ + ext for s_ in shapefiles for ext in vector.SHAPEFILE_PARTS})
            containers = [d + "/" for d in described if d.lower().endswith(".gdb")]   # folders read as one file
            scope = g.get("download_filter")      # files outside the group's filter belong to another summary
            for p in sorted(folder.rglob("*")):
                rel_f = p.relative_to(folder).as_posix()
                if (p.is_file() and rel_f not in described | sidecars and not p.name.endswith(".part")
                        and not any(rel_f.startswith(c) for c in containers)
                        and (not scope or rel_f in RECORD_FILES or re.search(scope, rel_f))):
                    report["undescribed"].append(os.path.relpath(p, root))

    for gi, f, path in attachments:
        dated = any(f.get(k) is not None for k in ("date", "start_date"))
        label = summaries.epoch(f)[2] if dated else None
        for product in f["attach_to"]:
            site = f.get("site")                # a report of one site attaches only to that site's items
            same_group = [i for i, (g2, p2, l2, s2) in placed.items() if g2 == gi and p2 == product]
            targets = [items[i] for i, (g2, p2, l2, s2) in placed.items()   # own group first, else any group
                       if (g2 == gi or not same_group) and p2 == product and (label is None or l2 == label)
                       and (site is None or s2 == site)]
            if not targets:
                report["unattached"].append(f"{path.name} -> {product}{f' {label}' if label else ''}")
            for item in targets:
                key = f["role"] if f["role"] not in item.assets else f"{f['role']}:{path.stem}"
                stac.add_file_asset(item, key, path, [f["role"]], path.name,
                                    "application/pdf" if path.suffix.lower() == ".pdf" else None)

    catalog = pystac.Catalog(s["dataset"], f"{s['title']}. Built from {Path(s['_path']).name}.")
    if s.get("doi"):
        catalog.extra_fields["beaver:doi"] = s["doi"]
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
