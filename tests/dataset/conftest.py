"""Shared fixtures for the dataset-pipeline tests: a small synthetic data root and site registry.

Everything is generated in a temporary folder, so the tests run without the drive or a network.
"""
import datetime
import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import Point

from data_acquisition.catalog import summary as summaries
from data_acquisition.sources import archives

UTM3 = "EPSG:32603"                       # the Swan Lake CRS; any projected CRS would do
ORIGIN = (508200.0, 7228000.0)            # left, top in UTM 3N metres


def write_tif(path: Path, bands: int = 3, dtype: str = "uint8", crs: str = UTM3, nodata=None,
              colorinterp=None, size: int = 32, value: float = 100) -> Path:
    """A small GeoTIFF, 0.1 m pixels, filled with ``value``."""
    profile = {"driver": "GTiff", "width": size, "height": size, "count": bands, "dtype": dtype, "crs": crs,
               "transform": from_origin(*ORIGIN, 0.1, 0.1), "nodata": nodata}
    with rasterio.open(path, "w", **profile) as d:
        d.write(np.full((bands, size, size), value, dtype=dtype))
        if colorinterp:
            d.colorinterp = colorinterp
    return path


def write_asc(path: Path, size: int = 8) -> Path:
    """An ESRI ASCII grid: a raster with no CRS of its own."""
    header = f"ncols {size}\nnrows {size}\nxllcorner {ORIGIN[0]}\nyllcorner {ORIGIN[1] - size}\ncellsize 1\nNODATA_value -9999\n"
    path.write_text(header + "\n".join(" ".join("1690.5" for _ in range(size)) for _ in range(size)) + "\n")
    return path


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A data root with one dataset folder of rasters, vectors, tables, a report and a zip."""
    folder = tmp_path / "repo" / "doi_10.0000_test"
    folder.mkdir(parents=True)
    write_tif(folder / "ortho_2021.tif", colorinterp=[rasterio.enums.ColorInterp.red,
                                                      rasterio.enums.ColorInterp.green,
                                                      rasterio.enums.ColorInterp.blue])
    (folder / "ortho_2021.tif.ovr").write_bytes(b"overview sidecar")          # a sidecar, never reported
    write_tif(folder / "dsm_2021.tif", bands=2, dtype="float32", nodata=-9999, value=40.0)
    write_asc(folder / "dem_2018.txt")
    dams = {}
    for year, n in ((2010, 2), (2013, 3)):
        dams[year] = gpd.GeoDataFrame({"name": [f"d{i}" for i in range(n)]},
                                      geometry=[Point(-164.8 + i * 0.001, 65.17) for i in range(n)], crs="EPSG:4326")
        dams[year].to_file(folder / "dams.gpkg", layer=f"dams_{year}", driver="GPKG")
    (folder / "gcps.csv").write_text("Surveyed ground control points\n,,\nGCP,Northing,Easting,Elevation (m)\n"
                                     f"1,{ORIGIN[1] - 1},{ORIGIN[0] + 1},40.1\n2,{ORIGIN[1] - 2},{ORIGIN[0] + 2},40.3\n")
    (folder / "reaches.csv").write_text("ReachID,oCC_EX\n1,0.5\n2,1.2\n3,0.0\n")
    (folder / "report_2021.pdf").write_bytes(b"%PDF-1.4 not really a pdf")
    write_tif(tmp_path / "inner.tif")
    with zipfile.ZipFile(folder / "bundle.zip", "w") as z:
        z.write(tmp_path / "inner.tif", "bundle/inner.tif")
    (tmp_path / "inner.tif").unlink()
    archives.extract(folder / "bundle.zip")                 # as a source client would
    return tmp_path


@pytest.fixture
def registry(tmp_path: Path, monkeypatch) -> Path:
    """A site registry with one site and one region, used in place of ``data_acquisition/sites.yaml``."""
    path = tmp_path / "sites.yaml"
    path.write_text("schema: 1\nsites:\n"
                    "  test_site: {name: Test site, crs: 'EPSG:32603', colonies: null, land_status: null, governance: null}\n"
                    "  test_region: {name: Test region, crs: 'EPSG:32603', colonies: null, land_status: null,\n"
                    "                governance: null, level: region, contains: [test_site]}\n")
    monkeypatch.setattr(summaries, "SITES", path)
    return path


@pytest.fixture
def summary(root: Path, registry: Path) -> dict:
    """A reviewed summary describing every file of the ``root`` fixture."""
    s = {"schema": 1, "dataset": "test_dataset", "title": "Test dataset",
         "authored": {"by": "claude", "model": "test", "date": datetime.date(2026, 10, 14)},
         "reviewed": {"by": "Tester", "date": datetime.date(2026, 10, 14)},
         "source": {"kind": "folder", "provider": "test"},
         "groups": [{"folder": "repo/doi_10.0000_test", "site": "test_site", "date": datetime.date(2021, 8, 3),
                     "files": [
                         {"path": "ortho_2021.tif", "product": "orthomosaic"},
                         {"path": "dsm_2021.tif", "product": "dsm", "bands": ["elevation", "uncertainty"]},
                         {"path": "dem_2018.txt", "product": "dtm", "date": datetime.date(2018, 8, 14),
                          "crs": "EPSG:32603"},
                         {"path": "dams.gpkg", "product": "annotations",
                          "layers": {"pattern": r"_(\d{4})$", "date_precision": "year"}},
                         {"path": "gcps.csv", "product": "survey_points", "variant": "gcp",
                          "table": {"skip": 2, "x": "Easting", "y": "Northing", "z": "Elevation (m)"}},
                         {"path": "reaches.csv", "product": "model_output", "date_precision": "unknown",
                          "start_date": datetime.date(1990, 1, 1), "end_date": datetime.date(2025, 5, 5),
                          "table": {"skip": 0}, "fields": {"id": "ReachID", "value": "oCC_EX"}},
                         {"path": "report_2021.pdf", "role": "report", "attach_to": ["orthomosaic", "dsm"]},
                         {"path": "bundle.zip", "role": "archive", "attach_to": ["orthomosaic"]},
                         {"path": "bundle/inner.tif", "product": "orthomosaic", "variant": "inner",
                          "archive": "bundle.zip"},
                     ]}]}
    assert summaries.check(s, summaries.load_sites()) == []
    path = registry.parent / "test_dataset.yaml"
    path.write_text(summaries.yaml.safe_dump(s, sort_keys=False))
    return s
