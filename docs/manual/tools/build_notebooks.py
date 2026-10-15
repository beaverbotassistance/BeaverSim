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


CH00 = Chapter(
    "00_setup", "0. Setup: environment, drives, sample data",
    "Exercises of [chapter 0](../00_setup.md). Run the setup cell first: it makes the sample data root.",
    '''import subprocess
from data_acquisition.catalog import summary as summaries''',
    [
        Exercise("**1.** List the files of the sample data root with their sizes. Which file is the largest, and why?",
                 '''...  # your code here (Path.rglob, stat().st_size)''',
                 '''for p in sorted(SAMPLE.rglob("*")):
    if p.is_file():
        print(f"{p.stat().st_size:>9,d}  {p.relative_to(SAMPLE)}")
# The orthomosaic is the largest: four bands of noisy colour texture, which compress poorly. The DSM is tiny
# although it holds 4-byte heights: a smooth surface compresses to almost nothing. The GeoPackage's ~100 KB is
# mostly the SQLite container (pages, indexes, metadata tables), not its two dams.'''),
        Exercise("**2.** Print the versions of GDAL and PROJ inside rasterio, of PROJ inside pyproj, and of the "
                 "system's "
                 "`ogr2ogr`. How many different versions of PROJ do you have?",
                 '''import pyproj, rasterio
...  # your code here''',
                 '''import pyproj, rasterio
print("rasterio: GDAL", rasterio.__gdal_version__, "| PROJ", rasterio.__proj_version__)
print("pyproj:   PROJ", pyproj.proj_version_str)
print("system:  ", subprocess.run(["ogr2ogr", "--version"], capture_output=True, text=True).stdout.strip())
# Usually three copies of GDAL/PROJ: rasterio's, pyproj's and the system's. Chapter 2 shows why it matters.'''),
        Exercise("**3.** Read `pytest.ini`: which plugins are disabled, and why?",
                 '''...  # your code here''',
                 '''print((ROOT / "pytest.ini").read_text())
# The ROS plugins (launch_testing, launch_ros, ament_*): ROS adds them to the Python path of every terminal on
# machines where it is installed, and they are incompatible with this version of pytest.'''),
        Exercise("**4.** Print the path of the site registry the pipeline uses, with and without `BEAVER_SITES`, and "
                 "the "
                 "sites in each.",
                 '''...  # your code here (summaries.load_sites, summaries.SITES, os.environ)''',
                 '''print("with BEAVER_SITES:   ", os.environ["BEAVER_SITES"], list(summaries.load_sites()))
saved = os.environ.pop("BEAVER_SITES")
print("without BEAVER_SITES:", summaries.SITES, len(summaries.load_sites()), "sites")
os.environ["BEAVER_SITES"] = saved'''),
    ])

