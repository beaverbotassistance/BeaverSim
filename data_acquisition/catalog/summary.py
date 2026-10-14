"""Dataset summary files: what the files and their standard metadata can't tell us, as data.

One YAML file per dataset, under ``data_acquisition/summaries/``. Everything source- or
site-specific (file naming, which report belongs to which product, band names a repository got
wrong) is written here, so the builder and readers stay generic. Layout::

    schema: 1
    dataset, title, [doi]                    doi: the dataset as a whole (e.g. a collection whose members are the groups)
    authored: {by, date[, model, note]}      who wrote the file (a person, or claude + model)
    reviewed: {by, date} | null              a person who checked it; until then values count as "claude"
    source:   {kind, provider, url[, api, log]}
    sites:    {<slug>: {hints}}               this dataset's hints for the manual site fields (optional)
    groups:   - folder, [doi], [record: {path, format}], <file fields as group defaults>, [evidence], files: [...]
    open_questions: [...]                    optional: what the author could not settle from the evidence

``evidence`` (per group) lists where the values came from; ``hints`` (per site) holds suggestions for
the manual fields, which only a person may set.

File fields (on a file, or on its group as a default):
    path, product (data files) or role + attach_to (reports, extra metadata),
    variant (short slug, when two files share site, time and product, e.g. two DEM-of-difference methods),
    site, date, platform, instruments, positioning, bands, unit, vertical_datum, notes

Products: orthomosaic, multispectral, dsm, dtm, chm (canopy height model), dod (DEM of difference),
uncertainty (precision or error maps), photos; vector products: annotations (features mapped by people
from imagery or in the field: dams, lodges, ponds, canals, colony outlines), survey_points (surveyed
points: ground control, topographic survey), model_output (model results, e.g. BRAT reach capacities).
A vector file with several layers is one item; its layers are listed in the catalog.

Time of a data file, one of:
    date: YYYY-MM-DD                          one acquisition (the usual case)
    date + date_precision: month | year       only the month or year is known (e.g. a lidar composite);
                                              with year, ``date: 2017`` is enough
    start_date + end_date                     a product spanning two epochs (e.g. a DEM of difference)

A report or metadata file (``role``) attaches to the items of its group whose product is in
``attach_to`` and whose date matches its own; without a date (its own or the group's) it attaches to
all of them, e.g. a README or a ground-control file shared by every survey.

Scope: a group's ``download_filter`` (regex on file names) is also the set of files it covers. Files in its
folder that do not match belong to another summary and are not reported as undescribed, so two
summaries can share a folder (e.g. one site of a multi-site record, and the record's other sites).

Archives: a repository that publishes a zip lists only the zip. Extract it with
``data_acquisition.sources.archives`` (verified against the zip's CRC-32, read-only), list the zip with
``role: archive``, and give each extracted file ``archive: <path of the zip>`` (or set it on the group).
Sidecars of a described raster (``.ovr``, ``.aux.xml``, ``.tfw``, ``.tfwx``, ``.msk``, ``.prj``) need not be listed.

CRS a file does not declare: ``crs: EPSG:<code>`` on the file (or group), taken from the record or its text;
used only when the file has no CRS of its own, and flagged in the catalog as coming from the summary.

Vector files whose layers are separate epochs (e.g. one layer of dams per year):
``layers: {pattern, date_precision}``, where ``pattern`` is a regex on layer names with one group capturing
the layer's time (``2012``, ``2012-07`` / ``201207``, ``2012-07-08`` / ``20120708``, as the precision says).
Each matching layer becomes its own item, dated by its name; layers that do not match are reported.

Tables of points (CSV): ``table: {skip, x, y[, z, delimiter]}`` gives the lines to skip above the column
names and the coordinate columns; with ``crs`` (or the site CRS), the rows become a point layer.

A report or metadata file attaches to items of its own group; when its group has none of the products in
``attach_to`` (e.g. a group holding only a time series), it attaches to matching items of any group.

``bands`` names the bands in file order for any product, including elevation products whose extra
bands are not elevations (e.g. ``[elevation, uncertainty]``).

Sites are defined once, in the registry ``data_acquisition/sites.yaml``: ``{<slug>: {name, crs, colonies,
land_status, governance[, confirmed]}}``. Manual site fields are ``null`` (unknown) or
``{value, by, date[, note]}``. A summary refers to sites by slug; :func:`load` fills in each site it uses from
the registry, so ``summary["sites"][slug]`` has the registry fields plus this summary's ``hints``.
"""
import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

