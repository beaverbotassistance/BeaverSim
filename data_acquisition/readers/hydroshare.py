"""HydroShare resource record reader: the science metadata (JSON of ``/hsapi2/resource/<id>/json/``)
and the file list (name, MD5, size, download link, from ``/hsapi/resource/<id>/files/``).

HydroShare serves the two from separate endpoints; the source client saves both responses,
unchanged, in one file: ``{"metadata_url", "metadata", "files_url", "files": [...]}``.

Returns the same shape as :func:`data_acquisition.readers.eml.read`, so the builder and the
evidence gatherer treat both the same way. The abstract is returned as ``methods``. A collection
resource has no files of its own; its members are returned as ``parts`` (resource ids).
"""
import json
import re
from typing import Any, Dict

LICENCES = {"creativecommons.org/licenses/by/4.0": "CC-BY-4.0", "creativecommons.org/licenses/by-nc/4.0": "CC-BY-NC-4.0",
            "creativecommons.org/publicdomain/zero/1.0": "CC0-1.0", "creativecommons.org/licenses/by-sa/4.0": "CC-BY-SA-4.0"}
PART = "This resource includes"        # the relation a collection lists its members with


def resource_id(text: str) -> str:
    """The 32-hex resource id in a HydroShare link or DOI (``10.4211/hs.<id>``)."""
    return re.search(r"(?:hs[.:]|resource/)([0-9a-f]{32})", text).group(1)


def _licence(url: str) -> Any:
    return LICENCES.get(re.sub(r"^https?://|/$", "", url or ""))


def read(text: str) -> Dict[str, Any]:
    d = json.loads(text)
    m = d["metadata"]
    rights = m.get("rights") or {}
    doi = re.search(r"doi\.org/(10\.\d+/\S+)", m.get("citation", ""))
    box = m.get("spatial_coverage") or {}
    bounds = ({"west": box["westlimit"], "east": box["eastlimit"], "south": box["southlimit"], "north": box["northlimit"]}
              if box.get("type") == "box" else
              {"west": box["east"], "east": box["east"], "south": box["north"], "north": box["north"]}
              if box.get("type") == "point" else {})
    period = m.get("period_coverage") or {}
    entities = {}
    for f in d.get("files") or []:
        name = f["url"].split("/data/contents/", 1)[-1]
        entities[name] = {"url": f["url"], "pid": f["url"], "size": f.get("size"),
                          "checksum": ("md5", f["checksum"].lower()) if f.get("checksum") else None,
                          "media_type": f.get("content_type"), "attributes": []}
    return {"package_id": f"doi:{doi.group(1)}" if doi else None, "title": m.get("title", ""),
            "licence": _licence(rights.get("url")), "rights": rights.get("statement", ""),
            # "Surname, Given" or "Given Surname"
            "creators": [c["name"].split(",")[0] if "," in c["name"] else c["name"].rsplit(" ", 1)[-1]
                         for c in m.get("creators") or [] if c.get("name")],
            "dates": sorted(v[:10] for v in (period.get("start"), period.get("end")) if v),
            "bounds": bounds, "methods": m.get("abstract", ""), "keywords": ", ".join(m.get("subjects") or []),
            "parts": [resource_id(r["value"]) for r in m.get("relations") or [] if r.get("type") == PART],
            "entities": entities}
