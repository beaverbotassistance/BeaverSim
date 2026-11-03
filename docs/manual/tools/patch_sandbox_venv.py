#!/usr/bin/env python3
"""Protect a virtual environment from the PYTHONPATH of the lab's sandbox (course, chapter 0).

Terminals in the lab's sandbox start with PYTHONPATH pointing to /opt/dua-venv and the system packages. Python
searches PYTHONPATH before the active environment, so those packages would replace the environment's own: pip
breaks, and libraries silently have other versions. This makes the environment ignore PYTHONPATH:

- ``bin/activate`` clears it, and ``deactivate`` puts it back, so other projects are not affected;
- the Jupyter kernel starts with it empty, so notebooks are protected however they are opened.

Run it once, after installing the requirements. Outside the sandbox it does nothing, unless ``--force`` is given
(for another machine with the same problem). Running it again changes nothing. Standard library only.

    python docs/manual/tools/patch_sandbox_venv.py [--venv beaversim_venv]
"""
import argparse
import json
import os
import sys
from pathlib import Path
from typing import List

REPOSITORY = Path(__file__).resolve().parents[3]
SANDBOX_PREFIX = "cearlab-sandbox"      # start of the container's name
SANDBOX_VENV = Path("/opt/dua-venv")    # the environment the sandbox's PYTHONPATH points to
MARKER = "_OLD_BEAVERSIM_PYTHONPATH"
DEACTIVATE = "deactivate () {\n"
RESTORE = f'''    # BeaverSim: give back the PYTHONPATH cleared below
    if [ -n "${{{MARKER}+x}}" ] ; then
        PYTHONPATH="${MARKER}"
        export PYTHONPATH
        unset {MARKER}
    fi
'''
BEFORE_PROMPT = 'if [ -z "${VIRTUAL_ENV_DISABLE_PROMPT:-}" ] ; then\n'
CLEAR = f'''# BeaverSim: the sandbox's PYTHONPATH (dua-venv, system packages, ROS) would override this environment
if [ -n "${{PYTHONPATH+x}}" ] ; then
    {MARKER}="$PYTHONPATH"
    unset PYTHONPATH
fi

'''


def in_sandbox() -> bool:
    """True inside the lab's sandbox: by the container's name, or by the environment only it has."""
    return os.environ.get("CONTAINER_ID", "").startswith(SANDBOX_PREFIX) or SANDBOX_VENV.is_dir()


def patch(venv: Path) -> List[str]:
    """Patch ``venv``; returns what was changed (nothing if it already is). Raises ValueError if it cannot."""
    activate = venv / "bin" / "activate"
    kernel = venv / "share" / "jupyter" / "kernels" / "python3" / "kernel.json"
    for path, hint in ((activate, "is it a virtual environment?"), (kernel, "install the requirements first")):
        if not path.is_file():
            raise ValueError(f"{path} not found: {hint}")
    changed = []
    text = activate.read_text()
    if MARKER not in text:
        if text.count(DEACTIVATE) != 1 or text.count(BEFORE_PROMPT) != 1:
            raise ValueError(f"{activate} does not look as expected; nothing changed")
        text = text.replace(DEACTIVATE, DEACTIVATE + RESTORE).replace(BEFORE_PROMPT, CLEAR + BEFORE_PROMPT)
        activate.write_text(text)
        changed.append(str(activate))
    spec = json.loads(kernel.read_text())
    if spec.get("env", {}).get("PYTHONPATH") != "":
        spec["env"] = {**spec.get("env", {}), "PYTHONPATH": ""}
        kernel.write_text(json.dumps(spec, indent=1) + "\n")
        changed.append(str(kernel))
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--venv", type=Path, default=REPOSITORY / "beaversim_venv", help="the environment to patch")
    parser.add_argument("--force", action="store_true", help="patch even outside the lab's sandbox")
    args = parser.parse_args()
    if not (args.force or in_sandbox()):
        print("Not in the lab's sandbox: nothing to do.")
        return
    try:
        changed = patch(args.venv)
    except ValueError as e:
        sys.exit(str(e))
    for path in changed:
        print("patched", path)
    print("Run: source <environment>/bin/activate" if changed else "Already patched: nothing to do.")


if __name__ == "__main__":
    main()