CH01 = Chapter(
    "01_geospatial_data", "1. Geospatial data: rasters, vectors, formats",
    "Exercises of [chapter 1](../01_geospatial_data.md). Run the setup cell first.",
    '''import subprocess, json
import matplotlib.pyplot as plt
import numpy as np
import pyogrio
import rasterio
from data_acquisition.readers import files, geotiff''',
    [
        Exercise("**1. A raster's header.** Open the sample's `ortho_2023-07-12.tif` and print its width, height, band "
                 "count, data types, resolution, geotransform, colour interpretation and nodata. Explain each.",
                 '''with rasterio.open(DATASET / "ortho_2023-07-12.tif") as r:
    ...  # your code here''',
                 '''with rasterio.open(DATASET / "ortho_2023-07-12.tif") as r:
    print("size:", r.width, "x", r.height, "| bands:", r.count, "| types:", r.dtypes)
    print("resolution:", r.res, "| nodata:", r.nodata)
    print("colour interpretation:", [c.name for c in r.colorinterp])
    print("geotransform:", r.transform)
# 400 x 400 pixels of 5 cm (20 m square); four uint8 bands, red, green, blue and alpha; no nodata value (the
# alpha band marks the empty corners). The geotransform: pixel width 0.05, no rotation, left edge at x = 368000;
# pixel height -0.05 (rows go south), top edge at y = 5420040.'''),
        Exercise("**2. Nodata and alpha.** How many pixels of the sample orthomosaic are transparent (alpha 0)? How "
                 "many "
                 "pixels of the sample DSM are nodata? Read the DSM with `masked=True` and compare the minimum with "
                 "and "
                 "without the mask.",
                 '''...  # your code here''',
                 '''with rasterio.open(DATASET / "ortho_2023-07-12.tif") as r:
    alpha = r.read(4)
print("transparent pixels:", int((alpha == 0).sum()), "of", alpha.size)
with rasterio.open(DATASET / "dsm_2023-07-12.tif") as r:
    raw, masked = r.read(1), r.read(1, masked=True)
    print("nodata value:", r.nodata, "| nodata pixels:", int((raw == r.nodata).sum()))
print("minimum without mask:", raw.min(), "| with mask:", masked.min())
# Without the mask, -9999 would be taken for a height 11 km below sea level.'''),
        Exercise("**3. Vectors.** List the layers of the sample's `dams_2023-07-12.gpkg` and of the extract's "
                 "`2018-07-26/annotations/dams.gpkg`: geometry type, number of features, attribute names. Compare the "
                 "geometry type pyogrio reports with the one `ogrinfo` reports for the extract's layer: what is lost?",
                 '''...  # your code here (pyogrio.list_layers, pyogrio.read_info, subprocess ogrinfo -json -so)''',
                 '''for path in (DATASET / "dams_2023-07-12.gpkg", EXTRACT / "2018-07-26/annotations/dams.gpkg"):
    for name, geometry in pyogrio.list_layers(path):
        info = pyogrio.read_info(path, layer=name)
        print(f"{path.name}: layer {name}, {geometry}, {info['features']} features, fields {list(info['fields'])}")
out = subprocess.run(["ogrinfo", "-json", "-so", str(EXTRACT / "2018-07-26/annotations/dams.gpkg"), "dams"],
                     capture_output=True, text=True).stdout
print("ogrinfo:", json.loads(out)["layers"][0]["geometryFields"][0]["type"])
# pyogrio reads 'MultiPolygon Z'; the file holds 'MultiPolygonZM'. pyogrio (and GeoPandas) drop the M values.'''),
        Exercise("**4. Companions.** Which companion files does the pipeline expect for `orthomosaic_part-3.tif`, and "
                 "for `dams.shp`?",
                 '''...  # your code here (files.companions)''',
                 '''print(sorted(files.companions("orthomosaic_part-3.tif")))
print(sorted(files.companions("dams.shp")))'''),
        Exercise("**5. Draw both.** Plot the extract's 26 July orthomosaic chunk and draw the dam outlines on it.",
                 '''...  # your code here (rasterio, pyogrio.read_dataframe, matplotlib)''',
                 '''day = EXTRACT / "2018-07-26"
with rasterio.open(day / "orthomosaic_chunk.tif") as r:
    image, to_pixel, crs = r.read(), ~r.transform, r.crs
dams = pyogrio.read_dataframe(day / "annotations/dams.gpkg").to_crs(crs.to_wkt())
fig, ax = plt.subplots(figsize=(6, 6))
ax.imshow(np.moveaxis(image, 0, -1))
for geom in dams.geometry:
    for part in geom.geoms:
        xy = np.array([to_pixel @ tuple(p[:2]) for p in part.exterior.coords])
        ax.plot(xy[:, 0], xy[:, 1], color="yellow")
ax.set_axis_off(); plt.show()'''),
        Exercise("**6. Find it in the code.** Which function decides whether a file is a raster, and which file "
                 "extensions does it try before opening a file?",
                 '''import inspect
...  # your code here''',
                 '''import inspect
print(inspect.getsource(geotiff.is_raster))
print("always rasters:", geotiff.EXTENSIONS, "| opened to check:", geotiff.PROBE)'''),
    ])

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

