#!/usr/bin/env python3
"""Make the course's sample data root: one small dataset folder, as a repository download would look.

The data are invented ("Training Pond", UTM zone 12N), but every file is real and readable by the
pipeline: an RGBA orthomosaic with a pond and a dam, a DSM, an elevation grid without a CRS of its own,
a dam layer, six drone photos with EXIF, a README, a metadata record (EML, as DataONE serves it) with
the files' MD5 checksums, and a site registry. About 2 MB.

    python docs/manual/tools/make_sample.py --out output/manual/sample_root
    export BEAVER_SITES=output/manual/sample_root/sites.yaml        # use the sample's site registry

The reference summary for it is ``docs/manual/solutions/training_pond.yaml``.
"""
import argparse
import datetime
import hashlib
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from PIL import ExifTags, Image
from pyproj import Transformer
from rasterio.enums import ColorInterp
from rasterio.transform import from_origin
from shapely.geometry import Polygon

CRS = "EPSG:32612"                        # WGS 84 / UTM zone 12N, metres
LEFT, TOP = 368000.0, 5420040.0           # top-left corner of the survey, metres
SURVEY = datetime.datetime(2023, 7, 12, 9, 30)
FOLDER = "repo/doi_10.5555_training.pond"   # 10.5555 is the DOI prefix reserved for examples
DAM = Polygon([(LEFT + 6.0, TOP - 9.0), (LEFT + 14.0, TOP - 8.0), (LEFT + 14.2, TOP - 9.4), (LEFT + 6.1, TOP - 10.3)])


def _scene(res: float, size: int) -> np.ndarray:
    """RGB of the survey: grass, a pond south of the dam, the dam (brown), at ``res`` metres per pixel."""
    rng = np.random.default_rng(7)
    rows, cols = np.mgrid[0:size, 0:size]
    x, y = LEFT + (cols + 0.5) * res, TOP - (rows + 0.5) * res
    rgb = np.stack([60 + 20 * rng.random((size, size)), 120 + 30 * rng.random((size, size)),
                    50 + 15 * rng.random((size, size))])
    pond = ((x - (LEFT + 10)) / 7) ** 2 + ((y - (TOP - 14)) / 4) ** 2 < 1
    rgb[:, pond] = np.array([[40], [70], [90]])
    from rasterio.features import geometry_mask
    dam = ~geometry_mask([DAM], (size, size), from_origin(LEFT, TOP, res, res))
    rgb[:, dam] = np.array([[120], [95], [70]]) + 15 * rng.random((3, int(dam.sum())))
    return rgb.astype("uint8")


def write_orthomosaic(path: Path) -> None:
    """RGBA, 5 cm pixels, 20 m square; the alpha band marks two corners outside the flight."""
    res, size = 0.05, 400
    rgb = _scene(res, size)
    alpha = np.full((size, size), 255, dtype="uint8")
    rows, cols = np.mgrid[0:size, 0:size]
    alpha[(rows + cols < 60) | (rows + cols > 2 * size - 60)] = 0
    rgb[:, alpha == 0] = 0
    with rasterio.open(path, "w", driver="GTiff", width=size, height=size, count=4, dtype="uint8", crs=CRS,
                       transform=from_origin(LEFT, TOP, res, res), compress="deflate") as d:
        d.write(np.concatenate([rgb, alpha[None]]))
        d.colorinterp = [ColorInterp.red, ColorInterp.green, ColorInterp.blue, ColorInterp.alpha]


