#!/usr/bin/env python3
"""Root catalog over every dataset catalog, and a site index across datasets.

Dataset catalogs (one per summary, ``<root>/stac/<dataset>/catalog.json``) stay as built. This writes:

- ``<root>/stac/catalog.json``: a STAC catalog whose children are the dataset catalogs;
- ``<root>/stac/sites.json``: per site of the registry (``data_acquisition/sites.yaml``), its name, CRS and
  manual fields, and per dataset the items, products and times found there, so one site's data from
  several sources (e.g. orthomosaics on Zenodo, DEMs on HydroShare) is seen together.

    python -m data_acquisition.catalog.root --root "<drive>/open_datasets"
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict

import pystac

from data_acquisition.catalog import descriptors, stac
from data_acquisition.catalog import summary as summaries


def _time(item: pystac.Item) -> str:
    if item.datetime:
        return item.datetime.date().isoformat()
    cm = item.common_metadata
    return f"{cm.start_datetime.date()}..{cm.end_datetime.date()}"


def build_root(stac_dir: Path) -> (Path, Dict[str, Any]):
    """Write the root catalog and the site index under ``stac_dir``; returns (catalog path, index)."""
    children = sorted(p for p in stac_dir.glob("*/catalog.json"))
    root = pystac.Catalog("open_datasets", "Every dataset catalog of the BeaverSim dataset pipeline, one per summary.")
    registry = summaries.load_sites()
    datasets: Dict[str, Dict[str, Any]] = defaultdict(lambda: defaultdict(lambda: {"items": 0, "products": {}}))
    for child in children:
        catalog = stac.load(child)
        root.add_link(pystac.Link("child", f"./{child.parent.name}/catalog.json", pystac.MediaType.JSON,
                                  title=catalog.description.split(". Built from")[0]))
        for item in catalog.get_items(recursive=True):
            site = descriptors.get_field(item, "site")
            entry = datasets[site][catalog.id]
            entry["items"] += 1
            product = next(k for k, a in item.assets.items() if "data" in (a.roles or []))
            entry["products"].setdefault(product, []).append(_time(item))
    index = {}
    for slug in sorted(set(registry) | set(datasets)):
        site = registry.get(slug, {})
        index[slug] = {"name": site.get("name"), "crs": site.get("crs"), "in_registry": slug in registry,
                       "level": site.get("level", "site"), "contains": site.get("contains") or [],
                       "within": sorted(s for s, v in registry.items() if slug in (v.get("contains") or [])),
                       **{f: site.get(f) for f in ("colonies", "land_status", "governance")},
                       "datasets": {d: {"items": e["items"],
                                        "products": {p: sorted(set(t)) for p, t in sorted(e["products"].items())}}
                                    for d, e in sorted(datasets.get(slug, {}).items())}}
    root.set_self_href(str((stac_dir / "catalog.json").resolve()))
    root.save_object(include_self_link=False)
    (stac_dir / "sites.json").write_text(json.dumps(index, indent=1))
    return stac_dir / "catalog.json", index


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", required=True, type=Path, help="data root; catalogs are in <root>/stac/")
    args = parser.parse_args()
    path, index = build_root(args.root / "stac")
    print(f"{path} ({len(list((args.root / 'stac').glob('*/catalog.json')))} dataset catalogs), sites.json:")
    for slug, site in index.items():
        missing = [f for f in ("colonies", "land_status", "governance") if site[f] is None]
        datasets = ", ".join(f"{d} ({e['items']})" for d, e in site["datasets"].items()) or "no data yet"
        within = f"  | within: {', '.join(site['within'])}" if site["within"] else ""
        print(f"  {slug:30s} {datasets}{within}{'  | missing: ' + ', '.join(missing) if missing else ''}")


if __name__ == "__main__":
    main()
