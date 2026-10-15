#!/usr/bin/env python3
"""Source step for field-season drives: build one site of ``beaver_dataset/`` from its layout file.

The layout file (``data_acquisition/field_layouts/<site>.yaml``, see ``docs/dataset/field_naming.md``)
says where each orthomosaic and annotation layer of the original folders goes, under the naming
policy, or why it is left out. Photos are placed by their EXIF capture date, read from the drive
inventory (``output/dataset/manifest.csv``, written by ``data_acquisition.dataset.manifest``).

- Photos and orthomosaics (with their sidecars) become **hard links** under the new names: no copy,
  and read-only, which also protects the original.
- An orthomosaic that ArcGIS georeferenced (a ``GeodataXform`` in its ``.aux.xml``, which GDAL does not
  apply) gets its own ``.aux.xml`` instead of a link: the same first-order adjustment, fitted to the
  same control points, written as the file's georeferencing, so every tool places it as ArcGIS did.
  No pixel is changed. The original sidecar is kept, linked as ``<name>.arcgis.aux.xml``.
- Each annotation layer is **exported** with ``ogr2ogr`` to its own GeoPackage, unchanged (features,
  attributes, Z and M), and checked against its source: feature count, geometry type, extent, and
  where its CRS places it, under both the PROJ of pyproj and that of GDAL (rasterio).
- ``crs_corrections`` in the layout file replace a CRS that GDAL/PROJ read differently from the software
  that made the data (e.g. ESRI's ARC System zones, which ArcGIS evaluates on a sphere), for both.

The site folder gets ``manifest.csv`` (every file and its original), ``excluded.csv`` (what was left
out, and why) and one ``survey.json`` per survey. The originals are never written to.

Always run with ``--dry-run`` first (the plan only). Building needs a reviewed layout file.

    python -m data_acquisition.sources.field --drive "/media/<user>/Seagate Portable Drive" \\
        --site rumney_ranch --dry-run
"""
import argparse
import csv
import json
import os
import re
import stat
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
import numpy as np
import rasterio
from pyproj import CRS, Transformer
from pyproj.crs import CompoundCRS
from rasterio.crs import CRS as RasterioCRS
from rasterio.warp import transform as rasterio_transform

from data_acquisition.readers import files

LAYOUTS = Path(__file__).resolve().parent.parent / "field_layouts"
DATASET = "beaver_dataset"
SEASONS = ("2018 Field Season/", "2019 Field Season/")
GCP_WARN_M = 3.0               # an applied ArcGIS fit whose control points miss it by more than this is reported
MIN_SURVEY_PHOTOS = 50          # fewer photos on a day, and no orthomosaic: stray shots, not a survey
SCHEMA = 1
# names allowed by docs/dataset/field_naming.md
ORTHO_NAME = re.compile(r"^surveys/\d{4}-\d{2}-\d{2}/orthomosaic_part-[0-9a-z]+(_chunk-[0-9a-z-]+)?\.tif$")
FEATURES = ("dams", "canals", "trails", "ponds", "lodges", "colony_boundaries", "dam_widths", "dam_thicknesses",
            "woody_vegetation", "river_reach", "stream")
LAYER_NAME = re.compile(r"^annotations/\d{4}(-\d{2}-\d{2})?/(" + "|".join(FEATURES)
                        + r")(_points)?(_colony-[0-9a-z]+)?(_[a-z0-9-]+)?\.gpkg$")
Action = Dict[str, str]


# ---------------------------------------------------------------- layout file

def load_layout(site: str) -> Dict[str, Any]:
    """The layout file of ``site``, checked; raises ValueError listing its problems."""
    path = LAYOUTS / f"{site}.yaml"
    layout = yaml.safe_load(path.read_text())
    problems = check_layout(layout)
    if problems:
        raise ValueError(f"{path}:\n  " + "\n  ".join(problems))
    return layout


