"""The course's sample data root and reference summary still work with the pipeline as it is."""
import ast
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import nbformat
import pystac
import pytest

from data_acquisition.catalog import build, descriptors, stac
from data_acquisition.catalog import summary as summaries
from data_acquisition.steps.curate import curate_item

MANUAL = Path(__file__).resolve().parents[2] / "docs" / "manual"


def _make_sample(root: Path) -> None:
    spec = importlib.util.spec_from_file_location("make_sample", MANUAL / "tools" / "make_sample.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.make(root)


def _load_tool(name: str):
    spec = importlib.util.spec_from_file_location(name, MANUAL / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sandbox_patch_clears_and_restores_pythonpath(tmp_path: Path):
    tool = _load_tool("patch_sandbox_venv")
    venv = tmp_path / "venv"
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(venv)], check=True)
    with pytest.raises(ValueError, match="install the requirements first"):
        tool.patch(venv)
    kernel = venv / "share" / "jupyter" / "kernels" / "python3" / "kernel.json"
    kernel.parent.mkdir(parents=True)
    kernel.write_text('{"argv": ["python"], "language": "python"}')
    assert len(tool.patch(venv)) == 2
    assert tool.patch(venv) == []                                      # running it again changes nothing
    assert json.loads(kernel.read_text())["env"] == {"PYTHONPATH": ""}
    script = (f'source "{venv}/bin/activate"; echo "[${{PYTHONPATH:-empty}}]"; '
              f'source "{venv}/bin/activate"; deactivate; echo "[$PYTHONPATH]"')
    out = subprocess.run(["bash", "-c", script], env={**os.environ, "PYTHONPATH": "/somewhere/else"},
                         capture_output=True, text=True, check=True).stdout.split()
    assert out == ["[empty]", "[/somewhere/else]"]


def test_notebook_builder_keeps_cells_written_by_hand(tmp_path: Path):
    tool = _load_tool("build_notebooks")
    chapter = tool.Chapter("99_test", "Test", "Intro.", "import json", [tool.Exercise("**1.**", "...", "print(1)")])
    assert tool.write_all([chapter], tmp_path) == (2, [])
    assert tool.write_all([chapter], tmp_path) == (2, [])               # generated cells: free to rewrite
    path = tmp_path / "notebooks" / "99_test.ipynb"
    nb = nbformat.read(path, as_version=4)
    nb.metadata["kernelspec"]["display_name"] = "an editor's name"      # only metadata changed: not an edit
    nbformat.write(nb, path)
    assert tool.write_all([chapter], tmp_path) == (2, [])
    nb = nbformat.read(path, as_version=4)
    nb.cells[-1].source = "my own answer"
    nbformat.write(nb, path)
    assert tool.write_all([chapter], tmp_path) == (0, [path])
    assert nbformat.read(path, as_version=4).cells[-1].source == "my own answer"
    assert tool.write_all([chapter], tmp_path, force=True) == (2, [])
    assert nbformat.read(path, as_version=4).cells[-1].source == "..."


def test_chapters_list_the_exercises_of_the_notebooks():
    tool = _load_tool("build_notebooks")
    for chapter in tool.CHAPTERS:
        text = (MANUAL / f"{chapter.name}.md").read_text()
        assert tool.exercise_list(chapter) in text, f"{chapter.name}: run docs/manual/tools/build_notebooks.py"


def test_coverage_report_finds_the_exercised_functions():
    tool = _load_tool("exercise_coverage")
    summary = tool.coverage()["catalog/summary.py"]
    assert summary["missing"] == [] and len(summary["used"]) == 11
    code = ("from data_acquisition.catalog import summary as summaries\n"
            "from data_acquisition.sources import dataset_folder\n"
            "summaries.epoch({})\ndataset_folder(1, 2, 3)\nother.epoch()\n"
            "run(['-m', 'data_acquisition.catalog.build'])\n")
    used, commands = tool._calls(ast.parse(code))
    assert used == {("catalog/summary.py", "epoch"), ("sources/__init__.py", "dataset_folder")}
    assert commands == {"catalog/build.py"}


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
