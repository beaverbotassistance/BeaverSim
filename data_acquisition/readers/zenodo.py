"""Zenodo record reader (the JSON of ``/api/records/<id>``): structured metadata plus the file list
(name, MD5, size, download link).

Returns the same shape as :func:`data_acquisition.readers.eml.read`, so the builder and the
evidence gatherer treat both the same way. Free text (description, method, notes) is returned as
``methods`` with HTML tags removed.
"""
import html
import json
import re
from typing import Any, Dict

LICENCES = {"cc-by-4.0": "CC-BY-4.0", "cc-by-nc-4.0": "CC-BY-NC-4.0", "cc-zero": "CC0-1.0",
            "cc0-1.0": "CC0-1.0", "cc-by-sa-4.0": "CC-BY-SA-4.0"}


def _plain(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()


def read(text: str) -> Dict[str, Any]:
    d = json.loads(text)
    m = d["metadata"]
    licence = (m.get("license") or {}).get("id", "")
    points = [(p["lon"], p["lat"]) for p in m.get("locations") or [] if "lat" in p and "lon" in p]
    bounds = {"west": min(x for x, _ in points), "east": max(x for x, _ in points),
              "south": min(y for _, y in points), "north": max(y for _, y in points)} if points else {}
    entities = {}
    for f in d.get("files") or []:
        algorithm, _, digest = (f.get("checksum") or "").partition(":")
        entities[f["key"]] = {"url": f["links"]["self"], "pid": f.get("id"), "size": f.get("size"),
                              "checksum": (algorithm, digest.lower()) if digest else None, "attributes": []}
    return {"package_id": f"doi:{d['doi']}" if d.get("doi") else None, "title": m.get("title", ""),
            "concept_id": f"doi:{d['conceptdoi']}" if d.get("conceptdoi") else None,
            "licence": LICENCES.get(licence.lower()), "rights": licence,
            # "Surname, Given" or "Given Surname"
            "creators": [c["name"].split(",")[0] if "," in c["name"] else c["name"].rsplit(" ", 1)[-1]
                         for c in m.get("creators") or []],
            "dates": sorted(v for e in m.get("dates") or [] for v in (e.get("start"), e.get("end")) if v),
            "bounds": bounds, "methods": " ".join(_plain(m.get(k, "")) for k in ("description", "method", "notes")
                                                  if m.get(k)),
            "keywords": ", ".join(m.get("keywords") or []), "entities": entities}
