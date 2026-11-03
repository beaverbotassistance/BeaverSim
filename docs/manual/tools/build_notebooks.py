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

SETUP = '''# Setup: run this cell first, in every notebook
import os, subprocess, sys
from pathlib import Path

# find the repository: from this folder upwards, the first one holding data_acquisition/
ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "data_acquisition").is_dir())
sys.path.insert(0, str(ROOT))                  # so that Python can import the pipeline
SAMPLE = ROOT / "output/manual/sample_root"    # the course's invented dataset
if not SAMPLE.exists():                        # generated once, with this same Python
    subprocess.run([sys.executable, str(ROOT / "docs/manual/tools/make_sample.py"), "--out", str(SAMPLE)], check=True)
DATASET = SAMPLE / "repo/doi_10.5555_training.pond"    # the sample's dataset folder
EXTRACT = ROOT / "docs/manual/data/montana_extract"    # a real piece of Rumney Ranch
os.environ["BEAVER_SITES"] = str(SAMPLE / "sites.yaml")    # use the sample's site registry, not the real one
import warnings; warnings.simplefilter("ignore")           # hide warnings; remove this line when debugging
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
    network: bool = False           # needs an internet connection (the course test skips it unless asked)


CH00 = Chapter(
    "00_setup", "0. Setup: environment, drives, sample data",
    "Exercises of [chapter 0](../00_setup.md). Run the setup cell first: it makes the sample data root.",
    '''from data_acquisition.catalog import summary as summaries''',
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
    '''import json
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
                 "`+proj=eqc +lat_ts=-52.28859923 +datum=WGS84 +units=m`. Which pairs agree and which are 30 km apart? "
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
# is read with the spherical formula by PROJ 9.5 and with the ellipsoidal one by PROJ 9.8: 30 km apart.'''),
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
    """import csv, json

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

CH08 = Chapter(
    "08_open_datasets", "8. Bringing in an open dataset",
    "Exercises of [chapter 8](../08_open_datasets.md). Run the setup cell first. **These exercises download from the "
    "Arctic Data Center**: an internet connection is needed. They use their own data root and the real site "
    "registry, because the Baldwin Peninsula is a real site.",
    """import csv, shutil, stat
os.environ.pop("BEAVER_SITES", None)         # the real site registry
OPEN = ROOT / "output/manual/open_root"
DOI = "doi:10.18739/A2CZ3253W"
FOLDER = OPEN / "arcticdata/doi_10.18739_A2CZ3253W"


def run(*args):
    \"\"\"Run a pipeline command from the repository root; print it and the last lines of its output.\"\"\"
    print("$ python -m", " ".join(str(a) for a in args))
    out = subprocess.run([sys.executable, "-m", *map(str, args)], cwd=ROOT, capture_output=True, text=True)
    print("\\n".join((out.stdout + out.stderr).strip().splitlines()[-8:]), "\\n")""",
    [
        Exercise("**1. List.** List `doi:10.18739/A2CZ3253W` with the DataONE client. What is its licence, and how "
                 "large is it?",
                 """...  # your code here: run("data_acquisition.sources.dataone", "--root", OPEN, "--id", DOI, ...)""",
                 """shutil.rmtree(OPEN, ignore_errors=True)      # start from an empty data root
run("data_acquisition.sources.dataone", "--root", OPEN, "--id", DOI, "--list")
# CC-BY-4.0, one zip of 55 KB (the listing rounds it to 0.000 GB)."""),
        Exercise("**2. Download.** Download it into `output/manual/open_root`. Find its row in `downloads.csv` and "
                 "explain each column. Run the download again: what happens?",
                 """...  # your code here""",
                 """run("data_acquisition.sources.dataone", "--root", OPEN, "--id", DOI)
for row in csv.DictReader(open(OPEN / "downloads.csv")):
    for key, value in row.items():
        print(f"  {key:19s} {value}")
run("data_acquisition.sources.dataone", "--root", OPEN, "--id", DOI)
# The second run downloads nothing: the file is there, and is only verified again."""),
        Exercise("**3. Extract.** Extract the zip. Which files appeared, and with which permissions? Run the "
                 "extraction again.",
                 """zip_path = next(FOLDER.glob("*.zip"))
...  # your code here""",
                 """zip_path = next(FOLDER.glob("*.zip"))
run("data_acquisition.sources.archives", zip_path)
for p in sorted(FOLDER.iterdir()):
    print(f"  {stat.filemode(p.stat().st_mode)}  {p.name}")
gdb = next(FOLDER.glob("*.gdb"))
print("  inside the geodatabase:", len(list(gdb.iterdir())), "files, e.g.",
      stat.filemode(next(gdb.iterdir()).stat().st_mode))
run("data_acquisition.sources.archives", zip_path)
# The extracted files are read-only; a second run only checks them against the zip's CRC-32."""),
        Exercise("**4. Catalogue.** Check, build and curate it with `--verify`, using the summary "
                 "`arcticdata_baldwin_dams`. What was each item verified against?",
                 """...  # your code here""",
                 """import json
run("data_acquisition.catalog.describe", "check", "--root", OPEN, "--summary", "arcticdata_baldwin_dams")
run("data_acquisition.catalog.build", "--root", OPEN, "--summary", "arcticdata_baldwin_dams")
run("data_acquisition.steps.curate", "--catalog", OPEN / "stac/arcticdata_baldwin_dams/catalog.json",
    "--summary", "arcticdata_baldwin_dams", "--verify")
for p in sorted((OPEN / "stac/arcticdata_baldwin_dams").glob("*/*/*.json")):
    d = json.loads(p.read_text())
    print(d["id"], "->", d["properties"]["beaver:provenance"]["verified"])"""),
        Exercise("**5. Intake.** Write an intake prompt for any Zenodo DOI into `output/manual/intake_example` "
                 "(nothing is downloaded). Read the client contract in it: which rules does it set?",
                 """...  # your code here (data_acquisition.intake --url ... --root ... --dataset ... --out ...)""",
                 """out = ROOT / "output/manual/intake_example"
run("data_acquisition.intake", "--url", "https://doi.org/10.5281/zenodo.7493153", "--root", OPEN,
    "--dataset", "example_new", "--out", out)
text = (out / "prompt.md").read_text()
start = text.find("Contract for a source client")
print(text[start:start + 1800])"""),
        Exercise("**6. Find it in the code.** Which function downloads a file with resume, and which writes the row "
                 "of `downloads.csv`?",
                 """import inspect
...  # your code here""",
                 """import inspect
from data_acquisition.sources import downloads, http
for fn in (http.fetch, downloads.finish, downloads.log):
    print(f"{fn.__module__}.{fn.__name__}: {inspect.getdoc(fn).splitlines()[0]}")"""),
    ], network=True)