def write_dsm(path: Path) -> None:
    """Elevation in metres, 10 cm pixels: a gentle slope, the pond 0.8 m lower, the dam 0.6 m higher;
    nodata where the flight did not reach."""
    res, size = 0.1, 200
    rows, cols = np.mgrid[0:size, 0:size]
    x, y = LEFT + (cols + 0.5) * res, TOP - (rows + 0.5) * res
    z = 1310.0 + 0.02 * (y - (TOP - 20))
    z[((x - (LEFT + 10)) / 7) ** 2 + ((y - (TOP - 14)) / 4) ** 2 < 1] -= 0.8
    from rasterio.features import geometry_mask
    z[~geometry_mask([DAM], (size, size), from_origin(LEFT, TOP, res, res))] += 0.6
    z[rows + cols < 30] = -9999
    with rasterio.open(path, "w", driver="GTiff", width=size, height=size, count=1, dtype="float32", crs=CRS,
                       transform=from_origin(LEFT, TOP, res, res), nodata=-9999, compress="deflate") as d:
        d.write(z.astype("float32")[None])


def write_grid_without_crs(path: Path) -> None:
    """An ESRI ASCII elevation grid from an older survey: 1 m cells, and no CRS in the file."""
    size = 20
    header = (f"ncols {size}\nnrows {size}\nxllcorner {LEFT}\nyllcorner {TOP - size}\ncellsize 1\n"
              "NODATA_value -9999\n")
    rows = [" ".join(f"{1310.0 + 0.02 * r:.2f}" for _ in range(size)) for r in range(size)]
    path.write_text(header + "\n".join(rows) + "\n")


def write_dams(path: Path) -> None:
    """The dam outline mapped from the orthomosaic, and a second, smaller dam upstream."""
    small = Polygon([(LEFT + 3, TOP - 2), (LEFT + 5, TOP - 2), (LEFT + 5, TOP - 2.6), (LEFT + 3, TOP - 2.6)])
    gpd.GeoDataFrame({"name": ["D1", "D2"], "mapped_on": ["2023-07-12", "2023-07-12"]},
                     geometry=[DAM, small], crs=CRS).to_file(path, layer="dams", driver="GPKG")


def write_photos(folder: Path) -> None:
    """Six small drone photos with EXIF: camera, capture time and GPS position over the survey."""
    folder.mkdir(parents=True, exist_ok=True)
    to_lonlat = Transformer.from_crs(CRS, "EPSG:4326", always_xy=True)
    rgb = np.moveaxis(_scene(0.25, 80), 0, -1)

    def dms(value: float):
        d = int(value)
        m = int((value - d) * 60)
        return (float(d), float(m), round((value - d - m / 60) * 3600, 4))

    for i in range(6):
        lon, lat = to_lonlat.transform(LEFT + 3 + 3 * i, TOP - 10)
        exif = Image.Exif()
        exif[ExifTags.Base.Model] = "FC6310"
        exif.get_ifd(ExifTags.IFD.Exif)[ExifTags.Base.DateTimeOriginal] = \
            (SURVEY + datetime.timedelta(seconds=4 * i)).strftime("%Y:%m:%d %H:%M:%S")
        gps = exif.get_ifd(ExifTags.IFD.GPSInfo)
        gps[ExifTags.GPS.GPSLatitudeRef], gps[ExifTags.GPS.GPSLatitude] = "N", dms(lat)
        gps[ExifTags.GPS.GPSLongitudeRef], gps[ExifTags.GPS.GPSLongitude] = "W", dms(-lon)
        gps[ExifTags.GPS.GPSAltitude] = 1350.0
        Image.fromarray(rgb).save(folder / f"DJI_{i + 1:04d}.JPG", exif=exif, quality=85)


