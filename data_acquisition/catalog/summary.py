"""Dataset summary files: what the files and their standard metadata can't tell us, as data.

One YAML file per dataset, under ``data_acquisition/summaries/``. Everything source- or
site-specific (file naming, which report belongs to which product, band names a repository got
wrong) is written here, so the builder and readers stay generic. Layout::

    schema: 1
    dataset, title
    authored: {by, date[, model, note]}      who wrote the file (a person, or claude + model)
    reviewed: {by, date} | null              a person who checked it; until then values count as "claude"
    source:   {kind, provider, url[, api, log]}
    sites:    {<slug>: {name, crs, colonies, land_status, governance[, confirmed]}}
    groups:   - folder, [doi], [record: {path, format}], <file fields as group defaults>, files: [...]

File fields (on a file, or on its group as a default):
    path, product (data files) or role + attach_to (reports, extra metadata),
    site, date, platform, instruments, positioning, bands, unit, vertical_datum, notes

Manual site fields are ``null`` (unknown) or ``{value, by, date[, note]}``.
"""
import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

HERE = Path(__file__).resolve().parent.parent / "summaries"
SCHEMA = 1
PRODUCTS = {"orthomosaic", "dsm", "dtm", "multispectral", "photos", "annotations"}
ROLES = {"report", "metadata"}
POSITIONING = {"rtk", "ppk", "gcp", "gnss", "none"}
FILE_FIELDS = {"path", "product", "role", "attach_to", "site", "date", "platform", "instruments", "positioning",
               "bands", "unit", "vertical_datum", "notes"}
GROUP_FIELDS = FILE_FIELDS - {"path", "product", "role", "attach_to"} | {"folder", "doi", "record", "download_filter",
                                                                         "files"}
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
        if s.get(who) is not None and not (s[who].get("by") and s[who].get("date")):
            p.append(f"{who} needs by and date")
    for slug, site in s["sites"].items():
        if not str(site.get("crs", "")).startswith("EPSG:"):
            p.append(f"site {slug}: crs must be EPSG:<code>")
        for field in MANUAL_SITE_FIELDS:
            v = site.get(field)
            if v is not None and not (isinstance(v, dict) and v.get("by") and ("value" in v or field == "confirmed")):
                p.append(f"site {slug}: {field} must be null or {{value, by, date}}")
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
                if not isinstance(merged.get("date"), datetime.date):
                    p.append(f"{fw}: date must be YYYY-MM-DD")
                if set(merged.get("positioning") or []) - POSITIONING:
                    p.append(f"{fw}: positioning must be from {sorted(POSITIONING)}")
    return p


def resolve(group: Dict[str, Any], file: Dict[str, Any]) -> Dict[str, Any]:
    """File fields with group defaults filled in."""
    merged = {k: v for k, v in group.items() if k in FILE_FIELDS}
    merged.update(file)
    return merged


def author(s: Dict[str, Any]) -> (str, Dict[str, Optional[str]]):
    """Descriptor source and who/when for values taken from this summary."""
    if s.get("reviewed"):
        return "manual", {"by": s["reviewed"]["by"], "date": str(s["reviewed"]["date"])}
    a = s["authored"]
    if a["by"] == "claude":
        return "claude", {"by": f"claude ({a.get('model', 'unknown model')})", "date": str(a["date"])}
    return "manual", {"by": a["by"], "date": str(a["date"])}
