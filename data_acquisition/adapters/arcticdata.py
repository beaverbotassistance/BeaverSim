#!/usr/bin/env python3
"""NSF Arctic Data Center adapter: download datasets and describe them as a STAC catalog.

Layout on disk (one folder per DOI, files read-only, EML record kept as ``metadata.xml``)::

    <root>/arcticdata/doi_10.18739_<id>/<files>, metadata.xml
    <root>/downloads.csv                          one row per downloaded file

Site, date and product come from file names, because some datasets (ABON) hold many sites and
dates; licence, positioning, band names and checksums come from the EML record. Disagreements
between the EML and the file are kept as quality flags, never silently resolved.

    python -m data_acquisition.adapters.arcticdata download --root "<drive>/open_datasets" --preset arcticdata_seward
    python -m data_acquisition.adapters.arcticdata catalog  --root "<drive>/open_datasets" --preset arcticdata_seward
"""
import argparse
import csv
import datetime
import hashlib
import os
import re
import stat
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional

import pystac

from data_acquisition import presets
from data_acquisition.catalog import descriptors, stac

API = "https://arcticdata.io/metacat/d1/mn/v2"
CHUNK = 8 * 1024 * 1024
LOG_FIELDS = ["source", "doi", "file", "path", "bytes", "checksum_algorithm", "checksum", "licence",
              "dataset_title", "downloaded", "url"]

LICENCES = {"publicdomain/zero/1.0": "CC0-1.0", "licenses/by/4.0": "CC-BY-4.0",
            "licenses/by-nc/4.0": "CC-BY-NC-4.0", "licenses/by-sa/4.0": "CC-BY-SA-4.0"}
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun",
                                      "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
DATE_IN_NAME = re.compile(r"_(\d{1,2})([A-Za-z]{3})[a-z]*(\d{4})_")

# file-name token -> (platform, instrument, multispectral bands in file order)
SENSORS = [
    (r"_P4RTK_", "DJI Phantom 4 RTK", "FC6310R", None),
    (r"_P4_Multi[Ss]pectral_", "DJI P4 Multispectral", "P4M", ["blue", "green", "red", "rededge", "nir"]),
    (r"_M3_", "DJI Mavic 3 Multispectral", "M3M", ["green", "red", "rededge", "nir"]),
]
COMMON_NAMES = {"blue": "blue", "green": "green", "red": "red", "red edge": "rededge", "rededge": "rededge",
                "near infrared": "nir", "nir": "nir", "near-infrared": "nir"}


# ---------------------------------------------------------------- EML

def _text(el: Optional[ET.Element]) -> str:
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip() if el is not None else ""


def parse_eml(xml: str) -> Dict[str, Any]:
    """Title, DOI, licence, dates, bbox, methods text and data entities of an EML record."""
    root = ET.fromstring(xml)
    ds = root.find("dataset")
    rights = _text(ds.find("intellectualRights"))
    licence = next((spdx for key, spdx in LICENCES.items() if key in rights), None)
    dates = sorted(_text(e) for e in ds.iter("calendarDate"))
    bounds = {k: float(_text(ds.find(f".//{k}BoundingCoordinate"))) for k in ("west", "east", "north", "south")
              if ds.find(f".//{k}BoundingCoordinate") is not None}
    entities = {}
    for kind in ("otherEntity", "spatialRaster", "spatialVector", "dataTable"):
        for e in ds.iter(kind):
            name = _text(e.find("entityName"))
            auth = e.find(".//authentication")
            url = _text(e.find(".//url"))
            attributes = []
            for a in e.iter("attribute"):
                codes = [(_text(c.find("code")), _text(c.find("definition"))) for c in a.iter("codeDefinition")]
                attributes.append({"name": _text(a.find("attributeName")),
                                   "definition": _text(a.find("attributeDefinition")), "codes": codes})
            entities[name] = {
                "url": url, "pid": urllib.parse.unquote(url.rsplit("/resolve/", 1)[-1]) if url else None,
                "size": int(_text(e.find(".//size"))) if e.find(".//size") is not None else None,
                "checksum": (auth.get("method", "").lower(), _text(auth)) if auth is not None else None,
                "attributes": attributes}
    return {"package_id": root.get("packageId"), "title": _text(ds.find("title")), "licence": licence,
            "rights": rights, "dates": dates, "bounds": bounds,
            "methods": " ".join(_text(m) for m in ds.iter("methodStep")),
            "creators": [_text(c.find(".//surName")) for c in ds.findall("creator")],
            "entities": entities}


