"""Evidence gathering (photo folders are one entry each) and the photo reader."""
from pathlib import Path

from PIL import ExifTags, Image

from data_acquisition.catalog import evidence
from data_acquisition.readers import photos


def test_photo_folder_is_one_entry(tmp_path: Path):
    survey = tmp_path / "site" / "surveys" / "2018-06-05"
    media = survey / "photos" / "100MEDIA"
    media.mkdir(parents=True)
    for i in range(evidence.PHOTO_FOLDER):
        Image.new("RGB", (4, 4)).save(media / f"DJI_{i:04d}.JPG")
    few = survey / "photos" / "101MEDIA"                  # too few photos: listed one by one
    few.mkdir()
    Image.new("RGB", (4, 4)).save(few / "DJI_0001.JPG")
    (survey / "notes.txt").write_text("flight notes")

    folder = evidence.gather(tmp_path, ["site"])["folders"][0]
    names = [f["name"] for f in folder["files"]]
    assert names == ["surveys/2018-06-05/notes.txt", "surveys/2018-06-05/photos/100MEDIA/",
                     "surveys/2018-06-05/photos/101MEDIA/DJI_0001.JPG"]
    group = folder["files"][1]
    assert group["photos"] == evidence.PHOTO_FOLDER
    assert group["first"]["name"] == "DJI_0000.JPG" and group["last"]["name"] == "DJI_0009.JPG"


def _photo(path: Path, taken: str, lon: float, lat: float) -> None:
    exif = Image.Exif()
    exif[ExifTags.Base.Model] = "FC6310\x00\x00"
    exif.get_ifd(ExifTags.IFD.Exif)[ExifTags.Base.DateTimeOriginal] = taken
    gps = exif.get_ifd(ExifTags.IFD.GPSInfo)
    gps[ExifTags.GPS.GPSLatitudeRef], gps[ExifTags.GPS.GPSLatitude] = "N", (48.0, 55.0, 30.0)
    gps[ExifTags.GPS.GPSLongitudeRef], gps[ExifTags.GPS.GPSLongitude] = "W", (113.0, 7.0, lon)
    Image.new("RGB", (4, 4)).save(path, exif=exif)


def test_photo_reader(tmp_path: Path):
    (tmp_path / "100MEDIA").mkdir()
    _photo(tmp_path / "100MEDIA" / "DJI_0001.JPG", "2018:06:05 08:00:00", 0.0, 0)
    _photo(tmp_path / "100MEDIA" / "DJI_0002.JPG", "2018:06:05 09:30:00", 30.0, 0)
    Image.new("RGB", (4, 4)).save(tmp_path / "100MEDIA" / "DJI_0003.JPG")          # no EXIF
    info = photos.info(tmp_path)
    assert info["count"] == 3 and info["cameras"] == {"FC6310": 2}
    assert (info["first"].hour, info["last"].hour) == (8, 9)
    assert info["no_position"] == ["100MEDIA/DJI_0003.JPG"]
    lon, lat = info["positions"][1]
    assert round(lat, 4) == 48.9250 and round(lon, 4) == -113.125
