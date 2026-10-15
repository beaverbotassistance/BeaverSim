#!/usr/bin/env python3
"""Write the course's notebooks: for each chapter, an exercise notebook (``docs/manual/notebooks/``) and its
solution (``docs/manual/solutions/notebooks/``), from one definition here, so the two never drift apart.

Each exercise is a prompt (Markdown), a starter cell (exercise notebook) and a solution cell (solution
notebook). Work in a copy of the exercise notebook: running this script rewrites both.

    python docs/manual/tools/build_notebooks.py
"""
from pathlib import Path
from typing import List, NamedTuple

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

MANUAL = Path(__file__).resolve().parents[1]

SETUP = '''# Setup: find the repository root, make the sample data root if needed, use the sample's site registry
import os, subprocess, sys
from pathlib import Path

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "data_acquisition").is_dir())
sys.path.insert(0, str(ROOT))
SAMPLE = ROOT / "output/manual/sample_root"
if not SAMPLE.exists():
    subprocess.run([sys.executable, str(ROOT / "docs/manual/tools/make_sample.py"), "--out", str(SAMPLE)], check=True)
DATASET = SAMPLE / "repo/doi_10.5555_training.pond"
EXTRACT = ROOT / "docs/manual/data/montana_extract"
os.environ["BEAVER_SITES"] = str(SAMPLE / "sites.yaml")
import warnings; warnings.simplefilter("ignore")
print("repository:", ROOT); print("sample data root:", SAMPLE)'''


class Exercise(NamedTuple):
    prompt: str
    starter: str
    solution: str


class Chapter(NamedTuple):
    name: str
    title: str
    intro: str
    imports: str
    exercises: List[Exercise]