def positioning(methods: str) -> List[str]:
    """Positioning methods stated in the EML methods text."""
    found = []
    if re.search(r"D-RTK|Real[- ]Time Kinematic|\bRTK\b", methods):
        found.append("rtk")
    if re.search(r"\bPPK\b|post[- ]processed kinematic", methods, re.I):
        found.append("ppk")
    if re.search(r"ground control", methods, re.I):
        found.append("gcp")
    return found


def repository_bands(entity: Dict[str, Any]) -> List[str]:
    """Band names the EML gives for an entity (attribute names, or band codes), lower case."""
    names = [a["name"] for a in entity["attributes"] if a["name"].lower() not in ("elevation", "band type")]
    if not names:
        names = [d for a in entity["attributes"] for _, d in a["codes"]]
    return [n.lower() for n in names]


# ---------------------------------------------------------------- download

def _get(url: str, timeout: int = 120) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()


def _hash(path: Path, algorithm: str) -> str:
    h = hashlib.new(algorithm)
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def _fetch(url: str, dest: Path, size: Optional[int]) -> None:
    """Stream ``url`` to ``dest``, resuming a partial ``.part`` file."""
    part = dest.with_name(dest.name + ".part")
    have = part.stat().st_size if part.exists() else 0
    req = urllib.request.Request(url)
    if have:
        req.add_header("Range", f"bytes={have}-")
    with urllib.request.urlopen(req, timeout=300) as r, open(part, "ab" if have and r.status == 206 else "wb") as f:
        for block in iter(lambda: r.read(CHUNK), b""):
            f.write(block)
    if size is not None and part.stat().st_size != size:
        raise IOError(f"{dest.name}: got {part.stat().st_size} bytes, expected {size}")
    part.rename(dest)


def folder_of(root: Path, doi: str) -> Path:
    return root / "arcticdata" / re.sub(r"[^A-Za-z0-9._-]+", "_", doi)


def download(root: Path, doi: str, name_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """Download the files of ``doi`` (optionally filtered by name), verified against the EML checksum."""
    xml = _get(f"{API}/object/{urllib.parse.quote(doi, safe='')}").decode("utf-8", "replace")
    eml = parse_eml(xml)
    folder = folder_of(root, doi)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "metadata.xml").write_text(xml)
    rows = []
    for name, e in eml["entities"].items():
        if name_filter and not re.search(name_filter, name):
            continue
        path = folder / name
        if not path.exists():
            print(f"  downloading {name} ({(e['size'] or 0) / 1e9:.2f} GB)")
            _fetch(f"{API}/object/{urllib.parse.quote(e['pid'], safe='')}", path, e["size"])
        algorithm, expected = e["checksum"] or ("", "")
        actual = _hash(path, algorithm) if algorithm else ""
        if expected and actual != expected:
            raise IOError(f"{name}: {algorithm} mismatch")
        path.chmod(path.stat().st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
        print(f"  ok {name}")
        rows.append({"source": "arcticdata", "doi": doi, "file": name,
                     "path": os.path.relpath(path, root).replace(os.sep, "/"), "bytes": path.stat().st_size,
                     "checksum_algorithm": algorithm.upper(), "checksum": actual, "licence": eml["licence"],
                     "dataset_title": eml["title"], "downloaded": datetime.date.today().isoformat(),
                     "url": e["url"]})
    return rows


def log_downloads(root: Path, rows: List[Dict[str, Any]]) -> None:
    """Merge rows into ``downloads.csv`` (one row per file path)."""
    path = root / "downloads.csv"
    old = list(csv.DictReader(open(path, newline=""))) if path.exists() else []
    keep = [r for r in old if r["path"] not in {x["path"] for x in rows}]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, LOG_FIELDS)
        w.writeheader()
        w.writerows(keep + rows)


