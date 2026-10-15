#!/usr/bin/env python3
"""Build a STAC catalog from a data root and a dataset summary. Generic: no source or site logic.

For each file the summary describes, the reader for its type gives the header facts, the group's
standard metadata record (if any) gives licence, checksum and repository descriptions, and the
summary gives everything else. Disagreements between the three are flagged on the item, never
resolved silently. Files on disk that the summary doesn't describe are reported.

    python -m data_acquisition.catalog.build --root "<drive>/open_datasets" --summary arcticdata_seward
"""
import argparse
import calendar
import functools
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pystac

from data_acquisition.catalog import descriptors, stac
from data_acquisition.catalog import summary as summaries
from data_acquisition.catalog.descriptors import add_quality, set_field
from data_acquisition.readers import RECORD_FILES, RECORDS, entity_bands, files, geotiff, photos, table, vector
from data_acquisition.sources import downloads

COMMON_NAMES = {"blue": "blue", "green": "green", "red": "red", "red edge": "rededge", "rededge": "rededge",
                "near infrared": "nir", "near-infrared": "nir", "nir": "nir"}
# products measured in metres, and the default name of their bands when the summary gives none
METRIC_BANDS = {"dsm": "elevation", "dtm": "elevation", "chm": "canopy_height", "dod": "elevation_change",
                "uncertainty": "uncertainty"}
REPORT = ("missing", "undescribed", "unsupported", "unattached", "unmatched_layers")
Flag = Tuple[str, str, str]                 # (flag, detail, source)


# ---------------------------------------------------------------- helpers

def _bands(product: str, wanted: Optional[List[str]], header: Dict[str, Any],
           entity: Optional[Dict[str, Any]]) -> Tuple[List[str], List[Flag]]:
    """Band names (summary, else declared by the file), and flags where summary, file and record disagree."""
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
        repo = [COMMON_NAMES.get(n, n) for n in entity_bands(entity)]
        expected = [] if product in METRIC_BANDS else [n for n in names if n != "alpha"]
        if repo != expected:
            flag = "band_order_conflict" if sorted(repo) == sorted(expected) else "repository_band_conflict"
            flags.append((flag, f"repository describes {repo or 'no'} bands; using {expected or 'none'} "
                                f"({'summary' if wanted else 'file'})", "repository"))
    return names, flags


def _period(dates: List[str]) -> Tuple[Optional[str], Optional[str]]:
    """First and last day of a record's dates, which may be whole years (``2001``) or months (``2024-06``)."""
    if not dates:
        return None, None
    first, last = dates[0], dates[-1]
    first = {4: first + "-01-01", 7: first + "-01"}.get(len(first), first)
    if len(last) == 4:
        last += "-12-31"
    elif len(last) == 7:
        last += f"-{calendar.monthrange(int(last[:4]), int(last[5:7]))[1]:02d}"
    return first[:10], last[:10]


@functools.lru_cache(maxsize=None)
def _vector_info(path: Path) -> Dict[str, Any]:
    return vector.info(path)        # read once per build, also when one file gives one item per layer


def _checksum(algorithm: Optional[str], value: Optional[str]) -> Optional[Dict[str, str]]:
    return {"algorithm": algorithm, "value": value} if algorithm and value else None


# ---------------------------------------------------------------- one item per data type

def _table_item(s, f, path, item_id, start, end, checksum) -> Tuple[pystac.Item, Dict[str, Any], List[Flag]]:
    """A CSV: a point layer (CRS from the summary or the site), or rows without geometry."""
    crs = f.get("crs") or s["sites"][f["site"]]["crs"]
    layers = table.info(path, f["table"], crs)
    item = stac.vector_item(item_id, path, layers, start, end, f["product"], ["data"], checksum, title=path.name)
    item.assets[f["product"]].media_type = "text/csv"
    item.properties["beaver:table"] = f["table"]
    if layers.get("spatial", True):
        item.properties["beaver:crs_from_summary"] = crs
        return item, layers, [("crs_from_summary", f"the table states no CRS; {crs} from the "
                                                   f"{'summary' if f.get('crs') else 'site'}", "build")]
    return item, layers, [("non_spatial", f"a table of {layers['features']} rows without coordinates; no footprint, "
                                          "site from the summary", "build")]


