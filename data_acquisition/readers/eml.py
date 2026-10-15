"""EML (Ecological Metadata Language) reader: the metadata standard of DataONE repositories
(Arctic Data Center, KNB, LTER, EDI).

Reads only structured fields. Free-text sections (methods) are returned as text for people, or a
summary drafter, to interpret; nothing here guesses from prose.
"""
import re
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any, Dict, Optional

LICENCES = {"publicdomain/zero/1.0": "CC0-1.0", "licenses/by/4.0": "CC-BY-4.0",
            "licenses/by-nc/4.0": "CC-BY-NC-4.0", "licenses/by-sa/4.0": "CC-BY-SA-4.0"}
ENTITY_KINDS = ("otherEntity", "spatialRaster", "spatialVector", "dataTable")


def _text(el: Optional[ET.Element]) -> str:
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip() if el is not None else ""


def read(xml: str) -> Dict[str, Any]:
    """Package id, title, licence (SPDX), creators, dates, bbox, methods text and data entities."""
    root = ET.fromstring(xml)
    ds = root.find("dataset")
    rights = _text(ds.find("intellectualRights"))
    bounds = {k: float(_text(ds.find(f".//{k}BoundingCoordinate"))) for k in ("west", "east", "north", "south")
              if ds.find(f".//{k}BoundingCoordinate") is not None}
    entities = {}
    for kind in ENTITY_KINDS:
        for e in ds.iter(kind):
            auth, url, size = e.find(".//authentication"), _text(e.find(".//url")), e.find(".//size")
            attributes = [{"name": _text(a.find("attributeName")), "definition": _text(a.find("attributeDefinition")),
                           "codes": [(_text(c.find("code")), _text(c.find("definition")))
                                     for c in a.iter("codeDefinition")]}
                          for a in e.iter("attribute")]
            entities[_text(e.find("entityName"))] = {
                "url": url or None, "pid": urllib.parse.unquote(url.rsplit("/resolve/", 1)[-1]) if url else None,
                "size": int(_text(size)) if size is not None else None,
                "checksum": (auth.get("method", "").lower().replace("-", ""), _text(auth)) if auth is not None else None,
                "attributes": attributes}
    return {"package_id": root.get("packageId"), "title": _text(ds.find("title")),
            "licence": next((spdx for key, spdx in LICENCES.items() if key in rights), None), "rights": rights,
            "creators": [_text(c.find(".//surName")) for c in ds.findall("creator")],
            "dates": sorted(_text(e) for e in ds.iter("calendarDate")), "bounds": bounds,
            "methods": " ".join(_text(m) for m in ds.iter("methodStep")), "entities": entities}