CH09 = Chapter(
    "09_describing_a_dataset", "9. Describing a dataset: summaries and Claude",
    "Exercises of [chapter 9](../09_describing_a_dataset.md). Run the setup cell first.",
    """import copy, datetime, difflib, json, tempfile
import rasterio
import yaml
from data_acquisition.catalog import build, describe, evidence
from data_acquisition.catalog import summary as summaries

OUT = ROOT / "output/manual/describe/training_pond"
REFERENCE = yaml.safe_load((ROOT / "docs/manual/solutions/training_pond.yaml").read_text())


def check(s):
    \"\"\"Check a summary (a dict) and build it in memory; print what the pipeline says.\"\"\"
    path = Path(tempfile.mkdtemp()) / "my_summary.yaml"
    path.write_text(yaml.safe_dump(copy.deepcopy(s), sort_keys=False))
    try:
        loaded = summaries.load(str(path))
    except ValueError as e:
        print("BLOCKS:\\n", str(e).split("\\n", 1)[1])
        return None
    catalog, report = build.build(SAMPLE, loaded)
    print("valid; build report:", {k: v for k, v in report.items() if v} or "empty")
    return catalog""",
    [
        Exercise("**1. Evidence.** Gather the evidence and the prompt for the sample dataset into "
                 "`output/manual/describe/training_pond`. For each file, what did code read? What did it read about "
                 "the photos, and why so little?",
                 """...  # your code here: describe prompt --root SAMPLE --folders "repo/*" --dataset training_pond""",
                 """subprocess.run([sys.executable, "-m", "data_acquisition.catalog.describe", "prompt",
                "--root", str(SAMPLE), "--folders", "repo/*", "--dataset", "training_pond",
                "--source-kind", "dataone", "--out", str(OUT)], cwd=ROOT, check=True, capture_output=True)
ev = json.loads((OUT / "evidence.json").read_text())
for f in ev["folders"][0]["files"]:
    print(f"{f['name']:45s} {[k for k in f if k not in ('name', 'bytes')]}")
print("photo folders become one entry from", evidence.PHOTO_FOLDER, "photos up; the sample has 6, read one by one, "
      "and code reads nothing from a single photo")"""),
        Exercise("**2. The rules.** Read the rules in `prompt.md`. Which of them stop Claude from inventing values?",
                 """...  # your code here (describe.RULES)""",
                 """for line in describe.RULES.split("\\n- "):
    if any(w in line.lower() for w in ("never", "only", "invent", "unclear", "disagree")):
        print("-", " ".join(line.split())[:220])"""),
        Exercise("**3. By hand.** Write a summary for the sample from the evidence alone, starting from the skeleton; "
                 "make it pass `check`; compare it with the reference summary.",
                 """mine = {
    "schema": 1, "dataset": "training_pond", "title": "...",
    "authored": {"by": "A Student", "date": datetime.date.today()}, "reviewed": None,
    "source": {"kind": "dataone", "provider": "..."},
    "groups": [{"folder": "repo/doi_10.5555_training.pond", "record": {"path": "metadata.xml", "format": "eml"},
                "site": "training_pond", "files": [
                    # one entry per file: {"path": ..., "product": ..., "date": datetime.date(...)} or role + attach_to
                ]}],
}
check(mine)""",
                 """mine = {
    "schema": 1, "dataset": "training_pond", "title": "Training Pond drone survey, July 2023",
    "authored": {"by": "A Student", "date": datetime.date.today()}, "reviewed": None,
    "source": {"kind": "dataone", "provider": "Example repository (invented)"},
    "groups": [{"folder": "repo/doi_10.5555_training.pond", "record": {"path": "metadata.xml", "format": "eml"},
                "site": "training_pond", "positioning": ["gnss"], "files": [
        {"path": "ortho_2023-07-12.tif", "product": "orthomosaic", "date": datetime.date(2023, 7, 12)},
        {"path": "dsm_2023-07-12.tif", "product": "dsm", "date": datetime.date(2023, 7, 12)},
        {"path": "dem_2022.asc", "product": "dtm", "date": datetime.date(2022, 8, 1), "date_precision": "month",
         "crs": "EPSG:32612"},
        {"path": "dams_2023-07-12.gpkg", "product": "annotations", "date": datetime.date(2023, 7, 12)},
        {"path": "photos_2023-07-12", "product": "photos", "date": datetime.date(2023, 7, 12)},
        {"path": "README.txt", "role": "metadata", "attach_to": ["orthomosaic", "dsm", "dtm", "annotations", "photos"]},
    ]}],
}
check(mine)
ref_files = {f["path"]: f for f in REFERENCE["groups"][0]["files"]}
for f in mine["groups"][0]["files"]:
    extra = {k: v for k, v in ref_files[f["path"]].items() if k not in f}
    if extra:
        print(f"the reference also gives {f['path']}: {extra}")"""),
        Exercise("**4. Review a draft.** `docs/manual/data/flawed_draft.yaml` passes the check but has four mistakes a "
                 "reviewer should catch. Find them with the evidence.",
                 """flawed = yaml.safe_load((ROOT / "docs/manual/data/flawed_draft.yaml").read_text())
check(flawed)
...  # your code here: compare its values with the evidence (headers, record, methods text)""",
                 """flawed = yaml.safe_load((ROOT / "docs/manual/data/flawed_draft.yaml").read_text())
check(flawed)
files = {f["path"]: f for f in flawed["groups"][0]["files"]}
with rasterio.open(DATASET / "ortho_2023-07-12.tif") as r:
    print("1. bands: draft", files["ortho_2023-07-12.tif"]["bands"], "| file declares", [c.name for c in r.colorinterp])
methods = (DATASET / "metadata.xml").read_text()
print("2. dem_2022.asc: draft date", files["dem_2022.asc"]["date"], "| methods text:",
      methods[methods.find("The 2022"):methods.find("The 2022") + 90])
print("3. positioning: draft", flawed["groups"][0]["positioning"], "| nothing in the evidence mentions RTK")
print("4. dams: draft product", files["dams_2023-07-12.gpkg"]["product"], "| methods: 'Dams were mapped by hand on the "
      "orthomosaic' -> annotations, not surveyed points")
catalog = check(flawed)
ortho = next(i for i in catalog.get_items(recursive=True) if i.id.endswith("orthomosaic"))
print("the build flags the bands:", [q["flag"] for q in ortho.properties["beaver:quality"]])"""),
        Exercise("**5. (Optional) Draft with Claude.** Run the prompt in a Claude Code session on the sample. The "
                 "prompt writes into `data_acquisition/summaries/` and may add a site to "
                 "`data_acquisition/sites.yaml`: delete "
                 "the draft and undo any registry change afterwards (`git status`, `git restore`).",
                 """# Done in a Claude Code session, not here. Afterwards:
print(subprocess.run(["git", "status", "--short"], cwd=ROOT, capture_output=True, text=True).stdout)""",
                 """# Done in a Claude Code session, not here. Afterwards, check what it changed:
status = subprocess.run(["git", "status", "--short"], cwd=ROOT, capture_output=True, text=True).stdout
print(status or "nothing changed")"""),
        Exercise("**6. Find it in the code.** Where are the drafting rules, and which function decides what evidence "
                 "a raster gets?",
                 """import inspect
...  # your code here""",
                 """import inspect
print("rules: describe.RULES in", inspect.getsourcefile(describe), "line",
      next(n for n, l in enumerate(inspect.getsource(describe).splitlines(), 1) if l.startswith("RULES")))
print(inspect.getsource(evidence._raster))"""),
    ])

CH10 = Chapter(
    "10_building_and_curating", "10. Building and curating catalogues",
    "Exercises of [chapter 10](../10_building_and_curating.md). Run the setup cell first.",
    """import copy, datetime, json, shutil, tempfile
import yaml
from data_acquisition.catalog import build, stac
from data_acquisition.catalog import summary as summaries
from data_acquisition.steps import curate

REFERENCE = yaml.safe_load((ROOT / "docs/manual/solutions/training_pond.yaml").read_text())


def load(s):
    path = Path(tempfile.mkdtemp()) / "summary.yaml"
    path.write_text(yaml.safe_dump(copy.deepcopy(s), sort_keys=False))
    return summaries.load(str(path))


def files(s):
    return s["groups"][0]["files"]""",
    [
        Exercise("**1. Build.** Build the sample with the reference summary. Then copy any small file into the dataset "
                 "folder and build again: what does the report say? Remove the copy.",
                 """s = load(REFERENCE)
...  # your code here""",
                 """s = load(REFERENCE)
catalog, report = build.build(SAMPLE, s)
print(len(list(catalog.get_items(recursive=True))), "items; report:", {k: v for k, v in report.items() if v} or "empty")
stray = DATASET / "README_copy.txt"
shutil.copy(DATASET / "README.txt", stray)
catalog, report = build.build(SAMPLE, s)
print("with a stray file:", {k: v for k, v in report.items() if v})
stray.unlink()"""),
        Exercise("**2. Flags.** Curate the items and list every flag with its source. Which ones need action?",
                 """...  # your code here (curate.curate_item)""",
                 """catalog, _ = build.build(SAMPLE, s)
for item in catalog.get_items(recursive=True):
    curate.curate_item(item, s)
    print(item.id, [(q["flag"], q["source"]) for q in item.properties["beaver:quality"]])
# needs_inspection asks for a person; not_in_record says the record does not list the photos (worth knowing, no
# action); crs_from_summary and the note record what the summary supplied."""),
        Exercise("**3. Make flags appear.** In copies of the reference summary, give the orthomosaic the wrong band "
                 "order, the grid a CRS of the wrong UTM zone (`EPSG:32611`), and the DSM a date outside the record's "
                 "period. Which flag does each produce, and who raises it?",
                 """...  # your code here""",
                 """def flags_of(s, item_suffix):
    catalog, _ = build.build(SAMPLE, load(s))
    item = next(i for i in catalog.get_items(recursive=True) if i.id.endswith(item_suffix))
    curate.curate_item(item, load(s))
    return [(q["flag"], q["source"]) for q in item.properties["beaver:quality"]]

wrong = copy.deepcopy(REFERENCE); files(wrong)[0]["bands"] = ["blue", "green", "red", "alpha"]
print("bands:", flags_of(wrong, "orthomosaic"))
wrong = copy.deepcopy(REFERENCE); files(wrong)[2]["crs"] = "EPSG:32611"
print("CRS:  ", flags_of(wrong, "dtm"))
wrong = copy.deepcopy(REFERENCE); files(wrong)[1]["date"] = datetime.date(2021, 5, 1)
print("date: ", flags_of(wrong, "dsm"))"""),
        Exercise("**4. Verify.** Curate with `verify_files=True`. What was each file checked against, and why do the "
                 "photos get `checksum_unknown`?",
                 """...  # your code here""",
                 """catalog, _ = build.build(SAMPLE, s)
for item in catalog.get_items(recursive=True):
    curate.curate_item(item, s, verify_files=True)
    flags = [q["flag"] for q in item.properties["beaver:quality"] if q["flag"].startswith("checksum")]
    print(f"{item.id:40s} verified: {item.properties['beaver:provenance'].get('verified')} {flags}")
# The photos are not in the record and were not downloaded by a client: nothing states their checksum."""),
        Exercise("**5. Rebuild.** Remove the DSM from a copy of the summary, rebuild into a scratch copy of the sample "
                 "root, and compare the collection's links with the item folders on disk.",
                 """scratch = Path(tempfile.mkdtemp()) / "root"
shutil.copytree(SAMPLE, scratch, ignore=shutil.ignore_patterns("stac"))
...  # your code here""",
                 """scratch = Path(tempfile.mkdtemp()) / "root"
shutil.copytree(SAMPLE, scratch, ignore=shutil.ignore_patterns("stac"))
for name, s2 in (("full", REFERENCE), ("without the DSM", copy.deepcopy(REFERENCE))):
    if name != "full":
        s2["groups"][0]["files"] = [f for f in files(s2) if f["path"] != "dsm_2023-07-12.tif"]
    catalog, _ = build.build(scratch, load(s2))
    stac.save(catalog, scratch / "stac/training_pond")
collection = scratch / "stac/training_pond/training_pond"
links = [l["href"].split("/")[1] for l in json.loads((collection / "collection.json").read_text())["links"]
         if l["rel"] == "item"]
print("linked:", links)
print("on disk:", sorted(p.name for p in collection.iterdir() if p.is_dir()))
# The DSM's folder is still on disk but no longer linked: follow links, do not scan folders."""),
        Exercise("**6. Find it in the code.** Where does `curate` clear the previous automatic flags, and where does "
                 "`build` write the report?",
                 """import inspect
...  # your code here""",
                 """import inspect
for fn, needle in ((curate.curate_item, '!= "auto"'), (build.main, "build_report.json")):
    source, first = inspect.getsourcelines(fn)
    for n, line in enumerate(source, first):
        if needle in line:
            print(f"{inspect.getsourcefile(fn)}:{n}: {line.strip()}")"""),
    ])