def _vector_item(f, path, item_id, start, end, checksum, layer) -> Tuple[pystac.Item, Dict[str, Any], List[Flag]]:
    """A vector file, or one ``layer`` of it."""
    layers = vector.one_layer(_vector_info(path), layer) if layer else _vector_info(path)
    item = stac.vector_item(item_id, path, layers, start, end, f["product"], ["data"], checksum,
                            title=f"{path.name}, layer {layer}" if layer else path.name)
    if layer:
        item.properties["beaver:layer"] = layer
    if layers["vertical_crs"]:
        item.properties["beaver:vertical_crs"] = layers["vertical_crs"]
    return item, layers, []


def _raster_item(f, path, item_id, start, end, checksum, entity) -> Tuple[pystac.Item, List[Flag]]:
    """A raster, its CRS from the summary when the file declares none."""
    header, flags = geotiff.info(path), []
    if not header["has_crs"]:
        if not f.get("crs"):
            raise ValueError("the raster declares no CRS; give `crs` in the summary")
        header["epsg"], header["crs"] = int(f["crs"].split(":")[1]), f["crs"]
        flags.append(("crs_from_summary", f"the raster declares no CRS; {f['crs']} from the summary", "build"))
    names, band_flags = _bands(f["product"], f.get("bands"), header, entity)
    bands = [{"name": n, "common_name": n if n in COMMON_NAMES.values() else None} for n in names]
    item = stac.raster_item(item_id, path, header, start, end, f["product"], ["data"], bands, title=path.name,
                            unit=f.get("unit") or ("m" if f["product"] in METRIC_BANDS else None), checksum=checksum)
    if not header["has_crs"]:
        item.properties["beaver:crs_from_summary"] = f["crs"]
    if path.suffix.lower() not in geotiff.EXTENSIONS:
        item.assets[f["product"]].media_type = None      # not a GeoTIFF; the GDAL driver is recorded instead
        item.assets[f["product"]].extra_fields["beaver:driver"] = header["driver"]
    return item, flags + band_flags


def _photos_item(f, path, item_id, start, end) -> Tuple[pystac.Item, List[Flag]]:
    """A folder of photos: one survey's flights."""
    info = photos.info(path)
    item = stac.photos_item(item_id, path, info, start, end, f["product"], ["data"], title=f"{path.name}/")
    flags = []
    if info["first"] and not (start <= info["first"].date() and info["last"].date() <= end):
        flags.append(("photo_dates", f"photos taken {info['first']:%Y-%m-%d}..{info['last']:%Y-%m-%d}, outside "
                                     f"the item's {start}..{end}", "build"))
    if info["no_position"]:
        flags.append(("photos_without_position", f"{len(info['no_position'])} of {info['count']} photos have no GPS "
                                                 "position; the footprint is from the others", "build"))
    if info["unreadable"]:
        flags.append(("photos_unreadable", f"EXIF unreadable in {len(info['unreadable'])} photos: "
                                           f"{', '.join(info['unreadable'][:5])}", "build"))
    return item, flags


def _fields_flags(f, layers) -> List[Flag]:
    """Declared attribute columns (``fields``) that the file does not have."""
    columns = {c for l in layers["layers"] for c in l["fields"]}
    named = [c for v in f["fields"].values() for c in ([v] if isinstance(v, str) else v)]
    absent = [c for c in named if c not in columns]
    return [("fields_missing", f"declared columns {absent} are not in the file (columns: {sorted(columns)})",
             "build")] if absent else []


def _record_flags(f, path, entity, record, archive, start, end, label) -> List[Flag]:
    """Where the file disagrees with its group's metadata record."""
    flags = []
    if entity is None:
        flags.append(("not_in_record", "the metadata record does not list this file", "repository"))
    elif not archive and path.is_file() and entity["size"] is not None and entity.get("size_exact", True) \
            and entity["size"] != path.stat().st_size:
        flags.append(("size_mismatch", f"record {entity['size']} bytes, file {path.stat().st_size}", "repository"))
    first, last = _period(record["dates"])
    if first:
        # a precise date (or span) must lie within the record's period; a month or year must only overlap it
        if (f.get("date_precision") or "day") == "day":
            outside = not first <= start.isoformat() <= end.isoformat() <= last
        else:
            outside = end.isoformat() < first or start.isoformat() > last
        if outside:
            flags.append(("date_outside_record", f"{label} not within {first}..{last}", "repository"))
    return flags


