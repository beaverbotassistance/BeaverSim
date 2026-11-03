#!/usr/bin/env python3
"""Which public functions of the pipeline do the course's solution notebooks call?

Reads the notebooks' code and the pipeline's code, without running either. A function counts when a solution calls
it through an import (``summaries.epoch(...)``, or ``dataset_folder(...)`` imported by name). Not counted: calls
inside text that a cell writes to a file, or that go through a table such as ``RECORDS[fmt]["read"]``; so the report
is a guide, not a proof. A module also run as a command (``python -m ...``) is marked ``command``. Only a report: a
function without an exercise is not an error.

    python docs/manual/tools/exercise_coverage.py
"""
import ast
import json
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple

REPOSITORY = Path(__file__).resolve().parents[3]
PIPELINE = REPOSITORY / "data_acquisition"
PARTS = ("catalog", "readers", "sources", "steps")
SOLUTIONS = REPOSITORY / "docs" / "manual" / "solutions" / "notebooks"


def public_functions() -> Dict[str, List[str]]:
    """Module (path under data_acquisition) -> its public top-level functions, ``main`` left out."""
    out = {}
    for path in [PIPELINE / "intake.py"] + [p for part in PARTS for p in sorted((PIPELINE / part).glob("*.py"))]:
        names = [n.name for n in ast.parse(path.read_text()).body if isinstance(n, ast.FunctionDef)
                 and not n.name.startswith("_") and n.name != "main"]
        if names:
            out[path.relative_to(PIPELINE).as_posix()] = names
    return out


def _module_file(dotted: str) -> str:
    """``data_acquisition.catalog.summary`` -> ``catalog/summary.py``; a package -> its ``__init__.py``."""
    relative = dotted.split(".", 1)[1].replace(".", "/") if "." in dotted else ""
    return f"{relative}/__init__.py" if (PIPELINE / relative).is_dir() else f"{relative}.py"


def _calls(tree: ast.AST) -> Tuple[Set[Tuple[str, str]], Set[str]]:
    """(module, function) pairs a notebook's code calls, and the modules it names as commands."""
    modules, functions, used, commands = {}, {}, set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("data_acquisition"):
            for a in node.names:
                as_module = f"{node.module}.{a.name}"
                if _module_file(as_module) and (PIPELINE / _module_file(as_module)).exists():
                    modules[a.asname or a.name] = _module_file(as_module)
                else:
                    functions[a.asname or a.name] = (_module_file(node.module), a.name)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and re.fullmatch(r"data_acquisition(\.\w+)+", node.value):
            commands.add(_module_file(node.value))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id in modules:
                used.add((modules[f.value.id], f.attr))
            elif isinstance(f, ast.Name) and f.id in functions:
                used.add(functions[f.id])
    return used, commands


def coverage() -> Dict[str, Dict[str, object]]:
    """Module -> its functions ``used`` and ``missing``, and whether it is run as a ``command``."""
    used, commands = set(), set()
    for path in sorted(SOLUTIONS.glob("*.ipynb")):
        cells = json.loads(path.read_text())["cells"]
        code = "\n".join("".join(c["source"]) for c in cells if c["cell_type"] == "code")
        calls, named = _calls(ast.parse("\n".join(l for l in code.splitlines() if not l.lstrip().startswith("%"))))
        used |= calls
        commands |= named
    return {module: {"used": [n for n in names if (module, n) in used],
                     "missing": [n for n in names if (module, n) not in used],
                     "command": module in commands}
            for module, names in public_functions().items()}


def main() -> None:
    report = coverage()
    for module, entry in report.items():
        total = len(entry["used"]) + len(entry["missing"])
        mark = " command" if entry["command"] else ""
        missing = ", ".join(entry["missing"]) or "-"
        print(f"{module:30s} {len(entry['used']):2d}/{total:2d}{mark:8s}  missing: {missing}")
    used = sum(len(e["used"]) for e in report.values())
    print(f"{used} of {sum(len(e['used']) + len(e['missing']) for e in report.values())} public functions called")


if __name__ == "__main__":
    main()