CH11 = Chapter(
    "11_field_data", "11. Field data: from a field drive to beaver_dataset",
    "Exercises of [chapter 11](../11_field_data.md). Run the setup cell first. They use the Montana extract and the "
    "Rumney layout file; none needs the drive.",
    """import copy, inspect, json
import geopandas as gpd
import pyproj, rasterio
from pyproj import CRS, Geod
from rasterio.crs import CRS as RasterioCRS
from rasterio.warp import transform
from data_acquisition.sources import field, field_alignment

LAYOUT = field.load_layout("rumney_ranch")
META = json.loads((EXTRACT / "extract.json").read_text())""",
    [
        Exercise("**1. The layout file.** For 26 July 2018, list where the orthomosaics and the annotation layers go. "
                 "Find, in the extract's `extract.json`, which of them the extract was cut from.",
                 """day = "2018-07-26"
...  # your code here (LAYOUT["orthomosaics"], LAYOUT["annotations"], META["dates"][day])""",
                 """day = "2018-07-26"
orthos = [e for e in LAYOUT["orthomosaics"] if e.get("to", "").startswith(f"surveys/{day}/")]
layers = [e for e in LAYOUT["annotations"] if e.get("to", "").startswith(f"annotations/{day}/")]
print(len(orthos), "orthomosaics,", len(layers), "annotation layers")
for e in layers:
    print(f"  {e['source']} / {e['layer']} -> {e['to']} ({e['features']} features)")
for kind in ("chunk", "full_tile"):
    target = META["dates"][day][kind]
    source = next(e["source"] for e in orthos if e["to"] == target)
    print(f"{kind}: {target}  <-  {LAYOUT['base']}{source}")"""),
        Exercise("**2. Names.** Check five names against the naming policy with `field.ORTHO_NAME` and "
                 "`field.LAYER_NAME`, three that follow it and two that do not. Then check a copy of the layout with "
                 "one bad name using `field.check_layout`.",
                 """names = ["surveys/2018-07-26/orthomosaic_part-4.tif",
         "surveys/2018-07-26/orthomosaic_part-4_chunk-3.tif",
         "annotations/2018-07-26/dams_points.gpkg",
         "surveys/26July2018/orthomosaic_part-4.tif",
         "annotations/2018-07-26/beaver_dams.gpkg"]
...  # your code here""",
                 """names = ["surveys/2018-07-26/orthomosaic_part-4.tif",
         "surveys/2018-07-26/orthomosaic_part-4_chunk-3.tif",
         "annotations/2018-07-26/dams_points.gpkg",
         "surveys/26July2018/orthomosaic_part-4.tif",
         "annotations/2018-07-26/beaver_dams.gpkg"]
for name in names:
    rule = field.ORTHO_NAME if name.startswith("surveys/") else field.LAYER_NAME
    print(f"{'ok ' if rule.match(name) else 'BAD'} {name}")
# The date must be ISO (YYYY-MM-DD), and a layer must start with a known feature (field.FEATURES).
broken = copy.deepcopy(LAYOUT)
broken["annotations"][0]["to"] = "annotations/2018-07-26/beaver_dams.gpkg"
broken["orthomosaics"][1]["to"] = broken["orthomosaics"][0]["to"]
print(*field.check_layout(broken), sep="\\n")"""),
        Exercise("**3. A CRS correction.** Apply the layout's `crs_corrections` to the ARC zone's ESRI definition "
                 "(`ESRI:102432`) with `field.corrected_crs`. What does the result say about the sphere? "
                 "Then place the "
                 "centre of the extract's box with the declared and the corrected CRS, under the PROJ of pyproj and "
                 "that of rasterio.",
                 """esri = CRS.from_user_input("ESRI:102432")
...  # your code here""",
                 """esri = CRS.from_user_input("ESRI:102432")
fixed = field.corrected_crs(esri.to_wkt(), LAYOUT["crs_corrections"])
print(fixed[:420], "...")
# ELLIPSOID["unknown",6378137,0]: an inverse flattening of 0 means a sphere of radius 6378137 m, and the method is
# "Equidistant Cylindrical (Spherical)", as ArcGIS evaluates the ARC zones.
b = META["box"]["bounds"]
x, y = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
print("PROJ: pyproj", pyproj.proj_version_str, "| rasterio", rasterio.__proj_version__)
places = {}
for name, wkt in (("declared", esri.to_wkt()), ("corrected", fixed)):
    places[name, "pyproj"] = pyproj.Transformer.from_crs(CRS.from_wkt(wkt), "EPSG:4326", always_xy=True).transform(x, y)
    lon, lat = transform(RasterioCRS.from_wkt(wkt), "EPSG:4326", [x], [y])
    places[name, "rasterio"] = (lon[0], lat[0])
reference = places["corrected", "pyproj"]
for key, (lon, lat) in places.items():
    km = Geod(ellps="WGS84").inv(reference[0], reference[1], lon, lat)[2] / 1000
    print(f"{key[0]:9s} {key[1]:8s} {lat:.5f} {lon:.5f}  {km:5.1f} km from the corrected place")
# Only the declared CRS under the newer PROJ (9.8, ellipsoidal Equidistant Cylindrical) lands about 30 km away
# (25 km north, 17 km east)."""),
        Exercise("**4. Alignment.** Measure the best-fit shift of the extract's dam (26 July and 6 August) "
                 "on the chunk "
                 "and on the full tile with `field_alignment.best_shift`, and compare with the full-resolution rows in "
                 "`extract.json`. Which image was it drawn on?",
                 """day = "2018-07-26"
dams = gpd.read_file(EXTRACT / day / "annotations/dams.gpkg", fid_as_index=True)
...  # your code here (reproject each outline to the image's CRS first)""",
                 """for day in ("2018-07-26", "2018-08-06"):
    dams = gpd.read_file(EXTRACT / day / "annotations/dams.gpkg", fid_as_index=True)
    drive = {(r["feature_id"], r["kind"]): r["shift_m"] for r in META["dates"][day]["alignment"]}
    for kind, label in (("chunk", "chunk"), ("full_tile", "full tile")):
        tif = EXTRACT / day / f"orthomosaic_{kind}.tif"
        with rasterio.open(tif) as r:
            outlines = dams.to_crs(r.crs.to_wkt())
        for fid, geom in outlines.geometry.items():
            east, north = field_alignment.best_shift(tif, geom)
            print(f"{day} feature {fid} {label:9s}: {east:+.2f} m east, {north:+.2f} m north "
                  f"(at 1.3 cm on the drive: {drive.get((fid, label))} m)")
# 26 July: the chunk fits within a pixel, the full tile needs about 0.6 m: drawn on the chunk.
# 6 August: both fit within ~0.15 m here, so one outline cannot tell; that date's medians (0.21 m on the chunks,
# 0.53 m on the full tiles) can. Single values are noisy: read medians."""),
        Exercise("**5. Find it in the code.** Which function plans the actions, which carries them out, and which "
                 "removes files a previous build left?",
                 """...  # your code here (inspect)""",
                 """for fn in (field.plan, field.execute, field.prune):
    print(f"{fn.__name__}  {inspect.getsourcefile(fn)}:{inspect.getsourcelines(fn)[1]}")
    print("   ", inspect.getdoc(fn).splitlines()[0])"""),
    ])

CH12 = Chapter(
    "12_inspecting", "12. Looking ahead: inspecting a dataset (milestone 2)",
    "Exercises of [chapter 12](../12_inspecting.md): a preview of milestone 2, made only from what the catalogue "
    "holds. Run the setup cell first.",
    """import json
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pystac, rasterio
from shapely.geometry import shape
from data_acquisition.catalog import build, root, stac
from data_acquisition.catalog import summary as summaries
from data_acquisition.steps import curate


def product(item):
    \"\"\"The product of an item: the key of its data asset.\"\"\"
    return next(k for k, a in item.assets.items() if "data" in (a.roles or []))""",
    [
        Exercise("**1. A table of items.** Build, curate and root the sample, open `<sample root>/stac/catalog.json` "
                 "with pystac, and make one table row per item: id, product, kind, site, start and end of its time, "
                 "date precision, number of flags.",
                 """s = summaries.load(str(ROOT / "docs/manual/solutions/training_pond.yaml"))
catalog, _ = build.build(SAMPLE, s)
for item in catalog.get_items(recursive=True):
    curate.curate_item(item, s)
stac.save(catalog, SAMPLE / "stac/training_pond")
root.build_root(SAMPLE / "stac")
...  # your code here (pystac.Catalog.from_file, item.datetime, item.properties)""",
                 """s = summaries.load(str(ROOT / "docs/manual/solutions/training_pond.yaml"))
catalog, _ = build.build(SAMPLE, s)
for item in catalog.get_items(recursive=True):
    curate.curate_item(item, s)
stac.save(catalog, SAMPLE / "stac/training_pond")
root.build_root(SAMPLE / "stac")

items = list(pystac.Catalog.from_file(str(SAMPLE / "stac/catalog.json")).get_items(recursive=True))
rows = []
for item in items:
    p = item.properties
    start = item.datetime or pystac.utils.str_to_datetime(p["start_datetime"])
    end = item.datetime or pystac.utils.str_to_datetime(p["end_datetime"])
    rows.append({"id": item.id, "product": product(item), "kind": p["beaver:kind"], "site": p["beaver:site"],
                 "start": start, "end": end, "precision": p.get("beaver:date_precision"),
                 "flags": len(p["beaver:quality"]), "geometry": shape(item.geometry)})
table = pd.DataFrame(rows)
table.drop(columns="geometry")"""),
        Exercise("**2. Coverage.** Turn the table into a GeoDataFrame and plot the footprints in the site's UTM zone, "
                 "coloured by product. What does each footprint cover, and why is the photos' one invisible?",
                 """...  # your code here (gpd.GeoDataFrame(table, crs="EPSG:4326"), .to_crs, .plot)""",
                 """frame = gpd.GeoDataFrame(table, crs="EPSG:4326").to_crs("EPSG:32612")
ax = frame.plot(column="product", alpha=0.3, edgecolor="black", legend=True, figsize=(6, 6))
ax.set_title("Training Pond: item footprints (UTM 12N)")
plt.show()
print(frame.assign(area_m2=frame.area.round())[["product", "area_m2"]])
# The rasters cover their grid (20 m x 20 m), the annotations the extent of their features. The photos' footprint
# is the outline of the camera positions, not the ground the photos show: these six were taken along one line, so
# it is a sliver of almost no area (finding 17 in docs/dataset/course_findings.md)."""),
        Exercise("**3. Timeline.** One row per product, a mark per item from its start to its end. Which item is an "
                 "interval, and why?",
                 """...  # your code here (plt.subplots, ax.plot or ax.barh)""",
                 """fig, ax = plt.subplots(figsize=(8, 3))
products = sorted(table["product"].unique())
for _, r in table.iterrows():
    y = products.index(r["product"])
    ax.plot([r["start"], r["end"]], [y, y], lw=8, solid_capstyle="butt")
    ax.plot([r["start"]], [y], marker="|", markersize=14, color="black")
ax.set_yticks(range(len(products)), products)
plt.show()
print(table.loc[table["start"] != table["end"], ["id", "start", "end", "precision"]])
# The DTM: the summary knows it only to the month (August 2022), so it covers the whole month."""),
        Exercise("**4. Quick-look.** Without a stored quick-look, read the orthomosaic at about 200 pixels wide "
                 "(`out_shape`) and show it next to the item's flags.",
                 """item = next(i for i in items if product(i) == "orthomosaic")
...  # your code here (rasterio.open(item.assets[...].get_absolute_href()), read(out_shape=...))""",
                 """item = next(i for i in items if product(i) == "orthomosaic")
with rasterio.open(item.assets["orthomosaic"].get_absolute_href()) as r:
    width = 200
    height = round(r.height * width / r.width)
    rgb = r.read([1, 2, 3], out_shape=(3, height, width))
plt.imshow(np.moveaxis(rgb, 0, -1))
plt.title(item.id)
plt.axis("off")
plt.show()
print(f"read {rgb.nbytes:,d} bytes instead of {r.width * r.height * 3:,d}")
print("flags:", item.properties["beaver:quality"] or "none")"""),
        Exercise("**5. What is missing.** By code: which items have a `thumbnail` asset, which have colonies, and what "
                 "does `sites.json` say is still to decide?",
                 """...  # your code here""",
                 """def has_thumbnail(item):
    return any("thumbnail" in (a.roles or []) for a in item.assets.values())


print("thumbnails:", [i.id for i in items if has_thumbnail(i)])
print("with colonies:", [i.id for i in items if i.properties.get("beaver:colonies")])
sites = json.loads((SAMPLE / "stac/sites.json").read_text())
for site, entry in sites.items():
    print(site, {k: entry[k] for k in ("colonies", "land_status", "governance")})
# No quick-looks and no colonies: the browser must read files at a reduced size, and the colony views wait for the
# registry's decisions (and define_aoi, milestone 5)."""),
    ])

