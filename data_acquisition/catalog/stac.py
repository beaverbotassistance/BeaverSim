"""Build, save, load and validate STAC catalogs of local files.

Catalogs are saved self-contained with relative links, and asset hrefs are made relative to the
item, so a catalog on the drive keeps working wherever the drive is mounted.
"""
import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pystac
from pystac.extensions.eo import Band, EOExtension
from pystac.extensions.file import FileExtension
from pystac.extensions.projection import ProjectionExtension
from pystac.extensions.raster import DataType, RasterBand, RasterExtension
from rasterio.warp import transform_bounds, transform_geom

# multihash prefixes (code, digest length) for the file extension's checksum field
MULTIHASH = {"md5": "d510", "sha256": "1220"}


def multihash(algorithm: str, hexdigest: str) -> str:
    return MULTIHASH[algorithm.lower().replace("-", "")] + hexdigest.lower()


def lonlat_box(bounds, crs: str) -> (Dict[str, Any], List[float]):
    """Lon/lat polygon and bbox of ``bounds`` (left, bottom, right, top) in ``crs`` (EPSG code or WKT),
    densified so projected edges stay accurate."""
    left, bottom, right, top = bounds
    ring = [[left, bottom], [right, bottom], [right, top], [left, top], [left, bottom]]
    geom = transform_geom(crs, "EPSG:4326", {"type": "Polygon", "coordinates": [ring]}, precision=7)
    bbox = list(transform_bounds(crs, "EPSG:4326", *bounds, densify_pts=21))
    geom["coordinates"] = [[list(p) for p in r] for r in geom["coordinates"]]
    return geom, bbox


def footprint(info: Dict[str, Any]) -> (Dict[str, Any], List[float]):
    """Lon/lat polygon and bbox of a raster's bounds (``info`` from ``readers.geotiff.info``)."""
    return lonlat_box(info["bounds"], f"EPSG:{info['epsg']}")


def _utc(d: datetime.date, end: bool = False) -> datetime.datetime:
    return datetime.datetime.combine(d, datetime.time.max if end else datetime.time(), datetime.timezone.utc)


def raster_item(item_id: str, path: Path, info: Dict[str, Any], start: datetime.date, end: datetime.date,
                asset_key: str, roles: List[str], bands: List[Dict[str, Optional[str]]], unit: Optional[str] = None,
                checksum: Optional[str] = None, title: Optional[str] = None) -> pystac.Item:
    """Item with one raster asset, footprint from the raster bounds, and proj/raster/eo/file fields.

    ``info`` comes from :func:`data_acquisition.readers.geotiff.info`. ``bands`` is one dict per band:
    ``{"name": ..., "common_name": ...}`` (common_name may be None); band names are written as
    ``eo:bands`` for every product.
    Time: one day (``start == end``) gives ``datetime`` at midnight UTC of that day; a longer span
    (a month, a year, two epochs) gives ``start_datetime`` / ``end_datetime`` and no ``datetime``.
    """
    geom, bbox = footprint(info)
    props = {"gsd": round(min(info["resolution"]), 4)}
    if start == end:
        item = pystac.Item(item_id, geom, bbox, _utc(start), properties=props)
    else:
        item = pystac.Item(item_id, geom, bbox, None, properties=props,
                           start_datetime=_utc(start), end_datetime=_utc(end, end=True))
    item.add_asset(asset_key, pystac.Asset(str(path.resolve()), title=title, roles=roles,
                                           media_type=pystac.MediaType.GEOTIFF))
    asset = item.assets[asset_key]

    proj = ProjectionExtension.ext(item, add_if_missing=True)
    proj.epsg, proj.bbox, proj.shape, proj.transform = info["epsg"], list(info["bounds"]), info["shape"], info["transform"]

    RasterExtension.ext(asset, add_if_missing=True).bands = [
        RasterBand.create(data_type=DataType(dt), nodata=info["nodata"], unit=unit,
                          spatial_resolution=round(min(info["resolution"]), 4))
        for dt in info["dtypes"]]
    if bands:
        EOExtension.ext(asset, add_if_missing=True).bands = [
            Band.create(name=b["name"], common_name=b.get("common_name")) for b in bands]

    file_ext = FileExtension.ext(asset, add_if_missing=True)
    file_ext.size = path.stat().st_size
    if checksum:
        file_ext.checksum = checksum
    return item


