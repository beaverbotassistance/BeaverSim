"""PANGAEA tab-delimited record reader (``?format=textfile``): header metadata plus, for datasets of
binary objects, the file table (name, MD5, media type, size).

Returns the same shape as :func:`data_acquisition.readers.eml.read`, so the builder and the
evidence gatherer treat both the same way. Free text (abstract) is returned as ``methods``.
"""
import re
from typing import Any, Dict

UNITS = {"Bytes": 1, "kBytes": 1e3, "MBytes": 1e6, "GBytes": 1e9, "TBytes": 1e12}
LICENCES = {"CC-BY-4.0": "CC-BY-4.0", "CC-BY-NC-4.0": "CC-BY-NC-4.0", "CC0-1.0": "CC0-1.0",
            "CC-BY-SA-4.0": "CC-BY-SA-4.0"}


def _size(text: str) -> int:
    """'1.9 kBytes' -> 1900 (PANGAEA rounds sizes, so this is approximate above Bytes)."""
    value, unit = text.split()
    return int(round(float(value) * UNITS[unit]))


def read(text: str) -> Dict[str, Any]:
    header, _, matrix = text.partition("*/\n")
    fields: Dict[str, str] = {}
    key = None
    for line in header.splitlines()[1:]:
        m = re.match(r"^([A-Za-z()' ]+):\t(.*)$", line)
        if m:
            key = m.group(1).strip()
            fields[key] = m.group(2).strip()
        elif key and line.startswith("\t"):
            fields[key] += "\n" + line.strip()
    citation = fields.get("Citation", "")
    doi = re.search(r"doi\.org/(10\.\d+/\S+)", citation)
    licence = re.search(r"\((CC[-\w.]+)\)", fields.get("License", ""))
    authors = citation.split("(", 1)[0]
    entities = {}
    rows = matrix.splitlines()
    columns = rows[0].split("\t") if rows else []
    if columns[:2] == ["Binary", "Binary (Hash)"]:
        for row in rows[1:]:
            name, md5, media, size = (row.split("\t") + [""] * 4)[:4]
            entities[name] = {"url": None, "pid": name, "size": _size(size) if size else None,
                              "size_exact": size.endswith(" Bytes"),
                              "checksum": ("md5", md5.lower()) if md5 else None, "media_type": media,
                              "attributes": []}
    title = re.sub(r"^.*?\(\d{4}\):\s*", "", citation).split(" [dataset]")[0]
    return {"package_id": f"doi:{doi.group(1)}" if doi else None, "title": title,
            "licence": LICENCES.get(licence.group(1)) if licence else None, "rights": fields.get("License", ""),
            "creators": [a.strip().split(",")[0] for a in authors.split(";") if a.strip()],
            "dates": [], "bounds": {}, "methods": fields.get("Abstract", ""),
            "keywords": fields.get("Keyword(s)", ""), "entities": entities}
