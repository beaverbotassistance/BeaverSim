"""Dataset presets: one YAML file per dataset with what the files can't tell us."""
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import yaml

HERE = Path(__file__).parent


def load(name_or_path: str) -> Dict[str, Any]:
    """Load a preset by name (``arcticdata_seward``) or path."""
    path = Path(name_or_path)
    if not path.suffix:
        path = HERE / f"{name_or_path}.yaml"
    with open(path) as f:
        preset = yaml.safe_load(f)
    preset["_path"] = str(path)
    return preset


def match_site(preset: Dict[str, Any], name: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """(slug, site entry) of the first site whose ``match`` regex finds ``name``, or None."""
    for slug, site in preset.get("sites", {}).items():
        if re.search(site["match"], name):
            return slug, site
    return None