CH03 = Chapter(
    "03_drone_surveys", "3. Drone surveys: from photos to maps",
    "Exercises of [chapter 3](../03_drone_surveys.md). Run the setup cell first.",
    """import re
import numpy as np
import rasterio
from data_acquisition.readers import photos""",
    [
        Exercise("**1. A photo's metadata.** Read the EXIF of one photo of the Montana extract with `photos.exif`: "
                 "camera, time, position, altitude. Then find, in the file's XMP block, DJI's `RelativeAltitude`, "
                 "`AbsoluteAltitude` and `GimbalPitchDegree`. What do they tell you?",
                 """photo = EXTRACT / "2018-07-26/photos/DJI_0139.JPG"
...  # your code here (photos.exif; the XMP is text inside the file: search for 'drone-dji:')""",
                 """photo = EXTRACT / "2018-07-26/photos/DJI_0139.JPG"
print(photos.exif(photo))
xmp = dict(re.findall(r'drone-dji:(\\w+)="([^"]*)"', photo.read_bytes().decode("latin-1")))
for key in ("RelativeAltitude", "AbsoluteAltitude", "GimbalPitchDegree", "FlightYawDegree"):
    print(f"{key}: {xmp[key]}")
# The drone flew about 43 m above its take-off point, camera pointing straight down (pitch -90). The EXIF GPS
# altitude is DJI's absolute altitude, stored twice; the relative altitude is what sets the photo's scale."""),
        Exercise("**2. Ground sample distance.** Derive the Phantom 4 Pro's sensor width from its 84 degree (diagonal) "
                 "field of view and 8.8 mm focal length, for a 3:2 sensor. Then compute the GSD at the photo's "
                 "relative "
                 "altitude, for 5472-pixel-wide photos. Compare with 1.3 cm.",
                 """F, IMW, FOV = 8.8, 5472, 84.0           # mm, pixels, degrees (diagonal)
...  # your code here""",
                 """F, IMW, FOV = 8.8, 5472, 84.0
diagonal = 2 * F * np.tan(np.radians(FOV / 2))
SW = diagonal * 3 / np.sqrt(3 ** 2 + 2 ** 2)      # width of a 3:2 rectangle with that diagonal
H = 42.8
gsd = SW * H / (F * IMW)
print(f"sensor diagonal {diagonal:.2f} mm, width {SW:.2f} mm; GSD at {H} m = {gsd * 100:.2f} cm")"""),
        Exercise("**3. One photo's footprint.** How many metres of ground does one photo cover at that height (5472 x "
                 "3648 pixels)? With 75% frontal overlap, and the short side along the flight line, how far apart are "
                 "consecutive photos?",
                 """...  # your code here (reuse gsd)""",
                 """across, along = gsd * 5472, gsd * 3648
print(f"one photo covers {across:.0f} m x {along:.0f} m")
print(f"75% frontal overlap: a photo every {along * (1 - 0.75):.0f} m along the line")"""),
        Exercise("**4. An affine fit.** Make 8 control points from a known affine plus random errors of 0.5 m; fit an "
                 "affine by least squares; print the residuals and their rms. How do they change with 4 points, or 20?",
                 """rng = np.random.default_rng(0)
true = np.array([[0.0125, 0.0001, 368000.0], [0.0001, -0.0135, 5420040.0]])   # pixel -> metres
...  # your code here""",
                 """rng = np.random.default_rng(0)
true = np.array([[0.0125, 0.0001, 368000.0], [0.0001, -0.0135, 5420040.0]])
for n in (4, 8, 20):
    pixels = rng.uniform(0, 4000, size=(n, 2))
    design = np.c_[pixels, np.ones(n)]
    clicked = design @ true.T + rng.normal(0, 0.5, size=(n, 2))       # where a person clicked, 0.5 m errors
    fit, *_ = np.linalg.lstsq(design, clicked, rcond=None)
    residuals = np.hypot(*(design @ fit - clicked).T)
    print(f"{n:2d} points: rms {np.sqrt(np.mean(residuals ** 2)):.2f} m, max {residuals.max():.2f} m")
# With few points the fit follows the errors (small residuals that look good but are not); with more points the
# rms approaches the real click error. Small residuals from few points are not evidence of accuracy."""),
        Exercise("**5. Two georeferencings.** The extract has, for each date, the same area from the chunk and "
                 "from the "
                 "full tile, on the same grid. Measure the shift between them with "
                 "`skimage.registration.phase_cross_correlation`, in metres.",
                 """from skimage.registration import phase_cross_correlation
...  # your code here""",
                 """from skimage.registration import phase_cross_correlation
for day in ("2018-07-26", "2018-08-06"):
    with rasterio.open(EXTRACT / day / "orthomosaic_chunk.tif") as r:
        chunk, res = r.read(2).astype(float), r.res[0]
    with rasterio.open(EXTRACT / day / "orthomosaic_full_tile.tif") as r:
        tile = r.read(2).astype(float)
    shift, _, _ = phase_cross_correlation(chunk, tile, upsample_factor=10)
    print(f"{day}: the two georeferencings differ by {np.hypot(*shift) * res:.2f} m")"""),
        Exercise("**6. Find it in the code.** Which function writes ArcGIS's adjustment into a sidecar, and which one "
                 "reads the control points from an `.aux.xml`?",
                 """import inspect
...  # your code here""",
                 """import inspect
from data_acquisition.readers import geotiff
from data_acquisition.sources import field
for fn in (field.georeference, geotiff.arcgis_adjustment):
    print(f"{fn.__module__}.{fn.__name__}: {inspect.getdoc(fn).splitlines()[0]}")"""),
    ])