def check_layout(layout: Dict[str, Any]) -> List[str]:
    """Problems of a layout file (empty when valid): fields, names, and no two sources on one target."""
    p = []
    if layout.get("schema") != SCHEMA:
        p.append(f"schema must be {SCHEMA}")
    for key in ("site", "authored", "base", "orthomosaics", "annotations"):
        if not layout.get(key):
            p.append(f"missing {key}")
    if layout.get("photos") != "by_exif_date":
        p.append("photos must be by_exif_date")
    for who in ("authored", "reviewed"):
        v = layout.get(who)
        if v is not None and not (isinstance(v, dict) and v.get("by") and v.get("date")):
            p.append(f"{who} needs by and date")
    for c in layout.get("crs_corrections") or []:
        if not (isinstance(c, dict) and c.get("from") and c.get("to") and c.get("reason")):
            p.append("crs_corrections entries need from (the CRS name as declared), to (a PROJ string) and reason")
        else:
            try:
                CRS.from_user_input(c["to"])
            except Exception as e:      # pyproj raises CRSError, or others for malformed input
                p.append(f"crs_corrections {c['from']}: to is not a CRS ({e})")
    targets: Dict[str, str] = {}
    for kind, name_rule in (("orthomosaics", ORTHO_NAME), ("annotations", LAYER_NAME)):
        for e in layout.get(kind) or []:
            where = f"{kind} {e.get('source')}" + (f" layer {e['layer']}" if e.get("layer") else "")
            if bool(e.get("to")) == bool(e.get("exclude")):
                p.append(f"{where}: needs exactly one of to or exclude")
            elif e.get("to") and not name_rule.match(e["to"]):
                p.append(f"{where}: {e['to']} does not follow docs/dataset/field_naming.md")
            if kind == "annotations" and not e.get("layer"):
                p.append(f"{where}: needs layer")
            if e.get("to") in targets:
                p.append(f"{where}: {e['to']} is also the target of {targets[e['to']]}")
            if e.get("to"):
                targets[e["to"]] = where
    return p


def source_path(layout: Dict[str, Any], source: str) -> str:
    """A layout source as a path relative to the drive root."""
    return source if source.startswith(SEASONS) else layout["base"] + source


# ---------------------------------------------------------------- plan

