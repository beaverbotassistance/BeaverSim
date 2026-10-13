"""Dataset summary files: what the files and their standard metadata can't tell us, as data.

One YAML file per dataset, under ``data_acquisition/summaries/``. Everything source- or
site-specific (file naming, which report belongs to which product, band names a repository got
wrong) is written here, so the builder and readers stay generic. Layout::

    schema: 1
    dataset, title
    authored: {by, date[, model, note]}      who wrote the file (a person, or claude + model)
    reviewed: {by, date} | null              a person who checked it; until then values count as "claude"
    source:   {kind, provider, url[, api, log]}
    sites:    {<slug>: {name, crs, colonies, land_status, governance[, confirmed, hints]}}
    groups:   - folder, [doi], [record: {path, format}], <file fields as group defaults>, [evidence], files: [...]
    open_questions: [...]                    optional: what the author could not settle from the evidence

``evidence`` (per group) lists where the values came from; ``hints`` (per site) holds suggestions for
the manual fields, which only a person may set.

File fields (on a file, or on its group as a default):
    path, product (data files) or role + attach_to (reports, extra metadata),
    variant (short slug, when two files share site, time and product, e.g. two DEM-of-difference methods),
    site, date, platform, instruments, positioning, bands, unit, vertical_datum, notes

Products: orthomosaic, multispectral, dsm, dtm, chm (canopy height model), dod (DEM of difference),
uncertainty (precision or error maps), photos, annotations.

Time of a data file, one of:
    date: YYYY-MM-DD                          one acquisition (the usual case)
    date + date_precision: month | year       only the month or year is known (e.g. a lidar composite);
                                              with year, ``date: 2017`` is enough
    start_date + end_date                     a product spanning two epochs (e.g. a DEM of difference)

A report or metadata file (``role``) attaches to the items of its group whose product is in
``attach_to`` and whose date matches its own; without a date (its own or the group's) it attaches to
all of them, e.g. a README or a ground-control file shared by every survey.

Archives: a repository that publishes a zip lists only the zip. Extract it with
``data_acquisition.sources.archives`` (verified against the zip's CRC-32, read-only), list the zip with
``role: archive``, and give each extracted file ``archive: <path of the zip>`` (or set it on the group).
Sidecars of a described raster (``.ovr``, ``.aux.xml``, ``.tfw``, ``.tfwx``, ``.msk``, ``.prj``) need not be listed.

``bands`` names the bands in file order for any product, including elevation products whose extra
bands are not elevations (e.g. ``[elevation, uncertainty]``).

Manual site fields are ``null`` (unknown) or ``{value, by, date[, note]}``.
"""
import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

HERE = Path(__file__).resolve().parent.parent / "summaries"
SCHEMA = 1
PRODUCTS = {"orthomosaic", "multispectral", "dsm", "dtm", "chm", "dod", "uncertainty", "photos", "annotations"}
PRECISIONS = ("day", "month", "year")
ROLES = {"report", "metadata", "archive"}
SIDECARS = (".ovr", ".aux.xml", ".tfw", ".tfwx", ".msk", ".prj")   # GDAL/ArcGIS sidecars of a raster
POSITIONING = {"rtk", "ppk", "gcp", "gnss", "none"}
FILE_FIELDS = {"path", "product", "variant", "role", "attach_to", "archive", "site", "date", "date_precision",
               "start_date", "end_date",
               "platform", "instruments", "positioning", "bands", "unit", "vertical_datum", "notes"}
GROUP_FIELDS = FILE_FIELDS - {"path", "product", "variant", "role", "attach_to"} | {"folder", "doi", "record", "download_filter",
                                                                         "files", "evidence"}
MANUAL_SITE_FIELDS = ("colonies", "land_status", "governance", "confirmed")


def load(name_or_path: str) -> Dict[str, Any]:
    """Load and check a summary by name (``arcticdata_seward``) or path. Raises ValueError listing problems."""
    path = Path(name_or_path)
    if not path.suffix:
        path = HERE / f"{name_or_path}.yaml"
    with open(path) as f:
        summary = yaml.safe_load(f)
    problems = check(summary)
    if problems:
        raise ValueError(f"{path}:\n  " + "\n  ".join(problems))
    summary["_path"] = str(path)
    return summary