CH02 = Chapter(
    "02_coordinates", "2. Coordinates: CRS, projections, units, heights",
    "Exercises of [chapter 2](../02_coordinates.md). Run the setup cell first.",
    '''import numpy as np
import pyogrio
import rasterio
from pyproj import CRS, Transformer
from rasterio.warp import transform''',
    [
        Exercise("**1. Read a CRS.** Open `ortho_2023-07-12.tif` of the sample dataset with rasterio. Print `crs`, "
                 "`crs.to_epsg()` and `crs.to_wkt()`. Is it geographic or projected? What are the units of `res`?",
                 '''with rasterio.open(DATASET / "ortho_2023-07-12.tif") as r:
    ...  # your code here''',
                 '''with rasterio.open(DATASET / "ortho_2023-07-12.tif") as r:
    print(r.crs, r.crs.to_epsg())
    print(r.crs.to_wkt()[:200], "...")
    crs = CRS.from_wkt(r.crs.to_wkt())
    print("projected:", crs.is_projected, "| units:", crs.axis_info[0].unit_name, "| res:", r.res)
# A projected CRS (UTM zone 12N) in metres: each pixel is 5 cm by 5 cm.'''),
        Exercise("**2. Degrees and metres.** Transform the top corners of the sample orthomosaic to EPSG:4326 with "
                 "`pyproj.Transformer`. How wide is the image in degrees of longitude, and in "
                 "metres? Explain the ratio.",
                 '''with rasterio.open(DATASET / "ortho_2023-07-12.tif") as r:
    b = r.bounds
to_lonlat = Transformer.from_crs("EPSG:32612", "EPSG:4326", always_xy=True)
...  # your code here''',
                 '''with rasterio.open(DATASET / "ortho_2023-07-12.tif") as r:
    b = r.bounds
to_lonlat = Transformer.from_crs("EPSG:32612", "EPSG:4326", always_xy=True)
(lon1, lat1), (lon2, lat2) = to_lonlat.transform(b.left, b.top), to_lonlat.transform(b.right, b.top)
width_m, width_deg = b.right - b.left, lon2 - lon1
print(f"{width_m:.1f} m = {width_deg:.7f} degrees of longitude -> {width_m / width_deg:,.0f} m per degree")
print(f"at the equator one degree is about 111,320 m; here (latitude {lat1:.2f}) about 111,320 x cos(latitude) = "
      f"{111320 * np.cos(np.radians(lat1)):,.0f} m")
# The small difference: the formula assumes a sphere; on the WGS 84 ellipsoid a degree of longitude at this latitude
# is slightly longer.'''),
        Exercise("**3. No CRS.** Open `dem_2022.asc`. What does rasterio report as its CRS? Where in the sample's "
                 "`metadata.xml` would you find the CRS to put in the summary?",
                 '''with rasterio.open(DATASET / "dem_2022.asc") as r:
    ...  # your code here''',
                 '''with rasterio.open(DATASET / "dem_2022.asc") as r:
    print("CRS:", r.crs, "| bounds:", r.bounds)
text = (DATASET / "metadata.xml").read_text()
start = text.find("<methodStep>")
print(text[start:text.find("</methodStep>")])
# No CRS in the file. The record's methods text says "in UTM zone 12N (EPSG:32612)": that goes in the summary
# as `crs: EPSG:32612`, and the item is flagged crs_from_summary.'''),
        Exercise("**4. Heights in feet.** Open `2018-07-26/annotations/dams.gpkg` of the Montana extract with "
                 "`pyogrio.read_info`. Split its CRS into horizontal and vertical parts. What is the "
                 "vertical datum, and "
                 "its unit? How many metres is 5 US survey feet?",
                 '''info = pyogrio.read_info(EXTRACT / "2018-07-26/annotations/dams.gpkg")
...  # your code here''',
                 '''info = pyogrio.read_info(EXTRACT / "2018-07-26/annotations/dams.gpkg")
horizontal, vertical = CRS.from_user_input(info["crs"]).sub_crs_list
print("horizontal:", horizontal.name)
print("vertical:", vertical.name, "| datum:", vertical.datum.name, "| unit:", vertical.axis_info[0].unit_name)
print("5 US survey feet =", 5 * 1200 / 3937, "m  (5 international feet = 1.524 m exactly)")'''),
        Exercise("**5. Two PROJ versions.** Take the first vertex of a dam in the extract (the dams are MultiPolygons: "
                 "`geometry.iloc[0].geoms[0].exterior.coords[0]`). Transform it to EPSG:4326 with `pyproj` and with "
                 "`rasterio.warp.transform`, first using the CRS written in the file, then using "
                 "`+proj=eqc +lat_ts=-52.28859923 +datum=WGS84 +units=m`. Which pairs agree and which are 25 km apart? "
                 "Why does the file in the extract not show the problem?",
                 '''path = EXTRACT / "2018-07-26/annotations/dams.gpkg"
dams = pyogrio.read_dataframe(path)
x, y = dams.geometry.iloc[0].geoms[0].exterior.coords[0][:2]
...  # your code here''',
                 '''import pyproj
path = EXTRACT / "2018-07-26/annotations/dams.gpkg"
dams = pyogrio.read_dataframe(path)
x, y = dams.geometry.iloc[0].geoms[0].exterior.coords[0][:2]
print("PROJ in pyproj:", pyproj.proj_version_str, "| PROJ in rasterio:", rasterio.__proj_version__)
in_file = CRS.from_user_input(pyogrio.read_info(path)["crs"]).sub_crs_list[0].to_wkt()
ellipsoid = "+proj=eqc +lat_ts=-52.28859923 +datum=WGS84 +units=m"
for name, crs in (("CRS in the file", in_file), ("ellipsoid string", ellipsoid)):
    a = Transformer.from_crs(CRS.from_user_input(crs), "EPSG:4326", always_xy=True).transform(x, y)
    b = transform(rasterio.crs.CRS.from_user_input(crs), "EPSG:4326", [x], [y])
    print(f"{name:17s} pyproj {a[0]:.4f}, {a[1]:.4f}   rasterio {b[0][0]:.4f}, {b[1][0]:.4f}")
# The file's CRS spells the sphere out (+R=6378137), so both PROJ versions agree. The plain ellipsoid string
# is read with the spherical formula by PROJ 9.5 and with the ellipsoidal one by PROJ 9.8: 25 km apart.'''),
        Exercise("**6. Find it in the code.** Which function writes the WKT2 of a raster into its STAC item when there "
                 "is no EPSG code? Which flag does `curate` raise for a raster whose CRS differs "
                 "from the site's, and in "
                 "which function? Use `inspect` or search the files.",
                 '''import inspect
from data_acquisition.catalog import stac
from data_acquisition.steps import curate
...  # your code here''',
                 '''import inspect
from data_acquisition.catalog import stac
from data_acquisition.steps import curate
for module, needle in ((stac, "proj.wkt2"), (curate, '"crs_mismatch"')):
    for name, fn in inspect.getmembers(module, inspect.isfunction):
        if fn.__module__ == module.__name__ and needle in inspect.getsource(fn):
            print(f"{module.__name__}.{name} contains {needle}")
# stac.raster_item (and stac.vector_item, for vectors) writes proj.wkt2; curate.check_raster raises crs_mismatch.'''),
    ])