CH04 = Chapter(
    "04_catalogs_and_metadata", "4. Catalogues and metadata: STAC, records, checksums",
    "Exercises of [chapter 4](../04_catalogs_and_metadata.md). Run the setup cell first.",
    """import hashlib, json
import pystac
import yaml
from data_acquisition.catalog import build, descriptors, stac
from data_acquisition.catalog import summary as summaries
from data_acquisition.readers import eml
from data_acquisition.sources import checksums
from data_acquisition.steps.curate import curate_item

OUT = ROOT / "output/manual/stac/training_pond"
""",
    [
        Exercise("**1. Build a catalogue.** Build the sample dataset with the reference summary, run `curate` on its "
                 "items, and save it under `output/manual/stac/training_pond`. Walk the tree: catalogue, collections, "
                 "items.",
                 """s = summaries.load(str(ROOT / "docs/manual/solutions/training_pond.yaml"))
...  # your code here (build.build, curate_item, stac.save)""",
                 """s = summaries.load(str(ROOT / "docs/manual/solutions/training_pond.yaml"))
catalog, report = build.build(SAMPLE, s)
for item in catalog.get_items(recursive=True):
    curate_item(item, s)
path = stac.save(catalog, OUT)
print("saved:", path, "| build report:", {k: v for k, v in report.items() if v} or "empty")
for collection in catalog.get_children():
    print("collection", collection.id)
    for item in collection.get_items():
        print("   item", item.id)"""),
        Exercise("**2. Read an item.** Open the orthomosaic item's JSON. Find its footprint, time, `gsd`, projection "
                 "fields, assets and their roles, and every `beaver:` property. Which descriptors are still missing?",
                 """...  # your code here (the item file is OUT / "training_pond" / <item id> / <item id>.json)""",
                 """item_id = "training_pond_2023-07-12_orthomosaic"
d = json.loads((OUT / "training_pond" / item_id / f"{item_id}.json").read_text())
print("footprint:", d["geometry"]["type"], "| bbox:", [round(v, 6) for v in d["bbox"]])
print("time:", d["properties"]["datetime"], "| gsd:", d["properties"]["gsd"])
print("projection:", {k: v for k, v in d["properties"].items() if k.startswith("proj:") and k != "proj:transform"})
print("assets:", {k: v["roles"] for k, v in d["assets"].items()})
for k, v in d["properties"].items():
    if k.startswith("beaver:") and k != "beaver:origin":
        print(f"  {k}: {str(v)[:100]}")
print("missing:", descriptors.missing(pystac.Item.from_dict(d)))"""),
        Exercise("**3. Validate.** Validate the catalogue against the STAC schemas with `stac.validate`.",
                 """...  # your code here""",
                 """errors = stac.validate(stac.load(OUT / "catalog.json"))
print("valid" if not errors else errors)"""),
        Exercise("**4. Verify a checksum.** Compute the MD5 of the sample orthomosaic; compare it with the record "
                 "(`metadata.xml`) and with the item's `file:checksum`. Decode the multihash prefix.",
                 """...  # your code here (hashlib.md5, eml.read, the item's assets)""",
                 """ortho = DATASET / "ortho_2023-07-12.tif"
md5 = hashlib.md5(ortho.read_bytes()).hexdigest()
record = eml.read((DATASET / "metadata.xml").read_text())
print("file:   ", md5)
print("record: ", record["entities"]["ortho_2023-07-12.tif"]["checksum"])
multihash = d["assets"]["orthomosaic"]["file:checksum"]
print("item:   ", multihash, "-> code", multihash[:2], "(md5), length", int(multihash[2:4], 16), "bytes")
print("all agree:", md5 == record["entities"]["ortho_2023-07-12.tif"]["checksum"][1] == multihash[4:])"""),
        Exercise("**5. A multipart ETag.** Compute the S3 multipart ETag of the sample orthomosaic for a part size of "
                 "5 MiB and of 64 KiB, by hand. Check both with `checksums.check(path, \"s3etag\", value)`. What does "
                 "`check` return for an ETag of a part size it does not try?",
                 """def s3_etag(path, part):
    ...  # MD5 of the concatenated MD5 digests of the parts, then "-<number of parts>"
""",
                 """def s3_etag(path, part):
    data = path.read_bytes()
    digests = [hashlib.md5(data[i:i + part]).digest() for i in range(0, len(data), part)]
    return f"{hashlib.md5(b''.join(digests)).hexdigest()}-{len(digests)}"

for part in (5 * 1024 * 1024, 64 * 1024):
    value = s3_etag(ortho, part)
    print(f"part {part:>9,d} bytes: {value} -> check: {checksums.check(ortho, 's3etag', value)}")
# 5 MiB: one part, checkable (True). 64 KiB: several parts of a size the pipeline does not try: None, undecided,
# and the pipeline falls back to another checksum instead of guessing."""),
        Exercise("**6. Find it in the code.** Where is the multihash prefix of each algorithm defined, and which "
                 "function fills `beaver:provenance`?",
                 """import inspect
...  # your code here""",
                 """import inspect
print("stac.MULTIHASH =", stac.MULTIHASH)
print(inspect.getsourcefile(build._provenance), inspect.getsourcelines(build._provenance)[1])
print(inspect.getdoc(build._provenance))"""),
    ])