HERE = Path(__file__).resolve().parent.parent / "summaries"
SITES = HERE.parent / "sites.yaml"          # the site registry
SCHEMA = 1
PRODUCTS = {"orthomosaic", "multispectral", "dsm", "dtm", "chm", "dod", "uncertainty", "photos",
            "annotations", "survey_points", "model_output"}
PRECISIONS = ("day", "month", "year")
ROLES = {"report", "metadata", "archive"}
SIDECARS = (".ovr", ".aux.xml", ".tfw", ".tfwx", ".msk", ".prj")   # GDAL/ArcGIS sidecars of a raster
POSITIONING = {"rtk", "ppk", "gcp", "gnss", "none"}
FILE_FIELDS = {"path", "product", "variant", "role", "attach_to", "archive", "site", "date", "date_precision",
               "start_date", "end_date", "crs", "table", "layers",
               "platform", "instruments", "positioning", "bands", "unit", "vertical_datum", "notes"}
GROUP_FIELDS = FILE_FIELDS - {"path", "product", "variant", "role", "attach_to"} | {"folder", "doi", "record", "download_filter",
                                                                         "files", "evidence"}
MANUAL_SITE_FIELDS = ("colonies", "land_status", "governance", "confirmed")


def load(name_or_path: str) -> Dict[str, Any]:
    """Load and check a summary by name (``arcticdata_seward``) or path. Raises ValueError listing problems."""
    path = Path(name_or_path)
    if not path.suffix:
        path = HERE / f"{name_or_path}.yaml"
    text = path.read_text()
    summary = yaml.safe_load(text)
    sites = load_sites()
    problems = check_sites(sites) + check(summary, sites) + anchors(text)
    if problems:
        raise ValueError(f"{path}:\n  " + "\n  ".join(problems))
    hints = summary.get("sites") or {}
    summary["sites"] = {slug: {**sites[slug], **({"hints": hints[slug]["hints"]} if hints.get(slug) else {})}
                        for slug in used_sites(summary) | set(hints)}
    summary["_path"] = str(path)
    return summary


def load_sites(path: Path = SITES) -> Dict[str, Dict[str, Any]]:
    """The site registry: ``{slug: {name, crs, colonies, land_status, governance[, confirmed]}}``."""
    return (yaml.safe_load(path.read_text()) or {}).get("sites") or {} if path.exists() else {}


def check_sites(sites: Dict[str, Dict[str, Any]]) -> List[str]:
    """Problems in the site registry (empty when valid)."""
    p = []
    for slug, site in sites.items():
        if not site.get("name"):
            p.append(f"sites.yaml {slug}: needs a name")
        if not str(site.get("crs", "")).startswith("EPSG:"):
            p.append(f"sites.yaml {slug}: crs must be EPSG:<code>")
        for field in MANUAL_SITE_FIELDS:
            v = site.get(field)
            if v is not None and not (isinstance(v, dict) and v.get("by") and ("value" in v or field == "confirmed")):
                p.append(f"sites.yaml {slug}: {field} must be null or {{value, by, date}}")
    return p


def used_sites(s: Dict[str, Any]) -> set:
    """Site slugs a summary's data files use."""
    return {resolve(g, f).get("site") for g in s.get("groups") or [] for f in g.get("files") or [] if f.get("product")}