VECTOR_MEDIA = {".gpkg": "application/geopackage+sqlite3", ".geojson": "application/geo+json",
                ".json": "application/geo+json", ".kml": "application/vnd.google-earth.kml+xml",
                ".kmz": "application/vnd.google-earth.kmz", ".fgb": "application/vnd.flatgeobuf",
                ".gpx": "application/gpx+xml", ".shp": "application/vnd.shp"}


def size_of(path: Path) -> int:
    """Bytes of a file, or of every file under a folder (a File Geodatabase is a folder)."""
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file()) if path.is_dir() else path.stat().st_size


def vector_item(item_id: str, path: Path, info: Dict[str, Any], start: datetime.date, end: datetime.date,
                asset_key: str, roles: List[str], checksum: Optional[str] = None,
                title: Optional[str] = None) -> pystac.Item:
    """Item with one vector asset: footprint from the layers' bounds, proj fields, and the layer list
    (name, geometry type, features, fields) as ``beaver:layers``.

    ``info`` comes from :func:`data_acquisition.readers.vector.info`. When layers have different CRSs,
    the footprint is the lon/lat box around all of them and no projection is recorded.
    """
    if info["bounds"] and info["crs"]:
        geom, bbox = lonlat_box(info["bounds"], info["crs"])
    else:
        boxes = [lonlat_box(l["bounds"], l["crs"])[1] for l in info["layers"] if l["bounds"] and l["crs"]]
        bbox = ([min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes),
                 max(b[3] for b in boxes)] if boxes else None)
        geom = ({"type": "Polygon", "coordinates": [[[bbox[0], bbox[1]], [bbox[2], bbox[1]], [bbox[2], bbox[3]],
                                                      [bbox[0], bbox[3]], [bbox[0], bbox[1]]]]} if bbox else None)
    props = {"beaver:layers": [{k: l[k] for k in ("name", "geometry_type", "features", "fields")}
                               for l in info["layers"]]}
    if start == end:
        item = pystac.Item(item_id, geom, bbox, _utc(start), properties=props)
    else:
        item = pystac.Item(item_id, geom, bbox, None, properties=props,
                           start_datetime=_utc(start), end_datetime=_utc(end, end=True))
    item.add_asset(asset_key, pystac.Asset(str(path.resolve()), title=title, roles=roles,
                                           media_type=VECTOR_MEDIA.get(path.suffix.lower())))
    if info["crs"]:
        proj = ProjectionExtension.ext(item, add_if_missing=True)
        if info["epsg"]:
            proj.epsg = info["epsg"]
        else:
            proj.wkt2 = info["crs"]
        if info["bounds"]:
            proj.bbox = info["bounds"]
    file_ext = FileExtension.ext(item.assets[asset_key], add_if_missing=True)
    file_ext.size = size_of(path)
    if checksum:
        file_ext.checksum = checksum
    return item


def add_file_asset(item: pystac.Item, key: str, path: Path, roles: List[str], title: Optional[str] = None,
                   media_type: Optional[str] = None) -> None:
    """Add a non-raster asset (report, metadata record, photo list) to ``item``."""
    item.add_asset(key, pystac.Asset(str(path.resolve()), title=title, roles=roles, media_type=media_type))
    FileExtension.ext(item.assets[key], add_if_missing=True).size = path.stat().st_size


def save(catalog: pystac.Catalog, out_dir: Path) -> Path:
    """Write ``catalog`` under ``out_dir`` with relative links and relative asset hrefs."""
    out_dir.mkdir(parents=True, exist_ok=True)
    catalog.normalize_hrefs(str(out_dir.resolve()))
    catalog.make_all_asset_hrefs_relative()
    catalog.save(pystac.CatalogType.SELF_CONTAINED)
    return out_dir / "catalog.json"


def load(path: Path) -> pystac.Catalog:
    return pystac.Catalog.from_file(str(path))


def asset_path(asset: pystac.Asset) -> Path:
    """Local path of an asset (resolves relative hrefs against its item)."""
    return Path(asset.get_absolute_href())


def validate(catalog: pystac.Catalog) -> List[str]:
    """Schema-validate every object in the catalog; returns error messages (empty when valid).

    Needs network access the first time, to fetch the STAC and extension schemas.
    """
    errors = []
    for obj in [catalog, *catalog.get_children(), *catalog.get_items(recursive=True)]:
        try:
            obj.validate()
        except pystac.errors.STACValidationError as e:
            errors.append(f"{obj.id}: {str(e).splitlines()[0]}")
    return errors
