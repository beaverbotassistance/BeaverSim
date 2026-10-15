"""CKAN package record reader (the JSON of ``/api/3/action/package_show``): the dataset's metadata and
its resources (name, link, size and hash when the portal gives them).

The source client saves the response, unchanged, labelled with its URL: ``{"package_url", "package"}``.
Resources that are web pages or services (landing pages, map viewers, APIs) are not files and are not
returned as entities. A resource's file name is the last segment of its link; CKAN states no algorithm
for a resource's ``hash``, so it is taken from the digest's length.

Returns the same shape as :func:`data_acquisition.readers.eml.read`, so the builder and the
evidence gatherer treat both the same way. The description (``notes``) is returned as ``methods``.
"""
import json
import posixpath
import re
import urllib.parse
from typing import Any, Dict, Optional, Tuple

LICENCES = {"cc-by": "CC-BY-4.0", "cc-by-4.0": "CC-BY-4.0", "cc-zero": "CC0-1.0", "cc-by-sa": "CC-BY-SA-4.0",
            "cc-nc": "CC-BY-NC-4.0", "ca-ogl-lgo": "OGL-Canada-2.0", "uk-ogl": "OGL-UK-3.0",
            # licences without an SPDX id get a LicenseRef- id (the SPDX convention); the record keeps the full title
            "on-oglo": "LicenseRef-OGL-Ontario-1.0"}
WEB = {"HTML", "HTM", "WEB APP", "WEB SERVICE", "API", "ESRI REST", "WMS", "WFS", "WMTS"}   # not files
DIGESTS = {32: "md5", 40: "sha1", 64: "sha256"}


def _checksum(value: str) -> Optional[Tuple[str, str]]:
    value = (value or "").strip().lower()
    return (DIGESTS[len(value)], value) if re.fullmatch(r"[0-9a-f]+", value) and len(value) in DIGESTS else None


def file_name(url: str) -> str:
    """The file name a resource link serves: its last path segment, unquoted."""
    return urllib.parse.unquote(posixpath.basename(urllib.parse.urlsplit(url).path))


def _bounds(spatial: str) -> Dict[str, float]:
    try:
        geometry = json.loads(spatial)
    except (TypeError, ValueError):
        return {}
    points = re.findall(r"\[\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\]", json.dumps(geometry.get("coordinates")))
    xs, ys = [float(x) for x, _ in points], [float(y) for _, y in points]
    return {"west": min(xs), "east": max(xs), "south": min(ys), "north": max(ys)} if points else {}


def read(text: str) -> Dict[str, Any]:
    p = json.loads(text)["package"]["result"]
    entities = {}
    for r in p.get("resources") or []:
        if (r.get("format") or "").upper() in WEB or not r.get("url"):
            continue
        name = file_name(r["url"])
        if not name or name in entities:
            name = f"{r['id']}_{name}"
        # portals keep links as typed (e.g. with spaces); escaped here, existing %-escapes kept
        entities[name] = {"url": urllib.parse.quote(r["url"], safe=":/?#[]@!$&'()*+,;=%~"), "pid": r["id"],
                          "size": int(r["size"]) if r.get("size") else None,
                          "checksum": _checksum(r.get("hash")), "media_type": r.get("mimetype"),
                          "description": r.get("name", ""), "attributes": []}
    organization = (p.get("organization") or {}).get("title", "")
    # 0001-01-01 is CKAN's placeholder for an unknown date
    dates = sorted(v[:10] for k in ("time_period_coverage_start", "time_period_coverage_end")
                   if (v := p.get(k)) and not v.startswith("0001"))
    return {"package_id": p["id"], "title": p.get("title", ""), "version": p.get("metadata_modified"),
            "licence": LICENCES.get((p.get("license_id") or "").lower()),
            "rights": ", ".join(v for v in (p.get("license_title"), p.get("license_url")) if v),
            "creators": [c for c in (p.get("author"), organization) if c],
            "dates": dates, "bounds": _bounds(p.get("spatial")), "methods": p.get("notes") or "",
            "keywords": ", ".join(t["name"] for t in p.get("tags") or []), "entities": entities}