def check(s: Dict[str, Any]) -> List[str]:
    """Schema problems of a summary (empty when valid)."""
    p = []
    if s.get("schema") != SCHEMA:
        p.append(f"schema must be {SCHEMA}")
    for key in ("dataset", "title", "authored", "source", "sites", "groups"):
        if not s.get(key):
            p.append(f"missing {key}")
    if p:
        return p
    for who in ("authored", "reviewed"):
        if s.get(who) is not None and not (isinstance(s[who], dict) and s[who].get("by") and s[who].get("date")):
            p.append(f"{who} needs by and date")
    for slug, site in s["sites"].items():
        if not str(site.get("crs", "")).startswith("EPSG:"):
            p.append(f"site {slug}: crs must be EPSG:<code>")
        for field in MANUAL_SITE_FIELDS:
            v = site.get(field)
            if v is not None and not (isinstance(v, dict) and v.get("by") and ("value" in v or field == "confirmed")):
                p.append(f"site {slug}: {field} must be null or {{value, by, date}}")
    seen: Dict[tuple, str] = {}
    for i, g in enumerate(s["groups"]):
        where = f"group {i} ({g.get('folder')})"
        p += [f"{where}: unknown field {k}" for k in set(g) - GROUP_FIELDS]
        if not g.get("folder") or not g.get("files"):
            p.append(f"{where}: needs folder and files")
            continue
        for f in g["files"]:
            fw = f"{where} {f.get('path')}"
            p += [f"{fw}: unknown field {k}" for k in set(f) - FILE_FIELDS]
            merged = resolve(g, f)
            if bool(f.get("product")) == bool(f.get("role")):
                p.append(f"{fw}: needs exactly one of product or role")
            elif f.get("product") and f["product"] not in PRODUCTS:
                p.append(f"{fw}: product must be one of {sorted(PRODUCTS)}")
            elif f.get("role") and (f["role"] not in ROLES or not f.get("attach_to")):
                p.append(f"{fw}: role must be one of {sorted(ROLES)} with attach_to")
            if f.get("product"):
                if merged.get("site") not in s["sites"]:
                    p.append(f"{fw}: site {merged.get('site')!r} not in sites")
                try:
                    key = (merged.get("site"), epoch(merged)[2], f["product"], f.get("variant"))
                    if key in seen:
                        p.append(f"{fw}: same site, time and product as {seen[key]}; give each a variant")
                    seen[key] = f.get("path")
                except ValueError as e:
                    p.append(f"{fw}: {e}")
                if set(merged.get("positioning") or []) - POSITIONING:
                    p.append(f"{fw}: positioning must be from {sorted(POSITIONING)}")
    return p


def epoch(f: Dict[str, Any]) -> (datetime.date, datetime.date, str):
    """(start, end, label) of a file's time: one day, a month, a year, or a start–end range.

    The label is used in item ids: ``2018-09-25``, ``2017-09``, ``2017``, ``2017-09-07_2018-09-25``.
    """
    if f.get("start_date") is not None or f.get("end_date") is not None:
        start, end = f.get("start_date"), f.get("end_date")
        if not (isinstance(start, datetime.date) and isinstance(end, datetime.date)) or start > end:
            raise ValueError("start_date and end_date must both be YYYY-MM-DD, start first")
        return start, end, f"{start.isoformat()}_{end.isoformat()}"
    precision, d = f.get("date_precision") or "day", f.get("date")
    if precision not in PRECISIONS:
        raise ValueError(f"date_precision must be one of {PRECISIONS}")
    if precision == "year" and isinstance(d, int):
        d = datetime.date(d, 1, 1)
    if not isinstance(d, datetime.date):
        raise ValueError("date must be YYYY-MM-DD (or a year with date_precision: year)")
    if precision == "year":
        return datetime.date(d.year, 1, 1), datetime.date(d.year, 12, 31), f"{d.year}"
    if precision == "month":
        nxt = datetime.date(d.year + d.month // 12, d.month % 12 + 1, 1)
        return datetime.date(d.year, d.month, 1), nxt - datetime.timedelta(days=1), f"{d.year}-{d.month:02d}"
    return d, d, d.isoformat()


def resolve(group: Dict[str, Any], file: Dict[str, Any]) -> Dict[str, Any]:
    """File fields with group defaults filled in; notes add up (group notes, then the file's)."""
    merged = {k: v for k, v in group.items() if k in FILE_FIELDS}
    merged.update(file)
    merged["notes"] = list(group.get("notes") or []) + list(file.get("notes") or [])
    return merged


def author(s: Dict[str, Any]) -> (str, Dict[str, Optional[str]]):
    """Descriptor source and who/when for values taken from this summary."""
    if s.get("reviewed"):
        return "manual", {"by": s["reviewed"]["by"], "date": str(s["reviewed"]["date"])}
    a = s["authored"]
    if a["by"] == "claude":
        return "claude", {"by": f"claude ({a.get('model', 'unknown model')})", "date": str(a["date"])}
    return "manual", {"by": a["by"], "date": str(a["date"])}