CH06 = Chapter(
    "06_what_the_pipeline_needs", "6. What the pipeline needs from you",
    "Exercises of [chapter 6](../06_what_the_pipeline_needs.md). Each exercise changes one thing in a copy of the "
    "reference summary and asks the pipeline what it thinks. Before running a cell, **write down which level you "
    "expect**: blocks, blocks one step, skips one file, or flags only. Run the setup cell first.",
    '''import copy, datetime, tempfile
import yaml
from data_acquisition.catalog import build
from data_acquisition.catalog import summary as summaries

REFERENCE = yaml.safe_load((ROOT / "docs/manual/solutions/training_pond.yaml").read_text())


def files(s):
    return s["groups"][0]["files"]


def check(s):
    """Write ``s`` to a temporary summary, check it, and build it in memory; print what the pipeline says."""
    path = Path(tempfile.mkdtemp()) / "my_copy.yaml"
    path.write_text(yaml.safe_dump(copy.deepcopy(s), sort_keys=False))
    try:
        loaded = summaries.load(str(path))
    except ValueError as e:
        print("BLOCKS: the summary is refused\\n", str(e).split("\\n", 1)[1])
        return None
    catalog, report = build.build(SAMPLE, loaded)
    problems = {k: v for k, v in report.items() if v}
    print(f"built {len(list(catalog.get_items(recursive=True)))} items; build report:", problems or "empty")
    return catalog


check(REFERENCE);''',
    [
        Exercise("**1.** Remove the `date` of `ortho_2023-07-12.tif`.",
                 '''s = copy.deepcopy(REFERENCE)
...  # your change here
check(s);''',
                 '''s = copy.deepcopy(REFERENCE)
del files(s)[0]["date"]
check(s);
# Blocks: a data file without a time is refused (summary.epoch, called by summary.check).'''),
        Exercise("**2.** Remove the `crs` of `dem_2022.asc`. What does the check say, and what does "
                 "the build report say?",
                 '''s = copy.deepcopy(REFERENCE)
...  # your change here
check(s);''',
                 '''s = copy.deepcopy(REFERENCE)
del files(s)[2]["crs"]
check(s);
# Skips one file: the summary is valid, but the grid declares no CRS, so the builder leaves it out
# ("unsupported"). The README then has no dtm to attach to ("unattached").'''),
        Exercise("**3.** Move `date: 2023-07-12` from the files to the group (keep the date of `dem_2022.asc`). "
                 "Which file is now reported, and under what?",
                 '''s = copy.deepcopy(REFERENCE)
...  # your change here (a date is datetime.date(2023, 7, 12), not a string)
check(s);''',
                 '''s = copy.deepcopy(REFERENCE)
for f in files(s):
    if f["path"] != "dem_2022.asc":
        f.pop("date", None)
s["groups"][0]["date"] = datetime.date(2023, 7, 12)
check(s);
# The README inherits the group's date, so it attaches only to items of 2023-07-12, and not to the
# 2022 grid: "unattached". Put dates on the data files, not on the group.'''),
        Exercise("**4.** Add a second orthomosaic entry for the same file with `variant: copy`. "
                 "What changes if you remove the variant?",
                 '''s = copy.deepcopy(REFERENCE)
...  # your change here
check(s);''',
                 '''s = copy.deepcopy(REFERENCE)
files(s).append(dict(copy.deepcopy(files(s)[0]), variant="copy"))
check(s);                                   # valid: two items, ..._orthomosaic and ..._orthomosaic_copy
del files(s)[-1]["variant"]
check(s);
# Without the variant: blocks ("same site, time and product ... give each a variant").'''),
        Exercise("**5.** Set `reviewed: true`. Then set `reviewed: {by: <you>, date: <today>}` and build: which "
                 "descriptor sources change in the items' `beaver:origin`?",
                 '''s = copy.deepcopy(REFERENCE)
...  # your change here
check(s);''',
                 '''s = copy.deepcopy(REFERENCE)
s["reviewed"] = True
check(s);                                   # blocks: "reviewed needs by and date"
before = check(copy.deepcopy(REFERENCE))
s["reviewed"] = {"by": "A Student", "date": datetime.date.today()}
after = check(s)
item = lambda c: next(i for i in c.get_items(recursive=True) if i.id.endswith("orthomosaic"))
print("not reviewed:", item(before).properties["beaver:origin"]["site"])
print("reviewed:    ", item(after).properties["beaver:origin"]["site"])
# Unreviewed values are labelled "claude"; after review they are "manual", with the reviewer's name.'''),
        Exercise("**6. Find it in the code.** Find the line that refuses a data file without a time, and the line that "
                 "skips a raster without a CRS.",
                 '''import inspect
...  # your code here''',
                 '''import inspect
for fn, needle in ((summaries.epoch, "date must be YYYY-MM-DD"), (build._raster_item, "declares no CRS")):
    source, first = inspect.getsourcelines(fn)
    for n, line in enumerate(source, first):
        if needle in line:
            print(f"{inspect.getsourcefile(fn)}:{n}: {line.strip()}")'''),
    ])