def anchors(text: str) -> List[str]:
    """YAML anchors and aliases (``&name`` / ``*name``) in a summary's text: not allowed, because each value
    must be readable where it applies and editable for one site or file without changing the others."""
    import re
    found = sorted(set(re.findall(r"(?m)(?:^|[\s:\-\[,])([&*][A-Za-z_][\w-]*)\s*$", text)))
    return [f"YAML anchors/aliases are not allowed, write each value out: {', '.join(found)}"] if found else []


def check(s: Dict[str, Any], sites: Optional[Dict[str, Dict[str, Any]]] = None) -> List[str]:
    """Schema problems of a summary (empty when valid); ``sites`` is the registry (loaded if not given)."""
    sites = load_sites() if sites is None else sites
    p = []
    if s.get("schema") != SCHEMA:
        p.append(f"schema must be {SCHEMA}")
    for key in ("dataset", "title", "authored", "source", "groups"):
        if not s.get(key):
            p.append(f"missing {key}")
    if p:
        return p
    for who in ("authored", "reviewed"):
        if s.get(who) is not None and not (isinstance(s[who], dict) and s[who].get("by") and s[who].get("date")):
            p.append(f"{who} needs by and date")
    for slug, site in (s.get("sites") or {}).items():
        extra = set(site or {}) - {"hints"}
        if extra:
            p.append(f"site {slug}: only hints belong in a summary; {sorted(extra)} go in data_acquisition/sites.yaml")
        if slug not in sites:
            p.append(f"site {slug} is not in data_acquisition/sites.yaml")
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
            if merged.get("crs") is not None and not str(merged["crs"]).startswith("EPSG:"):
                p.append(f"{fw}: crs must be EPSG:<code>")
            lay = merged.get("layers")
            if lay is not None:
                import re
                try:
                    groups = re.compile(lay.get("pattern", "")).groups if isinstance(lay, dict) else 0
                except re.error:
                    groups = 0
                if not (isinstance(lay, dict) and groups == 1 and lay.get("date_precision", "year") in PRECISIONS
                        and set(lay) <= {"pattern", "date_precision"}):
                    p.append(f"{fw}: layers must be {{pattern (a regex with one group), date_precision}}")
            tbl = merged.get("table")
            if tbl is not None and not (isinstance(tbl, dict) and tbl.get("x") and tbl.get("y")
                                        and set(tbl) <= {"skip", "x", "y", "z", "delimiter"}):
                p.append(f"{fw}: table must be {{skip, x, y[, z, delimiter]}}")
            if f.get("product"):
                if merged.get("site") not in sites:
                    p.append(f"{fw}: site {merged.get('site')!r} is not in data_acquisition/sites.yaml")
                try:
                    if merged.get("layers"):            # dated per layer, by the layer names
                        raise LookupError
                    key = (merged.get("site"), epoch(merged)[2], f["product"], f.get("variant"))
                    if key in seen:
                        p.append(f"{fw}: same site, time and product as {seen[key]}; give each a variant")
                    seen[key] = f.get("path")
                except ValueError as e:
                    p.append(f"{fw}: {e}")
                except LookupError:
                    pass
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


def layer_epoch(name: str, spec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Time fields (``date``, ``date_precision``) for a layer named ``name``, or None if the pattern does not match."""
    import re
    m = re.search(spec["pattern"], name)
    if not m:
        return None
    value, precision = m.group(1), spec.get("date_precision", "year")
    digits = re.sub(r"\D", "", value)
    parts = {"year": (4,), "month": (4, 2), "day": (4, 2, 2)}[precision]
    if len(digits) != sum(parts):
        return None
    numbers, i = [], 0
    for n in parts:
        numbers.append(int(digits[i:i + n]))
        i += n
    numbers += [1] * (3 - len(numbers))
    try:
        return {"date": datetime.date(*numbers), "date_precision": precision}
    except ValueError:
        return None


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
