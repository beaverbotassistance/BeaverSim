"""Readers: rasters, vectors, tables, and the metadata-record readers' handling of checksums."""
import datetime
import json

import numpy as np
import pytest
import rasterio

from data_acquisition.catalog import stac
from data_acquisition.readers import geotiff, hydroshare, table, vector
from tests.dataset.conftest import ORIGIN, UTM3, write_tif

FOLDER = "repo/doi_10.0000_test"


def test_raster_info(root):
    info = geotiff.info(root / FOLDER / "ortho_2021.tif")
    assert info["epsg"] == 32603 and info["count"] == 3 and info["has_crs"]
    assert geotiff.declared_bands(info) == ["red", "green", "blue"]


def test_is_raster(root):
    assert geotiff.is_raster(root / FOLDER / "ortho_2021.tif")
    assert geotiff.is_raster(root / FOLDER / "dem_2018.txt")                # an ESRI ASCII grid
    assert not geotiff.is_raster(root / FOLDER / "reaches.csv")
    readme = root / "README.txt"
    readme.write_text("not a raster\n")
    assert not geotiff.is_raster(readme)


def test_ascii_grid_has_no_crs(root):
    info = geotiff.info(root / FOLDER / "dem_2018.txt")
    assert info["driver"] == "AAIGrid" and not info["has_crs"]


def test_unapplied_georeference(tmp_path):
    tif = write_tif(tmp_path / "shifted.tif")
    (tmp_path / "shifted.tif.aux.xml").write_text(
        '<PAMDataset><Metadata domain="xml:ESRI" format="xml"><GeodataXform xsi:type="typens:PolynomialXform" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><PolynomialOrder>1</PolynomialOrder>'
        f'<SourceGCPs><Double>{ORIGIN[0]}</Double><Double>{ORIGIN[1]}</Double>'
        f'<Double>{ORIGIN[0] + 10}</Double><Double>{ORIGIN[1]}</Double></SourceGCPs>'
        f'<TargetGCPs><Double>{ORIGIN[0] + 3}</Double><Double>{ORIGIN[1] + 4}</Double>'
        f'<Double>{ORIGIN[0] + 10}</Double><Double>{ORIGIN[1] + 1}</Double></TargetGCPs>'
        '</GeodataXform></Metadata></PAMDataset>')
    xform = geotiff.unapplied_georeference(tif)
    assert xform == {"type": "PolynomialXform", "order": 1, "control_points": 2}
    adjustment = geotiff.arcgis_adjustment((tmp_path / "shifted.tif.aux.xml").read_text())
    assert adjustment["target"].tolist() == [[ORIGIN[0] + 3, ORIGIN[1] + 4], [ORIGIN[0] + 10, ORIGIN[1] + 1]]
    assert adjustment["not_applied"] == []
    assert geotiff.unapplied_georeference(write_tif(tmp_path / "plain.tif")) is None


def test_vector_info(root):
    info = vector.info(root / FOLDER / "dams.gpkg", sample_rows=1)
    assert [l["name"] for l in info["layers"]] == ["dams_2010", "dams_2013"]
    assert info["epsg"] == 4326 and info["features"] == 5 and info["layers"][0]["sample"] == [{"name": "d0"}]
    assert info["layers"][0]["geometry_type"] == "Point"


def test_point_table(root):
    info = table.info(root / FOLDER / "gcps.csv", {"skip": 2, "x": "Easting", "y": "Northing"}, UTM3)
    assert info["epsg"] == 32603 and info["features"] == 2
    assert info["bounds"] == [ORIGIN[0] + 1, ORIGIN[1] - 2, ORIGIN[0] + 2, ORIGIN[1] - 1]


def test_rows_only_table(root):
    info = table.info(root / FOLDER / "reaches.csv", {"skip": 0}, UTM3)
    assert info["spatial"] is False and info["features"] == 3 and info["bounds"] is None
    assert info["layers"][0]["fields"] == ["ReachID", "oCC_EX"]


def test_hydroshare_checksums_are_parsed():
    record = {"metadata": {"title": "t", "rights": {}, "creators": []},
              "files": [{"url": "https://x/data/contents/a.csv", "size": 1, "checksum": "AB" * 16},
                        {"url": "https://x/data/contents/b.csv", "size": 2, "checksum": "cd" * 16 + "-2"}]}
    entities = hydroshare.read(json.dumps(record))["entities"]
    assert entities["a.csv"]["checksum"] == ("md5", "ab" * 16)
    assert entities["b.csv"]["checksum"] == ("s3etag", "cd" * 16 + "-2")


def test_gsd_in_metres_for_a_raster_in_degrees(tmp_path):
    from rasterio.transform import from_origin
    path = tmp_path / "degrees.tif"
    with rasterio.open(path, "w", driver="GTiff", width=10, height=10, count=1, dtype="uint8", crs="EPSG:4326",
                       transform=from_origin(-113.1, 48.95, 1.8e-7, 1.2e-7)) as d:
        d.write(np.zeros((1, 10, 10), dtype="uint8"))
    info = geotiff.info(path)
    item = stac.raster_item("x", path, info, datetime.date(2018, 6, 5), datetime.date(2018, 6, 5), "orthomosaic",
                            ["data"], [{"name": "b1"}])
    assert item.properties["gsd"] == pytest.approx(0.0132, abs=1e-4)      # 1.2e-7 degrees of latitude ~ 1.3 cm


def test_raster_that_cannot_be_placed(tmp_path):
    path = write_tif(tmp_path / "local.tif")
    local = ('ENGCRS["unnamed",EDATUM["unknown"],CS[Cartesian,2],'
             'AXIS["x",east,LENGTHUNIT["metre",1]],AXIS["y",north,LENGTHUNIT["metre",1]]]')
    info = dict(geotiff.info(path), epsg=None, crs=local)
    with pytest.raises(ValueError, match="cannot be placed"):
        stac.raster_item("x", path, info, datetime.date(2018, 6, 5), datetime.date(2018, 6, 5), "orthomosaic",
                         ["data"], [{"name": "b1"}])