def _provenance(s, group, record, entity, log_row, rel, archive) -> Dict[str, Any]:
    """Where the file came from: source, identifiers, link, download, checksums, and the summary used."""
    algorithm, value = (entity or {}).get("checksum") or (None, None)
    provenance = {"source": s["source"]["provider"], "doi": group.get("doi"),
                  "package_id": record["package_id"] if record else None,
                  "dataset_title": record["title"] if record else s["title"],
                  "creators": record["creators"] if record else None, "path": rel,
                  "url": (entity or {}).get("url") or log_row.get("url"), "downloaded": log_row.get("downloaded"),
                  "checksum": None if archive else _checksum(algorithm, value), "summary": Path(s["_path"]).name}
    if record and record.get("concept_id"):
        provenance["concept_id"] = record["concept_id"]
    if s.get("doi") and s.get("doi") != group.get("doi"):
        provenance["dataset_doi"] = s["doi"]
    if log_row.get("checksum") and not archive:
        provenance["download_checksum"] = _checksum(log_row["checksum_algorithm"].lower(), log_row["checksum"])
        provenance["download_verified_by"] = log_row.get("verified_by") or "record checksum"
    if archive:
        provenance.update({"archive": f"{group['folder']}/{archive}", "archive_checksum": _checksum(algorithm, value),
                           "extracted": "CRC-32 verified against the archive (data_acquisition.sources.archives)"})
    return provenance


def data_item(s: Dict[str, Any], f: Dict[str, Any], path: Path, rel: str, group: Dict[str, Any],
              record: Optional[Dict[str, Any]], log: Dict[str, Dict[str, str]],
              layer: Optional[str] = None) -> pystac.Item:
    """Item for a data file (raster, vector or table), or for one ``layer`` of a vector file: header facts
    from its reader, the rest from the summary and the record, with flags where they disagree."""
    source, who = summaries.author(s)
    start, end, label = summaries.epoch(f)
    item_id = f"{f['site']}_{label}_{f['product']}" + (f"_{f['variant']}" if f.get("variant") else "")
    archive = f.get("archive")
    entity = record["entities"].get(archive or path.name) if record else None   # an extracted file: the archive's
    algorithm, value = (entity or {}).get("checksum") or (None, None)
    checksum = stac.multihash(algorithm, value) if algorithm in stac.MULTIHASH and not archive else None

    layers = None
    if f["product"] == "photos" and path.is_dir():
        kind = "photos"
        item, flags = _photos_item(f, path, item_id, start, end)
    elif f.get("table"):
        kind = "table"
        item, layers, flags = _table_item(s, f, path, item_id, start, end, checksum)
    elif vector.is_vector(path):
        kind = "vector"
        item, layers, flags = _vector_item(f, path, item_id, start, end, checksum, layer)
    else:
        kind = "raster"
        item, flags = _raster_item(f, path, item_id, start, end, checksum, entity)
    item.properties["beaver:kind"] = kind
    if f.get("fields") and layers is not None:      # meaning of attribute columns
        item.properties["beaver:fields"] = f["fields"]
        flags += _fields_flags(f, layers)
    if record is not None:
        flags += _record_flags(f, path, entity, record, archive, start, end, label)
    flags += [("note", note, source) for note in f.get("notes") or []]
    if f.get("inspect"):
        flags.append(("needs_inspection", f["inspect"], source))
    if f.get("date_precision") == "unknown":
        flags.append(("date_unknown", f"acquisition date not known; only its limits {start}..{end}", "build"))
    for flag, detail, flag_source in flags:
        add_quality(item, flag, detail, source=flag_source)

    item.common_metadata.platform = f.get("platform")
    item.common_metadata.instruments = f.get("instruments")
    if (f.get("date_precision") or "day") != "day":
        item.properties["beaver:date_precision"] = f["date_precision"]
    if f.get("vertical_datum"):
        item.properties["beaver:vertical_datum"] = f["vertical_datum"]
    set_field(item, "site", f["site"], source, **who)
    set_field(item, "positioning", f.get("positioning"), source, **who)
    if record is not None:
        set_field(item, "licence", record["licence"], "repository")
    else:
        item.properties.setdefault("beaver:licence", None)
    provenance = _provenance(s, group, record, entity, log.get(rel, {}), rel, archive)
    set_field(item, "provenance", provenance, "repository" if record else source, **({} if record else who))
    return item


