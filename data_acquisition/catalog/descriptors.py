"""The ``beaver:`` descriptors (pipeline_design.md §3.1).

Each descriptor is stored as a STAC property ``beaver:<field>``. Where its value came from is
stored in ``beaver:origin`` as ``{field: {"source": ..., ...}}``:

- ``auto``: derived from the data by code;
- ``repository``: read from the source's standard metadata record;
- ``claude``: written by Claude in a dataset summary not yet reviewed (never counts as confirmed);
- ``manual``: entered or checked by a person.

``manual`` and ``claude`` entries also carry who and when. A field whose value is ``None`` is missing.
"""
import datetime
from typing import Any, Dict, List, Optional

import pystac

PREFIX = "beaver:"
SOURCES = ("auto", "repository", "claude", "manual")

FIELDS = {
    "site": "site slug",
    "colonies": "colonies present in the item",
    "positioning": "how the product was positioned: rtk, ppk, gcp, gnss, none (list)",
    "season": "winter, spring, summer, autumn (meteorological, from date and hemisphere)",
    "quality": "flags: corrupt, partial coverage, conflicting metadata, ...",
    "licence": "SPDX licence id",
    "land_status": "ownership or jurisdiction of the site",
    "governance": "data-use terms, Indigenous data governance, publication approval",
    "provenance": "source, DOI, original path, download date, checksum",
}


def set_field(item: pystac.Item, field: str, value: Any, source: str,
              by: Optional[str] = None, date: Optional[str] = None, note: Optional[str] = None) -> None:
    """Set ``beaver:<field>`` on ``item`` and record where the value came from."""
    if field not in FIELDS:
        raise KeyError(f"unknown descriptor {field!r}")
    if source not in SOURCES:
        raise ValueError(f"source must be one of {SOURCES}, got {source!r}")
    if source in ("manual", "claude") and not by:
        raise ValueError(f"{source} value for {field!r} needs who entered it")
    item.properties[PREFIX + field] = value
    origin = {"source": source}
    origin.update({k: v for k, v in (("by", by), ("date", date), ("note", note)) if v})
    item.properties.setdefault(PREFIX + "origin", {})[field] = origin


def get_field(item: pystac.Item, field: str) -> Any:
    return item.properties.get(PREFIX + field)


def add_quality(item: pystac.Item, flag: str, detail: str, source: str = "auto") -> None:
    """Append a quality flag (``{"flag", "detail", "source"}``), skipping exact repeats."""
    flags = item.properties.setdefault(PREFIX + "quality", [])
    entry = {"flag": flag, "detail": detail, "source": source}
    if entry not in flags:
        flags.append(entry)
    item.properties.setdefault(PREFIX + "origin", {})["quality"] = {"source": "auto"}


def missing(item: pystac.Item) -> List[str]:
    """Descriptors not yet known for ``item`` (absent or ``None``)."""
    return [f for f in FIELDS if f != "quality" and get_field(item, f) is None]


def season(date: datetime.date, latitude: float) -> str:
    """Meteorological season (Dec–Feb winter in the north), flipped in the southern hemisphere.

    Calendar season only: snow cover at high latitude (e.g. Alaska in March) is a quality flag,
    not a season.
    """
    names = ["winter", "spring", "summer", "autumn"]
    index = (date.month % 12) // 3
    return names[(index + 2) % 4] if latitude < 0 else names[index]


def summary(items: List[pystac.Item]) -> List[Dict[str, Any]]:
    """One row per item: id, missing descriptors, quality flags."""
    return [{"item": it.id, "missing": ", ".join(missing(it)),
             "quality": "; ".join(q["flag"] for q in get_field(it, "quality") or [])} for it in items]