def _camera_folder(source: str) -> str:
    """The original folder holding a photo ('100MEDIA', a leg folder, ...), made filesystem-safe."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", source.split("/")[-2]).strip("_")


def _sidecars(drive: Path, source: str, target: str) -> List[Tuple[str, str]]:
    """(source, target) pairs for the sidecars of a raster, renamed with it (``x.tif.aux.xml``, ``x.tfwx``)."""
    src_stem, dst_stem = source.rsplit(".", 1)[0], target.rsplit(".", 1)[0]
    pairs = []
    for ext in files.RASTER_SIDECARS:
        for s, d in ((source + ext, target + ext), (src_stem + ext, dst_stem + ext)):
            if (drive / s).is_file():
                pairs.append((s, d))
    return pairs


def plan(drive: Path, layout: Dict[str, Any], inventory: List[Dict[str, str]]) -> Tuple[List[Action], List[Action]]:
    """(actions, excluded) to build the site: ``link`` and ``export`` actions with their source, and one row
    per original left out, with the reason."""
    site = layout["site"]
    root = f"{DATASET}/sites/{site}"
    actions: List[Action] = []
    excluded: List[Action] = []

    survey_days = set()
    for e in layout["orthomosaics"]:
        src = source_path(layout, e["source"])
        if e.get("exclude"):
            excluded.append({"source": src, "layer": "", "reason": e["exclude"]})
            continue
        actions.append({"action": "link", "dest": f"{root}/{e['to']}", "source": src, "layer": ""})
        for s, d in _sidecars(drive, src, e["to"]):
            if d.endswith(".tif.aux.xml") and "GeodataXform" in (drive / s).read_text(errors="replace"):
                actions.append({"action": "georef", "dest": f"{root}/{d}", "source": s, "layer": ""})
                d = d[:-len(".tif.aux.xml")] + ".arcgis.aux.xml"        # the original, for reference
            actions.append({"action": "link", "dest": f"{root}/{d}", "source": s, "layer": ""})
        survey_days.add(e["to"].split("/")[1])

    photos = [r for r in inventory if r["site"] == site and r["role"] == "raw_photo"]
    per_day = defaultdict(int)
    for r in photos:
        if r["include"] == "True":
            per_day[r["survey_date"]] += 1
    for r in photos:
        day = r["survey_date"]
        if r["include"] != "True":
            excluded.append({"source": r["source_path"], "layer": "",
                             "reason": r["note"] or "excluded by the inventory"})
        elif per_day[day] < MIN_SURVEY_PHOTOS and day not in survey_days:
            excluded.append({"source": r["source_path"], "layer": "",
                             "reason": f"stray photos ({per_day[day]} on {day}, no orthomosaic)"})
        else:
            name = Path(r["source_path"]).name
            actions.append({"action": "link", "source": r["source_path"], "layer": "",
                            "dest": f"{root}/surveys/{day}/photos/{_camera_folder(r['source_path'])}/{name}"})

    listed = {source_path(layout, e["source"]) for e in layout["orthomosaics"]}
    excluded += [{"source": r["source_path"], "layer": "", "reason": r["note"] or "excluded by the inventory"}
                 for r in inventory if r["site"] == site and r["role"] in ("reference_ortho", "video_frame")
                 and r["include"] != "True" and r["source_path"] not in listed]   # by rule: corrupt, no georef, ...

    for e in layout["annotations"]:
        src = source_path(layout, e["source"])
        if e.get("exclude"):
            excluded.append({"source": src, "layer": e["layer"], "reason": e["exclude"]})
        else:
            actions.append({"action": "export", "dest": f"{root}/{e['to']}", "source": src, "layer": e["layer"],
                            "features": str(e.get("features", ""))})
    dests = [a["dest"] for a in actions]
    clashes = {d for d in dests if dests.count(d) > 1}
    if clashes:
        raise ValueError(f"two sources for {sorted(clashes)[:5]}")
    return actions, excluded


# ---------------------------------------------------------------- build

def _read_only(path: Path) -> None:
    path.chmod(path.stat().st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def _layer_info(path: Path, layer: str) -> Dict[str, Any]:
    """Feature count, geometry type (with Z/M) and CRS of a layer, as GDAL reads it."""
    out = subprocess.run(["ogrinfo", "-json", "-so", str(path), layer], capture_output=True, text=True, check=True)
    info = json.loads(out.stdout)["layers"][0]
    geom = info["geometryFields"][0] if info.get("geometryFields") else {}
    return {"features": info["featureCount"], "geometry": geom.get("type"), "extent": geom.get("extent"),
            "crs": (geom.get("coordinateSystem") or {}).get("wkt")}


def _parts(wkt: str) -> Tuple[CRS, Optional[CRS]]:
    """(horizontal, vertical or None) parts of a CRS."""
    c = CRS.from_wkt(wkt)
    if not c.is_compound:
        return c, None
    return (next(p for p in c.sub_crs_list if not p.is_vertical),
            next((p for p in c.sub_crs_list if p.is_vertical), None))


def corrected_crs(wkt: Optional[str], corrections: List[Dict[str, str]]) -> Optional[str]:
    """The CRS that replaces ``wkt`` by the layout's ``crs_corrections`` (matched on the horizontal CRS's name;
    a vertical part is kept), as WKT2; None when no correction applies."""
    if not wkt:
        return None
    horizontal, vertical = _parts(wkt)
    fix = next((c for c in corrections if c["from"] == horizontal.name), None)
    if fix is None:
        return None
    as_json = CRS.from_user_input(fix["to"]).to_json_dict()
    as_json["name"] = f"{horizontal.name} (corrected: {fix['to']})"
    new = CRS.from_json_dict(as_json)
    return (CompoundCRS(f"{as_json['name']} + {vertical.name}", [new, vertical]) if vertical else new).to_wkt()


def _lonlat(wkt: str, points: List[Tuple[float, float]], proj: str) -> List[Tuple[float, float]]:
    """``points`` in the horizontal part of ``wkt``, as lon/lat, with the PROJ of pyproj or of GDAL (rasterio):
    the two can read the same CRS differently."""
    horizontal, _ = _parts(wkt)
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    if proj == "pyproj":
        lon, lat = Transformer.from_crs(horizontal, 4326, always_xy=True).transform(xs, ys)
    else:
        lon, lat = rasterio_transform(RasterioCRS.from_wkt(horizontal.to_wkt()), "EPSG:4326", xs, ys)
    return list(zip(lon, lat, strict=True))


def _same_place(reference: Optional[str], written: Optional[str], extent: Optional[List[float]]) -> bool:
    """True if ``written`` puts the layer where ``reference`` does: its extent corners land on the same lon/lat
    (within ~1 mm) under pyproj's and GDAL's PROJ alike, and any vertical part has the same datum and unit.
    Compared by effect, not by text: GDAL rewrites a CRS's description when it writes a GeoPackage."""
    if not reference or not written:
        return reference == written
    (_, va), (_, vb) = _parts(reference), _parts(written)
    if (va is None) != (vb is None) or (va and (va.datum.name, va.axis_info[0].unit_name)
                                        != (vb.datum.name, vb.axis_info[0].unit_name)):
        return False
    if not extent:
        return CRS.from_wkt(reference).equals(CRS.from_wkt(written))
    corners = [(extent[0], extent[1]), (extent[2], extent[3])]
    expected = _lonlat(reference, corners, "pyproj")
    return all(abs(p - q) < 1e-8 for proj in ("pyproj", "gdal")
               for a, b in zip(expected, _lonlat(written, corners, proj), strict=True)
               for p, q in zip(a, b, strict=True))


