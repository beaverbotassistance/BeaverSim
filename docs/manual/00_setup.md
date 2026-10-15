# Setup: environment, drives, sample data

> Status: outline. Learning goals, sections and exercises; the text is still to be written.

## You will learn

- Set up the Python environment and the GDAL command-line tools
- Know which data roots exist and where
- Generate the sample data root used by the exercises

## Sections

1. The repository and the virtual environment (`beaversim_venv`, `requirements.txt`, `requirements-dev.txt`)
2. GDAL command-line tools (`ogr2ogr`, `ogrinfo`, `gdalinfo`) and why the pipeline needs them
3. The two data roots: `open_datasets/` (downloads) and `beaver_dataset/` (field data), and the field-season drive
4. The sample data root: generating it, what is in it
5. The Montana extract committed with the course (`docs/manual/data/`)
6. Running the tests once to check the setup (`pytest tests/dataset`)

## Exercises

1. Generate the sample data root and list what it contains.
2. Run the dataset tests; find in `pytest.ini` why some plugins are disabled.

## Where this lives

- [`requirements.txt`](../../requirements.txt)
- [`requirements-dev.txt`](../../requirements-dev.txt)
- [`pytest.ini`](../../pytest.ini)
- [`tests/dataset/conftest.py`](../../tests/dataset/conftest.py)

## Sources

- (links to the sources of each concept, checked when the chapter is written)
