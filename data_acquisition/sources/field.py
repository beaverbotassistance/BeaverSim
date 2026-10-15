#!/usr/bin/env python3
"""Source step for field-season drives: build one site of ``beaver_dataset/`` from its layout file.

The layout file (``data_acquisition/field_layouts/<site>.yaml``, see ``docs/dataset/field_naming.md``)
says where each orthomosaic and annotation layer of the original folders goes, under the naming
policy, or why it is left out. Photos are placed by their EXIF capture date, read from the drive
inventory (``output/dataset/manifest.csv``, written by ``data_acquisition.dataset.manifest``).

- Photos and orthomosaics (with their sidecars) become **hard links** under the new names: no copy,
  and read-only, which also protects the original.
- Each annotation layer is **exported** with ``ogr2ogr`` to its own GeoPackage, unchanged (features,
  attributes, Z and M, CRS), and checked against its source: feature count, geometry type, CRS.

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
from pyproj import CRS, Transformer

from data_acquisition.readers import files

LAYOUTS = Path(__file__).resolve().parent.parent / "field_layouts"
DATASET = "beaver_dataset"
SEASONS = ("2018 Field Season/", "2019 Field Season/")
MIN_SURVEY_PHOTOS = 50          # fewer photos on a day, and no orthomosaic: stray shots, not a survey
SCHEMA = 1
# names allowed by docs/dataset/field_naming.md
ORTHO_NAME = re.compile(r"^surveys/\d{4}-\d{2}-\d{2}/orthomosaic_part-[0-9a-z]+\.tif$")
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
        actions += [{"action": "link", "dest": f"{root}/{d}", "source": s, "layer": ""}
                    for s, d in _sidecars(drive, src, e["to"])]
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


def _same_place(a: Optional[str], b: Optional[str], extent: Optional[List[float]]) -> bool:
    """True if two CRSs put the layer in the same place: its extent corners transform to the same lon/lat
    (within ~1 mm), and any vertical part has the same datum and unit. Compared by effect, not by text,
    because GDAL rewrites a CRS's description when it writes a GeoPackage (e.g. ESRI's spherical
    Equidistant Cylindrical, which PROJ evaluates with the same formula either way)."""
    if not a or not b:
        return a == b
    ca, cb = CRS.from_wkt(a), CRS.from_wkt(b)
    ha, hb = (c.sub_crs_list[0] if c.is_compound else c for c in (ca, cb))
    va, vb = (next((s for s in c.sub_crs_list if s.is_vertical), None) if c.is_compound else None for c in (ca, cb))
    if (va is None) != (vb is None) or (va and (va.datum.name, va.axis_info[0].unit_name)
                                        != (vb.datum.name, vb.axis_info[0].unit_name)):
        return False
    if not extent:
        return ha.equals(hb)
    corners = [(extent[0], extent[1]), (extent[2], extent[3])]
    to_a, to_b = (Transformer.from_crs(h, 4326, always_xy=True) for h in (ha, hb))
    return all(abs(p - q) < 1e-8 for c in corners
               for p, q in zip(to_a.transform(*c), to_b.transform(*c), strict=True))


def export_layer(src: Path, layer: str, dest: Path) -> Optional[str]:
    """Export one layer to a GeoPackage named as ``dest``, then compare it with its source; returns the
    difference found, or None."""
    name = dest.stem
    subprocess.run(["ogr2ogr", "-f", "GPKG", str(dest), str(src), layer, "-nln", name, "-preserve_fid",
                    "-lco", f"DESCRIPTION=exported unchanged from {src.name}, layer {layer}"],
                   capture_output=True, text=True, check=True)
    a, b = _layer_info(src, layer), _layer_info(dest, name)
    diffs = [f"{k}: {a[k]} -> {b[k]}" for k in ("features", "geometry") if a[k] != b[k]]
    if (a["extent"] is None) != (b["extent"] is None) or (a["extent"] and any(
            abs(p - q) > 1e-6 for p, q in zip(a["extent"], b["extent"], strict=True))):
        diffs.append(f"extent: {a['extent']} -> {b['extent']}")
    if not _same_place(a["crs"], b["crs"], a["extent"]):
        diffs.append("the CRS places the layer elsewhere")
    return "; ".join(diffs) or None


def execute(drive: Path, actions: List[Action]) -> Dict[str, int]:
    """Carry out the plan. Existing correct links and exports are kept, so a build can be resumed."""
    done: Dict[str, int] = defaultdict(int)
    problems = []
    for a in actions:
        dest, src = drive / a["dest"], drive / a["source"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        if a["action"] == "link":
            if dest.exists():
                if not os.path.samefile(src, dest):
                    raise FileExistsError(f"{dest} exists and is not a link to {src}")
                done["link (already there)"] += 1
                continue
            os.link(src, dest)
            _read_only(dest)                    # same file on disk: also protects the original
            done["link"] += 1
        elif a["action"] == "export":
            if dest.exists():
                done["export (already there)"] += 1
                continue
            diff = export_layer(src, a["layer"], dest)
            if diff or (a.get("features") and _layer_info(dest, dest.stem)["features"] != int(a["features"])):
                problems.append(f"{a['dest']}: {diff or 'feature count differs from the layout file'}")
            _read_only(dest)
            done["export"] += 1
    if problems:
        raise RuntimeError("exported layers differ from their sources:\n  " + "\n  ".join(problems))
    return dict(done)


def write_records(drive: Path, site: str, actions: List[Action], excluded: List[Action],
                  inventory: List[Dict[str, str]]) -> None:
    """``manifest.csv``, ``excluded.csv`` and one ``survey.json`` per survey, in the site folder."""
    root = drive / DATASET / "sites" / site
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
        if a["action"] != "link" or parts[3] != "surveys":
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
    print("built:", execute(args.drive, actions))
    write_records(args.drive, args.site, actions, excluded, inventory)
    print(f"-> {site_dir}")


if __name__ == "__main__":
    main()