def export_layer(src: Path, layer: str, dest: Path, corrections: List[Dict[str, str]]) -> Optional[str]:
    """Export one layer to a GeoPackage named as ``dest`` (its CRS replaced when a correction applies), then
    compare it with its source; returns the difference found, or None."""
    name = dest.stem
    a = _layer_info(src, layer)
    crs = corrected_crs(a["crs"], corrections)
    note = f"exported unchanged from {src.name}, layer {layer}" + (", CRS corrected" if crs else "")
    command = ["ogr2ogr", "-f", "GPKG", str(dest), str(src), layer, "-nln", name, "-preserve_fid",
               "-lco", f"DESCRIPTION={note}"]
    if crs:
        srs = dest.with_suffix(".srs.wkt")
        srs.write_text(crs)
        command += ["-a_srs", str(srs)]
    try:
        subprocess.run(command, capture_output=True, text=True, check=True)
    finally:
        if crs:
            srs.unlink()
    b = _layer_info(dest, name)
    diffs = [f"{k}: {a[k]} -> {b[k]}" for k in ("features", "geometry") if a[k] != b[k]]
    if (a["extent"] is None) != (b["extent"] is None) or (a["extent"] and any(
            abs(p - q) > 1e-6 for p, q in zip(a["extent"], b["extent"], strict=True))):
        diffs.append(f"extent: {a['extent']} -> {b['extent']}")
    if not _same_place(crs or a["crs"], b["crs"], a["extent"]):
        diffs.append("the CRS places the layer elsewhere")
    return "; ".join(diffs) or None


