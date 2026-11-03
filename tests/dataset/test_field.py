"""Field-drive source step: layout checks, CRS corrections, ArcGIS georeferencing applied as a sidecar."""
import os
from pathlib import Path

import numpy as np
import pytest
import rasterio
from affine import Affine
from pyproj import CRS

from data_acquisition.sources import field, field_inventory

ARC = ('PROJCS["WGS_1984_ARC_System_Zone_12",GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",'
       '6378137.0,298.257223563]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],'
       'PROJECTION["Equidistant_Cylindrical"],PARAMETER["False_Easting",0.0],PARAMETER["False_Northing",0.0],'
       'PARAMETER["Central_Meridian",0.0],PARAMETER["Standard_Parallel_1",-52.28859923],UNIT["Meter",1.0]]')
SPHERE = "+proj=eqc +lat_ts=-52.28859923 +lat_0=0 +lon_0=0 +x_0=0 +y_0=0 +R=6378137 +units=m +no_defs"
CORRECTIONS = [{"from": "WGS_1984_ARC_System_Zone_12", "to": SPHERE, "reason": "ArcGIS uses a sphere"}]


def test_the_copy_kept_does_not_depend_on_the_listing_order(tmp_path: Path, monkeypatch):
    for folder in ("100MEDIA", "106MEDIA"):
        (tmp_path / folder).mkdir()
        (tmp_path / folder / "DJI_0002.JPG").write_bytes(b"same size")
    info = {"camera": "FC6310", "taken_at": "2019-09-03T10:00:00", "lat": 48.93, "lon": -113.12}
    monkeypatch.setattr(field_inventory, "read_photos", lambda jpgs, *args: [info] * len(jpgs))
    monkeypatch.setattr(field_inventory, "site_of", lambda rel: "rumney_ranch")
    monkeypatch.setattr(field_inventory, "survey_date_of", lambda rel: None)
    files = [e for folder in tmp_path.iterdir() for e in os.scandir(folder)]
    for listed in (files, files[::-1]):
        rows = field_inventory.photo_rows(tmp_path, listed)
        assert [r["source_path"] for r in rows if r["include"]] == ["106MEDIA/DJI_0002.JPG"]


def test_layout_names_and_targets():
    layout = {"schema": 1, "site": "s", "authored": {"by": "claude", "date": "2026-10-15"}, "base": "b/",
              "photos": "by_exif_date",
              "orthomosaics": [{"source": "a.tif", "to": "surveys/2018-06-05/orthomosaic_part-1.tif"},
                               {"source": "b.tif", "to": "surveys/2018-06-05/orthomosaic_part-1.tif"}],
              "annotations": [{"source": "x.gdb", "layer": "L", "to": "annotations/2018-06-05/dams_colony-a.gpkg"},
                              {"source": "x.gdb", "layer": "M", "to": "annotations/2018/Dams.gpkg"}]}
    problems = field.check_layout(layout)
    assert any("also the target" in p for p in problems)
    assert any("Dams.gpkg does not follow" in p for p in problems)
    assert len(problems) == 2


def test_corrected_crs_keeps_the_vertical_part():
    compound = CRS.from_user_input(f'COMPD_CS["arc + navd88",{ARC},'
                                   'VERT_CS["NAVD88 height (ftUS)",VERT_DATUM["North American Vertical Datum 1988",'
                                   '2005],UNIT["US survey foot",0.304800609601219]]]').to_wkt()
    fixed = CRS.from_wkt(field.corrected_crs(compound, CORRECTIONS))
    horizontal, vertical = fixed.sub_crs_list
    assert horizontal.ellipsoid.semi_major_metre == horizontal.ellipsoid.semi_minor_metre == 6378137
    assert vertical.name == "NAVD88 height (ftUS)"
    assert field.corrected_crs(CRS.from_epsg(32612).to_wkt(), CORRECTIONS) is None


def test_same_place_catches_a_different_earth_model():
    corners = [-7703915.0, 5446253.0, -7701317.0, 5448352.0]
    sphere = CRS.from_user_input(SPHERE).to_wkt()
    assert field._same_place(sphere, sphere, corners)
    ellipsoid = CRS.from_user_input(SPHERE.replace("+R=6378137", "+datum=WGS84")).to_wkt()
    assert not field._same_place(sphere, ellipsoid, corners)       # 25 km apart under GDAL's PROJ


def _aux(source: np.ndarray, target: np.ndarray, extra_step: bool = False) -> str:
    doubles = lambda pts: "".join(f"<Double>{v!r}</Double>" for v in pts.ravel().tolist())
    fitted = ('<PolynomialOrder>1</PolynomialOrder><SpatialReference xsi:type="typens:ProjectedCoordinateSystem">'
              f"<WKT>{ARC}</WKT></SpatialReference>"
              f'<SourceGCPs xsi:type="typens:ArrayOfDouble">{doubles(source)}</SourceGCPs>'
              f'<TargetGCPs xsi:type="typens:ArrayOfDouble">{doubles(target)}</TargetGCPs>')
    if extra_step:
        body = (f'<XF_0 xsi:type="typens:PolynomialXform">{fitted}</XF_0>'
                '<XF_1 xsi:type="typens:PolynomialXform"><PolynomialOrder>1</PolynomialOrder>'
                '<CoeffX xsi:type="typens:ArrayOfDouble"><Double>1</Double></CoeffX></XF_1>')
        kind = "CompositeXform"
    else:
        body, kind = fitted, "PolynomialXform"
    return ('<PAMDataset><Metadata domain="xml:ESRI" format="xml"><GeodataXform xsi:type="typens:'
            f'{kind}" xmlns:xsi="x" xmlns:typens="y">{body}</GeodataXform></Metadata></PAMDataset>')


@pytest.mark.parametrize("extra_step", [False, True])
def test_georeference_applies_the_control_point_fit(tmp_path: Path, extra_step: bool):
    raw = Affine(1e-6, 0, -113.09, 0, -1e-6, 48.95)                  # the file's own coordinates, in degrees
    tif = tmp_path / "tile.tif"
    with rasterio.open(tif, "w", driver="GTiff", width=100, height=80, count=1, dtype="uint8", transform=raw) as d:
        d.write(np.zeros((1, 80, 100), dtype="uint8"))
    adjust = Affine(0.0125, 0.0001, -7700800.0, 0.0001, -0.0135, 5448900.0)   # pixel -> ARC zone metres
    pixels = np.array([(5, 5), (90, 10), (50, 70), (10, 60), (80, 75)], dtype=float)
    source = np.array([raw @ tuple(p) for p in pixels])
    target = np.array([adjust @ tuple(p) for p in pixels])
    aux = tmp_path / "original.tif.aux.xml"
    aux.write_text(_aux(source, target, extra_step))

    fit = field.georeference(tif, aux, tmp_path / "tile.tif.aux.xml", CORRECTIONS)
    assert fit["control_points"] == 5 and fit["max_m"] < 1e-6
    assert bool(fit["not_applied"]) == extra_step
    with rasterio.open(tif) as d:                                   # GDAL reads the written sidecar first
        assert np.allclose(list(d.transform)[:6], list(adjust)[:6])
        assert CRS.from_wkt(d.crs.to_wkt()).ellipsoid.semi_minor_metre == 6378137
