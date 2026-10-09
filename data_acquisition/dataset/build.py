#!/usr/bin/env python3
"""Build ``beaver_dataset/`` on the field-season drive from the manifest, using hard links.

Layout (see docs/dataset/hdd_inventory.md and the dataset README):

    beaver_dataset/
      README.md, manifest.csv, excluded.csv
      sites/<site>/
        site.json
        surveys/<YYYY-MM-DD>/
          survey.json
          raw/<camera folder>/<photo>       hard links to the original photos (read-only)
          reference/<orthomosaic>.tif       hard links to the original exports (read-only)
          products/                         generated later
        annotations/source/<gdb or shp>     copies of the original annotation files (read-only)

Hard links share data with the originals: deleting a link never touches the original, but
writing into a linked file would change it. Linked files are therefore made read-only, which
on NTFS also protects the original. Annotation conversion to GeoPackage is a separate step.

Always run with ``--dry-run`` first: it writes the plan (one row per action) to ``--plan``
without touching the drive.

    python -m data_acquisition.dataset.build --root "/media/<user>/Seagate Portable Drive" \\
        --manifest output/dataset/manifest.csv --plan output/dataset/build_plan.csv --dry-run
"""
import argparse
import csv
import json
import os
import re
import shutil
import stat
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

DATASET = "beaver_dataset"
STUDY_SITES = ["rumney_ranch", "pilling_ranch", "willow_creek", "cut_bank_creek"]
ORTHO_SIDECARS = (".ovr", ".aux.xml")          # pyramids and statistics travel with the orthomosaic
MIN_SURVEY_PHOTOS = 50                         # a survey needs this many photos or a reference orthomosaic
README = """# beaver_dataset

Curated view of the 2018-2019 beaver field seasons, built from the folders next to it
(`2018 Field Season/`, `2019 Field Season/`) by `data_acquisition/dataset/build.py`
(BeaverSim repository, branch dev_dataset).

## Rules
- `raw/` and `reference/` contain **hard links**: the same files as the originals, not copies.
  They are read-only, which also protects the originals. **Never write into these folders.**
  Deleting a link does not delete the original.
- Everything generated goes into `products/`, `annotations/` (converted layers) or `colonies/`.
- Copying `beaver_dataset/` to another disk turns links into ordinary copies (~1.1 TB).

## Layout
    sites/<site>/
      site.json                          surveys of the site
      surveys/<YYYY-MM-DD>/              one folder per capture date (EXIF), not per original folder
        survey.json                      photos, time span, original folders, notes
        raw/<camera folder>/<photo>      drone photos (DJI Phantom 4 Pro, FC6310)
        reference/<orthomosaic>.tif      orthomosaics from the original Metashape processing;
                                         the annotations were drawn on them
        products/                        our processing (later)
      annotations/source/                copies of the original ArcGIS geodatabases / shapefiles

## Files
- `manifest.csv`: every file in this folder and the original it comes from.
- `excluded.csv`: files left out and why (duplicates, non-study sites, split copies,
  non-georeferenced or corrupt exports, video frames, stray photos).
"""


def _bool(v) -> bool:
    return str(v) == "True"


