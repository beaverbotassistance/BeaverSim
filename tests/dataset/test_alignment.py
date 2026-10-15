"""The alignment check finds a known offset between an outline and the edges of the image it was drawn on."""
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box

from data_acquisition.sources import field_alignment

RES = 0.05                                  # metres per pixel
ORIGIN = (500000.0, 5400000.0)              # UTM zone 3N, metres


@pytest.fixture
def image(tmp_path: Path) -> Path:
    """A dark image with a bright 6 m × 4 m rectangle whose lower-left corner is 10 m east, 10 m south of
    the top-left corner of the image."""
    size = 600                              # 30 m
    data = np.full((3, size, size), 40, dtype="uint8")
    row0, col0 = int(16 / RES), int(10 / RES)          # top edge 16 m below the image top (lower edge at 20 m)
    data[:, row0:row0 + int(4 / RES), col0:col0 + int(6 / RES)] = 220
    path = tmp_path / "orthomosaic_part-1_chunk-1.tif"
    with rasterio.open(path, "w", driver="GTiff", width=size, height=size, count=3, dtype="uint8",
                       crs="EPSG:32603", transform=from_origin(*ORIGIN, RES, RES)) as d:
        d.write(data)
    return path


def test_best_shift_recovers_the_offset(image: Path):
    x0, y_top = ORIGIN
    rectangle = box(x0 + 10, y_top - 20, x0 + 16, y_top - 16)          # where the bright rectangle is
    drawn = box(x0 + 10.6, y_top - 20.4, x0 + 16.6, y_top - 16.4)     # drawn 0.6 m east, 0.4 m south of it
    east, north = field_alignment.best_shift(image, drawn)
    assert east == pytest.approx(-0.6, abs=RES) and north == pytest.approx(0.4, abs=RES)
    east, north = field_alignment.best_shift(image, rectangle)
    assert abs(east) <= RES and abs(north) <= RES


def test_outline_off_the_image_is_skipped(image: Path):
    x0, y_top = ORIGIN
    assert field_alignment.best_shift(image, box(x0 - 50, y_top - 20, x0 - 40, y_top - 10)) is None