CH13 = Chapter(
    "13_readers", "13. Readers",
    "Exercises of [chapter 13](../13_readers.md). Run the setup cell first.",
    """import tempfile, textwrap
import numpy as np
from data_acquisition.readers import RECORD_FILES, RECORDS, files, geotiff, photos, vector""",
    [
        Exercise("**1. Rasters.** Read the header of the sample's orthomosaic and of `dem_2022.asc` with "
                 "`geotiff.info`. Which bands does each declare, and what does the grid lack? "
                 "Is `README.txt` a raster?",
                 """...  # your code here (geotiff.info, geotiff.declared_bands, geotiff.is_raster)""",
                 """for name in ("ortho_2023-07-12.tif", "dem_2022.asc"):
    h = geotiff.info(DATASET / name)
    print(name, {k: h[k] for k in ("driver", "epsg", "has_crs", "count", "dtypes", "nodata", "colorinterp")})
    print("   declared bands:", geotiff.declared_bands(h))
print("README.txt is a raster:", geotiff.is_raster(DATASET / "README.txt"))
# The orthomosaic declares red, green, blue, alpha. The grid declares nothing (one grey band) and has no CRS:
# the summary must give it (crs_from_summary, chapter 10)."""),
        Exercise("**2. Vectors.** Read the extract's `dams.gpkg` (26 July) with `vector.info`. Where did its vertical "
                 "CRS go, and which geometry type is reported?",
                 """...  # your code here""",
                 """info = vector.info(EXTRACT / "2018-07-26/annotations/dams.gpkg")
layer = info["layers"][0]
print({k: layer[k] for k in ("name", "geometry_type", "features", "epsg", "vertical_crs")})
print("horizontal CRS:", layer["crs"][:90], "...")
# The compound CRS is split: the horizontal part is "crs", the vertical one (NAVD88, US survey feet) goes to
# vertical_crs. The type is the one GDAL reads, without M (chapter 1)."""),
        Exercise("**3. Records.** Read the sample's `metadata.xml` with the reader `RECORDS` gives for it. "
                 "What does it "
                 "say about each file's checksum?",
                 """...  # your code here (RECORD_FILES, RECORDS[...]["read"])""",
                 """fmt = RECORD_FILES["metadata.xml"]
record = RECORDS[fmt]["read"]((DATASET / "metadata.xml").read_text())
print(fmt, "|", record["title"], "|", record["licence"], "|", record["dates"])
for name, e in record["entities"].items():
    print(f"  {name:28s} {e['size']} bytes, checksum {e['checksum']}")"""),
        Exercise("**4. ArcGIS sidecars.** Read the four `original_*.arcgis.aux.xml` of the extract with "
                 "`geotiff.arcgis_adjustment`; fit a first-order polynomial through each one's control points and "
                 "compute the residuals. How do the chunks and the full tiles compare?",
                 """aux = EXTRACT / "2018-07-26/original_chunk.arcgis.aux.xml"
x = geotiff.arcgis_adjustment(aux.read_text())
...  # your code here (np.linalg.lstsq on [source, 1] -> target)""",
                 """for aux in sorted(EXTRACT.glob("*/original_*.arcgis.aux.xml")):
    x = geotiff.arcgis_adjustment(aux.read_text())
    design = np.c_[x["source"], np.ones(len(x["source"]))]
    coef = np.linalg.lstsq(design, x["target"], rcond=None)[0]
    residuals = np.hypot(*(design @ coef - x["target"]).T)
    print(f"{aux.parent.name} {aux.name:34s} {x['type']} order {x['order']}, {len(residuals):2d} points, "
          f"rms {np.sqrt((residuals ** 2).mean()):.3f} m, max {residuals.max():.3f} m")
# The chunks fit their few control points to a few centimetres; the full tiles miss theirs by 0.5-0.6 m on average
# (up to 2 m): one affine cannot follow a whole tile's distortion. That is why the annotations, drawn on the chunks,
# sit 0.5-1 m off on the full tiles (chapter 11). The rms is the one in georeference.csv on the drive: an affine
# change of the source coordinates (to pixels, as the field step does) leaves an affine fit's residuals unchanged."""),
        Exercise("**5. Companions.** Which files does `files.companions` give for `ortho.tif` and for `dams.shp`?",
                 """...  # your code here""",
                 """print(sorted(files.companions("ortho.tif")))
print(sorted(files.companions("dams.shp")))
print(files.inside_container("Dams.gdb/a00000001.gdbtable"))"""),
        Exercise("**6. Test an edge case.** EXIF stores the altitude as a positive number with a flag "
                 "(`GPSAltitudeRef`: "
                 "1 = below sea level). Write a pytest test that makes a photo 400 m below sea level and checks that "
                 "`photos.exif` reads -400 m. Run it in a scratch folder. What happens?",
                 """scratch = Path(tempfile.mkdtemp())
...  # write a test to scratch / "test_edge.py" (Pillow: Image.Exif, ExifTags.IFD.GPSInfo), run pytest on it""",
                 """scratch = Path(tempfile.mkdtemp())
test = textwrap.dedent('''
    import pytest
    from PIL import ExifTags, Image
    from data_acquisition.readers import photos

    @pytest.mark.xfail(strict=True, reason="GPSAltitudeRef is not read (course finding 19)")
    def test_altitude_below_sea_level(tmp_path):
        exif = Image.Exif()
        exif[ExifTags.IFD.GPSInfo] = {
            ExifTags.GPS.GPSLatitudeRef: "N", ExifTags.GPS.GPSLatitude: (31.0, 30.0, 0.0),
            ExifTags.GPS.GPSLongitudeRef: "E", ExifTags.GPS.GPSLongitude: (35.0, 30.0, 0.0),
            ExifTags.GPS.GPSAltitudeRef: b"\\\\x01", ExifTags.GPS.GPSAltitude: 400.0}
        path = tmp_path / "below.jpg"
        Image.new("RGB", (8, 8)).save(path, exif=exif)
        assert photos.exif(path)["alt"] == -400.0
''')
(scratch / "test_edge.py").write_text(test)
# -c: the repository's pytest.ini (it switches off plugins that do not work here), also for a test outside the repo
command = [sys.executable, "-m", "pytest", "-q", "--color=no", "-c", str(ROOT / "pytest.ini"), "--rootdir", str(ROOT)]
out = subprocess.run(command + [str(scratch / "test_edge.py")], cwd=ROOT, capture_output=True, text=True)
print((out.stdout + out.stderr).strip().splitlines()[-1])
# The reader returns +400: the assertion fails, so the test is marked xfail (strict: once the reader is fixed it
# will fail loudly, a reminder to remove the mark). A test that documents a bug, with the bug logged, is how an
# edge case enters the suite before its fix (chapter 18)."""),
    ])

