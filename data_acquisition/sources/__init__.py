"""Access clients, one per protocol: they fetch data, they don't describe it."""
import re
from pathlib import Path


def dataset_folder(root: Path, repository: str, doi: str) -> Path:
    """``<root>/<repository>/doi_<doi>/``, the folder every client downloads a dataset into.

    ``doi`` is the identifier of the exact version downloaded (for versioned repositories such as
    Zenodo, the version DOI, not the concept DOI), given as ``doi:10.x/y``, ``10.x/y`` or a doi.org link.
    """
    bare = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", doi.strip(), flags=re.I)
    return root / repository / re.sub(r"[^A-Za-z0-9._-]+", "_", f"doi:{bare}")