CHAPTERS = [CH02, CH06]


def notebook(chapter: Chapter, solutions: bool) -> nbformat.NotebookNode:
    kind = "Solutions" if solutions else "Exercises"
    cells = [new_markdown_cell(f"# {chapter.title}: {kind.lower()}\n\n{chapter.intro}"
                               + ("\n\nThese are the solutions; try the exercise notebook first."
                                  if solutions else "\n\nWork in a copy of this notebook: it is regenerated by "
                                  "`docs/manual/tools/build_notebooks.py`.")),
             new_code_cell(SETUP), new_code_cell(chapter.imports)]
    for e in chapter.exercises:
        cells += [new_markdown_cell(e.prompt), new_code_cell(e.solution if solutions else e.starter)]
    nb = new_notebook(cells=cells)
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    return nb


def main() -> None:
    for chapter in CHAPTERS:
        for solutions, folder in ((False, MANUAL / "notebooks"), (True, MANUAL / "solutions" / "notebooks")):
            folder.mkdir(parents=True, exist_ok=True)
            nbformat.write(notebook(chapter, solutions), folder / f"{chapter.name}.ipynb")
    print(f"{len(CHAPTERS)} chapters -> {MANUAL / 'notebooks'}, {MANUAL / 'solutions' / 'notebooks'}")


if __name__ == "__main__":
    main()
