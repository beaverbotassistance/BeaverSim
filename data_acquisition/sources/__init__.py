"""Access clients, one per protocol: they fetch data, they don't describe it."""
import re
from pathlib import Path

DOI = re.compile(r"^(https?://(dx\.)?doi\.org/|doi:)?(10\.\d{4,}/\S+)$", re.I)


def dataset_folder(root: Path, repository: str, identifier: str) -> Path:
    """The folder every client downloads a dataset into: ``<root>/<repository>/doi_<doi>/`` for a DOI,
    ``<root>/<repository>/id_<identifier>/`` for anything else (e.g. ``hs:<id>`` for an unpublished
    HydroShare resource), so a folder name never claims a DOI the dataset does not have.

    ``identifier`` names the exact version downloaded (for versioned repositories such as Zenodo, the
    version DOI, not the concept DOI); a DOI may be given as ``doi:10.x/y``, ``10.x/y`` or a doi.org link.
    """
    m = DOI.match(identifier.strip())
    name = f"doi:{m.group(3)}" if m else f"id:{identifier.strip()}"
    return root / repository / re.sub(r"[^A-Za-z0-9._-]+", "_", name)
