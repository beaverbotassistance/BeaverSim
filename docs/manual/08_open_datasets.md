# Bringing in an open dataset

> Status: outline. Learning goals, sections and exercises; the text is still to be written.

## You will learn

- Use a source client to list and download a dataset
- Know what is recorded at download and why
- Use the intake prompt for a dataset from a new repository

## Sections

1. Source clients: DataONE, PANGAEA, Zenodo, HydroShare, CKAN
2. `--list` before downloading; filters
3. `downloads.csv`: what, when, checksum, verified by
4. Archives: extracting with CRC-32 checks
5. Intake of a new repository with Claude (`intake.py`)

## Exercises

1. List the files of the Ontario dams dataset, then download it.
2. Find the row of each file in `downloads.csv` and explain each column.

## Where this lives

- [`data_acquisition/sources/`](../../data_acquisition/sources/)
- [`data_acquisition/sources/http.py`](../../data_acquisition/sources/http.py)
- [`data_acquisition/sources/downloads.py`](../../data_acquisition/sources/downloads.py)
- [`data_acquisition/intake.py`](../../data_acquisition/intake.py)

## Sources

- (links to the sources of each concept, checked when the chapter is written)