CH14 = Chapter(
    "14_builder", "14. The builder",
    "Exercises of [chapter 14](../14_builder.md). Run the setup cell first.",
    """import copy, datetime, inspect, json, shutil, tempfile
import geopandas as gpd
import yaml
from shapely.geometry import Point
from data_acquisition.catalog import build
from data_acquisition.catalog import summary as summaries
from data_acquisition.readers import RECORDS, geotiff

REFERENCE = yaml.safe_load((ROOT / "docs/manual/solutions/training_pond.yaml").read_text())


def load(s):
    path = Path(tempfile.mkdtemp()) / "summary.yaml"
    path.write_text(yaml.safe_dump(copy.deepcopy(s), sort_keys=False))
    return summaries.load(str(path))""",
    [
        Exercise("**1. Trace one entry.** Take the DTM entry of the reference summary: resolve it with its group, "
                 "compute its time and its item id, then build it with `build.data_item` and print where each value "
                 "came from.",
                 """s = load(REFERENCE)
group = s["groups"][0]
entry = next(f for f in group["files"] if f["path"] == "dem_2022.asc")
...  # your code here (summaries.resolve, summaries.epoch, build.data_item)""",
                 """s = load(REFERENCE)
group = s["groups"][0]
entry = next(f for f in group["files"] if f["path"] == "dem_2022.asc")
f = summaries.resolve(group, entry)
print("resolved:", {k: f[k] for k in ("site", "product", "date", "date_precision", "crs", "positioning", "notes")})
start, end, label = summaries.epoch(f)
print("time:", start, end, "| id:", f"{f['site']}_{label}_{f['product']}")
record = RECORDS[group["record"]["format"]]["read"]((DATASET / group["record"]["path"]).read_text())
item = build.data_item(s, f, DATASET / f["path"], f"repo/doi_10.5555_training.pond/{f['path']}", group, record, {})
for key in ("beaver:site", "beaver:positioning", "beaver:licence"):
    print(key, "<-", item.properties["beaver:origin"].get(key.split(":")[1]))
print("provenance:", json.dumps(item.properties["beaver:provenance"], indent=1, default=str)[:600])
for q in item.properties["beaver:quality"]:
    print("flag:", q)"""),
        Exercise("**2. Dates.** Compute `summary.epoch` for a day, a month, a year, a range and an `unknown` date; and "
                 "`build._period` for a record whose dates are `['2001', '2024-06']`.",
                 """...  # your code here""",
                 """d = datetime.date
for f in ({"date": d(2023, 7, 12)},
          {"date": d(2022, 8, 1), "date_precision": "month"},
          {"date": 2019, "date_precision": "year"},
          {"start_date": d(2017, 9, 7), "end_date": d(2018, 9, 25)},
          {"date_precision": "unknown", "start_date": d(2010, 1, 1), "end_date": d(2015, 12, 31)}):
    print(f, "->", summaries.epoch(f))
print(build._period(["2001", "2024-06"]))"""),
        Exercise("**3. Bands.** Call `build._bands` for the sample's orthomosaic with no bands given, with the right "
                 "ones, with three bands, and with the order reversed; then for a DSM.",
                 """header = geotiff.info(DATASET / "ortho_2023-07-12.tif")
...  # your code here (build._bands(product, wanted, header, entity=None))""",
                 """header = geotiff.info(DATASET / "ortho_2023-07-12.tif")
for wanted in (None, ["red", "green", "blue", "alpha"], ["red", "green", "blue"], ["alpha", "blue", "green", "red"]):
    print(wanted, "->", build._bands("orthomosaic", wanted, header, None))
print("dsm ->", build._bands("dsm", None, geotiff.info(DATASET / "dsm_2023-07-12.tif"), None))"""),
        Exercise("**4. One item per layer.** In a scratch copy of the sample, write a GeoPackage with layers "
                 "`dams_2021` and `dams_2023` (and one called `notes`), describe it (product `annotations`, variant "
                 "`by_year`) with `layers: {pattern: '_(\\\\d{4})$', date_precision: year}`, and build. How many "
                 "items, and what does the report say?",
                 """scratch = Path(tempfile.mkdtemp()) / "root"
shutil.copytree(SAMPLE, scratch, ignore=shutil.ignore_patterns("stac"))
...  # your code here""",
                 """scratch = Path(tempfile.mkdtemp()) / "root"
shutil.copytree(SAMPLE, scratch, ignore=shutil.ignore_patterns("stac"))
gpkg = scratch / "repo/doi_10.5555_training.pond/dams_by_year.gpkg"
for name, n in (("dams_2021", 2), ("dams_2023", 3), ("notes", 1)):
    points = [Point(368010 + i, 5420030) for i in range(n)]
    gpd.GeoDataFrame({"id": range(n)}, geometry=points, crs="EPSG:32612").to_file(gpkg, layer=name)
s2 = copy.deepcopy(REFERENCE)
s2["groups"][0]["files"].append({"path": "dams_by_year.gpkg", "product": "annotations", "variant": "by_year",
                                 "layers": {"pattern": r"_(\\d{4})$", "date_precision": "year"}})
catalog, report = build.build(scratch, load(s2))
print([i.id for i in catalog.get_items(recursive=True) if i.id.endswith("by_year")])
print({k: v for k, v in report.items() if v})
# Two items, one per year layer, each dated by its name; the layer "notes" does not match: unmatched_layers."""),
        Exercise("**5. Attachments.** Give README.txt a date (`2023-07-12`) in a copy of the summary, then "
                 "`attach_to: [chm]`. Where does it attach each time?",
                 """...  # your code here""",
                 """def attached(s):
    catalog, report = build.build(SAMPLE, load(s))
    with_readme = [i.id for i in catalog.get_items(recursive=True)
                   if any(a.href.endswith("README.txt") for a in i.assets.values())]
    return with_readme, report["unattached"]

dated = copy.deepcopy(REFERENCE)
dated["groups"][0]["files"][-1]["date"] = datetime.date(2023, 7, 12)
print("dated:", attached(dated))
chm = copy.deepcopy(REFERENCE)
chm["groups"][0]["files"][-1]["attach_to"] = ["chm"]
print("chm:", attached(chm))
# With a date it attaches only to the items of that date; for the DTM (2022) it finds none and reports it
# unattached. To a product no item has, it attaches nowhere."""),
        Exercise("**6. Find it in the code.** Where is the item id made, and where is a collection's licence set to "
                 "`various`?",
                 """...  # your code here (inspect)""",
                 """for fn, needle in ((build.data_item, "item_id = "), (build.build, '"various"')):
    source, first = inspect.getsourcelines(fn)
    for n, line in enumerate(source, first):
        if needle in line:
            print(f"{inspect.getsourcefile(fn)}:{n}: {line.strip()}")"""),
    ])

CH15 = Chapter(
    "15_curate", "15. curate and the descriptors",
    "Exercises of [chapter 15](../15_curate.md). Run the setup cell first.",
    """import copy, datetime, shutil, tempfile
import numpy as np
import pystac, rasterio, yaml
from rasterio.transform import from_origin
from data_acquisition.catalog import build, descriptors, stac
from data_acquisition.catalog import summary as summaries
from data_acquisition.readers import geotiff
from data_acquisition.steps import curate

REFERENCE = yaml.safe_load((ROOT / "docs/manual/solutions/training_pond.yaml").read_text())


def load(s):
    path = Path(tempfile.mkdtemp()) / "summary.yaml"
    path.write_text(yaml.safe_dump(copy.deepcopy(s), sort_keys=False))
    return summaries.load(str(path))


def scratch_root():
    root = Path(tempfile.mkdtemp()) / "root"
    shutil.copytree(SAMPLE, root, ignore=shutil.ignore_patterns("stac"))
    for p in root.rglob("*"):          # writable copies: the sample's files are read-only like downloads
        if p.is_file():
            p.chmod(0o644)
    return root


s = load(REFERENCE)
catalog, _ = build.build(SAMPLE, s)
items = {i.id.split("_")[-1]: i for i in catalog.get_items(recursive=True)}
print(sorted(items))""",
    [
        Exercise("**1. Descriptors.** On a copy of one sample item, set `colonies` as `manual` without `by`, "
                 "as `claude` "
                 "with `by`, and an unknown field. Which calls fail? What does `descriptors.missing` return before and "
                 "after?",
                 """item = items["orthomosaic"].clone()
...  # your code here (descriptors.set_field, descriptors.missing)""",
                 """item = items["orthomosaic"].clone()
print("missing before:", descriptors.missing(item))
for args, kwargs in ((("colonies", ["a"], "manual"), {}),
                     (("colonies", ["a"], "claude"), {"by": "claude (claude-opus-5-5)", "date": "2026-10-19"}),
                     (("colour", "green", "auto"), {})):
    try:
        descriptors.set_field(item, *args, **kwargs)
        print("ok:  ", args, "->", item.properties["beaver:origin"][args[0]])
    except (KeyError, ValueError) as e:
        print("fails:", args, "->", e)
print("missing after:", descriptors.missing(item))
# A claude value fills the field (no longer missing) but is not confirmed: its origin says so."""),
        Exercise("**2. Seasons.** Compute the season of 15 January, 15 April, 15 July and 15 October at 48° N and at "
                 "45° S. Then run `curate._season` on the sample's items: why is the DTM's season `summer`?",
                 """...  # your code here (descriptors.season, curate._season)""",
                 """for month in (1, 4, 7, 10):
    d = datetime.date(2023, month, 15)
    print(d, "48N:", descriptors.season(d, 48), "| 45S:", descriptors.season(d, -45))
for name, item in sorted(items.items()):
    print(f"{name:12s}", curate._season(item))
# The DTM is dated to August 2022 (a month): 1-31 August is all summer at 48° N, and shorter than 92 days."""),
        Exercise("**3. Make checks fire.** In a scratch copy of the sample, add a five-band multispectral raster with "
                 "values 0-255 and a DSM whose empty cells are -32767 without a declared nodata, describe them, build "
                 "and curate. Which flags appear?",
                 """root = scratch_root()
folder = root / "repo/doi_10.5555_training.pond"
...  # your code here (rasterio: write the two rasters; add two entries to a copy of the summary)""",
                 """root = scratch_root()
folder = root / "repo/doi_10.5555_training.pond"
profile = {"driver": "GTiff", "width": 100, "height": 100, "crs": "EPSG:32612",
           "transform": from_origin(368000, 5420040, 0.2, 0.2)}
rng = np.random.default_rng(0)
with rasterio.open(folder / "ms_2023-07-12.tif", "w", count=5, dtype="uint8", **profile) as d:
    d.write(rng.integers(0, 256, (5, 100, 100), dtype="uint8"))
heights = np.full((1, 100, 100), 1250.0, dtype="float32")
heights[:, :, :40] = -32767                     # empty cells, value written but not declared as nodata
with rasterio.open(folder / "dsm_raw_2023-07-12.tif", "w", count=1, dtype="float32", **profile) as d:
    d.write(heights)
s3 = copy.deepcopy(REFERENCE)
s3["groups"][0]["files"] += [
    {"path": "ms_2023-07-12.tif", "product": "multispectral", "date": datetime.date(2023, 7, 12)},
    {"path": "dsm_raw_2023-07-12.tif", "product": "dsm", "variant": "raw", "date": datetime.date(2023, 7, 12)}]
s3 = load(s3)
catalog3, report = build.build(root, s3)
for item in catalog3.get_items(recursive=True):
    if item.id.endswith(("multispectral", "dsm_raw")):
        curate.curate_item(item, s3)
        print(item.id, [(q["flag"], q["detail"]) for q in item.properties["beaver:quality"]])
# multispectral: not_reflectance (values 0-255) and nodata_undeclared; DSM: elevation_range (-32767 m)
# and nodata_undeclared. Two different problems with one cause in the DSM: the nodata value is not declared."""),
        Exercise("**4. Verification.** For each sample item, which source would `_checksum_verdict` use? "
                 "Then reproduce "
                 "finding 20 in a scratch copy: verify, change the DTM, verify again.",
                 """...  # your code here (curate._checksum_verdict(asset, path, provenance))""",
                 """for name, item in sorted(items.items()):
    key = next(k for k, a in item.assets.items() if "data" in (a.roles or []))
    asset = item.assets[key]
    print(f"{name:12s}", curate._checksum_verdict(asset, stac.asset_path(asset),
                                                  item.properties["beaver:provenance"]))
root = scratch_root()
catalog4, _ = build.build(root, s)
out = stac.save(catalog4, root / "stac/training_pond")
curate.curate(out, s, verify_files=True)
dtm = root / "repo/doi_10.5555_training.pond/dem_2022.asc"
dtm.write_text(dtm.read_text().replace("-9999", "-9998", 1))
curate.curate(out, s, verify_files=True)
item = next(i for i in stac.load(out).get_items(recursive=True) if i.id.endswith("dtm"))
print("verified:", item.properties["beaver:provenance"].get("verified"))
print("flags:", [q["flag"] for q in item.properties["beaver:quality"]])"""),
        Exercise("**5. Add a check.** Write, outside the pipeline, a check `no_overviews` for rasters wider or taller "
                 "than a limit that have no overviews, apply it after `curate_item`, and test it with a small limit.",
                 """def check_overviews(item, key, limit=4096):
    ...  # your code here (geotiff.info(...)["overviews"], descriptors.add_quality)""",
                 """OVERVIEW_LIMIT = 4096      # pixels: above this, a raster without overviews is slow to display whole


def check_overviews(item, key, limit=OVERVIEW_LIMIT):
    \"\"\"Flag a raster larger than ``limit`` pixels on a side that has no overviews.\"\"\"
    header = geotiff.info(stac.asset_path(item.assets[key]))
    height, width = header["shape"]
    if max(height, width) > limit and not header["overviews"]:
        descriptors.add_quality(item, "no_overviews", f"{width} x {height} pixels, no overviews (gdaladdo)")


for name, item in sorted(items.items()):
    if item.properties["beaver:kind"] != "raster":
        continue
    curate.curate_item(item, s)
    check_overviews(item, name, limit=100)
    print(f"{name:12s}", [q["flag"] for q in item.properties["beaver:quality"] if q["source"] == "auto"])
# The orthomosaic (400 pixels) and the DSM (200) exceed the limit of 100 without overviews; the DTM (20) does not.

# a test, as it would go in tests/dataset/ (with a raster that has overviews too)
def test_no_overviews(tmp_path):
    path = tmp_path / "big.tif"
    profile = {"driver": "GTiff", "width": 300, "height": 300, "count": 1, "dtype": "uint8", "crs": "EPSG:32612",
               "transform": from_origin(368000, 5420040, 0.1, 0.1)}
    with rasterio.open(path, "w", **profile) as d:
        d.write(np.zeros((1, 300, 300), dtype="uint8"))
    item = pystac.Item("t", None, None, datetime.datetime(2023, 7, 12), {})
    item.add_asset("dsm", pystac.Asset(str(path), roles=["data"]))
    check_overviews(item, "dsm", limit=200)
    assert [q["flag"] for q in item.properties["beaver:quality"]] == ["no_overviews"]
    with rasterio.open(path, "r+") as d:
        d.build_overviews([2, 4])
    item.properties["beaver:quality"] = []
    check_overviews(item, "dsm", limit=200)
    assert item.properties["beaver:quality"] == []


test_no_overviews(Path(tempfile.mkdtemp()))
print("test passed")"""),
    ])