CH05 = Chapter(
    "05_data_governance", "5. Data governance: licences, land, Indigenous data",
    "Exercises of [chapter 5](../05_data_governance.md). Run the setup cell first. The exercises change a *copy* "
    "of the sample's site registry, never the real one.",
    """import copy, datetime, tempfile
import yaml
from data_acquisition.catalog import build, descriptors
from data_acquisition.catalog import summary as summaries
from data_acquisition.readers import eml
from data_acquisition.steps.curate import curate_item

REFERENCE = yaml.safe_load((ROOT / "docs/manual/solutions/training_pond.yaml").read_text())
MY_REGISTRY = Path(tempfile.mkdtemp()) / "sites.yaml"
MY_REGISTRY.write_text((SAMPLE / "sites.yaml").read_text())""",
    [
        Exercise("**1. Licences from records.** Read the sample's `metadata.xml` with `eml.read` and print its "
                 "licence. "
                 "Change the licence URL in the text to CC BY-SA 4.0, then to a licence the reader does not know: "
                 "what does it return?",
                 """text = (DATASET / "metadata.xml").read_text()
...  # your code here""",
                 """text = (DATASET / "metadata.xml").read_text()
print("as published:", eml.read(text)["licence"])
by_sa = text.replace("licenses/by/4.0", "licenses/by-sa/4.0")
print("CC BY-SA:    ", eml.read(by_sa)["licence"])
unknown = text.replace("https://creativecommons.org/licenses/by/4.0/", "https://example.org/my-own-terms")
print("unknown:     ", eml.read(unknown)["licence"], "| the text is kept:", eml.read(unknown)["rights"][:60])
# A licence the reader does not know is None: left empty and listed as missing, never guessed."""),
        Exercise("**2. A registry entry.** In `MY_REGISTRY` (a copy of the sample's registry), set `land_status` to "
                 "`{value, by, date, note}` and check it with `summaries.check_sites`. Then try an entry without `by`.",
                 """registry = yaml.safe_load(MY_REGISTRY.read_text())
...  # your code here""",
                 """registry = yaml.safe_load(MY_REGISTRY.read_text())
site = registry["sites"]["training_pond"]
site["land_status"] = {"value": "private ranch (invented)", "by": "A Student", "date": datetime.date.today(),
                       "note": "from the landowner, by phone"}
print("valid entry:", summaries.check_sites(registry["sites"]) or "no problems")
bad = copy.deepcopy(registry["sites"]); bad["training_pond"]["land_status"] = {"value": "private"}
print("without by: ", summaries.check_sites(bad))
MY_REGISTRY.write_text(yaml.safe_dump(registry, sort_keys=False))"""),
        Exercise("**3. From registry to items.** Build and curate the sample with your registry (point `BEAVER_SITES` "
                 "to it). What does the orthomosaic item say about `land_status`, and where did the value come from? "
                 "What changes if `by` is `claude`?",
                 """os.environ["BEAVER_SITES"] = str(MY_REGISTRY)
...  # your code here
os.environ["BEAVER_SITES"] = str(SAMPLE / "sites.yaml")      # back to the sample's registry""",
                 """def orthomosaic_item():
    s = summaries.load(str(ROOT / "docs/manual/solutions/training_pond.yaml"))
    catalog, _ = build.build(SAMPLE, s)
    item = next(i for i in catalog.get_items(recursive=True) if i.id.endswith("orthomosaic"))
    curate_item(item, s)
    return item

os.environ["BEAVER_SITES"] = str(MY_REGISTRY)
item = orthomosaic_item()
print(item.properties["beaver:land_status"], item.properties["beaver:origin"]["land_status"])
registry = yaml.safe_load(MY_REGISTRY.read_text())
registry["sites"]["training_pond"]["land_status"]["by"] = "claude"
MY_REGISTRY.write_text(yaml.safe_dump(registry, sort_keys=False))
print(orthomosaic_item().properties["beaver:origin"]["land_status"])
os.environ["BEAVER_SITES"] = str(SAMPLE / "sites.yaml")
# Entered by a person: source "manual", with who and when. Entered by Claude: source "claude", never confirmed."""),
        Exercise("**4. Hints only.** Add `land_status: private` under the site in a copy of the reference summary, "
                 "next to `hints`. What does the check say?",
                 """s = copy.deepcopy(REFERENCE)
...  # your code here (summaries.check(s, summaries.load_sites()))""",
                 """s = copy.deepcopy(REFERENCE)
s["sites"]["training_pond"]["land_status"] = "private"
print(summaries.check(s, summaries.load_sites()))
# Blocks: a summary may only hint; land status is decided in the site registry, by a person."""),
        Exercise("**5. Find it in the code.** Where does `curate` copy the registry's fields into items, and where "
                 "does a site collection's licence become `various`?",
                 """import inspect
...  # your code here""",
                 """import inspect
from data_acquisition.steps import curate
for fn, needle in ((curate.curate_item, "_set_entered"), (build.build, '"various"')):
    source, first = inspect.getsourcelines(fn)
    for n, line in enumerate(source, first):
        if needle in line:
            print(f"{inspect.getsourcefile(fn)}:{n}: {line.strip()}")"""),
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

CH07 = Chapter(
    "07_pipeline_at_a_glance", "7. The pipeline at a glance",
    "Exercises of [chapter 7](../07_pipeline_at_a_glance.md). Run the setup cell first. The stages are run as "
    "shell commands, as you would in a terminal; `run` prints the command and the end of its output.",
    """import csv, json, subprocess

SUMMARY = ROOT / "docs/manual/solutions/training_pond.yaml"
STAC = SAMPLE / "stac"


def run(*args):
    \"\"\"Run a pipeline command from the repository root; print it and the last lines of its output.\"\"\"
    print("$ python -m", " ".join(str(a) for a in args))
    out = subprocess.run([sys.executable, "-m", *map(str, args)], cwd=ROOT, capture_output=True, text=True)
    print("\\n".join((out.stdout + out.stderr).strip().splitlines()[-6:]), "\\n")


def tree(folder):
    for p in sorted(folder.rglob("*")) if folder.exists() else []:
        if p.is_file():
            print("  ", p.relative_to(folder))""",
    [
        Exercise("**1. Run the stages.** On the sample root, run `describe check` with the reference summary, then "
                 "`build`, `curate` and `root`. After each, list what appeared under the sample root's `stac/`.",
                 """import shutil
shutil.rmtree(STAC, ignore_errors=True)      # start from a sample root without catalogues
run("data_acquisition.catalog.describe", "check", "--root", SAMPLE, "--summary", SUMMARY)
tree(STAC)
...  # your code here: build, curate, root""",
                 """import shutil
shutil.rmtree(STAC, ignore_errors=True)      # start from a sample root without catalogues
run("data_acquisition.catalog.describe", "check", "--root", SAMPLE, "--summary", SUMMARY)
tree(STAC)                                   # nothing: check builds in memory only
run("data_acquisition.catalog.build", "--root", SAMPLE, "--summary", SUMMARY)
tree(STAC)
run("data_acquisition.steps.curate", "--catalog", STAC / "training_pond/catalog.json", "--summary", SUMMARY)
run("data_acquisition.catalog.root", "--root", SAMPLE)
tree(STAC)"""),
        Exercise("**2. Read the outputs.** Open `build_report.json`, `curate_report.csv` and `sites.json`. What does "
                 "each tell you?",
                 """...  # your code here""",
                 """print("build report:", json.loads((STAC / "training_pond/build_report.json").read_text()))
for row in csv.DictReader(open(STAC / "training_pond/curate_report.csv")):
    print("curate:", row)
print("sites:", json.dumps(json.loads((STAC / "sites.json").read_text()), indent=1)[:600])
# The build report lists what could not be described or attached (here nothing); the curate report, per item,
# the missing descriptors and the flags; sites.json, per site, the datasets and what is still unknown.
# The photos are flagged not_in_record: the sample's metadata.xml does not list the photo folder, and the builder
# says so rather than assume it belongs to the record."""),
        Exercise("**3. Options.** Print the `--help` of every command. Which ones write into the data root, and which "
                 "option or command lets you see what would happen without writing anything?",
                 """...  # your code here""",
                 """for module in ("data_acquisition.sources.zenodo", "data_acquisition.catalog.describe",
               "data_acquisition.catalog.build", "data_acquisition.steps.curate", "data_acquisition.catalog.root",
               "data_acquisition.sources.field", "data_acquisition.sources.field_alignment"):
    out = subprocess.run([sys.executable, "-m", module, "--help"], cwd=ROOT, capture_output=True, text=True)
    print(module, "|", " ".join(out.stdout.split("\\n")[0].split()[1:]))
# Writing: the clients (downloads), build, curate, root, field, field_alignment. Looking first: --list (clients),
# describe check (in memory), --dry-run (field step)."""),
        Exercise("**4. Find the stages.** For each stage, name the module and its main function.",
                 """import inspect
...  # your code here""",
                 """import inspect
from data_acquisition.catalog import build, describe, root
from data_acquisition.sources import field, zenodo
from data_acquisition.steps import curate
for fn in (zenodo.main, describe.check_summary, build.build, curate.curate, root.main, field.main):
    module = sys.modules[fn.__module__]
    print(f"{fn.__module__}.{fn.__name__}\\n    {inspect.getdoc(module).splitlines()[0][:100]}")"""),
    ])

CHAPTERS = [CH00, CH01, CH02, CH03, CH04, CH05, CH06, CH07]


def notebook(chapter: Chapter, solutions: bool) -> nbformat.NotebookNode:
    kind = "Solutions" if solutions else "Exercises"
    cells = [new_markdown_cell(f"# {chapter.title}: {kind.lower()}\n\n{chapter.intro}"
                               + ("\n\nThese are the solutions; try the exercise notebook first."
                                  if solutions else "\n\nWork in a copy of this notebook: it is regenerated by "
                                  "`docs/manual/tools/build_notebooks.py`.")),
             new_code_cell(SETUP), new_code_cell(chapter.imports)]
    for e in chapter.exercises:
        cells += [new_markdown_cell(e.prompt), new_code_cell(e.solution if solutions else e.starter)]
    for i, cell in enumerate(cells):
        cell["id"] = f"{chapter.name[:2]}-{i:02d}"          # stable ids: a rebuild changes nothing in git
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