def _control_points(aux: str) -> Tuple[int, str, np.ndarray, np.ndarray, List[str]]:
    """The control-point adjustment of an ArcGIS ``GeodataXform``: (order, target CRS WKT, source points, target
    points, steps not applied). In a ``CompositeXform`` (a chain of steps) the step fitted to control points is
    taken; other steps (given by coefficients only, e.g. an extra scaling) are returned as not applied."""
    xform = re.search(r'<GeodataXform[^>]*xsi:type="typens:(\w+)"(.*?)</GeodataXform>', aux, re.S)
    if xform.group(1) == "CompositeXform":
        steps = re.findall(r'<(XF_\d+) xsi:type="typens:(\w+)">(.*?)</\1>', xform.group(2), re.S)
    else:
        steps = [("XF", xform.group(1), xform.group(2))]
    fitted = [(name, kind, body) for name, kind, body in steps if "<SourceGCPs" in body]
    if len(fitted) != 1 or fitted[0][1] != "PolynomialXform":
        raise ValueError(f"{[(n, k) for n, k, _ in steps]}: expected one polynomial fitted to control points")
    name, _, body = fitted[0]

    def points(tag: str) -> np.ndarray:
        block = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", body, re.S).group(1)
        return np.array([float(v) for v in re.findall(r"<Double>([^<]+)</Double>", block)]).reshape(-1, 2)

    order = re.search(r"<PolynomialOrder>(\d+)</PolynomialOrder>", body)
    wkt = re.search(r"<WKT>(.*?)</WKT>", body, re.S).group(1)
    skipped = [f"{n} ({k})" for n, k, _ in steps if n != name]
    return int(order.group(1)) if order else 0, wkt, points("SourceGCPs"), points("TargetGCPs"), skipped


def georeference(tif: Path, aux: Path, dest: Path, corrections: List[Dict[str, str]]) -> Dict[str, Any]:
    """Write ``dest`` (the ``.aux.xml`` of the linked ``tif``) with ArcGIS's georeferencing of ``tif`` applied:
    the first-order polynomial least-squares fit through its control points, as the file's geotransform, in the
    target CRS (corrected when the layout says so). Returns the fit's control points and residuals, and the
    steps of a chained adjustment that were not applied."""
    order, wkt, source, target, skipped = _control_points(aux.read_text(errors="replace"))
    if order != 1:
        raise ValueError(f"{aux.name}: polynomial order {order} is not an affine adjustment; not applied")
    with rasterio.open(tif) as r:                # the original: its own transform, before any adjustment
        to_pixel = ~r.transform
    pixels = np.array([to_pixel * tuple(p) for p in source])
    design = np.c_[pixels, np.ones(len(pixels))]
    (a, d), (b, e), (c, f) = np.linalg.lstsq(design, target, rcond=None)[0].tolist()     # plain floats
    residuals = np.hypot(*(design @ np.array([[a, d], [b, e], [c, f]]) - target).T)
    crs = corrected_crs(CRS.from_user_input(wkt).to_wkt(), corrections) or CRS.from_user_input(wkt).to_wkt()
    fit = {"control_points": len(source), "rms_m": round(float(np.sqrt(np.mean(residuals ** 2))), 3),
           "max_m": round(float(residuals.max()), 3), "not_applied": "; ".join(skipped)}
    note = (f"ArcGIS polynomial adjustment (order 1) of {aux.name} applied: least-squares fit through "
            f"{fit['control_points']} control points, residual rms {fit['rms_m']} m, max {fit['max_m']} m"
            + (f"; chained steps not applied: {fit['not_applied']}" if skipped else ""))
    dest.write_text(
        "<PAMDataset>\n"
        f'  <SRS dataAxisToSRSAxisMapping="1,2">{crs}</SRS>\n'
        f"  <GeoTransform>{c!r}, {a!r}, {b!r}, {f!r}, {d!r}, {e!r}</GeoTransform>\n"
        '  <Metadata domain="beaver">\n'
        f'    <MDI key="georeference">{note}</MDI>\n'
        "  </Metadata>\n"
        "</PAMDataset>\n")
    return fit