CH16 = Chapter(
    "16_sources", "16. Sources: downloads and checksums",
    "Exercises of [chapter 16](../16_sources.md). Run the setup cell first. Everything here runs offline.",
    """import base64, csv, http.client, inspect, tempfile
from data_acquisition.sources import checksums, dataset_folder, downloads, zenodo
from data_acquisition.sources import http as web

SCRATCH = Path(tempfile.mkdtemp())
source = SCRATCH / "published" / "data.bin"            # the "repository's" copy of a file, served as file://
source.parent.mkdir()
source.write_bytes(os.urandom(12 * 1024 * 1024 + 123))
print(source, source.stat().st_size, "bytes")""",
    [
        Exercise("**1. The contract in the model client.** Print `zenodo.py` and find, for each point of the contract, "
                 "the line that does it.",
                 """print(inspect.getsource(zenodo))""",
                 """lines = inspect.getsource(zenodo).splitlines()
contract = {"options": "add_argument", "--list prints, downloads nothing": "downloads.listing",
            "record saved unchanged": "metadata.json\\").write_text", "dataset folder": "dataset_folder(",
            "fetch": "http.fetch", "verify, read-only, log row": "downloads.finish(",
            "existing file only verified again": "if not path.exists()", "log merged": "downloads.log("}
for point, needle in contract.items():
    n = next(i for i, line in enumerate(lines, 1) if needle in line)
    print(f"{point:36s} line {n:3d}: {lines[n - 1].strip()}")
# Nothing dataset-specific: no DOI, file name or site appears in the client."""),
        Exercise("**2. Folders.** Name the folders of `10.5281/zenodo.1`, `https://doi.org/10.18739/A2CZ3253W`, "
                 "`hs:abc123` and a CKAN package id.",
                 """...  # your code here (dataset_folder(root, repository, identifier))""",
                 """for repository, identifier in (("zenodo", "10.5281/zenodo.1"),
                               ("arcticdata", "https://doi.org/10.18739/A2CZ3253W"),
                               ("hydroshare", "hs:abc123"),
                               ("open_canada", "b44984f7-9ba6-45aa-b25b-a6dc596afea5")):
    print(f"{identifier:42s} -> {dataset_folder(Path('<root>'), repository, identifier)}")"""),
        Exercise("**3. Checksums.** Compute the file's MD5 and SHA-256; make its multipart ETag with 5 MiB parts and "
                 "check it; check an ETag made with 7 MiB parts. Why is the answer None and not False?",
                 """...  # your code here (checksums.digest, checksums._etag, checksums.check)""",
                 """md5 = checksums.digest(source, "md5")
print("md5   ", md5)
print("sha256", checksums.digest(source, "sha256"))
etag5 = checksums._etag(source, 5 * 1024 * 1024)
etag7 = checksums._etag(source, 7 * 1024 * 1024)
print("5 MiB parts:", etag5, checksums.check(source, "etag", etag5))
print("7 MiB parts:", etag7, checksums.check(source, "etag", etag7))
print("a wrong md5:", checksums.check(source, "md5", "0" * 32))
# 7 MiB is not a part size of common upload tools, so no part size tried reproduces the ETag: the file may well
# be right, so the check is undecided (None) and the next one is tried. A plain digest is always decided."""),
        Exercise("**4. Served MD5s.** Build response headers with `Content-MD5`, with `x-goog-hash`, and with a "
                 "multipart `ETag`; what does `http.stated_md5` return for each?",
                 """headers = http.client.HTTPMessage()
...  # your code here (base64 of the raw 16-byte digest)""",
                 """raw = bytes.fromhex(md5)
for name, value in (("Content-MD5", base64.b64encode(raw).decode()),
                    ("x-goog-hash", "md5=" + base64.b64encode(raw).decode()),
                    ("x-goog-hash", "crc32c=n03x6A==,md5=" + base64.b64encode(raw).decode()),
                    ("ETag", f'"{md5}"'),
                    ("ETag", f'"{etag5}"')):
    headers = http.client.HTTPMessage()
    headers[name] = value
    print(f"{name:12s} {value[:44]:44s} -> {web.stated_md5(headers)}")
# A multipart ETag is not the file's MD5, so it is not taken as one (None). Google's combined form
# "crc32c=...,md5=..." (documented by Google) is missed: finding 22 in docs/dataset/course_findings.md."""),
        Exercise("**5. Download, resume, finish.** Leave a stale `.part` of the file in a scratch root, fetch it from "
                 "its `file://` link, finish it against its MD5, log it, and read the log row. Then finish a copy "
                 "against a wrong MD5: what happens to the file?",
                 """root = SCRATCH / "root"
dest = dataset_folder(root, "example", "10.5555/example") / "data.bin"
...  # your code here (web.fetch, downloads.finish, downloads.log)""",
                 """root = SCRATCH / "root"
dest = dataset_folder(root, "example", "10.5555/example") / "data.bin"
dest.parent.mkdir(parents=True)
dest.with_name("data.bin.part").write_bytes(source.read_bytes()[:1000])   # an interrupted earlier attempt
web.fetch(source.as_uri(), dest, source.stat().st_size, retries=False)
print("complete:", checksums.digest(dest, "md5") == md5, "| .part left:", dest.with_name("data.bin.part").exists())
record = {"title": "An example dataset", "licence": "CC0-1.0"}
row = downloads.finish(dest, root, source.as_uri(), ("md5", md5), source="example", identifier="doi:10.5555/example",
                       record=record)
downloads.log(root / "downloads.csv", [row])
print(next(csv.DictReader(open(root / "downloads.csv"))))
print("permissions:", oct(dest.stat().st_mode & 0o777))
# A file:// link answers no range request, so fetch started again from the beginning (the .part was rewritten).

copy = dest.with_name("copy.bin")
copy.write_bytes(dest.read_bytes())
try:
    downloads.finish(copy, root, source.as_uri(), ("md5", "0" * 32), source="example", identifier=None,
                     record=record)
except IOError as e:
    print("refused:", e)
print("the bad file is still there:", copy.exists(), oct(copy.stat().st_mode & 0o777))
# Refused, but left in place and writable (finding 9): delete it before downloading again."""),
    ])