# ---------------------------------------------------------------- catalog

def parse_name(name: str) -> Optional[Dict[str, Any]]:
    """Product, date and sensor from an Arctic Data Center file name; None if not a product."""
    m = DATE_IN_NAME.search(name)
    if not m or m.group(2).lower() not in MONTHS:
        return None
    date = datetime.date(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1)))
    sensor = next(((p, i, b) for pattern, p, i, b in SENSORS if re.search(pattern, name)), (None, None, None))
    lower = name.lower()
    if lower.endswith(".pdf") and "report" in lower:
        product = "report"
    elif not lower.endswith((".tif", ".tiff")):
        return None
    elif "digital_surface_model" in lower:
        product = "dsm"
    elif "multispectral" in lower:
        product = "multispectral"
    elif "orthomosaic" in lower:
        product = "orthomosaic"
    else:
        return None
    return {"product": product, "date": date, "platform": sensor[0], "instrument": sensor[1],
            "ms_bands": sensor[2], "multispectral_report": "multispectral" in lower}


def _downloads(root: Path) -> Dict[str, Dict[str, str]]:
    path = root / "downloads.csv"
    return {r["path"]: r for r in csv.DictReader(open(path, newline=""))} if path.exists() else {}


def band_names(parsed: Dict[str, Any], entity: Dict[str, Any], colorinterp: List[str]) -> (List[Dict], List[tuple]):
    """Band names for a raster, and quality flags where the EML and the file disagree."""
    product, count = parsed["product"], len(colorinterp)
    repo = repository_bands(entity)
    flags = []
    if product == "dsm":
        names = ["elevation"]
        if repo:
            flags.append(("repository_band_conflict", f"repository describes bands {repo} for an elevation model"))
    elif product == "orthomosaic":
        names = [c for c in colorinterp if c in ("red", "green", "blue")]
        if len(names) != count:
            names = repo if len(repo) == count else [f"b{i + 1}" for i in range(count)]
        elif len(repo) != count:
            flags.append(("repository_band_conflict", f"repository describes {repo or 'no'} bands, the file has "
                                                      f"{count} declared as {names}; the file is used"))
        elif repo != names:
            flags.append(("band_order_conflict", f"repository lists {repo}, the file declares {names}; "
                                                 "the file is used, check visually"))
    else:
        sensor = parsed["ms_bands"] or []
        if len(repo) == count:
            names = [COMMON_NAMES.get(n, n) for n in repo]
        elif len(sensor) == count:
            names = sensor
            flags.append(("repository_band_conflict", f"repository describes {repo or 'no'} bands, the file has "
                                                      f"{count}; names from the sensor ({parsed['instrument']}) "
                                                      "and the methods text"))
        else:
            names = [f"b{i + 1}" for i in range(count)]
            flags.append(("unknown_bands", f"{count} bands, names unknown"))
    return [{"name": n, "common_name": n if n in COMMON_NAMES.values() else None} for n in names], flags