def _clear(dest: Path) -> None:
    """Remove a file written by an earlier build, or a link that a written file replaces (unlinking a hard link
    removes this name only; the original is untouched)."""
    if dest.exists():
        if dest.stat().st_nlink == 1:       # our own file: never change the mode of a link (shared with the original)
            dest.chmod(dest.stat().st_mode | stat.S_IWUSR)
        dest.unlink()


def execute(drive: Path, actions: List[Action], corrections: List[Dict[str, str]]) -> Dict[str, Any]:
    """Carry out the plan. Existing correct links are kept, so a build can be resumed; exported layers and
    written sidecars are made again. Returns the counts, and the fit of each georeferenced orthomosaic."""
    done: Dict[str, Any] = defaultdict(int)
    fits: Dict[str, Dict[str, Any]] = {}
    problems = []
    for a in actions:
        dest, src = drive / a["dest"], drive / a["source"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        if a["action"] == "georef":
            _clear(dest)
            tif = src.with_name(src.name[:-len(".aux.xml")])
            fits[a["dest"]] = georeference(tif, src, dest, corrections)
            _read_only(dest)
            done["georef"] += 1
            continue
        if a["action"] == "link":
            if dest.exists():
                if not os.path.samefile(src, dest):
                    if dest.stat().st_nlink == 1 and dest.name.endswith(".tif.aux.xml"):
                        _clear(dest)            # a sidecar written by an earlier build, now linked again
                        os.link(src, dest)
                        _read_only(dest)
                        done["link"] += 1
                        continue
                    raise FileExistsError(f"{dest} exists and is not a link to {src}")
                done["link (already there)"] += 1
                continue
            os.link(src, dest)
            _read_only(dest)                    # same file on disk: also protects the original
            done["link"] += 1
        elif a["action"] == "export":
            _clear(dest)
            diff = export_layer(src, a["layer"], dest, corrections)
            if diff or (a.get("features") and _layer_info(dest, dest.stem)["features"] != int(a["features"])):
                problems.append(f"{a['dest']}: {diff or 'feature count differs from the layout file'}")
            _read_only(dest)
            done["export"] += 1
    if problems:
        raise RuntimeError("exported layers differ from their sources:\n  " + "\n  ".join(problems))
    done["fits"] = fits
    return dict(done)


RECORDS = ("manifest.csv", "excluded.csv", "georeference.csv", "alignment.csv", "survey.json")


def prune(drive: Path, site: str, actions: List[Action]) -> List[str]:
    """Remove files of the site folder that the plan no longer makes (left by an earlier build): links (this name
    only; the original is untouched) and files the field step wrote. Records are kept; they are rewritten."""
    site_dir = drive / DATASET / "sites" / site
    planned = {drive / a["dest"] for a in actions}
    removed = []
    for p in sorted(site_dir.rglob("*")):
        if p.is_file() and p not in planned and p.name not in RECORDS:
            _clear(p)
            removed.append(str(p.relative_to(site_dir)))
    return removed


def write_records(drive: Path, site: str, actions: List[Action], excluded: List[Action],
                  inventory: List[Dict[str, str]], fits: Dict[str, Dict[str, Any]]) -> None:
    """``manifest.csv``, ``excluded.csv``, ``georeference.csv`` (the fit of each orthomosaic whose ArcGIS
    adjustment was applied) and one ``survey.json`` per survey, in the site folder."""
    root = drive / DATASET / "sites" / site
    with open(root / "georeference.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["orthomosaic", "control_points", "rms_m", "max_m", "not_applied"])
        w.writerows([d.split(f"sites/{site}/", 1)[1][:-len(".aux.xml")], v["control_points"], v["rms_m"], v["max_m"],
                     v["not_applied"]] for d, v in sorted(fits.items()))
    with open(root / "manifest.csv", "w", newline="") as f:
        w = csv.DictWriter(f, ["action", "dest", "source", "layer"], extrasaction="ignore")
        w.writeheader()
        w.writerows(dict(a, dest=a["dest"].split(f"sites/{site}/", 1)[1]) for a in actions)
    with open(root / "excluded.csv", "w", newline="") as f:
        w = csv.DictWriter(f, ["source", "layer", "reason"])
        w.writeheader()
        w.writerows(excluded)
    taken = {r["source_path"]: r["taken_at"] for r in inventory if r["site"] == site and r["role"] == "raw_photo"}
    surveys: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"photos": 0, "orthomosaic_parts": [], "times": [],
                                                              "source_folders": set()})
    for a in actions:
        parts = a["dest"].split("/")
        if a["action"] not in ("link", "georef") or parts[3] != "surveys":
            continue
        s = surveys[parts[4]]
        if parts[5] == "photos":
            s["photos"] += 1
            s["times"].append(taken.get(a["source"]) or "")
        elif parts[5].endswith(".tif"):
            s["orthomosaic_parts"].append(parts[5])
        s["source_folders"].add(str(Path(a["source"]).parent))
    for day, s in surveys.items():
        times = sorted(t for t in s.pop("times") if t)
        meta = {"site": site, "date": day, **s, "orthomosaic_parts": sorted(s["orthomosaic_parts"]),
                "first_photo": times[0] if times else None, "last_photo": times[-1] if times else None,
                "source_folders": sorted(s["source_folders"])}
        (root / "surveys" / day / "survey.json").write_text(json.dumps(meta, indent=1))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--drive", required=True, type=Path, help="the drive (holds the season folders)")
    parser.add_argument("--site", required=True, help="site slug; its layout file is field_layouts/<site>.yaml")
    parser.add_argument("--inventory", type=Path, default=Path("output/dataset/manifest.csv"))
    parser.add_argument("--dry-run", action="store_true", help="write the plan only; touch nothing on the drive")
    args = parser.parse_args()

    layout = load_layout(args.site)
    with open(args.inventory, newline="") as f:
        inventory = list(csv.DictReader(f))
    actions, excluded = plan(args.drive, layout, inventory)
    out = Path("output/dataset/field") / args.site
    out.mkdir(parents=True, exist_ok=True)
    for name, rows, fields in (("plan.csv", actions, ["action", "dest", "source", "layer", "features"]),
                               ("excluded.csv", excluded, ["source", "layer", "reason"])):
        with open(out / name, "w", newline="") as f:
            w = csv.DictWriter(f, fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
    counts: Dict[str, int] = defaultdict(int)
    for a in actions:
        counts[a["action"]] += 1
    print(f"plan: {dict(counts)}, excluded: {len(excluded)} -> {out}")
    if args.dry_run:
        return
    if not layout.get("reviewed"):
        raise SystemExit(f"field_layouts/{args.site}.yaml is not reviewed: set reviewed: {{by, date}} first")
    site_dir = args.drive / DATASET / "sites" / args.site
    if site_dir.exists() and not (site_dir / "manifest.csv").exists():
        raise SystemExit(f"{site_dir} exists but was not built from a layout file: move it aside first")
    corrections = layout.get("crs_corrections") or []
    done = execute(args.drive, actions, corrections)
    fits = done.pop("fits")
    removed = prune(args.drive, args.site, actions)
    print("built:", done, f"| removed {len(removed)} left from an earlier build" if removed else "")
    for r in removed[:20]:
        print("  removed", r)
    write_records(args.drive, args.site, actions, excluded, inventory, fits)
    for dest, fit in sorted(fits.items()):
        if fit["max_m"] > GCP_WARN_M or fit["not_applied"]:
            print(f"  {dest}: control-point residual max {fit['max_m']} m (rms {fit['rms_m']} m)"
                  + (f"; not applied: {fit['not_applied']}" if fit["not_applied"] else ""))
    print(f"-> {site_dir}")


if __name__ == "__main__":
    main()
