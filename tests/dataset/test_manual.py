"""The course's sample data root and reference summary still work with the pipeline as it is."""
import importlib.util
from pathlib import Path

import pystac

from data_acquisition.catalog import build, descriptors, stac
from data_acquisition.catalog import summary as summaries
from data_acquisition.steps.curate import curate_item

MANUAL = Path(__file__).resolve().parents[2] / "docs" / "manual"


def _make_sample(root: Path) -> None:
    spec = importlib.util.spec_from_file_location("make_sample", MANUAL / "tools" / "make_sample.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.make(root)


def test_reference_summary_builds_the_sample(tmp_path: Path, monkeypatch):
    _make_sample(tmp_path)
    monkeypatch.setenv("BEAVER_SITES", str(tmp_path / "sites.yaml"))
    s = summaries.load(str(MANUAL / "solutions" / "training_pond.yaml"))
    catalog, report = build.build(tmp_path, s)
    assert report == {"missing": [], "undescribed": [], "unsupported": [], "unattached": [], "unmatched_layers": []}
    items = {i.id: i for i in catalog.get_items(recursive=True)}
    assert sorted(items) == ["training_pond_2022-08_dtm", "training_pond_2023-07-12_annotations",
                             "training_pond_2023-07-12_dsm", "training_pond_2023-07-12_orthomosaic",
                             "training_pond_2023-07-12_photos"]
    for item in items.values():
        curate_item(item, s)
    flags = {i: {q["flag"] for q in descriptors.get_field(item, "quality")} for i, item in items.items()}
    assert "crs_from_summary" in flags["training_pond_2022-08_dtm"]
    assert "needs_inspection" in flags["training_pond_2023-07-12_annotations"]
    assert "nodata_undeclared" not in flags["training_pond_2023-07-12_orthomosaic"]      # it has an alpha band
    out = stac.save(catalog, tmp_path / "stac" / "training_pond")
    assert stac.validate(stac.load(out)) == []
    assert isinstance(stac.load(out), pystac.Catalog)


def test_solution_notebooks_run(tmp_path: Path):
    """Every solution notebook runs to the end with the pipeline as it is (they make the sample root if needed).
    Notebooks that download (``needs_network``) run only with ``BEAVER_COURSE_NETWORK=1``."""
    import os

    import nbformat
    from nbclient import NotebookClient
    for path in sorted((MANUAL / "solutions" / "notebooks").glob("*.ipynb")):
        nb = nbformat.read(path, as_version=4)
        if nb.metadata.get("beaver_course", {}).get("needs_network") and not os.environ.get("BEAVER_COURSE_NETWORK"):
            continue
        NotebookClient(nb, timeout=300, kernel_name="python3",
                       resources={"metadata": {"path": str(path.parent)}}).execute()
        errors = [o for c in nb.cells if c.cell_type == "code" for o in c.get("outputs", [])
                  if o.get("output_type") == "error"]
        assert not errors, f"{path.name}: {errors[0].get('ename')}: {errors[0].get('evalue')}"