def build_catalog(root: Path, preset: Dict[str, Any]) -> (pystac.Catalog, List[str]):
    """STAC catalog of every downloaded file matching a preset site; returns (catalog, skipped files)."""
    downloads = _downloads(root)
    items: Dict[str, pystac.Item] = {}
    reports, skipped = [], []
    for folder in sorted((root / "arcticdata").glob("doi_*")):
        meta = folder / "metadata.xml"
        if not meta.exists():
            skipped.append(f"{folder.name}: no metadata.xml")
            continue
        eml = parse_eml(meta.read_text())
        for path in sorted(folder.iterdir()):
            if path.name == "metadata.xml" or path.name.endswith(".part"):
                continue
            parsed, site = parse_name(path.name), presets.match_site(preset, path.name)
            if not parsed or not site:
                skipped.append(f"{folder.name}/{path.name}: {'no site match' if parsed else 'not a product'}")
                continue
            slug, site_entry = site
            if parsed["product"] == "report":
                reports.append((slug, parsed, path, meta))
                continue
            item_id = f"{slug}_{parsed['date'].isoformat()}_{parsed['product']}"
            if item_id in items:
                raise ValueError(f"two files for {item_id}: {path}")
            entity = eml["entities"].get(path.name, {"attributes": [], "checksum": None, "url": None})
            algorithm, digest = entity["checksum"] or (None, None)
            checksum = stac.multihash(algorithm, digest) if algorithm in ("md5", "sha256") else None
            info = stac.raster_info(path)
            bands, flags = band_names(parsed, entity, info["colorinterp"])
            item = stac.raster_item(item_id, path, info, parsed["date"], parsed["product"], ["data"], bands,
                                    unit="m" if parsed["product"] == "dsm" else None,
                                    checksum=checksum, title=path.name)
            for flag, detail in flags:
                descriptors.add_quality(item, flag, detail, source="repository")
            item.common_metadata.platform = parsed["platform"]
            item.common_metadata.instruments = [parsed["instrument"]] if parsed["instrument"] else None
            stac.add_file_asset(item, "metadata", meta, ["metadata"], "EML record", "application/xml")
            if parsed["product"] == "dsm":
                item.properties["beaver:vertical_datum"] = ("WGS 84 ellipsoidal height"
                                                           if re.search(r"ellipsoid", path.name + eml["methods"], re.I)
                                                           else None)
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            dl = downloads.get(rel, {})
            descriptors.set_field(item, "site", slug, "auto", note=f"file name matches {site_entry['match']!r}")
            descriptors.set_field(item, "licence", eml["licence"], "repository")
            descriptors.set_field(item, "positioning", positioning(eml["methods"]) or None, "repository")
            doi = dl.get("doi") or re.sub(r"^doi_(10\.\d+)_", r"doi:\1/", folder.name)
            descriptors.set_field(item, "provenance", {
                "source": "arcticdata", "doi": doi, "package_id": eml["package_id"], "dataset_title": eml["title"],
                "creators": eml["creators"], "path": rel, "url": entity["url"] or dl.get("url"),
                "downloaded": dl.get("downloaded"),
                "checksum": f"{algorithm}:{digest}" if algorithm else None}, "repository")
            items[item_id] = item

    for slug, parsed, path, meta in reports:
        products = ["multispectral"] if parsed["multispectral_report"] else ["orthomosaic", "dsm"]
        for product in products:
            item = items.get(f"{slug}_{parsed['date'].isoformat()}_{product}")
            if item:
                stac.add_file_asset(item, "report", path, ["metadata"], "processing report", "application/pdf")
            else:
                skipped.append(f"{path.name}: no {product} item for the report")

    catalog = pystac.Catalog("arcticdata", f"{preset['title']}. Built by data_acquisition.adapters.arcticdata.")
    for slug in sorted({descriptors.get_field(i, "site") for i in items.values()}):
        site_items = sorted((i for i in items.values() if descriptors.get_field(i, "site") == slug),
                            key=lambda i: (i.datetime, i.id))
        licences = {descriptors.get_field(i, "licence") for i in site_items}
        collection = pystac.Collection(
            slug, preset["sites"][slug]["name"],
            pystac.Extent.from_items(site_items), license=licences.pop() if len(licences) == 1 else "various",
            providers=[pystac.Provider("NSF Arctic Data Center", roles=["host"], url="https://arcticdata.io")])
        collection.add_items(site_items)
        catalog.add_child(collection)
    return catalog, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("command", choices=["download", "catalog"])
    parser.add_argument("--root", required=True, type=Path, help="open_datasets folder")
    parser.add_argument("--preset", required=True, help="preset name or YAML path")
    parser.add_argument("--out", type=Path, default=None, help="catalog folder (default <root>/stac/<dataset>)")
    args = parser.parse_args()
    preset = presets.load(args.preset)
    if args.command == "download":
        for doi, name_filter in preset["downloads"].items():
            print(doi)
            log_downloads(args.root, download(args.root, doi, name_filter))
        return
    catalog, skipped = build_catalog(args.root, preset)
    out = stac.save(catalog, args.out or args.root / "stac" / preset["dataset"])
    n = len(list(catalog.get_items(recursive=True)))
    print(f"{n} items -> {out}")
    for s in skipped:
        print(f"  skipped {s}")


if __name__ == "__main__":
    main()