CH17 = Chapter(
    "17_field_step_internals", "17. The field step, inside",
    "Exercises of [chapter 17](../17_field_step_internals.md). Run the setup cell first. They build a miniature "
    "drive in a scratch folder from the Montana extract; the real drive is not needed.",
    """import csv, json, shutil, stat, tempfile
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from pyproj import CRS
from rasterio.windows import Window
from scipy import ndimage
from data_acquisition.readers import photos
from data_acquisition.sources import field, field_alignment
%matplotlib inline
# field_alignment switches matplotlib to a file-only backend when imported (finding 24): back to inline plots

DAY = EXTRACT / "2018-07-26"
BASE = "2018 Field Season/Drone Flights/Test Site/"
SITE = "test_site\"""",
    [
        Exercise("**1. A drive in miniature.** Make a scratch drive from the extract (26 July: the full tile, the "
                 "chunk, the photos, the dams), write a layout for it, and run `plan`, `execute` and `write_records`. "
                 "Read every record.",
                 """drive = Path(tempfile.mkdtemp()) / "drive"
...  # your code here: copy the files under drive / BASE, build inventory rows for the photos, write a layout""",
                 """drive = Path(tempfile.mkdtemp()) / "drive"
folder = drive / BASE / "01. 26July2018"
(folder / "SmallChunks").mkdir(parents=True)
(folder / "100MEDIA").mkdir()
shutil.copy(DAY / "orthomosaic_full_tile.tif", folder / "26July2018_4.tif")
shutil.copy(DAY / "orthomosaic_chunk.tif", folder / "SmallChunks/26July2018_4_3.tif")
shutil.copy(DAY / "annotations/dams.gpkg", drive / BASE / "Dams.gpkg")
inventory = []
for p in sorted((DAY / "photos").glob("*.JPG")):
    shutil.copy(p, folder / "100MEDIA" / p.name)
    inventory.append({"role": "raw_photo", "site": SITE, "survey_date": "2018-07-26", "include": "True", "note": "",
                      "source_path": f"{BASE}01. 26July2018/100MEDIA/{p.name}",
                      "taken_at": photos.exif(p)["taken"].isoformat()})
layout = {"schema": 1, "site": SITE, "authored": {"by": "me", "date": "2026-10-19"}, "base": BASE,
          "photos": "by_exif_date",
          "orthomosaics": [
              {"source": "01. 26July2018/26July2018_4.tif", "to": "surveys/2018-07-26/orthomosaic_part-4.tif"},
              {"source": "01. 26July2018/SmallChunks/26July2018_4_3.tif",
               "to": "surveys/2018-07-26/orthomosaic_part-4_chunk-3.tif"}],
          "annotations": [{"source": "Dams.gpkg", "layer": "dams", "to": "annotations/2018-07-26/dams.gpkg",
                           "features": 1}]}
print("layout problems:", field.check_layout(layout))
actions, excluded = field.plan(drive, layout, inventory)
done = field.execute(drive, actions, [])
fits = done.pop("fits")
print("done:", done)
field.write_records(drive, SITE, actions, excluded, inventory, fits)
site = drive / "beaver_dataset/sites" / SITE
for name in ("manifest.csv", "excluded.csv", "georeference.csv", "surveys/2018-07-26/survey.json"):
    print(f"--- {name}\\n{(site / name).read_text()}")
# No georeference.csv rows: these copies have no ArcGIS sidecar. On the drive, the chunk's sidecar would have made
# a georef action, and the original sidecar would be linked as orthomosaic_part-4_chunk-3.arcgis.aux.xml."""),
        Exercise("**2. Links.** For one linked file, compare it with its original (`os.path.samefile`, `st_nlink`, "
                 "permissions). Run `execute` again: what is done the second time?",
                 """...  # your code here""",
                 """link = site / "surveys/2018-07-26/orthomosaic_part-4.tif"
original = folder / "26July2018_4.tif"
print("same file:", os.path.samefile(link, original), "| names:", link.stat().st_nlink)
print("permissions: link", oct(link.stat().st_mode & 0o777), "| original", oct(original.stat().st_mode & 0o777))
written = site / "annotations/2018-07-26/dams.gpkg"
print("export: names", written.stat().st_nlink, "| permissions", oct(written.stat().st_mode & 0o777))
print("again:", {k: v for k, v in field.execute(drive, actions, []).items() if k != "fits"})
# One file with two names, read-only under both. The second run keeps the links ("already there") and makes the
# export again."""),
        Exercise("**3. Pruning.** Drop the chunk from the layout, put a file of your own in the site folder, "
                 "plan again "
                 "and `prune`. What is removed, and what happens to the original chunk?",
                 """...  # your code here""",
                 """(site / "my_notes.txt").write_text("a person's notes")
smaller = dict(layout, orthomosaics=layout["orthomosaics"][:1])
actions2, _ = field.plan(drive, smaller, inventory)
print("removed:", field.prune(drive, SITE, actions2))
print("original chunk still there:", (folder / "SmallChunks/26July2018_4_3.tif").exists())
# The chunk's link is gone and its original kept. But my_notes.txt is deleted too: prune removes every file the
# plan does not make (finding 23 in docs/dataset/course_findings.md)."""),
        Exercise("**4. Two PROJ versions.** With `field._same_place`, compare the extract layer's CRS with itself, and "
                 "with the same CRS on the WGS 84 ellipsoid, over the layer's extent.",
                 """...  # your code here (field._layer_info gives the CRS and extent)""",
                 """info = field._layer_info(DAY / "annotations/dams.gpkg", "dams")
sphere = info["crs"]
horizontal = CRS.from_wkt(sphere).sub_crs_list[0]
ellipsoid = CRS.from_proj4(horizontal.to_proj4().replace("+R=6378137", "+datum=WGS84")).to_wkt()
print("extent:", info["extent"])
print("same CRS:", field._same_place(sphere, sphere, info["extent"]))
print("ellipsoid:", field._same_place(horizontal.to_wkt(), ellipsoid, info["extent"]))
for proj in ("pyproj", "gdal"):
    print(proj, "sphere", field._lonlat(sphere, [info["extent"][:2]], proj),
          "| ellipsoid", field._lonlat(ellipsoid, [info["extent"][:2]], proj))
# Under pyproj's PROJ (9.5) both read the same; under GDAL's (9.8) the ellipsoid lands ~30 km away. Checking with
# one PROJ only would have missed it."""),
        Exercise("**5. The score surface.** Recompute `best_shift`'s score for the extract's dam on every shift of the "
                 "coarse grid, on the chunk and on the full tile, and plot the two surfaces.",
                 """...  # your code here: best_shift's steps (window, grey, gaussian_filter, sobel, outline points)""",
                 """def surface(tif, geom):
    \"\"\"The score of every shift of the coarse grid, as best_shift computes it.\"\"\"
    with rasterio.open(tif) as r:
        res = abs(r.transform.a)
        pad = int(field_alignment.MAX_SHIFT / res) + 20
        minx, miny, maxx, maxy = geom.bounds
        (r0, c0), (r1, c1) = r.index(minx, maxy), r.index(maxx, miny)
        window = Window(c0 - pad, r0 - pad, c1 - c0 + 2 * pad, r1 - r0 + 2 * pad)
        grey = r.read([1, 2, 3], window=window).astype(float).mean(0)
        to_px = ~r.window_transform(window)
    smooth = ndimage.gaussian_filter(grey, 2)
    grad = np.hypot(ndimage.sobel(smooth, 0), ndimage.sobel(smooth, 1))
    pts = field_alignment._outline_points(geom, to_px, res)
    steps = np.arange(-field_alignment.MAX_SHIFT, field_alignment.MAX_SHIFT + 1e-9, field_alignment.COARSE)
    scores = np.array([[ndimage.map_coordinates(grad, [pts[:, 1] - dn / res, pts[:, 0] + de / res], order=1).mean()
                        for de in steps] for dn in steps])
    return steps, scores


dams = gpd.read_file(DAY / "annotations/dams.gpkg")
fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))
for ax, kind in zip(axes, ("chunk", "full_tile")):
    tif = DAY / f"orthomosaic_{kind}.tif"
    with rasterio.open(tif) as r:
        geom = dams.to_crs(r.crs.to_wkt()).geometry.iloc[0]
    steps, scores = surface(tif, geom)
    n, e = np.unravel_index(scores.argmax(), scores.shape)
    im = ax.imshow(scores, origin="lower", extent=[steps[0], steps[-1], steps[0], steps[-1]], cmap="viridis")
    ax.plot(steps[e], steps[n], "r+", markersize=14)
    ax.set_title(f"{kind}: best {steps[e]:+.1f} m east, {steps[n]:+.1f} m north")
    ax.set_xlabel("shift east (m)")
    ax.set_ylabel("shift north (m)")
    fig.colorbar(im, ax=ax, shrink=0.8)
    print(kind, "coarse best:", round(steps[e], 2), round(steps[n], 2), "| best_shift:",
          tuple(round(v, 2) for v in field_alignment.best_shift(tif, geom)))
plt.tight_layout()
plt.show()
# One clear peak each: at the centre on the chunk (the outline was drawn on it), 0.6 m south on the full tile. Both
# surfaces are stretched north-south: the dam runs that way, and sliding an outline along its own length keeps much
# of it on edges, so a shift along a feature is less well determined than across it. Where other edges lie near an
# outline, such ridges become second peaks: why single values are noisy and medians are read."""),
    ])