# ---------------------------------------------------------------- the catalog

def _undescribed(folder: Path, root: Path, described: set, group: Dict[str, Any]) -> List[str]:
    """Files in ``folder`` that the group does not describe: not listed, not a companion of a listed file,
    not inside a listed geodatabase or folder of photos, and within the group's ``download_filter`` when it
    has one (files outside it belong to another summary)."""
    covered = described | {c for d in described for c in files.companions(d)}
    folders = tuple(d.rstrip("/") + "/" for d in described if (folder / d).is_dir())   # e.g. a folder of photos
    scope = group.get("download_filter")
    out = []
    for p in sorted(folder.rglob("*")):
        rel = p.relative_to(folder).as_posix()
        if (p.is_file() and rel not in covered and not rel.startswith(folders) and not p.name.endswith(".part")
                and not files.inside_container(rel) and (not scope or rel in RECORD_FILES or re.search(scope, rel))):
            out.append(os.path.relpath(p, root))
    return out


def _attach(attachments, items, placed, report) -> None:
    """Attach reports and extra metadata to the items they belong to: same group first (else any group),
    the product in ``attach_to``, the same date when the file has one, the same site when it names one."""
    for gi, f, path in attachments:
        label = summaries.epoch(f)[2] if any(f.get(k) is not None for k in ("date", "start_date")) else None
        for product in f["attach_to"]:
            same_group = [i for i, (g, p, _, _) in placed.items() if g == gi and p == product]
            targets = [items[i] for i, (g, p, l, site) in placed.items()
                       if (g == gi or not same_group) and p == product and (label is None or l == label)
                       and (f.get("site") is None or site == f.get("site"))]
            if not targets:
                report["unattached"].append(f"{path.name} -> {product}{f' {label}' if label else ''}")
            for item in targets:
                key = f["role"] if f["role"] not in item.assets else f"{f['role']}:{path.stem}"
                stac.add_file_asset(item, key, path, [f["role"]], path.name,
                                    "application/pdf" if path.suffix.lower() == ".pdf" else None)


def build(root: Path, s: Dict[str, Any]) -> Tuple[pystac.Catalog, Dict[str, List[str]]]:
    """Catalog of the files ``s`` describes under ``root``, and a report of problems."""
    log = downloads.read_log(root / s["source"]["log"]) if s["source"].get("log") else {}
    report: Dict[str, List[str]] = {k: [] for k in REPORT}
    _vector_info.cache_clear()
    items: Dict[str, pystac.Item] = {}
    placed: Dict[str, tuple] = {}          # item id -> (group index, product, epoch label, site)
    attachments = []

    def place(item: pystac.Item, gi: int, f: Dict[str, Any], g: Dict[str, Any], folder: Path, rel: str) -> None:
        if item.id in items:
            raise ValueError(f"two files (or layers) for {item.id}: {rel}")
        if g.get("record"):
            fmt = g["record"]["format"]
            stac.add_file_asset(item, "metadata", folder / g["record"]["path"], ["metadata"], f"{fmt} record",
                                RECORDS[fmt]["media"])
        items[item.id] = item
        placed[item.id] = (gi, f["product"], summaries.epoch(f)[2], f["site"])

    for gi, g in enumerate(s["groups"]):
        folder = root / g["folder"]
        record, described = None, set()
        if g.get("record"):
            described.add(g["record"]["path"])
            record = RECORDS[g["record"]["format"]]["read"]((folder / g["record"]["path"]).read_text())
        for file in g["files"]:
            f = summaries.resolve(g, file)
            path = folder / f["path"]
            described.add(f["path"])
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
                    place(data_item(s, lf, path, rel, g, record, log, layer=layer["name"]), gi, lf, g, folder, rel)
            elif f.get("table") or geotiff.is_raster(path) or vector.is_vector(path) or photos.is_photo_folder(path):
                try:
                    item = data_item(s, f, path, rel, g, record, log)
                except (ValueError, KeyError) as e:
                    report["unsupported"].append(f"{rel}: {e}")
                    continue
                place(item, gi, f, g, folder, rel)
            else:
                report["unsupported"].append(rel)
        if folder.exists():
            report["undescribed"] += _undescribed(folder, root, described, g)
    _attach(attachments, items, placed, report)

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
