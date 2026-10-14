#!/usr/bin/env python3
"""Regression snapshot of the dataset pipeline on the real datasets: did a code change alter the catalogs?

``snapshot`` builds every summary under ``data_acquisition/summaries/`` and runs the ``curate`` checks on
the items, all in memory (nothing is written next to the data; no checksums are hashed), and saves each
item in a normalised form. ``compare`` lists what differs between two snapshots, item by item and field
by field, and exits with 1 if anything does. Take a snapshot before a change, another after, compare.

    python -m tests.dataset.regression snapshot --root "<drive>/open_datasets" --out output/dataset/regression/before.json
    python -m tests.dataset.regression compare output/dataset/regression/before.json output/dataset/regression/after.json
"""
import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict

from data_acquisition.catalog import build
from data_acquisition.catalog import summary as summaries
from data_acquisition.steps.curate import curate_item

VOLATILE = ("verified",)        # provenance entries that change with the day a check ran


def _normalise(value: Any, root: str) -> Any:
    """Paths relative to the data root; dictionaries with sorted keys (via json); volatile entries dropped."""
    if isinstance(value, dict):
        return {k: _normalise(v, root) for k, v in value.items() if k not in VOLATILE}
    if isinstance(value, list):
        return [_normalise(v, root) for v in value]
    if isinstance(value, str) and value.startswith(root):
        return "<root>" + value[len(root):]
    return value


def snapshot(root: Path) -> Dict[str, Any]:
    out: Dict[str, Any] = {"root": str(root), "summaries": {}}
    for path in sorted(summaries.HERE.glob("*.yaml")):
        started = time.time()
        s = summaries.load(str(path))
        catalog, report = build.build(root, s)
        items = {}
        for item in catalog.get_items(recursive=True):
            curate_item(item, s, verify=False)
            items[item.id] = _normalise(item.to_dict(include_self_link=False, transform_hrefs=False),
                                        str(root.resolve()))
        out["summaries"][path.stem] = {"report": report, "items": items}
        print(f"  {path.stem}: {len(items)} items ({time.time() - started:.0f} s)")
    return out


def _flat(d: Any, prefix: str = "") -> Dict[str, Any]:
    if isinstance(d, dict):
        flat = {}
        for k, v in d.items():
            flat.update(_flat(v, f"{prefix}.{k}" if prefix else k))
        return flat
    return {prefix: json.dumps(d, sort_keys=True)}


def compare(a: Dict[str, Any], b: Dict[str, Any], limit: int = 20) -> int:
    """Print the differences between two snapshots; returns their number."""
    differences = 0
    for name in sorted(set(a["summaries"]) | set(b["summaries"])):
        sa, sb = a["summaries"].get(name), b["summaries"].get(name)
        if sa is None or sb is None:
            print(f"{name}: only in {'after' if sa is None else 'before'}")
            differences += 1
            continue
        if sa["report"] != sb["report"]:
            print(f"{name}: build report differs\n  before {sa['report']}\n  after  {sb['report']}")
            differences += 1
        ids_a, ids_b = set(sa["items"]), set(sb["items"])
        for item in sorted(ids_a ^ ids_b):
            print(f"{name}: item {item} only {'before' if item in ids_a else 'after'}")
            differences += 1
        shown = 0
        for item in sorted(ids_a & ids_b):
            fa, fb = _flat(sa["items"][item]), _flat(sb["items"][item])
            for key in sorted(set(fa) | set(fb)):
                if fa.get(key) != fb.get(key):
                    differences += 1
                    if shown < limit:
                        print(f"{name}: {item}: {key}\n  before {fa.get(key, '(absent)')[:200]}\n"
                              f"  after  {fb.get(key, '(absent)')[:200]}")
                    shown += 1
        if shown > limit:
            print(f"{name}: … {shown - limit} more differences")
    print(f"{differences} differences" if differences else "no differences")
    return differences


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("snapshot")
    s.add_argument("--root", required=True, type=Path)
    s.add_argument("--out", required=True, type=Path)
    c = sub.add_parser("compare")
    c.add_argument("before", type=Path)
    c.add_argument("after", type=Path)
    c.add_argument("--limit", type=int, default=20, help="differences shown per summary")
    args = parser.parse_args()
    if args.command == "snapshot":
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(snapshot(args.root), indent=1, sort_keys=True, default=str))
        print(f"-> {args.out}")
    else:
        diffs = compare(json.loads(args.before.read_text()), json.loads(args.after.read_text()), args.limit)
        sys.exit(1 if diffs else 0)


if __name__ == "__main__":
    main()
