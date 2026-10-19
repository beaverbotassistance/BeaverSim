# 18. Testing a change

The pipeline describes data that cannot be downloaded again easily and decisions that took people time. A change
that silently moves a footprint, drops a flag or renames an item is worse than a crash. This chapter covers the three
ways the code is checked: unit tests on synthetic data, the regression snapshot on the real datasets, and linting;
and how to use them for a change.

## You will learn

- How the tests are organised, and how to run and write one
- How the regression snapshot shows what a change did to every real item
- How to lint, and what the project's lint standard is
- The order of work for a change

## 1. Unit tests

[pytest](https://docs.pytest.org/en/stable/) runs everything in [`tests/dataset/`](../../tests/dataset/):

```
python -m pytest -q tests/dataset                 # all of them (75, about 30 s)
python -m pytest -q tests/dataset/test_build.py   # one file
python -m pytest -q tests/dataset -k layers       # tests whose name contains "layers"
```

[`pytest.ini`](../../pytest.ini) sets the test folder and switches off pytest plugins that ROS installs on this
machine's Python path and that break pytest; run pytest from the repository root so it is read.

**Unset `BEAVER_SITES` first** (`unset BEAVER_SITES`, or open a new terminal): the tests make their own site registry
but do not override the environment variable, so with it set (as [chapter 0](00_setup.md) does for the sample) 23
tests fail (finding 26 in [`course_findings.md`](../dataset/course_findings.md)).

| File | Covers |
|---|---|
| `test_readers.py` (10) | rasters, ASCII grids, vectors, tables, HydroShare checksums, ArcGIS adjustments, GSD, a raster that cannot be placed |
| `test_summary.py` (33) | dates and layer dates, `resolve`, the summary schema and `check`, the registry, `author` |
| `test_evidence.py` (2) | a photo folder as one evidence entry, the photo reader |
| `test_build.py` (10) | items and ids, reports, bands, CRS, tables, layers, archive provenance, descriptors, `curate` checks, seasons, STAC validation |
| `test_downloads.py` (5), `test_checksums_archives.py` (6) | the order of checks, size-only, `finish` and the log, served MD5 headers; digests, multipart ETags, archives |
| `test_field.py` (5), `test_alignment.py` (2) | layout checks, CRS corrections, `_same_place`, `georeference`; `best_shift` |
| `test_manual.py` (2) | the course: the reference summary builds the sample, and every solution notebook runs |

**Synthetic data.** No test needs the drive or a network. [`conftest.py`](../../tests/dataset/conftest.py) makes
small files in a temporary folder through [fixtures](https://docs.pytest.org/en/stable/how-to/fixtures.html): `root`
(a data root with rasters, an ASCII grid, a two-layer GeoPackage, two CSV tables, a report and an extracted zip),
`registry` (a site registry, put in place of the real one with `monkeypatch`), and `summary` (a reviewed summary
describing every file of `root`). A test asks for them by name:

```python
def test_layers_become_items(root, summary):
    ...
```

**A known bug** can enter the suite before its fix as
[`@pytest.mark.xfail(strict=True, reason=...)`](https://docs.pytest.org/en/stable/how-to/skipping.html#xfail-mark-test-functions-as-expected-to-fail):
the test documents the expected behaviour, and, being strict, fails once the bug is fixed, as a reminder to remove the
mark ([chapter 13](13_readers.md), exercise 6).

## 2. The regression snapshot

Unit tests check what someone thought of. The snapshot checks everything else, on the real data
([`tests/dataset/regression.py`](../../tests/dataset/regression.py)):

```
python -m tests.dataset.regression snapshot --root "<drive>/open_datasets" --out output/dataset/regression/before.json
#   ... make the change ...
python -m tests.dataset.regression snapshot --root "<drive>/open_datasets" --out output/dataset/regression/after.json
python -m tests.dataset.regression compare output/dataset/regression/before.json output/dataset/regression/after.json
```

`snapshot` builds every summary of [`data_acquisition/summaries/`](../../data_acquisition/summaries/) whose folders are
under the root (drafts left out), runs `curate`'s checks on each item **in memory** (nothing is written, no checksum
is computed), and saves each item with paths made relative to the root and the `verified` date dropped, since it
changes with the day. `compare` lists, per summary, report differences, items only before or after, and every field
that differs, and exits with 1 if anything does. Run it with `--root "<drive>/beaver_dataset"` for the field data too.

Reading a comparison: every difference should be one you **meant**. A change to a check should move only that
check's flags; a change to the builder only the fields it builds. Anything else is a side effect to understand before
committing.

## 3. Linting

The project uses [ruff](https://docs.astral.sh/ruff/) (pinned in `requirements-dev.txt`). There is no ruff
configuration in the repository yet, so ruff's defaults (and your own settings) decide what it reports, mostly a
type-hint style the code does not use (finding 25 in [`course_findings.md`](../dataset/course_findings.md)). The rules
the code does follow:

```
ruff check --select E,F,W --line-length 120 data_acquisition/catalog data_acquisition/sources \
    data_acquisition/readers data_acquisition/steps data_acquisition/intake.py tests/dataset
```

(`data_acquisition/modules/` is legacy simulator code, outside the pipeline.)

## 4. The order of work for a change

1. Take a **snapshot** (open datasets and, if the change can touch them, the field data).
2. Write a **test** that fails without the change (or an `xfail` for a known bug).
3. Make the change; run the unit tests.
4. Take a second snapshot and **compare**; explain every difference.
5. **Lint** the files you changed.
6. Update what the change touched in the documents: the docstrings, [`pipeline_design.md`](../dataset/pipeline_design.md),
   and this course.

## Exercises

Notebook: [`notebooks/18_testing.ipynb`](notebooks/18_testing.ipynb) (work in a copy); solutions in
[`solutions/notebooks/18_testing.ipynb`](solutions/notebooks/18_testing.ipynb).

1. **Run the suite.** Run all the dataset tests, then only those whose name contains `layers`. How many are there per
   file?
2. **Write a test with the fixtures.** In a scratch folder, write a test that uses `root`, `registry` and `summary`
   to build the synthetic dataset and checks it has no missing or unsupported files and eight items. Run it with the
   repository's settings and fixtures (`-c pytest.ini --rootdir . -p tests.dataset.conftest`).
3. **A snapshot of the sample.** With `regression._normalise` and `regression.compare`, take a snapshot of the
   sample's items, change a threshold of `curate` (the highest plausible elevation, `ELEVATION_RANGE`, to 1000 m),
   take another, and compare. Which differences appear, and are they all the ones you meant?
4. **Lint.** Run ruff on the pipeline with its defaults and with the selection above. How many findings each, and of
   which kinds?
5. **(Optional, needs the drive.)** Take a snapshot of the open datasets and compare it with itself.

## Where this lives

- [`tests/dataset/`](../../tests/dataset/): the tests, `conftest.py`, `regression.py`.
- [`pytest.ini`](../../pytest.ini), [`requirements-dev.txt`](../../requirements-dev.txt).

## Sources

- pytest, [getting started](https://docs.pytest.org/en/stable/getting-started.html),
  [fixtures](https://docs.pytest.org/en/stable/how-to/fixtures.html),
  [xfail](https://docs.pytest.org/en/stable/how-to/skipping.html), [plugins (`-p`)](https://docs.pytest.org/en/stable/how-to/plugins.html)
- Ruff, [rules](https://docs.astral.sh/ruff/rules/) and [configuration](https://docs.astral.sh/ruff/configuration/)