def _camera_folder(source_path: str) -> str:
    """Original folder holding the photo ('100MEDIA', a leg folder, ...), made filesystem-safe."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", source_path.split("/")[-2]).strip("_")


# ============================================================
# PLAN
# ============================================================

def plan(root: Path, manifest: List[Dict[str, str]]):
    """Every action needed to build the dataset (link, copy, write), and the manifest rows left out."""
    actions: List[Dict[str, str]] = []
    targets = set()
    excluded = [dict(r, reason=r["note"] or "excluded") for r in manifest
                if not _bool(r["include"]) or (r["site"] not in STUDY_SITES and r["role"] != "annotation")]

    # Surveys with too few photos and no orthomosaic are stray shots, not surveys
    counts = defaultdict(lambda: [0, 0])
    for r in manifest:
        if _bool(r["include"]) and r["role"] in ("raw_photo", "reference_ortho"):
            counts[(r["site"], r["survey_date"])][0 if r["role"] == "raw_photo" else 1] += 1
    strays = {k for k, (n_photos, n_orthos) in counts.items() if n_photos < MIN_SURVEY_PHOTOS and n_orthos == 0}

    def add(action, dest, source="", note=""):
        if action in ("link", "copy") and dest in targets:
            raise ValueError(f"two sources map to {dest}")
        targets.add(dest)
        actions.append({"action": action, "dest": dest, "source": source, "note": note})

    sites = defaultdict(lambda: defaultdict(lambda: {"photos": 0, "orthos": 0, "taken": [], "folders": set(), "notes": set()}))
    for r in manifest:
        if not _bool(r["include"]) or r["site"] not in STUDY_SITES or not r["survey_date"] \
                or r["role"] not in ("raw_photo", "reference_ortho"):
            continue
        if (r["site"], r["survey_date"]) in strays:
            excluded.append(dict(r, reason=f"stray photos (< {MIN_SURVEY_PHOTOS} photos, no orthomosaic on that date)"))
            continue
        survey = f"{DATASET}/sites/{r['site']}/surveys/{r['survey_date']}"
        s = sites[r["site"]][r["survey_date"]]
        if r["role"] == "raw_photo":
            add("link", f"{survey}/raw/{_camera_folder(r['source_path'])}/{Path(r['source_path']).name}", r["source_path"], r["note"])
            s["photos"] += 1
            s["taken"].append(r["taken_at"])
            s["folders"].add(str(Path(r["source_path"]).parent))
            if r["note"]:
                s["notes"].add(re.sub(r"\d{4}-\d{2}-\d{2}", "<date>", r["note"]))
        elif r["role"] == "reference_ortho":
            name = Path(r["source_path"]).name
            add("link", f"{survey}/reference/{name}", r["source_path"])
            for ext in ORTHO_SIDECARS:
                side = r["source_path"] + ext
                if (root / side).exists():
                    add("link", f"{survey}/reference/{name}{ext}", side)
            s["orthos"] += 1

    # Annotation sources (copied, not linked): one copy per geodatabase / shapefile set
    copied = set()
    for r in manifest:
        if r["role"] != "annotation" or not _bool(r["include"]) or r["site"] not in STUDY_SITES:
            continue
        src = r["source_path"]
        if src in copied:
            continue
        copied.add(src)
        dest_dir = f"{DATASET}/sites/{r['site']}/annotations/source"
        if src.endswith(".gdb"):
            add("copy", f"{dest_dir}/{Path(src).name}", src, "geodatabase folder")
        else:                                       # shapefile: copy every sidecar with the same stem
            stem = Path(src)
            for f in sorted((root / stem.parent).glob(stem.stem + ".*")):
                rel = os.path.relpath(f, root).replace(os.sep, "/")
                add("copy", f"{dest_dir}/{Path(src).parent.name}__{f.name}", rel, "shapefile part")

    # Metadata files
    for site, surveys in sites.items():
        add("write", f"{DATASET}/sites/{site}/site.json", note=json.dumps({"site": site, "surveys": sorted(surveys)}))
        for date, s in surveys.items():
            taken = sorted(t for t in s["taken"] if t)
            meta = {"site": site, "survey_date": date, "photos": s["photos"], "reference_orthos": s["orthos"],
                    "first_photo": taken[0] if taken else None, "last_photo": taken[-1] if taken else None,
                    "source_folders": sorted(s["folders"]), "notes": sorted(s["notes"])}
            add("write", f"{DATASET}/sites/{site}/surveys/{date}/survey.json", note=json.dumps(meta))
    for name in ("README.md", "manifest.csv", "excluded.csv"):
        add("write", f"{DATASET}/{name}")
    return actions, excluded


# ============================================================
# EXECUTE
# ============================================================

def _make_read_only(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def execute(root: Path, actions: List[Dict[str, str]], excluded: List[Dict[str, str]]) -> Dict[str, int]:
    """Carry out the plan. Existing correct links are skipped, so the build can be resumed."""
    done = defaultdict(int)
    for a in actions:
        dest = root / a["dest"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        if a["action"] == "link":
            src = root / a["source"]
            if dest.exists():
                if os.path.samefile(src, dest):
                    done["link (already there)"] += 1
                    continue
                raise FileExistsError(f"{dest} exists and is not a link to {src}")
            os.link(src, dest)
            _make_read_only(dest)                   # same file on disk: also protects the original
            done["link"] += 1
        elif a["action"] == "copy":
            src = root / a["source"]
            if dest.exists():
                done["copy (already there)"] += 1
                continue
            if src.is_dir():
                shutil.copytree(src, dest)
                for p in dest.rglob("*"):
                    if p.is_file():
                        _make_read_only(p)
            else:
                shutil.copy2(src, dest)
                _make_read_only(dest)
            done["copy"] += 1
        elif a["action"] == "write" and a["dest"].endswith(".json"):
            dest.write_text(json.dumps(json.loads(a["note"]), indent=1))
            done["write"] += 1
        elif a["dest"].endswith("README.md"):
            dest.write_text(README)
            done["write"] += 1
        elif a["dest"].endswith("manifest.csv"):
            with open(dest, "w", newline="") as f:
                w = csv.DictWriter(f, ["action", "dest", "source", "note"])
                w.writeheader()
                w.writerows(x for x in actions if x["action"] in ("link", "copy"))
            done["write"] += 1
        elif a["dest"].endswith("excluded.csv"):
            write_excluded(dest, excluded)
            done["write"] += 1
    return dict(done)


def write_excluded(path: Path, excluded: List[Dict[str, str]]) -> None:
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, ["role", "site", "survey_date", "source_path", "bytes", "reason"], extrasaction="ignore")
        w.writeheader()
        w.writerows(excluded)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", required=True)
    parser.add_argument("--manifest", default="output/dataset/manifest.csv")
    parser.add_argument("--plan", default="output/dataset/build_plan.csv")
    parser.add_argument("--dry-run", action="store_true", help="write the plan only; touch nothing on the drive")
    args = parser.parse_args()

    root = Path(args.root)
    with open(args.manifest, newline="") as f:
        manifest = list(csv.DictReader(f))
    actions, excluded = plan(root, manifest)
    write_excluded(Path(args.plan).with_name("excluded_preview.csv"), excluded)
    Path(args.plan).parent.mkdir(parents=True, exist_ok=True)
    with open(args.plan, "w", newline="") as f:
        w = csv.DictWriter(f, ["action", "dest", "source", "note"])
        w.writeheader()
        w.writerows(actions)
    counts = defaultdict(int)
    for a in actions:
        counts[a["action"]] += 1
    print(f"plan: {dict(counts)} -> {args.plan}")
    if args.dry_run:
        return
    print("executing:", execute(root, actions, excluded))


if __name__ == "__main__":
    main()