CH18 = Chapter(
    "18_testing", "18. Testing a change",
    "Exercises of [chapter 18](../18_testing.md). Run the setup cell first.",
    """import collections, copy, json, tempfile, textwrap
import yaml
from data_acquisition.catalog import build
from data_acquisition.catalog import summary as summaries
from data_acquisition.steps import curate
from tests.dataset import regression

PYTEST = [sys.executable, "-m", "pytest", "-q", "--color=no", "-c", str(ROOT / "pytest.ini"), "--rootdir", str(ROOT)]


def run(args):
    out = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    return (out.stdout + out.stderr).strip()""",
    [
        Exercise("**1. Run the suite.** Run all the dataset tests, then only those whose name contains `layers`. "
                 "How many "
                 "are there per file?",
                 """...  # your code here (run(PYTEST + [...]))""",
                 """print(run(PYTEST + ["tests/dataset", "--ignore=tests/dataset/test_manual.py"]).splitlines()[-1])
print(run(PYTEST + ["tests/dataset", "-k", "layers", "-v"]))
listed = run(PYTEST + ["tests/dataset", "--collect-only"]).splitlines()
print(collections.Counter(line.split("::")[0] for line in listed if "::" in line))
# test_manual.py is left out of the first run: it runs this very notebook (and every other solution)."""),
        Exercise("**2. Write a test with the fixtures.** In a scratch folder, write a test that uses `root`, "
                 "`registry` "
                 "and `summary` to build the synthetic dataset and checks it has no missing or unsupported files and "
                 "eight items. Run it with the repository's settings and fixtures.",
                 """scratch = Path(tempfile.mkdtemp())
...  # write scratch / "test_mine.py"; run(PYTEST + ["-p", "tests.dataset.conftest", str(scratch / "test_mine.py")])""",
                 """scratch = Path(tempfile.mkdtemp())
(scratch / "test_mine.py").write_text(textwrap.dedent('''
    from data_acquisition.catalog import build
    from data_acquisition.catalog import summary as summaries


    def test_every_dataset_file_becomes_an_item(root, registry, summary):
        s = summaries.load(str(registry.parent / "test_dataset.yaml"))      # the fixture writes it there
        catalog, report = build.build(root, s)
        assert not report["missing"] and not report["unsupported"]
        assert len(list(catalog.get_items(recursive=True))) == 8
'''))
print(run(PYTEST + ["-p", "tests.dataset.conftest", str(scratch / "test_mine.py")]))
# -p loads conftest.py as a plugin, so its fixtures are available to a test outside tests/dataset/."""),
        Exercise("**3. A snapshot of the sample.** With `regression._normalise` and `regression.compare`, take a "
                 "snapshot of the sample's items, change `curate.ELEVATION_RANGE` to (-500, 1000), take another, and "
                 "compare. Which differences appear?",
                 """def snapshot():
    ...  # build the sample with the reference summary, curate each item, normalise it
    return {"summaries": {"training_pond": {"report": ..., "items": ...}}}""",
                 """s = summaries.load(str(ROOT / "docs/manual/solutions/training_pond.yaml"))


def snapshot():
    \"\"\"As regression.snapshot, for the sample root and the reference summary.\"\"\"
    catalog, report = build.build(SAMPLE, s)
    items = {}
    for item in catalog.get_items(recursive=True):
        curate.curate_item(item, s)
        items[item.id] = regression._normalise(item.to_dict(include_self_link=False, transform_hrefs=False),
                                               str(SAMPLE.resolve()))
    return {"summaries": {"training_pond": {"report": report, "items": items}}}


before = snapshot()
saved = curate.ELEVATION_RANGE
curate.ELEVATION_RANGE = (-500.0, 1000.0)          # "the change"
try:
    after = snapshot()
finally:
    curate.ELEVATION_RANGE = saved
differences = regression.compare(before, after)
# Only the elevation items' quality flags change (the sample's heights are about 1,310 m): the change did what it
# meant and nothing else. A difference anywhere else would be a side effect to explain."""),
        Exercise("**4. Lint.** Run ruff on the pipeline with its defaults and with `--select E,F,W --line-length 120`. "
                 "How many findings each, and of which kinds?",
                 """PIPELINE = ["data_acquisition/catalog", "data_acquisition/sources", "data_acquisition/readers",
            "data_acquisition/steps", "data_acquisition/intake.py", "tests/dataset"]
...  # your code here""",
                 """PIPELINE = ["data_acquisition/catalog", "data_acquisition/sources", "data_acquisition/readers",
            "data_acquisition/steps", "data_acquisition/intake.py", "tests/dataset"]
ruff = [sys.executable, "-m", "ruff", "check", "--isolated", "--output-format", "json", "--line-length", "120"]
for name, extra in (("defaults", []), ("E, F, W", ["--select", "E,F,W"])):
    out = subprocess.run(ruff + extra + PIPELINE, cwd=ROOT, capture_output=True, text=True).stdout
    found = json.loads(out)
    kinds = collections.Counter((f["code"] or "?").rstrip("0123456789") for f in found)
    print(f"{name:9s} {len(found):4d} findings", dict(kinds.most_common(6)))
# --isolated ignores any personal ruff settings. The defaults are dominated by UP (type-hint style); the E, F, W
# findings are the ones the code means to follow (finding 25)."""),
        Exercise("**5. (Optional, needs the drive.)** Take a snapshot of the open datasets and compare it with itself.",
                 """DRIVE = Path("/media/<user>/Seagate Portable Drive")   # your drive
...  # regression.snapshot(DRIVE / "open_datasets")""",
                 """DRIVE = None      # e.g. Path("/media/<user>/Seagate Portable Drive"); None: this cell does nothing
if DRIVE is not None and (DRIVE / "open_datasets").exists():
    snap = regression.snapshot(DRIVE / "open_datasets")
    regression.compare(snap, snap)
else:
    print("no drive: skipped")"""),
    ])

CH19 = Chapter(
    "19_extending", "19. Extending the pipeline",
    "Exercises of [chapter 19](../19_extending.md). Run the setup cell first. The pipeline is changed only inside "
    "this session, and the changes are undone; no file of the pipeline is edited.",
    """import copy, datetime, shutil, tempfile, textwrap
import yaml
from data_acquisition.catalog import build
from data_acquisition.catalog import summary as summaries
from data_acquisition.steps import curate

REFERENCE = yaml.safe_load((ROOT / "docs/manual/solutions/training_pond.yaml").read_text())""",
    [
        Exercise("**1. A toy product, end to end.** Add a product `water_depth` (band name `depth`, metres) to "
                 "`PRODUCTS` and `METRIC_BANDS` for this session. In a scratch copy of the sample, describe the DSM as "
                 "a `water_depth` (variant `toy`) too, build and curate. What does the item get? "
                 "Then undo the changes.",
                 """...  # your code here (summaries.PRODUCTS.add, build.METRIC_BANDS[...] = ...)""",
                 """summaries.PRODUCTS.add("water_depth")
build.METRIC_BANDS["water_depth"] = "depth"
try:
    root = Path(tempfile.mkdtemp()) / "root"
    shutil.copytree(SAMPLE, root, ignore=shutil.ignore_patterns("stac"))
    s = copy.deepcopy(REFERENCE)
    s["groups"][0]["files"].append({"path": "dsm_2023-07-12.tif", "product": "water_depth", "variant": "toy",
                                    "date": datetime.date(2023, 7, 12)})
    path = Path(tempfile.mkdtemp()) / "summary.yaml"
    path.write_text(yaml.safe_dump(s, sort_keys=False))
    s = summaries.load(str(path))
    catalog, report = build.build(root, s)
    item = next(i for i in catalog.get_items(recursive=True) if i.id.endswith("water_depth_toy"))
    curate.curate_item(item, s)
    asset = item.assets["water_depth"]
    print(item.id)
    print("bands:", asset.extra_fields.get("eo:bands"), "| raster:", asset.extra_fields.get("raster:bands"))
    print("flags:", [q["flag"] for q in item.properties["beaver:quality"]])
finally:
    summaries.PRODUCTS.discard("water_depth")
    del build.METRIC_BANDS["water_depth"]
print("undone:", "water_depth" not in summaries.PRODUCTS and "water_depth" not in build.METRIC_BANDS)
# Two lines made a product: its band is named "depth" with unit m (METRIC_BANDS). No plausibility check applies:
# curate's elevation range is for dsm and dtm only, and a depth range would be a new check (chapter 15)."""),
        Exercise("**2. A test for it.** Write the test that would go with the change, using pytest's `monkeypatch` so "
                 "the additions are undone after the test, and run it.",
                 """scratch = Path(tempfile.mkdtemp())
...  # write scratch / "test_water_depth.py" and run it with the repository's settings""",
                 """scratch = Path(tempfile.mkdtemp())
(scratch / "test_water_depth.py").write_text(textwrap.dedent('''
    from data_acquisition.catalog import build
    from data_acquisition.catalog import summary as summaries


    def test_water_depth_is_a_metric_product(monkeypatch):
        monkeypatch.setattr(summaries, "PRODUCTS", summaries.PRODUCTS | {"water_depth"})
        monkeypatch.setitem(build.METRIC_BANDS, "water_depth", "depth")
        header = {"count": 1, "colorinterp": ["gray"]}
        assert build._bands("water_depth", None, header, None) == (["depth"], [])
        problems = summaries.check({"schema": 1, "dataset": "t", "title": "t",
                                    "authored": {"by": "me", "date": "2026-10-19"}, "source": {"kind": "folder",
                                    "provider": "p"}, "groups": [{"folder": "f", "site": "s", "files": [
                                    {"path": "d.tif", "product": "water_depth", "date": "2023-07-12"}]}]}, {})
        assert not any("product must be" in p for p in problems)
'''))
out = subprocess.run([sys.executable, "-m", "pytest", "-q", "--color=no", "-c", str(ROOT / "pytest.ini"),
                      "--rootdir", str(ROOT), str(scratch / "test_water_depth.py")],
                     cwd=ROOT, capture_output=True, text=True)
print((out.stdout + out.stderr).strip().splitlines()[-1])
# In the real change, the two additions would be edits to summary.py and build.py, and the test would need no
# monkeypatch; here it keeps the pipeline untouched."""),
        Exercise("**3. Data or code?** For each case, say whether it is data (which file) or code (which row "
                 "of §2): a new Zenodo dataset; a repository serving records in DataCite XML; a site's colony "
                 "boundaries; a survey "
                 "whose rasters are in feet; a dataset of LiDAR point clouds; a summary value Claude got wrong.",
                 """answers = {
    "a new Zenodo dataset": ...,
    # ...
}""",
                 """answers = {
    "a new Zenodo dataset": "data: a summary (the Zenodo client exists)",
    "records in DataCite XML": "code: a metadata standard (readers/datacite.py + RECORDS), and a client if the "
                               "repository is new",
    "a site's colony boundaries": "data: the site registry (colonies, entered by a person), later define_aoi",
    "rasters in feet": "data: the summary's `unit` (and a note); conversion is a later step",
    "LiDAR point clouds": "code: a data type (reader, builder kind, STAC item, evidence, check); plan with the design",
    "a wrong summary value": "data: correct the summary, with its evidence, and review it again",
}
for case, answer in answers.items():
    print(f"{case:28s} {answer}")"""),
    ])

CHAPTERS = [CH00, CH01, CH02, CH03, CH04, CH05, CH06, CH07, CH08, CH09, CH10, CH11, CH12, CH13, CH14, CH15, CH16,
            CH17, CH18, CH19]


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
    nb.metadata["beaver_course"] = {"needs_network": chapter.network}
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