def _md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def write_record(folder: Path, files: list) -> None:
    """A metadata record in EML, as DataONE serves it: title, licence, creator, dates, extent, methods, and one
    entity per file with its size and MD5."""
    to_lonlat = Transformer.from_crs(CRS, "EPSG:4326", always_xy=True)
    west, north = to_lonlat.transform(LEFT, TOP)
    east, south = to_lonlat.transform(LEFT + 20, TOP - 20)
    entities = "".join(
        f"<otherEntity><entityName>{f}</entityName><physical><size unit=\"bytes\">{(folder / f).stat().st_size}"
        f"</size><authentication method=\"MD5\">{_md5(folder / f)}</authentication><distribution><online><url>"
        f"https://example.org/training-pond/{f}</url></online></distribution></physical></otherEntity>"
        for f in files)
    (folder / "metadata.xml").write_text(
        f'<?xml version="1.0"?><eml:eml xmlns:eml="https://eml.ecoinformatics.org/eml-2.2.0" '
        f'packageId="doi:10.5555/training.pond" system="https://example.org"><dataset>'
        f"<title>Training Pond: drone survey of a beaver dam, July 2023 (invented, for the course)</title>"
        f"<creator><individualName><surName>Example</surName></individualName></creator>"
        f"<intellectualRights>This work is licensed under https://creativecommons.org/licenses/by/4.0/</intellectualRights>"
        f"<coverage><geographicCoverage><geographicDescription>Training Pond</geographicDescription>"
        f"<boundingCoordinates><westBoundingCoordinate>{west}</westBoundingCoordinate><eastBoundingCoordinate>{east}"
        f"</eastBoundingCoordinate><northBoundingCoordinate>{north}</northBoundingCoordinate><southBoundingCoordinate>"
        f"{south}</southBoundingCoordinate></boundingCoordinates></geographicCoverage><temporalCoverage><rangeOfDates>"
        f"<beginDate><calendarDate>2022-08-01</calendarDate></beginDate><endDate><calendarDate>2023-07-12"
        f"</calendarDate></endDate></rangeOfDates></temporalCoverage></coverage>"
        f"<methods><methodStep><description>Photos taken with a DJI Phantom 4 Pro (camera FC6310) on 12 July 2023, "
        f"processed into an orthomosaic and a DSM. The 2022 elevation grid comes from an earlier survey (August 2022) "
        f"in UTM zone 12N (EPSG:32612). Dams were mapped by hand on the orthomosaic.</description></methodStep>"
        f"</methods>{entities}</dataset></eml:eml>")


def make(root: Path) -> Path:
    """Write the sample data root under ``root``; returns the dataset folder."""
    folder = root / FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    write_orthomosaic(folder / "ortho_2023-07-12.tif")
    write_dsm(folder / "dsm_2023-07-12.tif")
    write_grid_without_crs(folder / "dem_2022.asc")
    write_dams(folder / "dams_2023-07-12.gpkg")
    write_photos(folder / "photos_2023-07-12" / "100MEDIA")
    (folder / "README.txt").write_text(
        "Training Pond drone survey, 12 July 2023 (invented data for the BeaverSim course).\n"
        "ortho_2023-07-12.tif  orthomosaic, RGB + alpha, 5 cm\n"
        "dsm_2023-07-12.tif    digital surface model, metres above sea level, 10 cm\n"
        "dem_2022.asc          elevation grid of the August 2022 survey, 1 m, UTM 12N\n"
        "dams_2023-07-12.gpkg  dams mapped on the orthomosaic\n"
        "photos_2023-07-12/    the drone photos\n")
    write_record(folder, ["ortho_2023-07-12.tif", "dsm_2023-07-12.tif", "dem_2022.asc", "dams_2023-07-12.gpkg",
                          "README.txt"])
    (root / "sites.yaml").write_text(
        "# Site registry of the sample data root (use it with: export BEAVER_SITES=<this file>)\nschema: 1\nsites:\n"
        "  training_pond:\n    name: Training Pond (invented site for the course), Montana, USA\n"
        "    crs: EPSG:32612\n    colonies: null\n    land_status: null\n    governance: null\n")
    return folder


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path, default=Path("output/manual/sample_root"))
    args = parser.parse_args()
    folder = make(args.out)
    size = sum(p.stat().st_size for p in args.out.rglob("*") if p.is_file())
    print(f"sample data root -> {args.out} ({size / 1e6:.1f} MB); dataset folder {folder.relative_to(args.out)}")


if __name__ == "__main__":
    main()
